"""Numerical, leakage and screen-state gates for Issue #210 (no quality claims)."""

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "specialists"))

import numpy as np
import pytest

import decision
import forecast
import terminal_codec as codec
from common import Budget, softmax


def record(index, logits=(8.0, 0.0), answer="A"):
    return {
        "id": str(index),
        "identity": str(index),
        "model_identity": "fixed-model",
        "labels": ["A", "B"],
        "logits": list(logits),
        "answer": answer,
    }


def test_single_token_labels_fail_closed():
    class Tokenizer:
        def encode(self, value, **kwargs):
            return [1, 2] if len(value) > 1 else [ord(value)]

    assert decision.option_ids(["A", "B"], Tokenizer()) == [65, 66]
    with pytest.raises(ValueError, match="exactly one"):
        decision.option_ids(["Yes", "No"], Tokenizer())


def test_calibration_has_analytic_optimum_and_preserves_ranking():
    # 75% correct with logit gap 2: calibrated p=.75, T=2/log(3).
    rows = [record(i, (2, 0), "B" if i % 4 == 0 else "A") for i in range(40)]
    fit = decision.calibrate(rows)
    assert fit["temperature"] == pytest.approx(2 / np.log(3), rel=1e-5)
    assert fit["nll_after"] < fit["nll_before"]
    assert decision.prediction(rows[0], fit)["label"] == "A"
    assert sum(
        decision.prediction(rows[0], fit)["probabilities"].values()
    ) == pytest.approx(1)


def test_calibration_leakage_model_binding_and_abstention():
    rows = [record(i) for i in range(4)]
    with pytest.raises(ValueError, match="overlaps"):
        decision.calibrate(rows, [rows[0]])
    fit = decision.calibrate(rows)
    with pytest.raises(ValueError, match="overlap"):
        decision.metrics(rows, fit)
    other = record(20, (0, 0))
    assert decision.prediction(other, fit, 0.9)["label"] is None
    assert decision.metrics([other], fit, 0.9)["selective_accuracy"] is None
    other["model_identity"] = "different"
    with pytest.raises(ValueError, match="another model"):
        decision.prediction(other, fit)


def test_calibration_rejects_nonfinite_duplicate_or_missing_gold():
    for bad in (
        [record(0, (np.nan, 0))],
        [record(0), record(0)],
        [record(0, answer="C")],
    ):
        with pytest.raises(ValueError):
            decision.calibrate(bad)
    with pytest.raises(ValueError):
        softmax([0, 1], 0)


def test_question_permutation_does_not_hide_split_leakage():
    a = {"question": "Pick a color", "options": {"A": "blue", "B": "red"}}
    b = {"question": "Pick a color", "options": {"B": "blue", "A": "red"}}
    with pytest.raises(ValueError, match="leakage"):
        decision.validate_splits({"train": [a], "test": [b]})


def test_decision_metrics_known_result():
    rows = [record(1, (0, 0), "A"), record(2, (0, 0), "B")]
    result = decision.metrics(rows)
    assert result["accuracy"] == 0.5
    assert result["brier"] == 0.5
    assert result["nll"] == pytest.approx(np.log(2))
    assert result["ece_10_bins"] == 0


def test_forecast_inputs_missing_and_future_covariate_contract():
    row = {"context": [[1, None, 3]], "known_covariates": [[1, 0, 1, 0, 1]]}
    context, kwargs = forecast.inputs(row, 2)
    assert np.isnan(context[0, 0, 1])
    assert kwargs["known_covariates"].shape == (1, 1, 5)
    row["known_covariates"][0].pop()
    with pytest.raises(ValueError, match="exactly 5"):
        forecast.inputs(row, 2)
    with pytest.raises(ValueError):
        forecast.inputs({"context": [[None, None]]}, 2)
    with pytest.raises(ValueError):
        forecast.inputs({"context": [[1, 2]], "observation_mask": [[0, 1]]}, 2)


@pytest.fixture
def tiny_forecaster():
    torch = pytest.importorskip("torch")
    pytest.importorskip("timestral")
    from timestral.config import TimestralConfig
    from timestral.model import TimestralModel
    from timestral import TimestralForecaster

    torch.set_num_threads(2)
    torch.manual_seed(7)
    config = TimestralConfig(
        patch_size=4,
        d_model=16,
        num_heads=2,
        mlp_hidden_dim=32,
        block_schedule=("time_variate", "time"),
        quantile_knots=(0.1, 0.5, 0.9),
        block_size=4,
        context_length=64,
    )
    return TimestralForecaster(TimestralModel(config))


def test_pinball_numerical_oracle_and_gradients():
    torch = pytest.importorskip("torch")
    pred = torch.tensor([[[0.0, 2.0, 4.0]]], requires_grad=True)
    target = torch.tensor([[3.0]])
    loss = forecast.pinball(pred, target, [0.1, 0.5, 0.9])
    assert loss.item() == pytest.approx((0.3 + 0.5 + 0.1) / 3)
    loss.backward()
    assert torch.isfinite(pred.grad).all()
    assert pred.grad[0, 0, 0] < 0 and pred.grad[0, 0, 2] > 0


def test_forecast_real_architecture_quantiles_and_roundtrip(tiny_forecaster, tmp_path):
    row = {
        "id": "test",
        "context": [[1, 2, None, 4, 5, 6, 7, 8]],
        "target": [[9, 10, 11, 12]],
        "known_covariates": [[0, 1] * 6],
        "categorical_known_covariates": [[0, 1, 2] * 4],
    }
    output = forecast.forecast(tiny_forecaster, row, 4)
    quantiles = np.asarray(output["quantiles"])
    assert quantiles.shape == (1, 4, 3)
    assert np.isfinite(quantiles).all() and (np.diff(quantiles, axis=-1) >= 0).all()
    out = tmp_path / "adapted"
    forecast.train(tiny_forecaster, [row], out, 1, Budget())
    after = forecast.forecast(tiny_forecaster, row, 4)
    reloaded = forecast.load(str(out), budget=Budget())
    assert np.asarray(
        forecast.forecast(reloaded, row, 4)["quantiles"]
    ) == pytest.approx(np.asarray(after["quantiles"]))


def test_future_target_is_absent_from_training_inputs(tiny_forecaster):
    row = {
        "context": [[1, 2, 3, 4]],
        "target": [[5, 6, 7, 8]],
        "categorical_known_covariates": [[1, 1, 2, 2, 3, 3, 3, 3]],
    }
    first, _, _ = forecast.training_tensors(tiny_forecaster, row)
    changed = copy.deepcopy(row)
    changed["target"] = [[500, 600, 700, 800]]
    second, _, _ = forecast.training_tensors(tiny_forecaster, changed)
    for key in ("inputs", "observed", "known_future", "known_future_mask"):
        assert (first[key] == second[key]).all()
    # Unseen category 3 maps to observed history mean (2.5), not future mean.
    assert first["known_future"][1, 0].item() == pytest.approx(2.5)


def test_forecast_adaptation_and_inference_share_preprocessing(tiny_forecaster):
    torch = pytest.importorskip("torch")
    row = {
        "id": "preprocessing",
        "context": [[None, 2, None, 4, 5, 6]],
        "target": [[7, 8, 9, 10]],
        "known_covariates": [[0, 1] * 5],
        "categorical_known_covariates": [[16777216, 16777217] * 5],
    }
    context, kwargs = forecast.inputs(row, 4)
    assert (
        kwargs["categorical_known_covariates"][0, 0, 0]
        != kwargs["categorical_known_covariates"][0, 0, 1]
    )
    packed, _, horizon = forecast.training_tensors(tiny_forecaster, row)
    tiny_forecaster.model.eval()
    with torch.no_grad():
        raw = tiny_forecaster.model.predict_block(**packed)[:1, :horizon]
        oracle = tiny_forecaster.forecast(
            context,
            prediction_length=horizon,
            symmetric_averaging=False,
            clip_nonnegative=False,
            **kwargs,
        ).quantiles[0]
    assert raw.numpy() == pytest.approx(oracle.numpy(), abs=1e-5)


def test_rolling_backtest_uses_only_history(tiny_forecaster):
    original = forecast.forecast
    observed = []

    def spy(model, row, horizon):
        observed.append(row)
        return original(model, row, horizon)

    forecast.forecast = spy
    try:
        result = forecast.backtest(
            tiny_forecaster,
            {"id": "series", "values": [[1, 2, 3, 4, 5, 6, 7, 8]]},
            4,
            [4],
            2,
            Budget(),
        )
    finally:
        forecast.forecast = original
    assert observed[0]["context"] == [[1, 2, 3, 4]]
    assert result["rows"][0]["observed_targets"] == 4


def test_terminal_copy_is_atomic():
    before = codec.Screen(("aaaa", "bbbb", "cccc"))
    after = codec.Screen(("bbbb", "cccc", "aaaa"), 2, 1, False)
    encoded = codec.delta(before, after)
    assert codec.COPY in encoded
    assert codec.apply_delta(before, encoded) == after


def test_terminal_randomized_delta_roundtrips_and_grammar():
    rng = np.random.default_rng(9)
    for _ in range(40):
        lines = tuple(
            "".join(chr(v) for v in rng.integers(32, 127, 12)) for _ in range(4)
        )
        before = codec.Screen(lines)
        changed = list(lines)
        changed[0] = lines[1]
        changed[2] = " " * 12
        after = codec.Screen(tuple(changed), 3, 11, False)
        tokens = codec.delta(before, after)
        for index, token in enumerate(tokens):
            assert token in codec.allowed(tokens[:index], before)
        assert codec.allowed(tokens, before) == []
        assert codec.apply_delta(before, tokens) == after


def test_terminal_rejects_out_of_bounds_duplicate_rows_and_incomplete_updates():
    screen = codec.Screen.custom(rows=2, cols=12)
    for tokens in (
        [codec.OUTPUT, codec.ROW + 2],
        [codec.OUTPUT, codec.ROW, codec.COPY, 0, codec.ROW_END, codec.ROW],
        [codec.OUTPUT, codec.CURSOR, 0, 12],
        [codec.OUTPUT, codec.CURSOR, 0, 0, 1],
    ):
        with pytest.raises(ValueError):
            codec.apply_delta(screen, tokens)


def test_terminal_wait_raw_keys_custom_screen():
    assert codec.event_tokens({"keys": [27, 91, 68]}) == [
        codec.INPUT,
        27,
        91,
        68,
        codec.INPUT_END,
    ]
    assert codec.event_tokens({"wait_ms": 1000}) == [
        codec.WAIT,
        3,
        232,
        codec.INPUT_END,
    ]
    assert max(codec.snapshot(codec.Screen.custom(rows=2, cols=12))) < 333
    with pytest.raises(ValueError):
        codec.event_tokens({"wait_ms": -1})


def tiny_episode():
    before = codec.Screen.custom("lab$ ", 2, 12)
    after = codec.Screen.custom("lab$ a", 2, 12)
    return {
        "id": "tiny",
        "initial_screen": before.as_dict(),
        "frames": [
            {"event": {"keys": [97]}, "screen": after.as_dict()},
            {"event": {"wait_ms": 100}, "screen": after.as_dict()},
        ],
    }


def test_terminal_training_gradient_and_artifact_reload(tmp_path):
    torch = pytest.importorskip("torch")
    import terminal_model as tm

    torch.set_num_threads(2)
    model = tm.new_model()
    samples = tm.examples([tiny_episode()], model.config.context_length)
    before = model.embedding.weight.detach().clone()
    losses = tm.train(model, samples, tmp_path / "terminal", 2, Budget())
    assert np.isfinite(losses).all()
    assert not torch.equal(before, model.embedding.weight)
    reloaded = tm.load(tmp_path / "terminal")
    tokens = torch.tensor([samples[0]["prefix"]])
    with torch.no_grad():
        assert torch.equal(model(tokens), reloaded(tokens))


def test_parallel_draft_verification_equals_sequential_even_on_bad_draft():
    torch = pytest.importorskip("torch")
    import terminal_model as tm

    torch.set_num_threads(2)
    # Short dimensions cap grammar length regardless of random predictions.
    model = tm.new_model().eval()
    screen = codec.Screen.custom("$ ", 1, 3)
    prefix = codec.snapshot(screen) + codec.event_tokens({"keys": [97]})
    expected = tm.decode(model, prefix, screen, Budget())
    draft = tm.parallel_draft(model, prefix, screen, Budget())
    verified, _ = tm.verify_draft(model, prefix, screen, draft, Budget())
    assert verified == expected
    verified, stats = tm.verify_draft(
        model, prefix, screen, [codec.OUTPUT_END] * 40, Budget()
    )
    assert verified == expected
    assert stats["corrected_draft_tokens"] > 0


def test_terminal_row_mask_isolates_drafts_but_cursor_can_read_rows():
    pytest.importorskip("torch")
    import terminal_model as tm

    tokens = [
        codec.BOS,
        codec.OUTPUT,
        codec.ROW,
        codec.COPY,
        0,
        codec.ROW_END,
        codec.ROW + 1,
        codec.COPY,
        0,
        codec.ROW_END,
        codec.CURSOR,
        0,
    ]
    mask = tm.row_mask(tokens, 1)
    assert mask[7, 3] and not mask[7, 0] and not mask[7, 6]
    assert not mask[10, 3] and mask[3, 7]


def test_correction_data_cannot_teach_unseen_oracle_words():
    pytest.importorskip("torch")
    import terminal_model as tm

    episode = tiny_episode()
    # An unseen directory name appears only in the current oracle frame, never
    # in any earlier real screen or typing. It is not a valid recoverable typo.
    episode["frames"][0]["screen"] = codec.Screen.custom("novel", 2, 12).as_dict()
    predicted = [
        {"id": "tiny:0", "screen": codec.Screen.custom("noxel", 2, 12).as_dict()}
    ]
    assert tm.correction_examples([episode], predicted, 2048) == []
    episode["initial_screen"] = codec.Screen.custom("novel", 2, 12).as_dict()
    assert len(tm.correction_examples([episode], predicted, 2048)) == 1


def test_decision_eval_refuses_failed_stale_and_mismatched_ceiling():
    from decision_eval import evaluate

    for receipt in (
        {},
        {"schema": "decision-ceiling-v1", "valid": False},
        {"schema": "decision-ceiling-v1", "valid": True, "validator_sha256": "stale"},
    ):
        with pytest.raises(ValueError, match="ceiling"):
            evaluate([record(0)], receipt)


def test_terminal_eval_refuses_unqualified_ruler_before_model_use():
    pytest.importorskip("torch")
    from terminal_eval import evaluate

    with pytest.raises(ValueError, match="ceiling"):
        evaluate(None, [tiny_episode()], {}, Budget())


def test_data_preparation_freezes_four_disjoint_splits(tmp_path):
    from decision_eval import prepare
    from common import read_json, read_rows

    rows = [
        {
            "id": str(i),
            "question": f"Question {i}",
            "options": {"A": "one", "B": "two"},
            "answer": "A",
        }
        for i in range(20)
    ]
    prepare(rows, tmp_path / "splits")
    groups = {
        name: read_rows(tmp_path / "splits" / f"{name}.jsonl")
        for name in ("train", "calibration", "test", "regression")
    }
    decision.validate_splits(groups)
    assert sum(len(items) for items in groups.values()) == 20
    assert (
        read_json(tmp_path / "splits" / "splits.json")["splits"]["train"]["count"] == 14
    )


def test_training_scores_cannot_calibrate_the_model():
    row = {**record(0), "seen_in_training": True}
    with pytest.raises(ValueError, match="training examples"):
        decision.calibrate([row])


def test_recorded_memory_probes_wait_for_real_output():
    from terminal_record import synthetic_recipe

    recipe = synthetic_recipe(seed=11, memory=True)
    assert len(recipe["probes"]) == 2
    assert len(set(recipe["probes"].values())) == 2
    assert all(
        recipe["events"][int(index)] == {"wait_ms": 500} for index in recipe["probes"]
    )


def test_pytorch_decision_lora_exports_a_loadable_bound_candidate(tmp_path):
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    pytest.importorskip("safetensors")
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace

    torch.set_num_threads(2)
    base = tmp_path / "base"
    config = transformers.Qwen3Config(
        vocab_size=8,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=1,
        num_attention_heads=2,
        num_key_value_heads=1,
        head_dim=8,
        tie_word_embeddings=True,
    )
    transformers.Qwen3ForCausalLM(config).save_pretrained(base)
    tokenizer = Tokenizer(
        WordLevel(
            {
                "[UNK]": 0,
                "A": 1,
                "B": 2,
                "Which": 3,
                "integer": 4,
                "is": 5,
                "even": 6,
                "Answer": 7,
            },
            unk_token="[UNK]",
        )
    )
    tokenizer.pre_tokenizer = Whitespace()
    fast = transformers.PreTrainedTokenizerFast(
        tokenizer_object=tokenizer, unk_token="[UNK]"
    )
    fast.chat_template = "{{ messages[0]['content'] }}"
    fast.save_pretrained(base)
    row = {
        "id": "training",
        "question": "Which integer is even?",
        "options": {"A": "2", "B": "3"},
        "answer": "A",
    }
    out = tmp_path / "candidate"
    decision.train(str(base), [row], out, 1, Budget())
    candidate = decision.DecisionModel(str(out), budget=Budget())
    scores = candidate.score(row)
    assert scores["seen_in_training"] is True
    assert np.isfinite(scores["logits"]).all()
    with pytest.raises(ValueError, match="training examples"):
        decision.metrics([scores])


@pytest.fixture
def local_server(tmp_path):
    import threading
    from http.server import ThreadingHTTPServer
    from server import LabRuntime, handler

    root = tmp_path / "public"
    root.mkdir()
    (root / "index.html").write_text("public asset")
    (tmp_path / "private.txt").write_text("outside web root")
    runtime = LabRuntime("unused", None, "unused", None, None)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(runtime, root.resolve()))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server, runtime
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def http_request(server, method, path, body=None, headers=None):
    import http.client

    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    result = response.status, response.read()
    connection.close()
    return result


def test_loopback_rejects_cross_origin_and_rebinding(local_server):
    server, _ = local_server
    status, _ = http_request(
        server, "GET", "/api/specialists/health", headers={"Host": "foreign.example"}
    )
    assert status == 403
    status, _ = http_request(
        server,
        "POST",
        "/api/specialists/forecast/synthetic",
        "{}",
        {"Origin": "https://foreign.example", "Content-Type": "application/json"},
    )
    assert status == 403
    status, _ = http_request(server, "GET", "/%2e%2e/private.txt")
    assert status == 404


def test_loopback_runs_same_origin_request_and_reports_busy(local_server):
    server, runtime = local_server
    headers = {
        "Origin": f"http://127.0.0.1:{server.server_port}",
        "Content-Type": "application/json",
    }
    status, body = http_request(
        server, "POST", "/api/specialists/forecast/synthetic", "{}", headers
    )
    assert status == 200 and b"synthetic-7" in body
    with runtime.lock:
        status, _ = http_request(
            server, "POST", "/api/specialists/forecast/synthetic", "{}", headers
        )
    assert status == 409
