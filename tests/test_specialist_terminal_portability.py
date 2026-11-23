"""Terminal provenance, complete-world accounting and portable-weight gates."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "specialists"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


def test_terminal_ceiling_uses_typed_exact_public_contract():
    pytest.importorskip("torch")
    import terminal_eval

    item = episode()
    item["world_conditions"] = {
        "cwd": "/tmp",
        "initial_files": {},
        "programs": {"shell": "/bin/sh"},
        "environment": {"TERM": "xterm"},
    }
    item["source"] = {"timing": "after 60ms quiescence"}
    request = terminal_eval.ceiling_request([item])
    item_schema = terminal_eval.terminal_answer_schema([item])["properties"][
        "answers"
    ]["items"]
    screen_schema = item_schema["properties"]["screens"]["items"]
    assert item_schema["properties"]["id"]["enum"] == [item["id"]]
    assert screen_schema["type"] == "object"
    assert screen_schema["properties"]["lines"]["type"] == "array"
    assert "answer" not in item_schema["properties"]
    assert request[0]["sampling_policy"] == "after 60ms quiescence"
    assert "frames" not in request[0]
    assert "screen" not in request[0]["events"][0]

    correct = [
        {
            "id": item["id"],
            "screens": [frame["screen"] for frame in item["frames"]],
        }
    ]
    assert terminal_eval.terminal_answers_match([item], correct)
    assert not terminal_eval.terminal_answers_match(
        [item], [{"id": item["id"], "answer": "prose"}]
    )
    assert not terminal_eval.terminal_answers_match(
        [item], [{"id": "wrong", "screens": correct[0]["screens"]}]
    )
    assert not terminal_eval.terminal_answers_match(
        [item], [{"id": item["id"], "screens": []}]
    )
    wrong_dimensions = json.loads(json.dumps(correct))
    wrong_dimensions[0]["screens"][0]["lines"][0] = "short"
    assert not terminal_eval.terminal_answers_match([item], wrong_dimensions)
    wrong_screen = json.loads(json.dumps(correct))
    wrong_screen[0]["screens"][0]["cursor_col"] += 1
    assert not terminal_eval.terminal_answers_match([item], wrong_screen)


def test_terminal_ceiling_is_bounded_and_uses_v2_receipt(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    import terminal_eval

    item = episode()
    item["world_conditions"] = {
        "cwd": "/tmp",
        "initial_files": {},
        "programs": {"shell": "/bin/sh"},
        "environment": {"TERM": "xterm"},
    }
    item["source"] = {"timing": "after 60ms quiescence"}
    oversized = json.loads(json.dumps(item))
    oversized["initial_screen"] = Screen.custom("$ ", 8, 48).as_dict()
    oversized["frames"] = [
        {"event": {"wait_ms": 1}, "screen": Screen.custom("$ ", 8, 48).as_dict()}
        for _ in range(131)
    ]
    with pytest.raises(ValueError, match="50000 screen-cell budget"):
        terminal_eval.ceiling_request([oversized])

    expected = [{"id": item["id"], "screens": [f["screen"] for f in item["frames"]]}]

    def fake_frontier(schema, out, prompt, timeout):
        assert timeout == 180
        saved_schema = json.loads(Path(schema).read_text())
        screen_schema = saved_schema["properties"]["answers"]["items"]["properties"][
            "screens"
        ]["items"]
        assert screen_schema["type"] == "object"
        assert "answer" not in saved_schema["properties"]["answers"]["items"][
            "properties"
        ]
        assert "frames" not in prompt
        (Path(out) / "answers.json").write_text(json.dumps({"answers": expected}))
        return expected, ["agent_message"]

    monkeypatch.setattr(terminal_eval, "frontier_answers", fake_frontier)
    out = tmp_path / "ceiling"
    terminal_eval.ceiling([item], out)
    receipt = json.loads((out / "ceiling.json").read_text())
    assert receipt["schema"] == "terminal-ceiling-v2"
    assert receipt["valid"] is True
    assert receipt["frame_count"] == 1
    assert receipt["timeout_seconds"] == 180
    terminal_eval.validate_ceiling([item], receipt)


def test_frontier_answers_honors_timeout(monkeypatch, tmp_path):
    import subprocess
    from types import SimpleNamespace

    import common
    import scripts.factory.frontier_cli as frontier_cli

    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["timeout"] = kwargs["timeout"]
        (tmp_path / "answers.json").write_text('{"answers":[]}')
        return SimpleNamespace(
            returncode=0, stdout='{"item":{"type":"agent_message"}}\n'
        )

    monkeypatch.setattr(frontier_cli, "codex_command", lambda *args, **kwargs: ["codex"])
    monkeypatch.setattr(subprocess, "run", fake_run)
    answers, item_types = common.frontier_answers(
        tmp_path / "schema.json", tmp_path, "small prompt", timeout=180
    )
    assert answers == []
    assert item_types == ["agent_message"]
    assert seen["timeout"] == 180


def test_frontier_timeout_is_reported_as_infrastructure_failure(monkeypatch, tmp_path):
    import subprocess

    import common
    import scripts.factory.frontier_cli as frontier_cli

    monkeypatch.setattr(frontier_cli, "codex_command", lambda *args, **kwargs: ["codex"])

    def timed_out(*args, **kwargs):
        raise subprocess.TimeoutExpired("codex", kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timed_out)
    with pytest.raises(RuntimeError, match="frontier infrastructure failure"):
        common.frontier_answers(
            tmp_path / "schema.json", tmp_path, "small prompt", timeout=180
        )


def test_current_synthetic_shell_and_memory_recipes_fit_ceiling_budget():
    pytest.importorskip("torch")
    import terminal_eval
    from terminal_record import synthetic_recipe

    item = episode()
    item["world_conditions"] = {
        "cwd": "/tmp",
        "initial_files": {},
        "programs": {"shell": "/bin/sh"},
        "environment": {"TERM": "xterm"},
    }
    item["source"] = {"timing": "quiescence"}
    screen = Screen.custom("$ ", 8, 48).as_dict()
    item["initial_screen"] = Screen.custom("$ ", 8, 48).as_dict()
    for memory, expected_cells in ((False, 25728), (True, 48768)):
        recipe = synthetic_recipe(memory=memory)
        item["frames"] = [
            {"event": event, "screen": screen} for event in recipe["events"]
        ]
        request = terminal_eval.ceiling_request([item])
        cells = (
            len(request[0]["events"])
            * len(item["initial_screen"]["lines"])
            * len(item["initial_screen"]["lines"][0])
        )
        assert len(recipe["events"]) == (67 if not memory else 127)
        assert cells == expected_cells


def test_invalid_receipt_fails_before_episode_request_validation():
    pytest.importorskip("torch")
    import terminal_eval

    item = episode()
    with pytest.raises(ValueError, match="missing, failed, stale or mismatched"):
        terminal_eval.validate_ceiling([item], {"schema": "terminal-ceiling-v1"})


def test_terminal_ceiling_v1_receipt_is_invalidated():
    pytest.importorskip("torch")
    import terminal_eval

    item = episode()
    item["world_conditions"] = {
        "cwd": "/tmp",
        "initial_files": {},
        "programs": {"shell": "/bin/sh"},
        "environment": {"TERM": "xterm"},
    }
    item["source"] = {"timing": "after 60ms quiescence"}
    with pytest.raises(ValueError, match="terminal ceiling"):
        terminal_eval.validate_ceiling(
            [item],
            {
                "schema": "terminal-ceiling-v1",
                "valid": True,
                "data_sha256": digest([item]),
                "validator_sha256": file_hash(terminal_eval.__file__),
            },
        )


def test_high_cell_agreement_does_not_count_as_world_success(monkeypatch):
    pytest.importorskip("torch")
    import terminal_eval

    item = episode()
    item["world_conditions"] = {
        "cwd": "/tmp",
        "initial_files": {},
        "programs": {"shell": "/bin/sh"},
        "environment": {"TERM": "xterm"},
    }
    item["source"] = {"timing": "after 60ms quiescence"}
    before = Screen.from_dict(item["initial_screen"])

    class FakeSession:
        def __init__(self, model, initial):
            self.screen, self.context_resets = initial, 0

        def step(self, event, budget, parallel):
            self.screen = before
            return {"tokens": [1]}

    monkeypatch.setattr(terminal_eval, "Session", FakeSession)
    receipt = {
        "schema": terminal_eval.TERMINAL_CEILING_SCHEMA,
        "valid": True,
        "data_sha256": digest([item]),
        "request_sha256": digest(terminal_eval.ceiling_request([item])),
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
