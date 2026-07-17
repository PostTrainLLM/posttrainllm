#!/usr/bin/env python3
"""Score Qwen3-4B-Instruct (Pace's bundled MLX planner) as an intent classifier
on the same held-out split used for the posttrainllm ToolRouterModel eval.

Samples 1000 stratified examples to keep runtime reasonable (~15-20 min).
"""
import json, random, time, sys, re
from collections import defaultdict, Counter

import mlx_lm

EVAL_PATH = "/Users/sarthak/Desktop/fleet/posttrainllm/data/pace-intent-eval.jsonl"
MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
SAMPLE_N = 1000
SEED = 42

VALID_INTENTS = {
    "pureknowledge", "screendescription", "screenaction",
    "chitchat", "phonelargemodel", "research", "unknown"
}
INTENT_MAP = {
    "pureknowledge": "pureKnowledge",
    "screendescription": "screenDescription",
    "screenaction": "screenAction",
    "phonelargemodel": "phoneLargeModel",
}

SYSTEM_PROMPT = """You classify a single user voice turn into ONE routing category for Pace, a macOS voice companion. Pick the most accurate route.

Categories:
- chitchat: greetings, thanks, goodbyes, mic checks
- pureKnowledge: any question that wants a spoken answer WITHOUT looking at the current screen — factual questions, self-history, questions about Pace itself
- screenDescription: user wants Pace to look at and describe the current screen
- screenAction: user wants Pace to DO something — click, type, open, launch, play, pause, create, draft, etc.
- phoneLargeModel: user explicitly asked for a bigger/stronger model
- research: multi-step research — "research X", "compare A vs B", "investigate Z", "dig into Y"
- unknown: genuinely cannot categorize

Respond with ONLY the category name, nothing else."""

def load_eval():
    data = []
    with open(EVAL_PATH) as f:
        for line in f:
            data.append(json.loads(line))
    return data

def stratified_sample(data, n, seed):
    rng = random.Random(seed)
    by_cls = defaultdict(list)
    for e in data:
        by_cls[e["tool"]].append(e)
    # Proportional sample
    total = len(data)
    sample = []
    for cls, items in by_cls.items():
        n_cls = max(20, int(n * len(items) / total))
        n_cls = min(n_cls, len(items))
        sample.extend(rng.sample(items, n_cls))
    rng.shuffle(sample)
    return sample[:n]

def normalize_prediction(text):
    """Extract the intent from the model's response."""
    text = text.strip().lower().strip(".!? ")
    # Remove thinking blocks
    text = re.sub(r"</?think>", "", text)
    text = text.strip()
    # Map to canonical form
    if text in VALID_INTENTS:
        return INTENT_MAP.get(text, text)
    # Try to find a valid intent in the text
    for intent in VALID_INTENTS:
        if intent in text:
            return INTENT_MAP.get(intent, intent)
    return "unknown"  # fallback

def main():
    print(f"Loading eval data from {EVAL_PATH}...")
    data = load_eval()
    print(f"  {len(data)} total examples")

    sample = stratified_sample(data, SAMPLE_N, SEED)
    print(f"  sampled {len(sample)} stratified examples")
    print(f"  class distribution: {Counter(e['tool'] for e in sample)}")
    print()

    print(f"Loading model {MODEL}...")
    model, tokenizer = mlx_lm.load(MODEL)
    print("  model loaded")
    print()

    correct = 0
    total = 0
    per_class_correct = defaultdict(int)
    per_class_total = defaultdict(int)
    confusion = defaultdict(lambda: defaultdict(int))
    latencies = []
    mispredicted = []

    start_time = time.time()

    for i, ex in enumerate(sample):
        query = ex["query"]
        true_label = ex["tool"]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f'user said: "{query}"'},
        ]

        t0 = time.perf_counter()
        response = mlx_lm.generate(
            model, tokenizer,
            prompt=tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True),
            max_tokens=10,
        )
        elapsed = time.perf_counter() - t0
        latencies.append(elapsed)

        pred = normalize_prediction(response)
        total += 1
        per_class_total[true_label] += 1
        confusion[true_label][pred] += 1

        if pred == true_label:
            correct += 1
            per_class_correct[true_label] += 1
        else:
            if len(mispredicted) < 20:
                mispredicted.append({
                    "query": query[:80],
                    "true": true_label,
                    "pred": pred,
                    "raw": response.strip()[:50],
                })

        if (i + 1) % 100 == 0:
            elapsed_total = time.time() - start_time
            acc_so_far = correct / total * 100
            print(f"  {i+1}/{len(sample)}  acc={acc_so_far:.1f}%  "
                  f"elapsed={elapsed_total:.0f}s  "
                  f"avg_latency={sum(latencies)/len(latencies):.2f}s")

    elapsed_total = time.time() - start_time

    print()
    print("=" * 60)
    print(f"QWEN3-4B-INSTRUCT BASELINE — {MODEL}")
    print("=" * 60)
    print(f"Overall accuracy: {correct}/{total} = {correct/total*100:.2f}%")
    print(f"Total time: {elapsed_total:.0f}s")
    print(f"Avg latency: {sum(latencies)/len(latencies):.2f}s")
    print(f"p50 latency: {sorted(latencies)[len(latencies)//2]:.2f}s")
    print()

    print("Per-class accuracy:")
    print(f"  {'Class':24s}  {'Acc':>8s}  {'Count':>6s}")
    print(f"  {'-'*24}  {'-'*8}  {'-'*6}")
    for cls in ["chitchat", "pureKnowledge", "screenDescription",
                "screenAction", "research", "phoneLargeModel", "unknown"]:
        tc = per_class_total[cls]
        cc = per_class_correct[cls]
        acc = cc / tc * 100 if tc > 0 else 0
        print(f"  {cls:24s}  {acc:7.1f}%  {tc:6d}")

    print()
    print("Confusion matrix (rows=true, cols=predicted):")
    classes = ["chitchat", "pureKnowledge", "screenDescription",
               "screenAction", "research", "phoneLargeModel", "unknown"]
    header = f"  {'':24s} " + " ".join(f"{c[:8]:>8s}" for c in classes)
    print(header)
    for true_cls in classes:
        row = f"  {true_cls:24s} "
        for pred_cls in classes:
            count = confusion[true_cls][pred_cls]
            row += f" {count:8d}"
        print(row)

    if mispredicted:
        print()
        print("Sample mispredictions (first 20):")
        for m in mispredicted:
            print(f"  true={m['true']:20s} pred={m['pred']:20s} raw='{m['raw']}'")
            print(f"    query: {m['query']}")

    # Save results
    results = {
        "model": MODEL,
        "sample_size": total,
        "overall_accuracy": correct / total,
        "per_class": {
            cls: {
                "accuracy": per_class_correct[cls] / per_class_total[cls] if per_class_total[cls] > 0 else 0,
                "count": per_class_total[cls],
            }
            for cls in classes
        },
        "latency_s": {
            "mean": sum(latencies) / len(latencies),
            "p50": sorted(latencies)[len(latencies) // 2],
        },
        "total_time_s": elapsed_total,
    }
    out_path = "/Users/sarthak/Desktop/fleet/posttrainllm/runs/2026-07-13-pace-intent-router-v1/eval-qwen-baseline.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {out_path}")

if __name__ == "__main__":
    main()
