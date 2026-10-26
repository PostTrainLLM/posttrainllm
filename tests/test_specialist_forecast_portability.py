"""Portable prefix scans must retain upstream missing-observation semantics."""

import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("timestral")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "specialists"))
from forecast_browser import portable_operations


@pytest.mark.parametrize("length", [1, 7, 32, 65])
def test_portable_missing_values_and_restore(length):
    import timestral.forecaster as forecaster
    import timestral.model as model

    original_fill = forecaster.ffill_with_mask
    original_validity = model.compute_enc_key_validity
    values = torch.arange(length, dtype=torch.float32).repeat(4, 1)
    mask = torch.ones_like(values, dtype=torch.bool)
    mask[0] = False
    mask[1, ::3] = False
    mask[2, : length // 2] = False
    values = torch.where(mask, values, 0.0)
    expected = original_fill(values, mask)
    expected_validity = original_validity(mask, True)
    with pytest.raises(RuntimeError, match="restore"):
        with portable_operations():
            torch.testing.assert_close(
                forecaster.ffill_with_mask(values, mask), expected
            )
            assert torch.equal(
                model.compute_enc_key_validity(mask, True), expected_validity
            )
            assert torch.equal(model.compute_enc_key_validity(mask, False), mask)
            raise RuntimeError("restore")
    assert forecaster.ffill_with_mask is original_fill
    assert model.compute_enc_key_validity is original_validity


@pytest.mark.parametrize("covariates", ["none", "past", "known"])
@pytest.mark.parametrize("horizon", [1, 5, 9])
def test_complete_graph_matches_reference(covariates, horizon):
    from timestral.config import TimestralConfig
    from timestral.forecaster import TimestralForecaster
    from timestral.model import TimestralModel
    from forecast_browser import graph

    torch.set_num_threads(2)
    torch.manual_seed(210)
    config = TimestralConfig(
        patch_size=4,
        d_model=16,
        num_heads=1,
        mlp_hidden_dim=32,
        block_schedule=("time_variate", "time"),
        quantile_knots=(0.1, 0.5, 0.9),
        block_size=2,
        context_length=8,
    )
    forecaster = TimestralForecaster(TimestralModel(config))
    inputs = torch.arange(14, dtype=torch.float32).reshape(1, 2, 7) - 3
    mask = torch.ones_like(inputs, dtype=torch.bool)
    mask[..., 0] = False
    mask[..., 3:5] = False
    past = torch.sin(inputs[:, :1]) if covariates == "past" else None
    known = (
        torch.arange(7 + horizon, dtype=torch.float32).reshape(1, 1, -1) % 2
        if covariates == "known"
        else None
    )
    with torch.no_grad():
        expected = forecaster.forecast(
            inputs,
            horizon,
            observation_mask=mask,
            past_covariates=past,
            known_covariates=known,
        ).quantiles
        with portable_operations(forecaster.model):
            actual = graph(forecaster, horizon)(inputs, mask, past, known)
    torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-6)
    assert "predict_block" not in forecaster.model.__dict__


def test_boolean_selection_runs_in_onnx_runtime():
    import numpy as np

    onnx = pytest.importorskip("onnx")
    runtime = pytest.importorskip("onnxruntime")
    from forecast_browser import normalize_boolean_selection

    inputs = [
        onnx.helper.make_tensor_value_info(name, onnx.TensorProto.BOOL, shape)
        for name, shape in [("condition", [3, 1]), ("yes", [3, 2]), ("no", [1, 2])]
    ]
    output = onnx.helper.make_tensor_value_info("output", onnx.TensorProto.BOOL, [3, 2])
    model = onnx.helper.make_model(
        onnx.helper.make_graph(
            [onnx.helper.make_node("Where", ["condition", "yes", "no"], ["output"])],
            "boolean selection",
            inputs,
            [output],
        ),
        opset_imports=[onnx.helper.make_opsetid("", 18)],
        ir_version=10,
    )
    model = normalize_boolean_selection(model)
    options = runtime.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = runtime.InferenceSession(
        model.SerializeToString(),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    values = {
        "condition": np.array([[True], [False], [True]]),
        "yes": np.array([[True, False], [True, True], [False, True]]),
        "no": np.array([[False, False]]),
    }
    np.testing.assert_array_equal(
        session.run(None, values)[0],
        np.where(values["condition"], values["yes"], values["no"]),
    )


@pytest.mark.parametrize("horizon", [1, 9])
def test_categorical_preparation_matches_reference(horizon):
    from timestral.config import TimestralConfig
    from timestral.forecaster import TimestralForecaster
    from timestral.model import TimestralModel
    from forecast import inputs
    from forecast_browser import graph, prepare

    torch.set_num_threads(2)
    torch.manual_seed(210)
    forecaster = TimestralForecaster(
        TimestralModel(
            TimestralConfig(
                patch_size=4,
                d_model=16,
                num_heads=1,
                mlp_hidden_dim=32,
                block_schedule=("time_variate", "time"),
                quantile_knots=(0.1, 0.5, 0.9),
                block_size=2,
                context_length=8,
            )
        )
    )
    row = {
        "id": "categorical-parity",
        "context": [[None, -2, 3, None, 5, 6, 7], [3, 4, None, 6, 7, 8, 9]],
        "past_covariates": [[1, 2, None, 4, 5, 6, 7]],
        "known_covariates": [[0, 1, 0, 1, 0, 1, 0] + [1] * horizon],
        "categorical_past_covariates": [
            [2**30, 2**30 + 1, None, 2**30, 2**30 + 1, 2**30, 2**30]
        ],
        "categorical_known_covariates": [[0, 1, None, 0, 1, 0, 1] + [99] * horizon],
    }
    context, kwargs = inputs(row, horizon)
    with torch.no_grad():
        expected = forecaster.forecast(context, horizon, **kwargs).quantiles
        prepared = prepare(forecaster, row, horizon)
        with portable_operations(forecaster.model):
            actual = graph(forecaster, horizon)(*prepared)
    torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-6)


def test_export_writes_only_a_parity_checked_manifest(tmp_path):
    import json
    import hashlib

    pytest.importorskip("onnx")
    pytest.importorskip("onnxruntime")
    from timestral.config import TimestralConfig
    from timestral.forecaster import TimestralForecaster
    from timestral.model import TimestralModel
    from common import Budget
    from forecast_browser import export

    torch.set_num_threads(2)
    torch.manual_seed(210)
    forecaster = TimestralForecaster(
        TimestralModel(
            TimestralConfig(
                patch_size=4,
                d_model=16,
                num_heads=1,
                mlp_hidden_dim=32,
                block_schedule=("time_variate", "time"),
                quantile_knots=(0.1, 0.5, 0.9),
                block_size=2,
                context_length=8,
            )
        )
    )
    forecaster.source_identity = "a" * 64
    row = {
        "id": "categorical-parity",
        "context": [[1, None, 2, 3, 4, 5, 6]],
        "categorical_known_covariates": [[1, 2, 1, None, 1, 2, 1, 99]],
    }
    output = tmp_path / "artifact"
    receipt = export(forecaster, row, 1, output, Budget())
    assert json.loads((output / "manifest.json").read_text()) == receipt
    assert (
        receipt["model_sha256"]
        == hashlib.sha256((output / "model.onnx").read_bytes()).hexdigest()
    )
    assert receipt["input_names"] == ["context", "observed", "known"]
    assert receipt["shape"]["categorical_known_covariates"] == 1
    assert receipt["model_identity"] == forecaster.source_identity
    assert receipt["quality"] == "unqualified"
    assert len(receipt["probes"]) == 3
    assert all(probe["max_error"] < 0.002 for probe in receipt["probes"])
    with pytest.raises(FileExistsError):
        export(forecaster, row, 1, output, Budget())
