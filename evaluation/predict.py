"""Run a (fine-tuned) Qwen3-VL model on MapVQA questions with vLLM and write one prediction per line.

Usage:
  python evaluation/predict.py --model <checkpoint or HF id> --questions data/validation.json \
      --image_root /path/to/argoverse2/sensor/<split> --out predictions.jsonl

The model sees exactly the training prompt: the human turn of each example, with its 12 camera
images inserted at the <image> placeholders. Decoding is greedy (temperature 0).
"""
import argparse
import json
import os
import re
from pathlib import Path

os.environ.setdefault("VLLM_WORKER_MULTIPROC_METHOD", "spawn")

from PIL import Image  # noqa: E402
from qwen_vl_utils import process_vision_info  # noqa: E402
from transformers import AutoProcessor  # noqa: E402
from tqdm import tqdm  # noqa: E402
from vllm import LLM, SamplingParams  # noqa: E402


def build_messages(example, image_root):
    """User message of an example: text segments and images in the order of the <image> placeholders."""
    images = [Image.open(Path(image_root) / p).convert("RGB") for p in example["image"]]
    prompt = example["conversations"][0]["value"]
    content = []
    for segment in re.split(r"(<image>)", prompt):
        if segment == "<image>":
            if not images:
                raise ValueError("more <image> placeholders than images")
            content.append({"type": "image", "image": images.pop(0)})
        elif segment.strip():
            content.append({"type": "text", "text": segment.strip()})
    if images:
        raise ValueError(f"{len(images)} image(s) without a placeholder")
    return [{"role": "user", "content": content}]


def to_vllm_input(messages, processor):
    text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs, video_kwargs = process_vision_info(
        messages,
        image_patch_size=processor.image_processor.patch_size,
        return_video_kwargs=True,
        return_video_metadata=True,
    )
    mm_data = {}
    if image_inputs is not None:
        mm_data["image"] = image_inputs
    if video_inputs is not None:
        mm_data["video"] = video_inputs
    return {"prompt": text, "multi_modal_data": mm_data, "mm_processor_kwargs": video_kwargs}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="checkpoint directory or Hugging Face model id")
    parser.add_argument("--questions", default="data/validation.json", help="MapVQA JSON (validation file or generate.py output)")
    parser.add_argument("--image_root", required=True, help="root of the Argoverse 2 sensor split the image paths are relative to")
    parser.add_argument("--out", default="predictions.jsonl")
    parser.add_argument("--max_tokens", type=int, default=6144, help="max generated tokens (reasoning + answer)")
    parser.add_argument("--max_samples", type=int, default=None)
    parser.add_argument("--tensor_parallel_size", type=int, default=1)
    parser.add_argument("--gpu_memory_utilization", type=float, default=0.9)
    args = parser.parse_args()

    with open(args.questions) as f:
        examples = json.load(f)
    if args.max_samples is not None:
        examples = examples[: args.max_samples]

    processor = AutoProcessor.from_pretrained(args.model)
    inputs, indices = [], []
    for i, ex in enumerate(tqdm(examples, desc="Preparing inputs")):
        try:
            inputs.append(to_vllm_input(build_messages(ex, args.image_root), processor))
            indices.append(ex.get("index", i))
        except Exception as e:  # keep going; the sample is reported as missing by score.py
            print(f"Skipping sample {ex.get('index', i)}: {e}")

    llm = LLM(
        model=args.model,
        max_model_len=128000,
        mm_encoder_tp_mode="data",
        tensor_parallel_size=args.tensor_parallel_size,
        gpu_memory_utilization=args.gpu_memory_utilization,
        trust_remote_code=True,
        mm_processor_cache_gb=0,
    )
    outputs = llm.generate(inputs, sampling_params=SamplingParams(temperature=0.0, max_tokens=args.max_tokens))

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        for index, output in zip(indices, outputs):
            f.write(json.dumps({
                "index": index,
                "generated_text": output.outputs[0].text,
                "finish_reason": output.outputs[0].finish_reason,
            }, ensure_ascii=False) + "\n")
    print(f"Wrote {len(indices)} predictions to {args.out}")


if __name__ == "__main__":
    main()
