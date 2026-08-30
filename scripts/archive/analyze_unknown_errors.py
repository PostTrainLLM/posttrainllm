#!/usr/bin/env python3
"""Analyze v5's errors on the unknown class to understand what it misclassifies."""
import json
import subprocess
import sys
from collections import Counter

MODEL = "runs/pace-intent-router-v5.tinygpt"
EVAL = "data/pace-intent-eval.jsonl"
BINARY = "native-mac/.build/release/posttrainllm"

# Load eval
examples = []
with open(EVAL) as f:
    for line in f:
        examples.append(json.loads(line))

# Get unknown examples
unknown_examples = [ex for ex in examples if ex["tool"] == "unknown"]
print(f"Unknown eval examples: {len(unknown_examples)}")

# Classify them
queries = [ex["query"] for ex in unknown_examples]
query_text = "\n".join(queries)

proc = subprocess.run(
    [BINARY, "extract", MODEL, "--stdin", "--json", "--top-k", "3"],
    input=query_text,
    capture_output=True,
    text=True,
    timeout=120,
)

predictions = []
for line in proc.stdout.strip().split("\n"):
    if line.strip():
        predictions.append(json.loads(line))

# Analyze errors
errors = []
for ex, pred in zip(unknown_examples, predictions):
    top1 = pred["predictions"][0]["tool"]
    conf = pred["predictions"][0]["prob"]
    if top1 != "unknown":
        errors.append({
            "query": ex["query"],
            "predicted": top1,
            "confidence": conf,
            "top3": [(p["tool"], round(p["prob"], 3)) for p in pred["predictions"][:3]]
        })

print(f"\nErrors on unknown: {len(errors)}/{len(unknown_examples)} ({100*len(errors)/len(unknown_examples):.1f}%)")

# What classes are unknown examples being misclassified as?
misclassified_as = Counter(e["predicted"] for e in errors)
print("\nUnknown → misclassified as:")
for cls, count in misclassified_as.most_common():
    print(f"  {cls}: {count}")

# Show some examples
print("\nSample errors (first 30):")
for e in errors[:30]:
    print(f"  [{e['predicted']} ({e['confidence']:.2f})] {e['query'][:80]}")

# Confidence distribution of errors
confs = [e["confidence"] for e in errors]
confs.sort()
print(f"\nError confidence: min={confs[0]:.3f}, p25={confs[len(confs)//4]:.3f}, "
      f"p50={confs[len(confs)//2]:.3f}, p75={confs[3*len(confs)//4]:.3f}, max={confs[-1]:.3f}")

# How many errors would be caught by escalation threshold?
for threshold in [0.80, 0.85, 0.90, 0.95]:
    would_escalate = sum(1 for e in errors if e["confidence"] < threshold)
    print(f"  threshold {threshold}: {would_escalate}/{len(errors)} errors would escalate ({100*would_escalate/len(errors):.0f}%)")
