#!/usr/bin/env python3
"""Assemble committed autocorrect bake-off evidence from local run outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "evals" / "autocorrect" / "eval-v1.jsonl"
MODEL_KEYS = ("t5-small", "flan-t5-small", "byt5-small")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output = args.output.resolve()
    fixture_hash = hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    candidates = []
    for key in MODEL_KEYS:
        measurements = load_json(run_dir / f"{key}-measurements.json")
        evaluation = load_json(run_dir / f"{key}-evaluation.json")
        predictions = load_jsonl(run_dir / f"{key}-predictions.jsonl")
        if evaluation["fixture_sha256"] != fixture_hash:
            raise SystemExit(f"{key}: fixture hash mismatch")
        if [row["id"] for row in predictions] != [
            row["id"] for row in evaluation["rows"]
        ]:
            raise SystemExit(f"{key}: prediction/evaluation row mismatch")
        candidates.append(
            {
                "model_key": key,
                "model_id": measurements["model_id"],
                "revision": measurements["revision"],
                "prompt_template": measurements["prompt_template"],
                "generation": measurements["generation"],
                "runtime": measurements["runtime"],
                "measurements": measurements["measurements"],
                "tokenizer_rows": measurements["tokenizer_rows"],
                "timing_rows": measurements["timing_rows"],
                "evaluation": {
                    "overall": evaluation["overall"],
                    "slices": evaluation["slices"],
                },
                "predictions": predictions,
            }
        )

    artifact = {
        "schema_version": 1,
        "report_id": "autocorrect-base-bakeoff-v1",
        "observed_on": "2026-07-25",
        "fixture": {
            "path": str(FIXTURE.relative_to(ROOT)),
            "sha256": fixture_hash,
            "rows": 18,
        },
        "host": {
            "model": "Apple M5 Pro",
            "memory_gib": 48,
            "power_mode": "not separately controlled",
            "thermal_procedure": "single warm-up followed by one bounded greedy pass per candidate",
        },
        "runner": {
            "script": "scripts/research/autocorrect_base_bakeoff.py",
            "dependencies": {
                "python": "3.12",
                "torch": "2.13.0",
                "transformers": "5.14.1",
                "sentencepiece": "0.2.2",
            },
            "network_policy": "weights downloaded once at pinned revisions; inference rerun with HF_HUB_OFFLINE=1 and TRANSFORMERS_OFFLINE=1",
            "measurement_notes": {
                "ttft": "Wall time for a separate one-token greedy generate after warm-up.",
                "end_to_end": "Wall time for greedy generation capped at 96 new tokens.",
                "peak_rss": "Process ru_maxrss after the complete candidate pass.",
                "energy": "Not measured in this bounded base-selection tranche.",
            },
        },
        "candidates": candidates,
        "selection": {
            "model_key": "flan-t5-small",
            "decision": "advance-to-training-feasibility",
            "reason": (
                "It is the smallest candidate that preserves most input and shows "
                "any positive zero-shot error reduction while remaining inside the "
                "frozen RSS and latency envelope. T5-small rewrites/translates and "
                "ByT5-small repeats input, breaches TTFT/end-to-end gates, and is "
                "substantially larger."
            ),
            "frozen_prompt_template": (
                "Correct only the typing errors in the following text. "
                "Return only the corrected text:\n{text}"
            ),
            "frozen_precision": "float32",
            "frozen_device": "mps",
            "frozen_generation": {
                "do_sample": False,
                "num_beams": 1,
                "max_new_tokens": 96,
            },
            "baseline_command": (
                "HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 "
                "TOKENIZERS_PARALLELISM=false uv run --isolated --python 3.12 "
                "--with torch==2.13.0 --with transformers==5.14.1 "
                "--with sentencepiece==0.2.2 python "
                "scripts/research/autocorrect_base_bakeoff.py --model-key flan-t5-small "
                "--model-dir "
                "/Users/sarthak/.cache/posttrainllm/autocorrect-bases/"
                "flan-t5-small-0fc9ddf --output-dir "
                "runs/autocorrect-base-bakeoff-v1 --device mps"
            ),
            "trainable_failure_slices": [
                "missed edits across substitution, omission, transposition, insertion, and space errors",
                "code-like span formatting damage",
                "deliberate whitespace preservation",
            ],
            "baseline_quality": {
                "error_reduction_rate": 0.0625,
                "exact_match_rate": 0.3888888888888889,
                "clean_byte_exact_preservation_rate": 0.6666666666666666,
                "protected_span_preservation_rate": 0.8666666666666667,
            },
            "not_authorized": [
                "adapter implementation",
                "training",
                "pilot",
                "packaging",
                "shipping",
            ],
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
