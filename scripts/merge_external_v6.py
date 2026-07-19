#!/usr/bin/env python3
"""
Merge external HuggingFace datasets with the v5 training corpus.

Strategy:
- Normalize external data to {query, tool} format (same as v5)
- Cap each class to avoid overwhelming the synthetic data:
  - unknown: take ALL external (this is the weak class)
  - pureKnowledge: cap at 8000 (we already have plenty)
  - screenAction: cap at 8000
  - chitchat: cap at 3000
  - research: take ALL (only 836, small)
- Merge with v5 train data
- Write as v6 train file
"""

import json
import random

random.seed(42)

V5_TRAIN = "data/pace-intent-train-v5.jsonl"
EXTERNAL = "data/external/pace_mapped_external.jsonl"
OUTPUT = "data/pace-intent-train-v6.jsonl"

# Caps per class for external data
CAPS = {
    "unknown": 4000,        # weak class — add lots
    "pureKnowledge": 8000,  # already have 21k
    "screenAction": 8000,   # already have 34k
    "chitchat": 3000,       # already have 13k
    "research": 836,        # take all (small)
    "screenDescription": 0, # no external data for this
    "phoneLargeModel": 0,   # no external data for this
}

def main():
    # Load v5
    v5_examples = []
    with open(V5_TRAIN) as f:
        for line in f:
            ex = json.loads(line)
            v5_examples.append({"query": ex["query"], "tool": ex["tool"]})
    print(f"V5 train: {len(v5_examples)}")

    # Load external and group by intent
    external_by_class = {}
    with open(EXTERNAL) as f:
        for line in f:
            ex = json.loads(line)
            intent = ex["intent"]
            if intent not in external_by_class:
                external_by_class[intent] = []
            external_by_class[intent].append({"query": ex["text"], "tool": intent})

    print("\nExternal available:")
    for cls, examples in sorted(external_by_class.items()):
        cap = CAPS.get(cls, 0)
        taken = min(len(examples), cap)
        print(f"  {cls}: {len(examples)} available, cap={cap}, taking={taken}")

    # Sample external with caps
    external_sampled = []
    for cls, examples in external_by_class.items():
        cap = CAPS.get(cls, 0)
        if cap > 0:
            random.shuffle(examples)
            external_sampled.extend(examples[:cap])
    print(f"\nExternal sampled: {len(external_sampled)}")

    # Merge
    merged = v5_examples + external_sampled
    random.shuffle(merged)
    print(f"Merged total: {len(merged)}")

    # Distribution
    from collections import Counter
    dist = Counter(e["tool"] for e in merged)
    print("\nMerged distribution:")
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v} ({100*v/len(merged):.1f}%)")

    # Write
    with open(OUTPUT, "w") as f:
        for ex in merged:
            f.write(json.dumps(ex) + "\n")
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
