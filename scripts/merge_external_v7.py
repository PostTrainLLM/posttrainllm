#!/usr/bin/env python3
"""
Conservative merge: only add CLINC150 OOS + OVOS OOD examples to the
unknown class. Skip all other external data — it polluted the other
classes in v6.

The key insight: external "unknown" examples from banking/smart-home
domains look too similar to Pace's actionable commands. Only genuinely
out-of-scope queries (CLINC150 OOS, OVOS near_ood/far_ood) should be
added, and ONLY to the unknown class.
"""

import json
import random

random.seed(42)

V5_TRAIN = "data/pace-intent-train-v5.jsonl"
OUTPUT = "data/pace-intent-train-v7.jsonl"

def main():
    # Load v5
    v5_examples = []
    with open(V5_TRAIN) as f:
        for line in f:
            ex = json.loads(line)
            v5_examples.append({"query": ex["query"], "tool": ex["tool"]})
    print(f"V5 train: {len(v5_examples)}")

    # Load CLINC150 OOS only (train + test)
    clinc_oos = []
    for split_file in ["data/external/clinc150_train.jsonl",
                       "data/external/clinc150_test.jsonl"]:
        with open(split_file) as f:
            for line in f:
                ex = json.loads(line)
                if ex["is_oos"]:
                    clinc_oos.append({"query": ex["text"], "tool": "unknown"})
    print(f"CLINC150 OOS: {len(clinc_oos)}")

    # Load OVOS OOD only (near_ood + far_ood + asr_noise + typos)
    ovos_ood = []
    with open("data/external/ovos_enUS_test.jsonl") as f:
        for line in f:
            ex = json.loads(line)
            split = ex.get("split", "")
            if split in ("near_ood", "far_ood", "asr_noise", "typos"):
                ovos_ood.append({"query": ex["utterance"], "tool": "unknown"})
    print(f"OVOS OOD: {len(ovos_ood)}")

    # Load nfqa NOT-A-QUESTION only
    nfqa_unknown = []
    with open("data/external/nfqa_en.jsonl") as f:
        for line in f:
            ex = json.loads(line)
            if ex.get("ensemble_prediction") == "NOT-A-QUESTION":
                nfqa_unknown.append({"query": ex["question"], "tool": "unknown"})
    print(f"nfqa NOT-A-QUESTION: {len(nfqa_unknown)}")

    # Combine OOS examples
    all_oos = clinc_oos + ovos_ood + nfqa_unknown
    print(f"Total OOS: {len(all_oos)}")

    # Cap to avoid overwhelming — v5 already has 14k unknown
    # Adding ~2k more high-quality OOS examples
    CAP = 2000
    random.shuffle(all_oos)
    oos_sampled = all_oos[:CAP]
    print(f"OOS sampled (cap={CAP}): {len(oos_sampled)}")

    # Merge
    merged = v5_examples + oos_sampled
    random.shuffle(merged)
    print(f"Merged total: {len(merged)}")

    # Distribution
    from collections import Counter
    dist = Counter(e["tool"] for e in merged)
    print("\nMerged distribution:")
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v} ({100*v/len(merged):.1f}%)")

    with open(OUTPUT, "w") as f:
        for ex in merged:
            f.write(json.dumps(ex) + "\n")
    print(f"\nSaved to {OUTPUT}")


if __name__ == "__main__":
    main()
