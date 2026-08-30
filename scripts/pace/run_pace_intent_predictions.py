#!/usr/bin/env python3
"""Produce private prediction-set artifacts for the Pace intent benchmark.

The script never scores or publishes. Inputs and model outputs belong under an
ignored run directory; ``run_everyday_benchmark.py`` is the authority that
validates identity, scores, and emits privacy-safe receipts.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import sys

# research/ is a sibling group under scripts/; add it to the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.joinpath("research")))
import check_everyday_benchmark as checker

LABELS = [
    "chitchat",
    "pureKnowledge",
    "screenDescription",
    "screenAction",
    "research",
    "phoneLargeModel",
    "unknown",
]

INSTRUCTIONS = """You classify one user voice turn for Pace, a macOS voice companion.
Return exactly one label.

- chitchat: greetings, thanks, goodbyes, apologies, or social filler
- pureKnowledge: a single spoken-answer question needing no current screen; questions about Pace itself; a past-tense mention of research is not a new research request
- screenDescription: inspect, read, summarize, or describe visible screen content without changing it
- screenAction: perform a supported Mac action such as click, type, open an app, navigate, or control volume
- research: a requested multi-step investigation, comparison, source search, or synthesis
- phoneLargeModel: explicitly or idiomatically escalate to a bigger, cloud, frontier, or smarter model
- unknown: unsupported physical/home/device/commerce actions, gibberish, or genuinely uncategorizable input

Pace-specific boundaries: volume control is screenAction; home lights and appliances are unknown; questions about Pace are pureKnowledge.
"""


def load_artifact(path: Path, artifact_type: str) -> dict[str, Any]:
    contract = checker.load_contract()
    value = checker.load_json(path)
    errors: list[str] = []
    checker.validate_artifact(value, contract, errors)
    if errors:
        raise ValueError(f"{path}: " + "; ".join(errors))
    if value.get("artifact_type") != artifact_type:
        raise ValueError(f"{path}: expected {artifact_type}")
    return value


def normalize_label(raw: str) -> str | None:
    compact = re.sub(r"[^a-z]", "", raw.lower())
    by_compact = {re.sub(r"[^a-z]", "", label.lower()): label for label in LABELS}
    if compact in by_compact:
        return by_compact[compact]
    matches = [label for key, label in by_compact.items() if key in compact]
    return matches[0] if len(matches) == 1 else None


def summarize_specialist_predictions(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(predictions) != len(LABELS):
        raise ValueError(f"specialist must emit all {len(LABELS)} class probabilities")
    tools = [item.get("tool") for item in predictions]
    if set(tools) != set(LABELS):
        raise ValueError(
            "specialist probabilities must cover every Pace label exactly once"
        )
    raw_probabilities = [item.get("prob") for item in predictions]
    if any(
        not isinstance(probability, (int, float)) or isinstance(probability, bool)
        for probability in raw_probabilities
    ):
        raise ValueError("specialist probabilities must be numeric")
    probabilities = [float(probability) for probability in raw_probabilities]
    if any(
        not math.isfinite(probability) or probability < 0
        for probability in probabilities
    ):
        raise ValueError("specialist probabilities must be finite and non-negative")
    total = sum(probabilities)
    if total <= 0:
        raise ValueError("specialist probabilities must have positive mass")
    normalized = [probability / total for probability in probabilities]
    ordered = sorted(normalized, reverse=True)
    entropy = -sum(
        probability * math.log(probability)
        for probability in normalized
        if probability > 0
    )
    return {
        "revision": "pace-softmax-summary-v1",
        "max_probability": ordered[0],
        "margin": ordered[0] - ordered[1],
        "normalized_entropy": entropy / math.log(len(LABELS)),
        "ood_score": None,
    }


def run_specialist(
    args: argparse.Namespace,
    instances: list[dict[str, Any]],
) -> list[tuple[str | None, float, str | None, dict[str, Any] | None]]:
    started = time.perf_counter()
    completed = subprocess.run(
        [
            str(args.binary),
            "extract",
            str(args.model),
            "--stdin",
            "--json",
            "--top-k",
            str(len(LABELS)),
        ],
        input="\n".join(item["input_text"] for item in instances) + "\n",
        capture_output=True,
        text=True,
        timeout=args.timeout,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if completed.returncode != 0:
        raise RuntimeError(f"specialist backend failed: {completed.stderr[-2000:]}")
    rows = [
        json.loads(line)
        for line in completed.stdout.splitlines()
        if line.strip().startswith("{")
    ]
    if len(rows) != len(instances):
        raise RuntimeError(
            f"specialist emitted {len(rows)} rows for {len(instances)} instances"
        )
    fallback_ms = elapsed_ms / len(instances)
    output = []
    for row in rows:
        predictions = row.get("predictions") or []
        label = predictions[0].get("tool") if predictions else None
        error = None if label in LABELS else "backend returned no valid label"
        signals = (
            summarize_specialist_predictions(predictions) if error is None else None
        )
        output.append(
            (
                label if error is None else None,
                float(row.get("latency_ms", fallback_ms)),
                error,
                signals,
            )
        )
    return output


def run_qwen(
    args: argparse.Namespace,
    instances: list[dict[str, Any]],
) -> list[tuple[str | None, float, str | None, dict[str, Any] | None]]:
    import mlx_lm  # Imported only for the explicitly selected local backend.

    model, tokenizer = mlx_lm.load(str(args.model))
    output = []
    for item in instances:
        messages = [
            {
                "role": "system",
                "content": INSTRUCTIONS + "\nRespond with only the label.",
            },
            {"role": "user", "content": item["input_text"]},
        ]
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        started = time.perf_counter()
        raw = mlx_lm.generate(model, tokenizer, prompt=prompt, max_tokens=12)
        latency_ms = (time.perf_counter() - started) * 1000
        label = normalize_label(raw)
        error = None if label is not None else "backend returned no valid label"
        output.append((label, latency_ms, error, None))
    return output


def codex_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "predictions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string", "enum": LABELS},
                    },
                    "required": ["id", "label"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["predictions"],
        "additionalProperties": False,
    }


def run_codex(
    args: argparse.Namespace,
    instances: list[dict[str, Any]],
) -> list[tuple[str | None, float, str | None, dict[str, Any] | None]]:
    payload = [{"id": item["id"], "text": item["input_text"]} for item in instances]
    prompt = (
        INSTRUCTIONS
        + "\nClassify every item below independently. Return one prediction for every id, in the same order. "
        "Do not inspect files, use tools, or explain.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    with tempfile.TemporaryDirectory(prefix="pace-intent-codex-") as raw_tmp:
        tmp = Path(raw_tmp)
        schema_path = tmp / "schema.json"
        response_path = tmp / "response.json"
        schema_path.write_text(json.dumps(codex_schema()), encoding="utf-8")
        command = [
            "codex",
            "exec",
            "-m",
            args.model,
            "-c",
            f"model_reasoning_effort={args.reasoning}",
            "--skip-git-repo-check",
            "--ephemeral",
            "-s",
            "read-only",
            "--output-schema",
            str(schema_path),
            "-o",
            str(response_path),
            "-",
        ]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=args.timeout,
            check=False,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        if completed.returncode != 0:
            raise RuntimeError(f"Codex backend failed: {completed.stderr[-3000:]}")
        response = json.loads(response_path.read_text(encoding="utf-8"))
    rows = response.get("predictions")
    if not isinstance(rows, list) or len(rows) != len(instances):
        raise RuntimeError(
            f"Codex returned {len(rows) if isinstance(rows, list) else 'invalid'} predictions"
        )
    by_id = {row.get("id"): row.get("label") for row in rows if isinstance(row, dict)}
    if set(by_id) != {item["id"] for item in instances}:
        raise RuntimeError(
            "Codex prediction ids do not exactly match the sealed instances"
        )
    amortized_ms = latency_ms / len(instances)
    return [(by_id[item["id"]], amortized_ms, None, None) for item in instances]


def run_apple_fm(
    args: argparse.Namespace,
    instances: list[dict[str, Any]],
) -> list[tuple[str | None, float, str | None, dict[str, Any] | None]]:
    completed = subprocess.run(
        [str(args.bridge)],
        input="\n".join(
            json.dumps({"id": item["id"], "text": item["input_text"]})
            for item in instances
        )
        + "\n",
        capture_output=True,
        text=True,
        timeout=args.timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Apple FM backend failed: {completed.stderr[-2000:]}")
    rows = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    if len(rows) != len(instances):
        raise RuntimeError(
            f"Apple FM emitted {len(rows)} rows for {len(instances)} instances"
        )
    by_id = {row.get("id"): row for row in rows}
    output = []
    for item in instances:
        row = by_id.get(item["id"], {})
        label = row.get("label") if row.get("label") in LABELS else None
        error = row.get("error") or (
            None if label is not None else "backend returned no valid label"
        )
        output.append(
            (
                label if error is None else None,
                float(row.get("latency_ms", 0)),
                error,
                None,
            )
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend", required=True, choices=("specialist", "qwen", "codex", "apple-fm")
    )
    parser.add_argument("--instances", required=True, type=Path)
    parser.add_argument("--entry", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--model", type=str)
    parser.add_argument(
        "--binary", type=Path, default=Path("native-mac/.build/release/posttrainllm")
    )
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--reasoning", default="medium")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    try:
        instances = load_artifact(args.instances, "instance_set")
        entry = load_artifact(args.entry, "entry")
        if args.repetitions < 1:
            raise ValueError("--repetitions must be positive")
        if args.backend in {"specialist", "qwen", "codex"} and not args.model:
            raise ValueError(f"--model is required for {args.backend}")
        if args.backend == "apple-fm" and args.bridge is None:
            raise ValueError("--bridge is required for apple-fm")
        backend = {
            "specialist": run_specialist,
            "qwen": run_qwen,
            "codex": run_codex,
            "apple-fm": run_apple_fm,
        }[args.backend]
        outputs = []
        for pass_index in range(1, args.repetitions + 1):
            rows = backend(args, instances["instances"])
            for item, (label, latency_ms, error, decision_signals) in zip(
                instances["instances"], rows
            ):
                output = {
                    "instance_id": item["id"],
                    "pass_index": pass_index,
                    "predicted_label": label,
                    "latency_ms": latency_ms,
                    "error": error,
                    "routing": None,
                }
                if decision_signals is not None:
                    output["decision_signals"] = decision_signals
                outputs.append(output)
        artifact = {
            "artifact_type": "prediction_set",
            "contract_version": "everyday-benchmark/v1",
            "prediction_set_id": f"{entry['entry_id']}-{instances['instance_set_id']}-predictions",
            "revision": "1",
            "task_ref": instances["task_ref"],
            "entry_ref": {"id": entry["entry_id"], "revision": entry["revision"]},
            "instance_set_ref": {
                "id": instances["instance_set_id"],
                "revision": instances["revision"],
            },
            "outputs": outputs,
        }
        errors: list[str] = []
        checker.validate_artifact(artifact, checker.load_contract(), errors)
        if errors:
            raise ValueError("generated predictions are invalid: " + "; ".join(errors))
        if args.out.exists():
            raise ValueError(f"refusing to overwrite {args.out}")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    except (
        OSError,
        ValueError,
        RuntimeError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as exc:
        print(f"pace-intent predictions failed: {exc}")
        return 1
    print(f"pace-intent predictions: wrote {args.out} ({len(outputs)} outputs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
