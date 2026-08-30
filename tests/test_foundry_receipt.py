#!/usr/bin/env python3
"""Unit tests proving private payloads cannot enter Foundry receipts.

Covers the spec requirement (automate-posttrainllm, task 3.3):
  "Add tests proving private datasets/prompts/checkpoints/outputs cannot
  enter fleet reports."

These tests exercise ``scripts.foundry_receipt.sanitize_payload`` and
``scripts.check_foundry_receipt.validate`` directly, plus an end-to-end
build_receipt over a fixture run folder containing private fragments.

Run: ``python3 tests/test_foundry_receipt.py``
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


receipt_mod = _load_module("foundry_receipt", ROOT / "scripts/factory/foundry_receipt.py")
check_mod = _load_module("check_foundry_receipt", ROOT / "scripts/factory/check_foundry_receipt.py")


# ---------------------------------------------------------------------------
# sanitize_payload unit tests
# ---------------------------------------------------------------------------


def test_sanitize_drops_denylisted_keys():
    payload = {
        "ok": 1,
        "prompt": "PRIVATE PROMPT",
        "completion": "PRIVATE COMPLETION",
        "gold": "PRIVATE GOLD",
        "prediction": "PRIVATE PREDICTION",
        "checkpoint": b"BYTES",
        "api_key": "sk-xxx",
        "nested": {"prompt": "leak", "safe": 2},
        "items": [{"weights": "leak"}, {"ok": 3}],
    }
    out = receipt_mod.sanitize_payload(payload)
    assert "prompt" not in out
    assert "completion" not in out
    assert "gold" not in out
    assert "prediction" not in out
    assert "checkpoint" not in out
    assert "api_key" not in out
    assert "prompt" not in out["nested"]
    assert "weights" not in out["items"][0]
    assert out["ok"] == 1
    assert out["nested"]["safe"] == 2
    assert out["items"][1]["ok"] == 3
    print("  ok: sanitize_payload drops all denylisted keys")


def test_sanitize_redacts_overlong_strings():
    long_str = "x" * 5000
    out = receipt_mod.sanitize_payload({"big": long_str, "ok": "short"})
    assert out["ok"] == "short"
    assert isinstance(out["big"], str)
    assert out["big"].startswith("<redacted:overlong-string:")
    print("  ok: sanitize_payload redacts overlong strings")


def test_sanitize_preserves_legitimate_metadata():
    payload = {
        "run_id": "2026-07-19-test",
        "target": "test-target",
        "method": "sft-lora",
        "score": 0.95,
        "dataset_sha256": "abc123",
        "dataset_rows": 100,
        "storage": {"primary": "huggingface_hub", "status": "weights-published"},
    }
    out = receipt_mod.sanitize_payload(payload)
    assert out == payload
    print("  ok: sanitize_payload preserves legitimate metadata")


# ---------------------------------------------------------------------------
# check_foundry_receipt.validate tests
# ---------------------------------------------------------------------------


def _valid_receipt_base() -> dict:
    return {
        "schema_version": 1,
        "project": "posttrainllm",
        "generated_at": "2026-07-19T00:00:00+00:00",
        "source_revision": {"commit": "abc123", "branch": "main", "dirty": False},
        "ci": {"status": "not-applicable"},
        "public_site": {"build": "pass", "live": "pass", "indexing": "pass", "freshness_window_days": 14},
        "playground": {"bundle": "pass", "activation_event": "playground_loaded", "failure_event": "foundry_page_crash"},
        "artifacts": [],
        "local_runs": [],
        "nightly": [],
        "publication_authority": "manual",
        "accepted_exceptions": [],
        "blocked": [],
    }


def test_validator_accepts_clean_receipt():
    errors: list[str] = []
    check_mod.validate(_valid_receipt_base(), 500, errors)
    assert not errors, f"unexpected errors: {errors}"
    print("  ok: validator accepts a clean receipt")


def test_validator_rejects_denylisted_field():
    for bad_field in ("prompt", "completion", "checkpoint", "api_key", "weights"):
        r = _valid_receipt_base()
        r[bad_field] = "PRIVATE"
        errors: list[str] = []
        check_mod.validate(r, 500, errors)
        assert any("private field" in e for e in errors), f"{bad_field} not rejected: {errors}"
    print("  ok: validator rejects every denylisted field")


def test_validator_rejects_oversize_string():
    r = _valid_receipt_base()
    r["public_site"]["build"] = "x" * 5000
    errors: list[str] = []
    check_mod.validate(r, 500, errors)
    assert any("oversize string" in e for e in errors), errors
    print("  ok: validator rejects oversize strings")


def test_validator_rejects_auto_publication_authority():
    r = _valid_receipt_base()
    r["publication_authority"] = "automatic"
    errors: list[str] = []
    check_mod.validate(r, 500, errors)
    assert any("publication_authority" in e for e in errors), errors
    print("  ok: validator rejects non-manual publication_authority")


def test_validator_rejects_local_run_without_pending_approval():
    r = _valid_receipt_base()
    r["local_runs"] = [{"run_id": "x", "publication": "published", "source_revision": "abc"}]
    errors: list[str] = []
    check_mod.validate(r, 500, errors)
    assert any("pending-approval" in e for e in errors), errors
    print("  ok: validator rejects local_run without pending-approval")


def test_validator_rejects_quality_claim_missing_provenance():
    r = _valid_receipt_base()
    r["artifacts"] = [
        {
            "id": "x",
            "quality_claims": [
                {"metric": "m", "source_revision": None, "model": "m",
                 "eval_config": "c", "dataset_version": "v", "observed_at": "t",
                 "artifact_location": "loc", "retention": "r"}
            ],
        }
    ]
    errors: list[str] = []
    check_mod.validate(r, 500, errors)
    assert any("source_revision" in e for e in errors), errors
    print("  ok: validator rejects quality_claim with missing provenance")


# ---------------------------------------------------------------------------
# End-to-end: build_receipt over a fixture run with private fragments
# ---------------------------------------------------------------------------


def test_build_receipt_sanitizes_private_run_folder():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        runs = tmp / "runs"
        run = runs / "2026-07-19-fixture-private"
        run.mkdir(parents=True)
        train = tmp / "train.jsonl"
        train.write_text("\n".join(f'{{"q":"row {i}"}}' for i in range(10)) + "\n")
        dev = tmp / "dev.jsonl"
        dev.write_text("\n".join(f'{{"q":"dev {i}"}}' for i in range(3)) + "\n")

        def w(name, obj):
            (run / name).write_text(json.dumps(obj, indent=2))

        w("config.json", {
            "run_id": "2026-07-19-fixture-private", "target": "fixture-private",
            "owner_goal": "x", "base_model": {"id": "fb", "revision": "a", "precision": "bf16"},
            "candidate": {"method": "sft-lora", "adapter_format": "tgla", "training_command": "x"},
            "eval": {"primary": "fg", "regression": "fb", "threshold": {"primary_min": 0.9, "breadth_drop_max_pp": 3}},
        })
        w("dataset.json", {
            "sources": [{"kind": "sft", "path": str(train), "rows": 10},
                        {"kind": "heldout", "path": str(dev), "rows": 3}],
            "processing": {"dedupe": True, "quality_filter": True, "heldout_split": "locked"},
            "counts": {"train_rows": 10, "heldout_rows": 3, "dropped_rows": 0},
        })
        w("eval-baseline.json", {"model_id": "fb", "command": "x", "suite": "fg", "score": 0.5, "passed": False, "date": "2026-07-19"})
        w("eval-candidate.json", {"model_id": "fc", "command": "x", "suite": "fg", "score": 0.9, "passed": True, "date": "2026-07-19"})
        w("decision.json", {"decision": "retry-training", "reason": "x", "failure_reason": "x", "failure_reason_confidence": "inferred", "lesson": "x", "next_action": "x", "evidence_sources": ["report.md"], "blocked_by": ["x"]})
        w("slice-metrics.json", {"overall": {"rows": 10}, "slices": {"easy": {"rows": 5, "baseline": 0.8, "candidate": 0.95, "delta": 0.15, "pass": True}}})
        (run / "trace_review.md").write_text("# Trace review (fixture)\n")
        # Minimal provenance so the receipt can read source_revision + dataset hash.
        w("provenance.json", {
            "schema_version": 1, "renderer": "test-fixture",
            "git": {"commit": "abc123", "branch": "main", "dirty": False},
            "commands": {"baseline": "x", "candidate": "x", "training": "x"},
            "datasets": [{"path": str(train), "rows": 10, "sha256": "deadbeef"}],
        })
        # Private fragments
        w("prompt.json", {"prompt": "PRIVATE PROMPT TEXT"})
        w("completion.json", {"completion": "PRIVATE COMPLETION TEXT"})
        w("checkpoint.json", {"checkpoint_bytes": "PRIVATE CHECKPOINT", "weights": "PRIVATE WEIGHTS"})
        (run / "train.log").write_text("PRIVATE LOG WITH prompt gold completion prediction\n")

        receipt = receipt_mod.build_receipt(include_ci=False, runs_dir=runs)
        blob = json.dumps(receipt)

        # No private fixture text leaks
        for needle in ("PRIVATE PROMPT", "PRIVATE COMPLETION", "PRIVATE CHECKPOINT", "PRIVATE WEIGHTS", "PRIVATE LOG"):
            assert needle not in blob, f"private text leaked: {needle}"

        # No denylisted keys
        def find_bad(v, path=""):
            if isinstance(v, dict):
                for k, val in v.items():
                    kl = str(k).lower()
                    if any(bad in kl for bad in receipt_mod.DENYLIST_FIELDS):
                        return f"{path}.{k}"
                    r = find_bad(val, f"{path}.{k}")
                    if r:
                        return r
            elif isinstance(v, list):
                for i, val in enumerate(v):
                    r = find_bad(val, f"{path}[{i}]")
                    if r:
                        return r
            return None
        assert find_bad(receipt) is None, f"denylisted key leaked: {find_bad(receipt)}"

        # The local run IS represented (metadata only)
        assert len(receipt["local_runs"]) == 1
        lr = receipt["local_runs"][0]
        assert lr["run_id"] == "2026-07-19-fixture-private"
        assert lr["publication"] == "pending-approval"
        assert lr["decision"] == "retry-training"
        assert lr["baseline_score"] == 0.5
        assert lr["candidate_score"] == 0.9
        assert lr["lifecycle"] is None  # legacy folders remain receipt-compatible

        # Validator accepts it
        errors: list[str] = []
        check_mod.validate(receipt, len(blob.encode("utf-8")), errors)
        assert not errors, f"validator rejected clean sanitized receipt: {errors}"

    print("  ok: build_receipt sanitizes a private run folder end-to-end")


def test_active_lifecycle_receipt_is_read_only_and_sanitized():
    with tempfile.TemporaryDirectory() as tmp:
        runs = Path(tmp) / "runs"
        active = runs / "active"
        active.mkdir(parents=True)
        (active / "config.json").write_text(json.dumps({
            "run_id": "active", "target": "fixture",
            "candidate": {"method": "metadata-only"},
        }))
        active_status = {
            "schema_version": 1,
            "run_id": "active",
            "revision": 3,
            "phase": "training",
            "updated_at": "2026-07-20T00:00:00+00:00",
            "last_transition": {
                "source": "fixture",
                "command": "factory-run transition",
                "reason": None,
            },
            "failure": None,
            "imported": False,
            "import_evidence": [],
        }
        (active / "run-status.json").write_text(json.dumps(active_status))

        failed = runs / "failed"
        failed.mkdir()
        (failed / "config.json").write_text(json.dumps({
            "run_id": "failed", "target": "fixture",
            "candidate": {"method": "metadata-only"},
        }))
        failed_status = {
            **active_status,
            "run_id": "failed",
            "phase": "failed",
            "failure": {
                "code": "should-not-project",
                "summary": "PRIVATE PROMPT must never enter a receipt",
            },
        }
        (failed / "run-status.json").write_text(json.dumps(failed_status))

        receipt = receipt_mod.build_receipt(include_ci=False, runs_dir=runs)
        assert len(receipt["local_runs"]) == 2
        by_id = {run["run_id"]: run for run in receipt["local_runs"]}
        assert by_id["active"]["decision"] is None
        assert by_id["active"]["source_revision"] is None
        assert by_id["active"]["publish_check"] == "not-applicable"
        assert by_id["active"]["lifecycle"]["phase"] == "training"
        assert by_id["failed"]["lifecycle"]["failure"]["summary"] == "<redacted:unsafe-summary>"
        assert "PRIVATE PROMPT" not in json.dumps(receipt)
        errors: list[str] = []
        check_mod.validate(receipt, len(json.dumps(receipt).encode()), errors)
        assert not errors, errors
    print("  ok: active lifecycle receipt stays read-only and sanitizes failure metadata")


def test_build_receipt_blocks_quality_claims_without_source_revision():
    """A registry pkg whose eval_report lacks source_revision must record a
    blocked gap and emit zero quality_claims (per the spec scenario:
    'Evidence inputs are missing → cannot update a public quality claim')."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        # Monkeypatch ROOT so build_receipt reads our fixture registry.
        orig_root = receipt_mod.ROOT
        receipt_mod.ROOT = tmp
        try:
            (tmp / "specialists").mkdir()
            (tmp / "specialists/registry.json").write_text(json.dumps({
                "version": 1, "updated": "2026-07-19",
                "packages": [{
                    "id": "test-pkg", "kind": "mac-safetensors-hf",
                    "package_path": "specialists/test-pkg",
                    "artifact_path": "hf://models/posttrainllm/test-pkg",
                    "storage": {"primary": "huggingface_hub", "repo_id": "posttrainllm/test-pkg", "status": "weights-published"},
                    "base": "Qwen/Qwen3-4B-Instruct-2507", "status": "release-ready-weights",
                    "model_card": "specialists/test-pkg/model_card.md",
                    "eval_report": "specialists/test-pkg/eval_report.json",
                    "prompt": "specialists/test-pkg/prompt.md",
                    "lock": "specialists/test-pkg/tinygpt.lock.json",
                }],
            }))
            pkg_dir = tmp / "specialists/test-pkg"
            pkg_dir.mkdir()
            (pkg_dir / "eval_report.json").write_text(json.dumps({
                "id": "test-pkg", "updated": "2026-07-19",
                "artifact": "hf://models/posttrainllm/test-pkg",
                "base": "Qwen/Qwen3-4B-Instruct-2507", "precision": "bf16",
                # NOTE: no source_revision field
                "scores": [{"suite": "file_ops_hard_gate", "n": 12, "stock_4b": 0.58, "distilled_4b": 1.0, "source": "docs/x.md"}],
                "verdict": "x", "caveats": [],
            }))
            (pkg_dir / "tinygpt.lock.json").write_text("{}")

            receipt = receipt_mod.build_receipt(include_ci=False, runs_dir=None)
            art = receipt["artifacts"][0]
            assert art["id"] == "test-pkg"
            assert art["quality_claims"] == [], f"expected no claims, got {art['quality_claims']}"
            assert any("test-pkg" in b and "provenance-complete" in b for b in receipt["blocked"]), receipt["blocked"]
        finally:
            receipt_mod.ROOT = orig_root
    print("  ok: build_receipt blocks quality_claims missing source_revision")


def main() -> int:
    tests = [
        test_sanitize_drops_denylisted_keys,
        test_sanitize_redacts_overlong_strings,
        test_sanitize_preserves_legitimate_metadata,
        test_validator_accepts_clean_receipt,
        test_validator_rejects_denylisted_field,
        test_validator_rejects_oversize_string,
        test_validator_rejects_auto_publication_authority,
        test_validator_rejects_local_run_without_pending_approval,
        test_validator_rejects_quality_claim_missing_provenance,
        test_build_receipt_sanitizes_private_run_folder,
        test_active_lifecycle_receipt_is_read_only_and_sanitized,
        test_build_receipt_blocks_quality_claims_without_source_revision,
    ]
    failures = 0
    for t in tests:
        print(f"-- {t.__name__}")
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL: {e}")
            failures += 1
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            failures += 1
    print()
    if failures:
        print(f"{failures}/{len(tests)} tests failed")
        return 1
    print(f"all {len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
