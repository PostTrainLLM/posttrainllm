#!/usr/bin/env python3
"""Run one bounded, offline autocorrect base-model smoke.

The model weights must already exist in an explicit local directory. Runtime
dependencies are intentionally supplied by the caller so this script does not
change the project's production dependency surface.
"""

from __future__ import annotations

import argparse
import json
import platform
import resource
import statistics
import time
from pathlib import Path

from autocorrect_foundation import evaluate, load_jsonl


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals" / "autocorrect" / "eval-v1.jsonl"

MODEL_CONFIGS = {
    "t5-small": {
        "model_id": "google-t5/t5-small",
        "revision": "df1b051c49625cf57a3d0d8d3863ed4d13564fe4",
        "prompt": "correct: {text}",
    },
    "flan-t5-small": {
        "model_id": "google/flan-t5-small",
        "revision": "0fc9ddf78a1e988dac52e2dac162b0ede4fd74ab",
        "prompt": (
            "Correct only the typing errors in the following text. "
            "Return only the corrected text:\n{text}"
        ),
    },
    "byt5-small": {
        "model_id": "google/byt5-small",
        "revision": "68377bdc18a2ffec8a0533fef03b1c513a4dd49d",
        "prompt": "correct: {text}",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-key", required=True, choices=sorted(MODEL_CONFIGS))
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--device", choices=("cpu", "mps"), default="mps")
    return parser.parse_args()


def load_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def synchronize(torch_module, device: str) -> None:
    if device == "mps":
        torch_module.mps.synchronize()


def peak_rss_mib() -> float:
    # macOS reports ru_maxrss in bytes; Linux reports KiB.
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024**2 if platform.system() == "Darwin" else 1024
    return value / divisor


def main() -> int:
    args = parse_args()
    config = MODEL_CONFIGS[args.model_key]
    model_dir = args.model_dir.resolve()
    output_dir = args.output_dir.resolve()
    if not model_dir.is_dir():
        raise SystemExit(f"model directory does not exist: {model_dir}")

    import torch
    import transformers
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    if args.device == "mps" and not torch.backends.mps.is_available():
        raise SystemExit("MPS is unavailable")

    rows = load_rows()
    load_started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        model_dir,
        local_files_only=True,
        use_fast=True,
    )
    model = AutoModelForSeq2SeqLM.from_pretrained(
        model_dir,
        local_files_only=True,
    ).to(args.device)
    model.eval()
    synchronize(torch, args.device)
    load_seconds = time.perf_counter() - load_started

    prompts = [config["prompt"].format(text=row["noisy"]) for row in rows]
    tokenizer_rows = []
    for row, prompt in zip(rows, prompts, strict=True):
        noisy_tokens = len(tokenizer(row["noisy"], add_special_tokens=True).input_ids)
        clean_tokens = len(tokenizer(row["clean"], add_special_tokens=True).input_ids)
        prompt_tokens = len(tokenizer(prompt, add_special_tokens=True).input_ids)
        tokenizer_rows.append(
            {
                "id": row["id"],
                "noisy_tokens": noisy_tokens,
                "clean_tokens": clean_tokens,
                "noisy_minus_clean_tokens": noisy_tokens - clean_tokens,
                "prompt_tokens": prompt_tokens,
            }
        )

    # One warm-up establishes kernels without contaminating reported row timing.
    warmup = tokenizer(prompts[0], return_tensors="pt").to(args.device)
    with torch.inference_mode():
        model.generate(**warmup, do_sample=False, num_beams=1, max_new_tokens=2)
    synchronize(torch, args.device)

    predictions = []
    timing_rows = []
    total_generated_tokens = 0
    total_generation_seconds = 0.0
    for row, prompt in zip(rows, prompts, strict=True):
        encoded = tokenizer(prompt, return_tensors="pt").to(args.device)

        synchronize(torch, args.device)
        ttft_started = time.perf_counter()
        with torch.inference_mode():
            model.generate(
                **encoded,
                do_sample=False,
                num_beams=1,
                max_new_tokens=1,
            )
        synchronize(torch, args.device)
        ttft_ms = (time.perf_counter() - ttft_started) * 1000

        synchronize(torch, args.device)
        generation_started = time.perf_counter()
        with torch.inference_mode():
            output = model.generate(
                **encoded,
                do_sample=False,
                num_beams=1,
                max_new_tokens=96,
            )
        synchronize(torch, args.device)
        generation_seconds = time.perf_counter() - generation_started
        generated_tokens = max(0, int(output.shape[-1]) - 1)
        prediction = tokenizer.decode(output[0], skip_special_tokens=True)

        predictions.append({"id": row["id"], "prediction": prediction})
        timing_rows.append(
            {
                "id": row["id"],
                "ttft_ms": round(ttft_ms, 3),
                "end_to_end_ms": round(generation_seconds * 1000, 3),
                "generated_tokens": generated_tokens,
            }
        )
        total_generated_tokens += generated_tokens
        total_generation_seconds += generation_seconds

    output_dir.mkdir(parents=True, exist_ok=True)
    predictions_path = output_dir / f"{args.model_key}-predictions.jsonl"
    predictions_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in predictions),
        encoding="utf-8",
    )
    evaluation = evaluate(load_jsonl(FIXTURE), predictions)
    evaluation_path = output_dir / f"{args.model_key}-evaluation.json"
    evaluation_path.write_text(
        json.dumps(evaluation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": 1,
        "kind": "autocorrect-base-bakeoff",
        "model_key": args.model_key,
        "model_id": config["model_id"],
        "revision": config["revision"],
        "local_model_dir": str(model_dir),
        "fixture": str(FIXTURE.relative_to(ROOT)),
        "prompt_template": config["prompt"],
        "generation": {
            "do_sample": False,
            "num_beams": 1,
            "max_new_tokens": 96,
        },
        "runtime": {
            "device": args.device,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "measurements": {
            "load_seconds": round(load_seconds, 3),
            "peak_rss_mib": round(peak_rss_mib(), 3),
            "median_ttft_ms": round(median([row["ttft_ms"] for row in timing_rows]), 3),
            "median_end_to_end_ms": round(
                median([row["end_to_end_ms"] for row in timing_rows]), 3
            ),
            "throughput_generated_tokens_per_second": round(
                total_generated_tokens / total_generation_seconds
                if total_generation_seconds
                else 0.0,
                3,
            ),
            "median_noisy_tokens": median(
                [row["noisy_tokens"] for row in tokenizer_rows]
            ),
            "median_clean_tokens": median(
                [row["clean_tokens"] for row in tokenizer_rows]
            ),
            "mean_noisy_minus_clean_tokens": round(
                statistics.mean(
                    row["noisy_minus_clean_tokens"] for row in tokenizer_rows
                ),
                3,
            ),
        },
        "tokenizer_rows": tokenizer_rows,
        "timing_rows": timing_rows,
        "predictions_file": predictions_path.name,
        "evaluation_file": evaluation_path.name,
    }
    report_path = output_dir / f"{args.model_key}-measurements.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["measurements"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
