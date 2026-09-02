import argparse
import json
import pickle

from needle2_successor_decide import ARMS, best_safe_point, dev, tiny


def dump(path, value) -> None:
    path.write_text(json.dumps(value))


def test_best_safe_point_maximizes_safe_coverage() -> None:
    point = best_safe_point(
        {
            "risk_coverage": [
                {
                    "coverage": 0.2,
                    "precision": 1.0,
                    "threshold": 0.9,
                    "out_of_scope_false_actions": 0,
                    "destructive_bypasses": 0,
                },
                {
                    "coverage": 0.5,
                    "precision": 0.8,
                    "threshold": 0.7,
                    "out_of_scope_false_actions": 0,
                    "destructive_bypasses": 0,
                },
                {
                    "coverage": 0.8,
                    "precision": 0.6,
                    "threshold": 0.2,
                    "out_of_scope_false_actions": 1,
                    "destructive_bypasses": 0,
                },
            ]
        }
    )
    assert point["coverage"] == 0.5


def test_tiny_gate_checks_loss_and_exactness(tmp_path) -> None:
    models = []
    for arm in ARMS:
        adapter = tmp_path / f"{arm}.pkl"
        with adapter.open("wb") as handle:
            pickle.dump({"seed": 1, "final_loss": 0.01}, handle)
        models.append(
            {"model_id": arm, "adapter": str(adapter), "tool_selection_exact": 1}
        )
    evaluation = tmp_path / "tiny.json"
    output = tmp_path / "out.json"
    dump(evaluation, {"models": models})
    assert tiny(argparse.Namespace(eval=[evaluation], output=output)) == 0
    assert json.loads(output.read_text())["passed"] is True


def test_dev_gate_selects_only_safe_improving_arms(tmp_path) -> None:
    models = []
    for arm_index, arm in enumerate(ARMS):
        for seed in (1, 2, 3):
            models.append(
                {
                    "model_id": f"{arm}-seed-{seed}",
                    "adapter": f"{arm}-{seed}.pkl",
                    "tool_selection_exact": 0.6 if arm_index == 3 else 0.4,
                    "out_of_scope_false_actions": 0 if arm_index == 3 else 1,
                    "destructive_bypasses": 0,
                    "risk_coverage": [
                        {
                            "coverage": 0.4,
                            "precision": 0.9,
                            "threshold": 0.8,
                            "out_of_scope_false_actions": 0,
                            "destructive_bypasses": 0,
                        }
                    ],
                }
            )
    evaluation = tmp_path / "dev.json"
    incumbent = tmp_path / "incumbent.json"
    output = tmp_path / "selection.json"
    dump(evaluation, {"models": models})
    dump(
        incumbent,
        {"result": {"tool_selection_exact": {"rate": 0.3404255319}}},
    )
    assert (
        dev(argparse.Namespace(eval=evaluation, incumbent=incumbent, output=output))
        == 0
    )
    result = json.loads(output.read_text())
    assert result["selected_arm"] == "distractor-safety"
    assert result["selected_model"] == "distractor-safety-seed-1"
    assert result["sealed_unlocked"] is True
