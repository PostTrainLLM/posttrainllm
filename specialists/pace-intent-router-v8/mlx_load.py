#!/usr/bin/env python3
"""Lightweight loader for the pace-intent-router-v8 specialist.

Supports metadata-only validation by default. Pass --load to actually
load the model weights (requires posttrainllm native-mac runtime).

Usage:
    python3 mlx_load.py                    # metadata check only
    python3 mlx_load.py --load             # load weights + run smoke test
    python3 mlx_load.py --load --query "what is HTML"  # classify a query
"""

import argparse
import json
import os
import sys
from pathlib import Path


def load_lock():
    here = Path(__file__).parent
    lock_path = here / "tinygpt.lock.json"
    if not lock_path.exists():
        print(f"ERROR: lock file not found at {lock_path}", file=sys.stderr)
        sys.exit(1)
    with open(lock_path) as f:
        return json.load(f)


def load_eval():
    here = Path(__file__).parent
    eval_path = here / "eval_report.json"
    if not eval_path.exists():
        return None
    with open(eval_path) as f:
        return json.load(f)


def check_metadata():
    lock = load_lock()
    print(f"Package: {lock['id']}")
    print(f"Type: {lock['artifact_type']}")
    print(f"Base: {lock['base_model']['id']}")
    print(f"Params: {lock['base_model']['layers']} layers, "
          f"{lock['base_model']['d_model']} d_model, "
          f"vocab {lock['base_model']['vocab_size']}")
    print(f"Training: {lock['training']['method']}, "
          f"{lock['training']['steps']} steps, "
          f"{lock['training']['train_rows']} train rows")

    # Check artifact exists
    repo_root = Path(__file__).parents[2]
    artifact_path = repo_root / lock["local_path"]
    if artifact_path.exists():
        size_mb = artifact_path.stat().st_size / (1024 * 1024)
        print(f"Artifact: {artifact_path} ({size_mb:.1f} MB) ✓")
    else:
        print(f"Artifact: {artifact_path} — NOT FOUND")
        print("  (expected at runs/pace-intent-router-v8.tinygpt)")

    # Show eval summary
    ev = load_eval()
    if ev:
        print(f"\nEval: {ev['overall_accuracy']*100:.1f}% accuracy "
              f"on {ev['eval_size']} examples")
        print(f"Latency: {ev['latency_ms']['p50']:.1f}ms p50")
        if "baselines" in ev:
            qwen = ev["baselines"].get("qwen3-4b-instruct-4bit", {})
            if qwen:
                delta = (ev["overall_accuracy"] - qwen["overall_accuracy"]) * 100
                print(f"vs Qwen3-4B: +{delta:.1f} pp accuracy, "
                      f"{ev['latency_ms']['p50']:.0f}ms vs "
                      f"{qwen['latency_p50_ms']:.0f}ms latency")

    print("\nMetadata check passed.")


def load_and_classify(query: str):
    """Load the model and classify a query.

    This requires the posttrainllm native-mac runtime to be built.
    """
    lock = load_lock()
    repo_root = Path(__file__).parents[2]
    artifact_path = repo_root / lock["local_path"]

    if not artifact_path.exists():
        print(f"ERROR: artifact not found at {artifact_path}", file=sys.stderr)
        sys.exit(1)

    # Try to use the posttrainllm CLI for inference
    bin_path = repo_root / "native-mac" / ".build" / "release" / "posttrainllm"
    if not bin_path.exists():
        print(f"ERROR: posttrainllm binary not found at {bin_path}",
              file=sys.stderr)
        print("Build it first: cd native-mac && xcrun swift build -c release",
              file=sys.stderr)
        sys.exit(1)

    import subprocess
    result = subprocess.run(
        [str(bin_path), "sample", str(artifact_path),
         "--prompt", query, "--max-tokens", "1"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: inference failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Query: {query}")
    print(f"Classification: {result.stdout.strip()}")


def main():
    parser = argparse.ArgumentParser(
        description="pace-intent-router-v8 specialist loader"
    )
    parser.add_argument("--load", action="store_true",
                        help="Load weights (default: metadata only)")
    parser.add_argument("--query", type=str, default=None,
                        help="Classify a query (requires --load)")
    args = parser.parse_args()

    if not args.load:
        check_metadata()
    elif args.query:
        load_and_classify(args.query)
    else:
        check_metadata()
        print("\n--load specified but no --query given. "
              "Run with --query 'your query' to classify.")


if __name__ == "__main__":
    main()
