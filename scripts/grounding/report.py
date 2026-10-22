"""Derive the issue-200 factory report and retain only a passing local adapter."""

import hashlib
import json
import random
import shutil
import statistics
import subprocess
import sys
from datetime import datetime, timezone

from prepare import OUT, ROOT, validate_rows, write


def read(name):
    return json.loads((OUT / name).read_text())


def uncertainty(parent, candidate):
    other = {r["id"]: r for r in candidate["rows"]}
    rows = [
        r
        for r in parent["rows"]
        if r.get("split") == "test" and r.get("present") is False
    ]
    differences = [
        int(not r["abstained"]) - int(not other[r["id"]]["abstained"]) for r in rows
    ]
    rng = random.Random(200)
    values = sorted(
        statistics.mean(rng.choices(differences, k=len(rows))) for _ in range(10000)
    )
    return {
        "improvement": statistics.mean(differences),
        "paired_95_percentile_ci": [values[249], values[9749]],
        "unit": "held-out source document",
        "bootstrap_samples": 10000,
        "seed": 200,
    }


def evidence():
    contract = read("contract.json")
    for path, expected in contract["files_sha256"].items():
        assert hashlib.sha256((OUT / path).read_bytes()).hexdigest() == expected, path
    rows = {}
    for name in ["baseline", "ordinary", "perturbation"]:
        result, bfcl = read(f"{name}-result.json"), read(f"bfcl-{name}-result.json")
        assert result["complete"] and bfcl["complete"]
        rows[name] = {
            "raw": result,
            "bfcl_raw": bfcl,
            "test": result["slices"]["test"],
            "regression": result["regression"]["regression_accuracy"],
            "bfcl": bfcl["passed"] / bfcl["count"],
        }
    assert (
        read("frontier-result.json")["valid"]
        and read("bfcl-frontier-result.json")["valid"]
    )
    return contract, rows


def retain_package(contract):
    package = OUT / "package"
    source = OUT / "adapters/perturbation/adapters.safetensors"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if package.exists():
        manifest = read("package/artifact-manifest.json")
        assert manifest["weights_sha256"] == digest
        assert (
            hashlib.sha256((package / source.name).read_bytes()).hexdigest() == digest
        )
        assert manifest["base"] == {
            "id": contract["model"],
            "revision": contract["revision"],
        }
        return digest
    package.mkdir()
    shutil.copy2(source, package / source.name)
    actual = read("adapters/perturbation/adapter_config.json")
    config = {
        key: actual[key] for key in ["fine_tune_type", "num_layers", "lora_parameters"]
    }
    config.update({"model": contract["model"], "base_revision": contract["revision"]})
    write(package / "adapter_config.json", config)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "artifact": {"id": "grounding-qwen17-perturbation-v1", "revision": digest},
        "kind": "adapter",
        "artifact_path": ".",
        "base": {"id": contract["model"], "revision": contract["revision"]},
        "tokenizer": {
            "id": contract["model"],
            "revision": contract["revision"],
            "chat_template": "qwen3-no-thinking",
        },
        "history": [
            {
                "action": "sft",
                "tool": "mlx-lm-0.32.2",
                "detail": "QLoRA rank4,4layers;20 TRAIN-only wiring updates then80 full TRAIN updates",
            }
        ],
        "runtimes": ["mlx-lm"],
        "next": ["eval"],
        "receipts": [{"kind": "eval", "path": "receipts/qualification.json"}],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "distribution": "owner-local-only; no public release",
        "weights_sha256": digest,
    }
    write(package / "artifact-manifest.json", manifest)
    return digest


def metrics(name, row, digest=None):
    result, bfcl = row["raw"], row["bfcl_raw"]
    train = (
        []
        if name == "baseline"
        else [read(f"{name}-{stage}-training.json") for stage in ["tiny", "full"]]
    )
    return {
        "model_id": "qwen3-1.7b-4bit"
        if name == "baseline"
        else f"grounding-qwen17-{name}-v1",
        "suite": "grounding-200-v1",
        "score": 1 - row["test"]["unsupported_answer_rate"],
        "passed": True,
        "date": "2026-10-22",
        "command": f".venv/bin/python scripts/grounding/evaluate.py {name}"
        + (
            f" --adapter runs/2026-10-22-grounding-200-v1/adapters/{name}"
            if train
            else ""
        ),
        "test": row["test"],
        "regression_accuracy": row["regression"],
        "bfcl_accuracy": row["bfcl"],
        "train_time": sum(r["elapsed_seconds"] for r in train),
        "eval_time": result["elapsed_seconds"] + bfcl["elapsed_seconds"],
        "latency_ms": statistics.median(r["seconds"] for r in result["rows"]) * 1000,
        "tokens_per_second": sum(r["generation_tokens"] for r in result["rows"])
        / sum(r["seconds"] for r in result["rows"]),
        "peak_rss_mb": max(r["peak_rss_bytes"] for r in [result, bfcl, *train])
        / 1024**2,
        "cost_usd": 0,
        "adapter_sha256": digest,
        "limits": "Narrow synthetic opaque-fact pilot;12 QA and20 BFCL controls do not establish broad non-regression.",
    }


def factory_inputs(contract, rows, digest):
    write(
        OUT / "config.json",
        {
            "run_id": OUT.name,
            "target": "context-grounded abstention",
            "candidate": {
                "method": "matched QLoRA evidence-perturbation inspired ablation",
                "training_command": ".venv/bin/python scripts/grounding/run.py",
            },
            "eval": {
                "primary": "correct abstention on20 evidence-absent TEST documents; lower unsupported-answer rate is better"
            },
            "contract": contract,
        },
    )
    write(
        OUT / "dataset.json",
        {
            "counts": {"train_rows": 96, "dev_rows": 24, "heldout_rows": 40},
            "sources": [
                {
                    "path": str((OUT / path).relative_to(ROOT)),
                    "sha256": digest,
                    "rows": len((OUT / path).read_text().splitlines()),
                }
                for path, digest in contract["files_sha256"].items()
            ],
            "processing": {
                "split": "source-document disjoint",
                "source": contract["source"],
            },
        },
    )
    for name in ["baseline", "candidate"]:
        key = "baseline" if name == "baseline" else "perturbation"
        write(
            OUT / f"eval-{name}.json",
            metrics(key, rows[key], digest if name == "candidate" else None),
        )


def write_slices(rows, comparisons):
    slices = {}
    for field in [
        "release code",
        "storage bay",
        "calibration token",
        "inspection label",
    ]:
        scores = []
        for key in ["baseline", "perturbation"]:
            selected = [
                r
                for r in rows[key]["raw"]["rows"]
                if r.get("split") == "test"
                and r.get("slice") == field
                and not r["present"]
            ]
            scores.append(statistics.mean(r["abstained"] for r in selected))
        slices[field] = {
            "baseline": scores[0],
            "candidate": scores[1],
            "delta": scores[1] - scores[0],
            "rows": 5,
        }
    write(OUT / "slice-metrics.json", {"overall": comparisons, "slices": slices})


def factory(contract, rows, comparisons, digest):
    factory_inputs(contract, rows, digest)
    write_slices(rows, comparisons)
    write(
        OUT / "decision.json",
        {
            "decision": "ship",
            "scope": "retain packaged local pilot only; no public release",
            "reason": "Frozen finite pilot gates pass against both base and ordinary SFT; retain the perturbation adapter locally.",
            "failure_reason_confidence": "not-applicable",
            "next_action": "No automatic scale-up or production integration; any broader claim needs a new real-document evaluation.",
            "evidence_sources": [
                "contract.json",
                "training-admission.json",
                "slice-metrics.json",
                "bfcl-frontier-result.json",
                "perturbation-result.json",
            ],
            "comparisons": comparisons,
            "ordinary_decision": "reject: no grounding gain and BFCL80% to0%",
        },
    )
    write(
        OUT / "artifact.json",
        {
            "artifact_id": "grounding-qwen17-perturbation-v1",
            "kind": "adapter",
            "base_model": contract["model"],
            "path": "package",
            "package_dir": "package",
            "lifecycle_manifest": "artifact-manifest.json",
            "shipped": True,
            "distribution": "owner-local-only; no public release",
            "weights_sha256": digest,
        },
    )
    (OUT / "trace_review.md").write_text(
        "# Trace Review\n\nThe five base/ordinary absent-context failures substitute unrelated batch references for missing inspection labels. Perturbation removes all five on this frozen20-document TEST. All20 evidence-present answers remain exact. BFCL baseline and perturbation have identical16 passing IDs; ordinary collapses to ABSTAIN on tool requests. No hidden TEST data enters training; source documents and actual target values are disjoint. TRAIN and TEST both use T-prefixed values; the earlier prefix-disjoint wording was incorrect. Every absent record excludes its paired decisive value. This is a synthetic contextual-grounding ablation, not reproduction of Merlin-Arthur or broad factual reliability.\n"
    )
    (OUT / "train.log").write_text(
        "\n".join(
            (OUT / "logs" / name).read_text()
            for name in [
                "01-train-ordinary.log",
                "02-train-perturbation.log",
                "03-train-perturbation.log",
            ]
        )
    )
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/factory/assemble_factory_run.py"),
            str(OUT),
            "--force",
            "--publish-check",
        ],
        check=True,
    )


def report():
    contract, rows = evidence()
    comparisons = {
        name: uncertainty(rows[name]["raw"], rows["perturbation"]["raw"])
        for name in ["baseline", "ordinary"]
    }
    candidate = rows["perturbation"]
    assert all(
        c["improvement"] >= 0.1 and c["paired_95_percentile_ci"][0] >= 0.1
        for c in comparisons.values()
    )
    assert (
        candidate["test"]["answerable_accuracy"]
        >= rows["baseline"]["test"]["answerable_accuracy"] - 0.02
    )
    assert candidate["regression"] >= rows["baseline"]["regression"] - 0.02
    assert candidate["bfcl"] >= rows["baseline"]["bfcl"] - 0.02
    digest = retain_package(contract)
    receipt = {
        "issue": 200,
        "date": "2026-10-22",
        "contract_sha256": hashlib.sha256(
            (OUT / "contract.json").read_bytes()
        ).hexdigest(),
        "model": contract["model"],
        "revision": contract["revision"],
        "runtime": {**contract["runtime"], "numpy": read("runtime-lock.json")["numpy"]},
        "counts": contract["counts"],
        "leakage": validate_rows(
            [
                json.loads(line)
                for split in ["train", "dev", "test"]
                for line in (OUT / f"{split}.jsonl").read_text().splitlines()
            ]
        ),
        "comparisons": comparisons,
        "systems": {
            name: metrics(name, row, digest if name == "perturbation" else None)
            for name, row in rows.items()
        },
        "decision": "retain local perturbation pilot; reject ordinary SFT; no public release",
        "weights_sha256": digest,
        "local_run": str(OUT.relative_to(ROOT)),
        "limits": contract["limitations"],
        "retained_evidence_move": "Raw files originally ran under evals/grounding-200-v1 and were reversibly moved byte-for-byte into ignored runs after execution.",
    }
    write(OUT / "package/receipts/qualification.json", receipt)
    write(ROOT / "evals/grounding-200-v1.json", receipt)
    factory(contract, rows, comparisons, digest)
    print(
        json.dumps(
            {
                "decision": receipt["decision"],
                "adapter_sha256": digest,
                "comparisons": comparisons,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    report()
