#!/usr/bin/env python3
"""Render a batch-first post-training plan for offline RL/DPO loops."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run-id", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--prompts", required=True)
    p.add_argument("--base-model", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--rollouts-per-prompt", type=int, default=4)
    p.add_argument("--method", default="reference-anchored-dpo")
    args = p.parse_args()

    prompts = Path(args.prompts)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    row_count = sum(1 for line in prompts.read_text().splitlines() if line.strip())
    manifest = {
        "run_id": args.run_id,
        "target": args.target,
        "loop": "batch-first-posttraining",
        "method": args.method,
        "base_model": args.base_model,
        "prompt_set": {
            "path": str(prompts),
            "rows": row_count,
            "sha256": sha256(prompts),
        },
        "rollouts": {
            "per_prompt": args.rollouts_per_prompt,
            "expected_rows": row_count * args.rollouts_per_prompt,
            "policy": "frozen inference policy until this batch is scored",
        },
        "steps": [
            "freeze prompts and baseline",
            "generate N rollouts per prompt from one inference policy",
            "score rollouts offline with verifier/reward",
            "convert scored rollouts to preference or reward JSONL",
            "train one compact adapter update",
            "evaluate against frozen baseline and slice metrics",
            "write trace_review.md and decision.json before any package claim",
        ],
        "required_outputs": [
            "rollouts.jsonl",
            "scores.jsonl",
            "preferences.jsonl or rewards.jsonl",
            "train.log",
            "eval-candidate.json",
            "slice-metrics.json",
            "trace_review.md",
            "decision.json",
        ],
    }
    (out_dir / "batch-posttrain-plan.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    (out_dir / "README.md").write_text(
        f"""# {args.run_id}

Batch-first post-training plan for `{args.target}`.

This folder is a plan scaffold, not a completed run. Generate rollouts in bulk,
score them offline, train one adapter update, then evaluate and decide.

Prompt rows: {row_count}
Rollouts per prompt: {args.rollouts_per_prompt}
Expected rollout rows: {row_count * args.rollouts_per_prompt}

Do not update the inference policy mid-batch. If the policy changes, start a
new plan/run id so stale-rollout effects are explicit.
"""
    )
    print(f"rendered batch post-training plan -> {out_dir}")


if __name__ == "__main__":
    main()
