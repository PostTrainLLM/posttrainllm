"""Native scores bind real subprocess requests and reject stale calibration."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "specialists"))
from common import Budget, digest, file_hash
from decision import calibrate, identity, metrics, prediction
from decision_native import base_files
from decision_native_score import NativeDecisionModel


class Tokenizer:
    def apply_chat_template(self, messages, **kwargs):
        return messages[0]["content"]

    def encode(self, text, **kwargs):
        return {"A": [32], "B": [33]}.get(text, [1, 2, 3])


def item(name="test"):
    return {
        "id": name,
        "question": name,
        "options": {"A": "yes", "B": "no"},
        "answer": "A",
    }


def fixture(tmp_path, change=""):
    base = tmp_path / "base"
    base.mkdir()
    (base / "config.json").write_text(json.dumps({"max_position_embeddings": 256}))
    (base / "model.safetensors").write_bytes(b"model-fixture")
    (base / "tokenizer.json").write_text("{}")
    binary = tmp_path / "posttrainllm"
    binary.write_text(
        f"#!{Path(sys.executable).resolve()}\n"
        "import json, sys\nfrom pathlib import Path\n"
        "probe = json.loads(Path(sys.argv[sys.argv.index('--probe') + 1]).read_text())\n"
        "value = {'schema': 'native-exact-token-logits-v1', 'tokens': len(probe['tokens']), 'labels': probe['labels'], 'logits': [3.0, 1.0]}\n"
        + change
        + "\nprint(json.dumps(value))\n"
    )
    binary.chmod(0o700)
    return base, binary


def model(base, binary, adapter=None, tokenizer=None):
    return NativeDecisionModel(
        binary, base, "a" * 40, adapter, tokenizer=tokenizer or Tokenizer()
    )


def test_native_subprocess_score_and_backend_specific_calibration(tmp_path):
    base, binary = fixture(tmp_path)
    native = model(base, binary)
    scores = [native.score(item(f"calibration-{i}")) for i in range(4)]
    primary = [native.score(item("primary"))]
    regression = [native.score(item("regression"))]
    fitted = calibrate(scores, primary + regression)
    assert metrics(primary, fitted)["accuracy"] == 1
    assert metrics(regression, fitted)["accuracy"] == 1
    assert scores[0]["logits"] == [3.0, 1.0]
    assert scores[0]["runtime_identity"]["source_revision_declared"] == "a" * 40
    assert scores[0]["runtime_identity"]["artifacts_observed"][
        "binary_sha256"
    ] == file_hash(binary)
    assert scores[0]["probe_sha256"] == digest(
        {"tokens": [1, 2, 3], "labels": [32, 33]}
    )
    with pytest.raises(ValueError, match="overlap"):
        metrics(scores, fitted)
    with pytest.raises(ValueError, match="another model"):
        prediction({**primary[0], "model_identity": "mlx-source"}, fitted)
    changed_revision = NativeDecisionModel(
        binary, base, "b" * 40, tokenizer=Tokenizer()
    )
    with pytest.raises(ValueError, match="another model"):
        prediction(changed_revision.score(item()), fitted)


@pytest.mark.parametrize("filename", ["model.safetensors", "tokenizer.json"])
def test_native_scoring_rejects_changed_artifacts(tmp_path, filename):
    base, binary = fixture(tmp_path)
    native = model(base, binary)
    (base / filename).write_bytes(b"changed")
    with pytest.raises(ValueError, match="artifacts changed"):
        native.score(item())


def test_native_scoring_rejects_change_during_the_actual_process(tmp_path):
    change = "Path(sys.argv[sys.argv.index('--hf') + 1], 'model.safetensors').write_bytes(b'changed')\n"
    base, binary = fixture(tmp_path, change)
    with pytest.raises(ValueError, match="artifacts changed"):
        model(base, binary).score(item())


def test_native_timeout_reaps_the_owned_process(tmp_path):
    pid_file = tmp_path / "native.pid"
    change = (
        f"import os, time\nPath({str(pid_file)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(30)\n"
    )
    base, binary = fixture(tmp_path, change)
    native = NativeDecisionModel(
        binary, base, "a" * 40, budget=Budget(3), tokenizer=Tokenizer()
    )
    with pytest.raises(subprocess.TimeoutExpired):
        native.score(item())
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


@pytest.mark.parametrize(
    "change",
    [
        "value['labels'] = [33, 32]",
        "value['tokens'] = 4",
        "value['logits'] = [1.0]",
        "value['logits'] = [float('nan'), 1.0]",
        "value['logits'] = [True, 1.0]",
    ],
)
def test_native_scoring_rejects_mismatched_response(tmp_path, change):
    base, binary = fixture(tmp_path, change)
    with pytest.raises(ValueError, match="response does not match"):
        model(base, binary).score(item())


def test_native_adapter_training_provenance_and_calibration_leakage(tmp_path):
    base, binary = fixture(tmp_path)
    adapter = tmp_path / "native.lora"
    adapter.write_bytes(b"adapter-fixture")
    sidecar = Path(str(adapter) + ".json")
    metadata = {
        "schema": "decision-native-adapter-v1",
        "base_files": base_files(base),
        "native_adapter_sha256": file_hash(adapter),
    }
    sidecar.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="training provenance"):
        model(base, binary, adapter)
    metadata["train_identities"] = [identity(item("train"))]
    sidecar.write_text(json.dumps(metadata))
    native = model(base, binary, adapter)
    trained = native.score(item("train"))
    assert trained["seen_in_training"] is True
    with pytest.raises(ValueError, match="training examples"):
        calibrate([trained])
    assert native.model_identity != model(base, binary).model_identity
    adapter.write_bytes(b"changed-adapter")
    with pytest.raises(ValueError, match="provenance mismatch"):
        model(base, binary, adapter)


def test_native_merged_base_preserves_training_exclusion(tmp_path):
    base, binary = fixture(tmp_path)
    (base / "specialist.json").write_text(
        json.dumps({"train_identities": [identity(item("train"))]})
    )
    native = model(base, binary)
    with pytest.raises(ValueError, match="training examples"):
        calibrate([native.score(item("train"))])


def test_native_identity_binds_standalone_chat_template(tmp_path):
    base, binary = fixture(tmp_path)
    old = model(base, binary)
    (base / "chat_template.jinja").write_text("changed prompt template")
    with pytest.raises(ValueError, match="artifacts changed"):
        old.score(item())
    assert model(base, binary).model_identity != old.model_identity


def test_native_identity_binds_colocated_metal_resources(tmp_path):
    base, binary = fixture(tmp_path)
    bundle = binary.parent / "mlx-swift_Cmlx.bundle"
    bundle.mkdir()
    shader = bundle / "default.metallib"
    shader.write_bytes(b"compiled-metal-fixture")
    native = model(base, binary)
    shader.write_bytes(b"changed-metal-fixture")
    with pytest.raises(ValueError, match="artifacts changed"):
        native.score(item())
    assert model(base, binary).model_identity != native.model_identity


def test_native_preflight_rejects_late_oversize_before_any_process(tmp_path):
    marker = tmp_path / "native-called"
    base, binary = fixture(tmp_path, f"Path({str(marker)!r}).write_text('called')")

    class LongTokenizer(Tokenizer):
        def encode(self, text, **kwargs):
            if "too-long" in text:
                return [1] * 257
            return super().encode(text, **kwargs)

    native = model(base, binary, tokenizer=LongTokenizer())
    with pytest.raises(ValueError, match="bounded exact token"):
        native.preflight([item("valid"), item("too-long")])
    assert not marker.exists()


def test_native_non_object_response_and_stderr_are_reported(tmp_path):
    base, binary = fixture(tmp_path, "value = []")
    with pytest.raises(ValueError, match="response does not match"):
        model(base, binary).score(item())
    binary.write_text(
        f"#!{Path(sys.executable).resolve()}\nimport sys\nsys.stderr.write('base identity mismatch')\nsys.exit(2)\n"
    )
    with pytest.raises(ValueError, match="base identity mismatch"):
        model(base, binary).score(item())


def test_native_full_checksum_is_rechecked_at_finish(tmp_path, monkeypatch):
    base, binary = fixture(tmp_path)
    native = model(base, binary)
    native.score(item())
    changed = {**native.artifacts, "binary_sha256": "changed"}
    monkeypatch.setattr(native, "snapshot", lambda: changed)
    with pytest.raises(ValueError, match="artifacts changed"):
        native.finish()


def test_native_cli_does_not_publish_scores_if_final_validation_fails(
    tmp_path, monkeypatch
):
    import decision
    import decision_native_score

    base, binary = fixture(tmp_path)
    native = model(base, binary)
    data, out = tmp_path / "data.jsonl", tmp_path / "scores.jsonl"
    data.write_text(json.dumps(item()) + "\n")
    changed = {**native.artifacts, "binary_sha256": "changed"}
    monkeypatch.setattr(native, "snapshot", lambda: changed)
    monkeypatch.setattr(
        decision_native_score, "NativeDecisionModel", lambda *args: native
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "decision.py",
            "score-native",
            "--binary",
            str(binary),
            "--base",
            str(base),
            "--source-revision",
            "a" * 40,
            "--data",
            str(data),
            "--out",
            str(out),
        ],
    )
    with pytest.raises(ValueError, match="artifacts changed"):
        decision.main()
    assert not out.exists()


@pytest.mark.parametrize(
    "encoding, message", [([1, 2], "exactly one token"), ([32], "collide")]
)
def test_native_option_token_contract(tmp_path, encoding, message):
    base, binary = fixture(tmp_path)

    class InvalidTokenizer(Tokenizer):
        def encode(self, text, **kwargs):
            return encoding

    with pytest.raises(ValueError, match=message):
        model(base, binary, tokenizer=InvalidTokenizer()).score(item())
