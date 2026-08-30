#!/usr/bin/env python3
"""
Evaluate a trained intent router .tinygpt model on the held-out eval set.

Uses `posttrainllm extract --stdin --json` to classify each query,
then computes per-class accuracy + overall accuracy + latency.

Usage:
    python3 scripts/archive/eval_intent_router.py \
        --model runs/pace-intent-router-v6.tinygpt \
        --eval data/pace-intent-eval.jsonl \
        --binary native-mac/.build/release/posttrainllm
"""

import argparse
import json
import subprocess
import sys
import time
from collections import defaultdict


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="Path to .tinygpt checkpoint")
    parser.add_argument("--eval", required=True, help="Path to eval JSONL")
    parser.add_argument("--binary", default="native-mac/.build/release/posttrainllm",
                        help="Path to posttrainllm binary")
    parser.add_argument("--out", default=None, help="Output JSON file")
    parser.add_argument("--label", default="", help="Model label for the report")
    args = parser.parse_args()

    # Load eval data
    eval_examples = []
    with open(args.eval) as f:
        for line in f:
            ex = json.loads(line)
            eval_examples.append(ex)
    print(f"Loaded {len(eval_examples)} eval examples")

    # Stream queries through posttrainllm extract --stdin --json
    queries = [ex["query"] for ex in eval_examples]
    query_text = "\n".join(queries)

    print(f"Classifying {len(queries)} queries via {args.binary} extract...")
    t0 = time.time()
    proc = subprocess.run(
        [args.binary, "extract", args.model, "--stdin", "--json", "--top-k", "1"],
        input=query_text,
        capture_output=True,
        text=True,
        timeout=300,
    )
    elapsed = time.time() - t0
    print(f"Classification done in {elapsed:.1f}s")

    if proc.returncode != 0:
        print(f"ERROR: posttrainllm extract failed (exit {proc.returncode})")
        print(proc.stderr[:2000])
        sys.exit(1)

    # Parse predictions
    predictions = []
    for line in proc.stdout.strip().split("\n"):
        if not line.strip():
            continue
        try:
            pred = json.loads(line)
            predictions.append(pred)
        except json.JSONDecodeError:
            print(f"WARNING: could not parse line: {line[:100]}")
            predictions.append(None)

    if len(predictions) != len(eval_examples):
        print(f"WARNING: {len(predictions)} predictions for {len(eval_examples)} examples")

    # Score
    correct = 0
    per_class_correct = defaultdict(int)
    per_class_total = defaultdict(int)
    latencies = []

    for i, (ex, pred) in enumerate(zip(eval_examples, predictions)):
        gold = ex["tool"]
        per_class_total[gold] += 1
        if pred is None:
            continue
        # Extract top-1 prediction
        if "predictions" in pred and len(pred["predictions"]) > 0:
            predicted_tool = pred["predictions"][0]["tool"]
            latency_ms = pred.get("latency_ms", 0)
            latencies.append(latency_ms)
        elif "tool" in pred:
            predicted_tool = pred["tool"]
            latency_ms = pred.get("latency_ms", 0)
            latencies.append(latency_ms)
        else:
            continue

        if predicted_tool == gold:
            correct += 1
            per_class_correct[gold] += 1

    overall_accuracy = correct / len(eval_examples)
    print(f"\nOverall accuracy: {overall_accuracy:.4f} ({correct}/{len(eval_examples)})")

    print("\nPer-class accuracy:")
    per_class = {}
    for cls in sorted(per_class_total.keys()):
        total = per_class_total[cls]
        corr = per_class_correct[cls]
        acc = corr / total if total > 0 else 0
        per_class[cls] = {"accuracy": acc, "count": total}
        print(f"  {cls}: {acc:.4f} ({corr}/{total})")

    if latencies:
        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        mean = sum(latencies) / len(latencies)
        print(f"\nLatency: p50={p50:.2f}ms, mean={mean:.2f}ms")
    else:
        p50 = 0
        mean = 0

    # Save results
    result = {
        "model": args.label or args.model,
        "overall_accuracy": overall_accuracy,
        "eval_size": len(eval_examples),
        "per_class": per_class,
        "latency_ms": {"p50": p50, "mean": mean},
    }

    if args.out:
        with open(args.out, "w") as f:
            json.dump(result, f, indent=2)
        print(f"\nSaved to {args.out}")


if __name__ == "__main__":
    main()
