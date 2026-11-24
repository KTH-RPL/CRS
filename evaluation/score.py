"""Score MapVQA predictions: overall accuracy and accuracy per question type.

Usage:
  python evaluation/score.py --predictions predictions.jsonl --questions data/validation.json --out scores.json

The answer letter is read from "ANSWER: X" (the trained output format); for other model outputs it
falls back to a bare letter, a leading "X." / "X)" or a single option letter mentioned in the text.
A prediction without a readable letter counts as wrong.
"""
import argparse
import json
import re
from collections import Counter

ANSWER_RE = re.compile(r"ANSWER\s*:\s*([A-Z])", re.IGNORECASE)
BARE_LETTER_RE = re.compile(r"^\s*([A-Z])\s*$", re.IGNORECASE)
LEADING_LETTER_RE = re.compile(r"^\s*([A-Z])[\.\)\:\-]\s+", re.IGNORECASE)
INLINE_LETTER_RE = re.compile(r"\b([A-Z])\b", re.IGNORECASE)
OPTION_RE = re.compile(r"^([A-Z])\. ", re.MULTILINE)


def extract_answer_letter(text, num_options=4):
    if not text:
        return None
    text = text.strip()
    max_letter = chr(ord("A") + num_options - 1)

    def valid(letter):
        return "A" <= letter <= max_letter

    for regex in (ANSWER_RE,):
        m = regex.search(text)
        if m:
            letter = m.group(1).upper()
            return letter if valid(letter) else None
    for regex in (BARE_LETTER_RE, LEADING_LETTER_RE):
        m = regex.match(text)
        if m:
            letter = m.group(1).upper()
            return letter if valid(letter) else None
    candidates = {c.upper() for c in INLINE_LETTER_RE.findall(text) if valid(c.upper())}
    return candidates.pop() if len(candidates) == 1 else None


def ground_truth(example):
    """(answer letter, number of options) of an example; uses the parsed fields when present."""
    prompt = example["conversations"][0]["value"]
    options = example.get("options") or OPTION_RE.findall(prompt.split("Answers:", 1)[-1])
    answer = example.get("answer") or extract_answer_letter(example["conversations"][1]["value"], len(options) or 4)
    return answer, max(len(options), 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--predictions", required=True, help="JSONL from predict.py (fields: index, generated_text)")
    parser.add_argument("--questions", default="data/validation.json")
    parser.add_argument("--out", default="scores.json", help="per-example details and summary")
    args = parser.parse_args()

    with open(args.questions) as f:
        examples = json.load(f)
    by_index = {ex.get("index", i): ex for i, ex in enumerate(examples)}

    predictions = {}
    with open(args.predictions) as f:
        for line in f:
            if line.strip():
                p = json.loads(line)
                predictions[p["index"]] = p.get("generated_text", "")

    total, correct, unreadable = Counter(), Counter(), 0
    records = []
    for index, ex in by_index.items():
        gt, n_options = ground_truth(ex)
        text = predictions.get(index)
        pred = extract_answer_letter(text, n_options) if text is not None else None
        if pred is None:
            unreadable += 1
        ok = pred == gt
        qtype = ex.get("type", "unknown")
        total[qtype] += 1
        correct[qtype] += ok
        records.append({"index": index, "type": qtype, "gt": gt, "pred": pred, "correct": ok,
                        "missing": text is None, "generated_text": text})

    n, c = sum(total.values()), sum(correct.values())
    summary = {
        "total": n,
        "correct": c,
        "accuracy": c / n if n else 0.0,
        "missing_predictions": sum(r["missing"] for r in records),
        "no_answer_letter": unreadable,
        "per_type": {t: {"total": total[t], "correct": correct[t], "accuracy": correct[t] / total[t]}
                     for t in sorted(total)},
    }
    with open(args.out, "w") as f:
        json.dump({"summary": summary, "examples": records}, f, indent=2, ensure_ascii=False)

    print(f"Accuracy: {summary['accuracy'] * 100:.2f}%  ({c}/{n}, {summary['missing_predictions']} missing, "
          f"{unreadable} without an answer letter)")
    for t, s in summary["per_type"].items():
        print(f"  {t:38s} {s['accuracy'] * 100:6.2f}%  ({s['correct']}/{s['total']})")
    print(f"Details written to {args.out}")


if __name__ == "__main__":
    main()
