"""Terminal provenance, complete-world accounting and portable-weight gates."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "specialists"))
from common import Budget, digest, file_hash
from terminal_codec import Screen
from terminal_data import heldout_identities, identity, public_conditions


def episode(name="heldout"):
    before = Screen.custom("$ ", 1, 8)
    after = Screen.custom("$ a", 1, 8)
    return {
        "id": name,
        "family": "shell",
        "initial_screen": before.as_dict(),
        "frames": [{"event": {"keys": [97]}, "screen": after.as_dict()}],
    }


def test_terminal_overlap_cannot_be_hidden_by_renaming():
    original = episode("train")
    renamed = {
        **original,
        "id": "different-id",
        "world_id": "renamed-world",
        "seed": 4321,
        "family": "other-label",
    }
    model = SimpleNamespace(training_episode_identities=[identity(original)])
    with pytest.raises(ValueError, match="overlap"):
        heldout_identities(model, [renamed])
    with pytest.raises(ValueError, match="provenance"):
        heldout_identities(SimpleNamespace(), [original])


def test_terminal_reuses_no_hidden_world_between_splits():
    train = {**episode("train"), "world_id": "same-world"}
    test = {**episode("test"), "world_id": "same-world", "seed": 7}
    test["frames"][0]["event"] = {"keys": [98]}
    with pytest.raises(ValueError, match="world_id"):
        heldout_identities(
            SimpleNamespace(training_episode_identities=[identity(train)]), [test]
        )


def test_ceiling_requires_public_initial_conditions_and_pinned_image():
    item = episode()
    with pytest.raises(ValueError, match="world_conditions"):
        public_conditions(item)
    item["world_conditions"] = {
        "cwd": "/tmp",
        "initial_files": {},
        "programs": {},
        "environment": {},
    }
    assert public_conditions(item)["initial_files"] == {}
    item["source"] = {"kind": "real-docker-terminal"}
    with pytest.raises(ValueError, match="image_id"):
        public_conditions(item)


def test_high_cell_agreement_does_not_count_as_world_success(monkeypatch):
    pytest.importorskip("torch")
    import terminal_eval

    item = episode()
    before = Screen.from_dict(item["initial_screen"])

    class FakeSession:
        def __init__(self, model, initial):
            self.screen, self.context_resets = initial, 0

        def step(self, event, budget, parallel):
            self.screen = before
            return {"tokens": [1]}

    monkeypatch.setattr(terminal_eval, "Session", FakeSession)
    receipt = {
        "schema": "terminal-ceiling-v1",
        "valid": True,
        "data_sha256": digest([item]),
        "validator_sha256": file_hash(terminal_eval.__file__),
    }
    result = terminal_eval.evaluate(
        SimpleNamespace(training_episode_identities=[], source_identity="random"),
        [item],
        receipt,
        Budget(),
    )
    assert result["cell_fraction"] == 7 / 8
    assert result["complete_world_successes"] == 0
    assert result["families"]["shell"] == {"passed": 0, "total": 1}


def test_portable_weights_and_training_identity_survive_reload(tmp_path):
    torch = pytest.importorskip("torch")
    pytest.importorskip("safetensors")
    import terminal_model as tm
    from terminal_export import export, weights

    torch.set_num_threads(2)
    model = tm.new_model(
        {
            "vocab_size": 333,
            "context_length": 64,
            "d_model": 8,
            "n_heads": 2,
            "n_layers": 1,
            "d_mlp": 16,
            "dropout": 0.0,
        }
    )
    data = episode("train")
    path = tmp_path / "model"
    tm.train(model, tm.examples([data], 64), path, 1, Budget())
    loaded = tm.load(path)
    assert loaded.training_episode_identities == [identity(data)]
    with pytest.raises(ValueError, match="overlap"):
        heldout_identities(loaded, [data])
    mapped = weights(loaded)
    np.testing.assert_array_equal(
        mapped[6],
        loaded.transformer.layers[0].self_attn.in_proj_weight[:8].detach().numpy().T,
    )
    export(path, tmp_path / "f32.json")
    export(path, tmp_path / "f16.json", "f16")
    first = json.loads((tmp_path / "f32.json").read_text())
    second = json.loads((tmp_path / "f16.json").read_text())
    assert len(first["parity"]["probes"]) == 3
    assert first["training_episode_identities"] == [identity(data)]
    assert len(second["weights_base64"]) < len(first["weights_base64"])
    assert first["source"] == second["source"]


def test_finetune_does_not_erase_prior_training_provenance(tmp_path):
    pytest.importorskip("torch")
    pytest.importorskip("safetensors")
    import terminal_model as tm

    cfg = {
        "vocab_size": 333,
        "context_length": 64,
        "d_model": 8,
        "n_heads": 2,
        "n_layers": 1,
        "d_mlp": 16,
        "dropout": 0.0,
    }
    first, second = episode("first"), episode("second")
    second["seed"] = 123
    second["frames"][0] = {
        "event": {"keys": [98]},
        "screen": Screen.custom("$ b", 1, 8).as_dict(),
    }
    model = tm.new_model(cfg)
    tm.train(model, tm.examples([first], 64), tmp_path / "first", 1, Budget())
    tm.train(model, tm.examples([second], 64), tmp_path / "second", 1, Budget())
    assert {
        row["id"] for row in tm.load(tmp_path / "second").training_episode_identities
    } == {"first", "second"}
