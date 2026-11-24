"""Generate the MapVQA multiple-choice QA dataset from annotated scene-graph logs.

Each example uses a window of 4 frames x 3 front cameras (12 images) and is written
in the Qwen-VL conversation format.
"""
import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

if __name__ == "__main__" and sys.flags.hash_randomization and os.environ.get("PYTHONHASHSEED") != "0":
    os.environ["PYTHONHASHSEED"] = "0"
    os.execv(sys.executable, sys.orig_argv)

from tqdm import tqdm

from core.graph_builder import GraphBuilder
from core.process_geometry import IMG_SIZE_BY_CAM, poly_to_grounding_box
from core.relation_schema import RELATION_SCHEMA
from core.temporal import extract_all_timestamps
from qa.engine import QAEngine

REPO_ROOT = Path(__file__).resolve().parent.parent

PROMPT_TEMPLATE = (
    "\n"
    "You are given images captured from an ego vehicle. \n"
    "Images are provided for the past 4 frames starting from the oldest to the most recent, "
    "with 3 images per frame for a total of 12 frames.\n"
    "The question always refers to the last frame.\n"
    "Images per frame are provided in this exact order:\n"
    "1. LEFT camera\n"
    "2. CENTER camera\n"
    "3. RIGHT camera\n"
    "\n"
    "Output format rules: \n"
    "{task_instruction}\n"
    "\n"
    "Question:\n"
    "{question_text}\n"
    "\n"
    "Answers:\n"
    "{formatted_options}\n"
)

TASK_INSTRUCTION = (
    "Before providing the final answer, perform a step-by-step visual analysis of the scene, "
    "referencing specific cameras or grounding boxes where relevant to justify your conclusion."
)

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
CAM_ORDER = ["ring_front_left", "ring_front_center", "ring_front_right"]

WINDOW_SIZE = 3


def ensure_ends_with_period(text):
    s = text.rstrip()
    if not s or s[-1] == ".":
        return s
    return s + "."


def extract_position_refs(texts):
    """Ordered unique <position_X> references across texts."""
    refs = []
    for text in texts:
        for m in re.findall(r"<(position_\d+)>", text):
            if m not in refs:
                refs.append(m)
    return refs


def rewrite_text_with_mapping(text, mapping):
    """Replace <position_X> with <i> according to mapping."""
    for pos_name, idx in mapping.items():
        text = text.replace(f"<{pos_name}>", f"<{idx}>")
    return text


def build_click_position_lookup(graph):
    """{position name: {camera: polygon, ..., "node_type": type}} for all clicked nodes."""
    lookup = {}
    for _, attrs in graph.nodes(data=True):
        cp = attrs.get("properties", {}).get("click_position")
        if not isinstance(cp, dict) or not cp.get("name"):
            continue
        views = {cam: geom["polygon"] for cam, geom in cp.items()
                 if cam != "name" and geom and geom.get("polygon")}
        views["node_type"] = attrs.get("type", "")
        lookup[cp["name"]] = views
    return lookup


def rewrite_qa_and_build_metadata(question, options, click_lookup_by_ts):
    """Rename <position_X> references to <1>, <2>, ... and collect their polygons per frame."""
    mapping = {pos: i + 1 for i, pos in enumerate(extract_position_refs([question] + options))}

    meta_data = {}
    for pos_name, idx in mapping.items():
        views_by_ts = {str(ts): lookup[pos_name]
                       for ts, lookup in click_lookup_by_ts.items() if lookup.get(pos_name)}
        if views_by_ts:
            meta_data[f"point_{idx}"] = {"type": "polygon", "views_by_ts": views_by_ts}

    question = rewrite_text_with_mapping(question, mapping)
    options = [rewrite_text_with_mapping(o, mapping) for o in options]
    return question, options, mapping, meta_data


def build_picture_block_with_grounding(ts_window, meta_data):
    """One "<image>" line per picture; grounding boxes/points are added for the last frame."""
    lines = []
    for i, ts in enumerate(ts_window):
        for cam in CAM_ORDER:
            lines.append(f"Frame {i} ({cam.split('_')[-1].upper()}): <image>")
            if ts != ts_window[-1]:
                continue
            for point_key, info in meta_data.items():
                views = info["views_by_ts"].get(str(ts), {})
                poly = views.get(cam)
                if not poly:
                    continue
                w, h = IMG_SIZE_BY_CAM[cam]
                box, _ = poly_to_grounding_box(poly, w, h, views.get("node_type"))
                if not box:
                    continue
                if len(box) == 4:
                    x1, y1, x2, y2 = box
                    assert 0 <= x1 <= x2 <= 1000 and 0 <= y1 <= y2 <= 1000
                    if not ((x1 == 0 and x2 == 0) or (x1 == 1000 and x2 == 1000)
                            or (y1 == 0 and y2 == 0) or (y1 == 1000 and y2 == 1000)):
                        lines.append(f"<ref>{point_key}</ref><box>({x1},{y1},{x2},{y2})</box>")
                else:
                    x1, y1 = box
                    assert 0 <= x1 <= 1000 and 0 <= y1 <= 1000
                    if not (x1 in (0, 1000) or y1 in (0, 1000)):
                        lines.append(f"<ref>{point_key}</ref><point>({x1},{y1})</point>")
    return "\n".join(lines)


def build_image_paths(logid, ts_window, sensor):
    """Image paths (relative to the Argoverse 2 split root), LEFT/CENTER/RIGHT per frame."""
    return [f"{logid}/sensors/cameras/{cam}/{sensor[cam][ts]}.jpg"
            for ts in ts_window for cam in CAM_ORDER]


def format_answer(letter, reasoning, answer_format):
    if answer_format == "cot":
        return f"Reasoning:\n{reasoning}\n\nANSWER: {letter}"
    if answer_format == "rcot":
        return f"ANSWER: {letter}\n\nReasoning:\n{reasoning.rstrip()}"
    return f"ANSWER: {letter}"


def build_example(qa_item, t, logid, sensor, click_lookup_by_ts, answer_format):
    question, options, mapping, meta_data = rewrite_qa_and_build_metadata(
        qa_item["q"], qa_item["options"], click_lookup_by_ts)
    correct = ensure_ends_with_period(rewrite_text_with_mapping(qa_item["a"], mapping))
    options = [ensure_ends_with_period(o) for o in options]
    correct_idx = next((i for i, o in enumerate(options) if o == correct), 0)

    ts_window = list(range(t - WINDOW_SIZE, t + 1))
    human_prompt = PROMPT_TEMPLATE.format(
        task_instruction=TASK_INSTRUCTION,
        question_text=question,
        formatted_options="\n".join(f"{LETTERS[i]}. {o}" for i, o in enumerate(options)),
    )
    picture_block = build_picture_block_with_grounding(ts_window, meta_data)

    return {
        "type": qa_item["type"],
        "image": build_image_paths(logid, ts_window, sensor),
        "conversations": [
            {"from": "human", "value": f"{picture_block}\n{human_prompt}"},
            {"from": "gpt", "value": format_answer(LETTERS[correct_idx], qa_item["cot_reasoning"], answer_format)},
        ],
    }


def generate_log(path, metadata_dir, answer_format):
    with open(path) as f:
        data = json.load(f)

    gb = GraphBuilder(RELATION_SCHEMA, openlane_root=str(metadata_dir))
    missing_inv = gb.validate_relation_schema(data)
    if missing_inv:
        raise ValueError(f"Relation schema incomplete, inverse missing for: {missing_inv}")

    sensor = gb._load_openlane_file(data["logid"])["sensor"]
    qa_engine = QAEngine()
    timestamps = extract_all_timestamps(data)

    for t in timestamps[WINDOW_SIZE:]:
        G, complete_types = gb.build_frame(data, t)
        if not G:
            print(f"no graph constructed for frame {t}")
            continue
        click_lookup_by_ts = {ts: build_click_position_lookup(gb.build_frame(data, ts)[0])
                              for ts in range(t - WINDOW_SIZE, t + 1)}

        for qa_item in qa_engine.generate(G, gb, complete_types, t, WINDOW_SIZE, data):
            yield build_example(qa_item, t, data["logid"], sensor, click_lookup_by_ts, answer_format)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, default=REPO_ROOT / "data" / "annotations",
                        help="directory with one annotated scene-graph JSON per log")
    parser.add_argument("--metadata", type=Path, default=REPO_ROOT / "data" / "metadata",
                        help="directory with the preprocessed OpenLane-V2 metadata per log")
    parser.add_argument("--out", type=Path, required=True, help="output JSON file")
    parser.add_argument("--format", choices=["cot", "rcot", "answer"], default="cot",
                        help="cot: reasoning then answer; rcot: answer then reasoning; answer: answer only")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    random.seed(args.seed)
    log_files = sorted(args.annotations.glob("*.json"))
    if not log_files:
        raise SystemExit(f"No .json files found in {args.annotations}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("[\n")
        for path in tqdm(log_files, desc="Processing logs"):
            for example in generate_log(path, args.metadata, args.format):
                if n:
                    f.write(",\n")
                json.dump(example, f, ensure_ascii=False)
                n += 1
        f.write("\n]\n")
    print(f"Saved {n} examples to {args.out}")


if __name__ == "__main__":
    main()
