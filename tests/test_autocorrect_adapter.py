#!/usr/bin/env python3
"""Offline checks for the autocorrect encoder-decoder LoRA adapter path.

The stdlib tests always run. The torch tests build a tiny randomly-initialized
T5 -- no checkpoint is downloaded or loaded -- and are skipped with a visible
marker when torch is not importable, because torch is deliberately not a
dependency of this repository.

Run:
    python3 tests/test_autocorrect_adapter.py
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


aa = load_module("autocorrect_adapter")
FIXTURES = ROOT / "evals" / "autocorrect"
RECIPE = aa.load_recipe()


class Skip(Exception):
    """Raised to report a test as skipped rather than passed."""


def torch_or_skip():
    try:
        import torch
    except ImportError:
        raise Skip("torch is not importable in this interpreter")
    return torch


# ---------------------------------------------------------------------------
# Stdlib layer
# ---------------------------------------------------------------------------


def test_recipe_is_internally_consistent():
    assert aa.validate_recipe() == []


def test_recipe_drift_is_detected():
    """Every cross-artifact claim in the recipe must fail closed when moved."""
    cases = {
        "prompt": lambda r: r["base"].__setitem__("prompt_template", "Fix: {text}"),
        "revision": lambda r: r["base"].__setitem__("revision", "deadbeef"),
        "model": lambda r: r["base"].__setitem__("model_id", "google-t5/t5-small"),
        "precision": lambda r: r["training"].__setitem__("precision", "float16"),
        "dataset": lambda r: r["data"]["pilot"].__setitem__("dataset_sha256", "0" * 64),
        "rows": lambda r: r["data"]["tiny_overfit"].__setitem__("rows", 99),
        "truncation": lambda r: r["data"].__setitem__("truncation_policy", "longest_first"),
        "unfrozen_base": lambda r: r["geometry"].__setitem__("base_requires_grad", True),
        "nonzero_b": lambda r: r["geometry"]["init_policy"].__setitem__("b", "gaussian"),
        "trainable_count": lambda r: r["geometry"].__setitem__(
            "expected_trainable_parameters", 1
        ),
        "step_cap": lambda r: r["training"].__setitem__("pilot_max_steps", 5000),
        "gate_drift": lambda r: r["gates"]["tiny_overfit"].__setitem__("exact_match_min", 0.5),
    }
    for name, mutate in cases.items():
        broken = copy.deepcopy(RECIPE)
        mutate(broken)
        problems = aa.validate_recipe(broken)
        assert problems, f"{name}: drift was not detected"


def test_target_resolution_is_exact_suffix_matching():
    names = [
        "encoder.block.0.layer.0.SelfAttention.q",
        "encoder.block.0.layer.0.SelfAttention.k",
        "encoder.block.0.layer.0.SelfAttention.v",
        "encoder.block.0.layer.0.SelfAttention.o",
        "decoder.block.0.layer.1.EncDecAttention.q",
        "decoder.block.0.layer.1.EncDecAttention.v",
        "decoder.block.0.layer.2.DenseReluDense.wi_0",
        "some.other.SelfAttention.qq",
        "lm_head",
    ]
    resolved = aa.resolve_target_names(names, RECIPE["geometry"]["target_module_suffixes"])
    assert resolved == sorted(
        [
            "encoder.block.0.layer.0.SelfAttention.q",
            "encoder.block.0.layer.0.SelfAttention.v",
            "decoder.block.0.layer.1.EncDecAttention.q",
            "decoder.block.0.layer.1.EncDecAttention.v",
        ]
    ), resolved


def test_expected_lora_size_matches_the_real_base_config():
    config_path = Path(RECIPE["base"]["local_dir"]) / "config.json"
    if not config_path.exists():
        raise Skip("the pinned FLAN-T5-small config is not present locally")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    modules, params = aa.expected_lora_size(config, RECIPE["geometry"]["rank"])
    assert modules == RECIPE["geometry"]["expected_adapted_modules"]
    assert params == RECIPE["geometry"]["expected_trainable_parameters"]


def test_examples_are_prompted_frozen_and_split_safe():
    for stage in aa.STAGES:
        examples = aa.build_examples(stage)
        assert len(examples) == RECIPE["data"][stage]["rows"]
        assert all("test" != example["split"] for example in examples)
        for example in examples:
            assert example["source"].startswith("Correct only the typing errors")
            assert example["source"].endswith(example["source"].split("\n")[-1])
            assert example["target"] and "\n" not in example["target"]

    drifted = copy.deepcopy(RECIPE)
    drifted["data"]["tiny_overfit"]["dataset_sha256"] = "0" * 64
    try:
        aa.build_examples("tiny_overfit", drifted)
    except aa.AdapterError:
        pass
    else:
        raise AssertionError("a drifted dataset hash must refuse to build examples")


def test_learning_rate_warms_up_then_holds():
    total = 200
    first = aa.learning_rate_at(0, total, RECIPE)
    peak = RECIPE["optimizer"]["learning_rate"]
    warmup = 20  # ceil(200 * 0.1)
    assert 0 < first < peak
    assert aa.learning_rate_at(warmup - 1, total, RECIPE) == peak
    assert aa.learning_rate_at(total - 1, total, RECIPE) == peak
    values = [aa.learning_rate_at(step, total, RECIPE) for step in range(warmup)]
    assert values == sorted(values), "warmup must be monotonically increasing"
    for bad in (-1, total):
        try:
            aa.learning_rate_at(bad, total, RECIPE)
        except aa.AdapterError:
            pass
        else:
            raise AssertionError(f"step {bad} must be rejected")


def test_checkpoint_schedule_always_includes_the_last_step():
    assert aa.checkpoint_steps(200, RECIPE) == [50, 100, 150, 200]
    assert aa.checkpoint_steps(120, RECIPE) == [50, 100, 120]
    assert aa.checkpoint_steps(30, RECIPE) == [30]
    assert aa.checkpoint_steps(0, RECIPE) == []


def test_stop_rules_fire_and_map_to_decisions():
    state = aa.StopRuleState(RECIPE, "tiny_overfit")
    assert not state.observe_loss(1, 0.5)
    assert state.observe_loss(2, float("nan"))
    assert state.triggered == "non-finite-loss"
    assert state.decision() == "retry-training"

    state = aa.StopRuleState(RECIPE, "tiny_overfit")
    assert state.finish_tiny_overfit(0.875)
    assert state.decision() == "retry-training"
    assert not aa.StopRuleState(RECIPE, "tiny_overfit").finish_tiny_overfit(1.0)

    state = aa.StopRuleState(RECIPE, "pilot")
    assert not state.observe_eval(50, {"clean_byte_exact_preservation_rate": 1.0})
    assert state.observe_eval(100, {"clean_byte_exact_preservation_rate": 0.99})
    assert state.triggered == "clean-preservation-collapse"
    assert state.decision() is None, "a regression is reported, not auto-decided"

    state = aa.StopRuleState(RECIPE, "pilot")
    assert state.observe_wall_time(121)
    assert state.triggered == "wall-time"

    state = aa.StopRuleState(RECIPE, "pilot")
    assert not state.observe_step(299)
    assert state.observe_step(300)
    assert state.triggered == "step-budget"

    # The first rule to fire wins; later observations must not overwrite it.
    state = aa.StopRuleState(RECIPE, "pilot")
    state.observe_loss(1, float("inf"))
    state.observe_wall_time(999)
    assert state.triggered == "non-finite-loss"


def test_plan_is_resolved_but_never_authorized():
    for stage in aa.STAGES:
        plan = aa.build_plan(stage)
        assert plan["authorized"] is False
        assert plan["rows"] == RECIPE["data"][stage]["rows"]
        assert plan["checkpoint_steps"][-1] == plan["total_steps"]
        assert plan["warmup_steps"] > 0


# ---------------------------------------------------------------------------
# Torch layer: tiny randomly-initialized T5, no checkpoint involved
# ---------------------------------------------------------------------------


def tiny_model():
    torch = torch_or_skip()
    try:
        from transformers import T5Config, T5ForConditionalGeneration
    except ImportError:
        raise Skip("transformers is not importable in this interpreter")
    config = T5Config(
        vocab_size=64,
        d_model=16,
        d_kv=4,
        d_ff=32,
        num_layers=2,
        num_decoder_layers=2,
        num_heads=4,
        dropout_rate=0.0,
        decoder_start_token_id=0,
        pad_token_id=0,
        eos_token_id=1,
    )
    torch.manual_seed(RECIPE["training"]["seed"])
    return T5ForConditionalGeneration(config).eval(), config


def tiny_batch():
    torch = torch_or_skip()
    return {
        "input_ids": torch.tensor([[3, 4, 5, 6], [7, 8, 9, 2]]),
        "attention_mask": torch.ones(2, 4, dtype=torch.long),
        "labels": torch.tensor([[10, 11, 1], [12, 13, 1]]),
    }


def test_zero_initialized_adapter_is_bit_identical_to_the_base():
    """Load parity: delta_W is exactly zero until the first optimizer step."""
    torch = torch_or_skip()
    model, _ = tiny_model()
    batch = tiny_batch()
    with torch.no_grad():
        before = model(**batch).logits.clone()
    aa.inject_lora(model, RECIPE)
    with torch.no_grad():
        after = model(**batch).logits
    assert torch.equal(before, after), "zero-init LoRA changed the base output"


def test_injection_freezes_the_base_and_trains_only_lora():
    torch_or_skip()
    model, config = tiny_model()
    names = aa.inject_lora(model, RECIPE)
    expected_modules, expected_params = aa.expected_lora_size(
        config.to_dict(), RECIPE["geometry"]["rank"]
    )
    assert len(names) == expected_modules

    trainable = aa.trainable_parameters(model)
    assert trainable, "no trainable parameters after injection"
    assert all(name.endswith(("lora_a", "lora_b")) for name, _ in trainable)
    assert sum(p.numel() for _, p in trainable) == expected_params

    frozen = [
        name
        for name, p in model.named_parameters()
        if not p.requires_grad and name.endswith(("lora_a", "lora_b"))
    ]
    assert not frozen, f"LoRA tensors must be trainable: {frozen}"


def test_injection_is_deterministic_and_order_independent():
    torch = torch_or_skip()
    first, _ = tiny_model()
    second, _ = tiny_model()
    aa.inject_lora(first, RECIPE)
    aa.inject_lora(second, RECIPE)
    left, right = aa.adapter_state_dict(first), aa.adapter_state_dict(second)
    assert set(left) == set(right)
    for key in left:
        assert torch.equal(left[key], right[key]), f"{key} is not reproducible"
    # Distinct modules must not share identical A matrices.
    a_matrices = [v for k, v in left.items() if k.endswith("lora_a")]
    assert not torch.equal(a_matrices[0], a_matrices[1])


def test_gradients_are_finite_and_reach_a_after_the_first_step():
    """At step 0 only B has gradient (B=0 zeroes dL/dA); A must wake up after."""
    torch = torch_or_skip()
    model, _ = tiny_model()
    aa.inject_lora(model, RECIPE)
    optimizer = aa.make_optimizer(model, RECIPE)
    batch = tiny_batch()

    model.train()
    model(**batch).loss.backward()
    grads = {name: p.grad for name, p in aa.trainable_parameters(model)}
    assert all(g is not None and torch.isfinite(g).all() for g in grads.values())
    assert all(
        float(g.abs().sum()) == 0.0 for name, g in grads.items() if name.endswith("lora_a")
    ), "dL/dA must be exactly zero while B is zero"
    assert any(
        float(g.abs().sum()) > 0.0 for name, g in grads.items() if name.endswith("lora_b")
    ), "dL/dB must be non-zero at step 0"

    loss = aa.training_step(model, batch, optimizer, RECIPE)
    assert torch.isfinite(torch.tensor(loss))
    model(**batch).loss.backward()
    a_grads = [
        float(p.grad.abs().sum())
        for name, p in aa.trainable_parameters(model)
        if name.endswith("lora_a")
    ]
    assert any(g > 0.0 for g in a_grads), "dL/dA must be non-zero once B has moved"


def test_one_step_changes_only_lora_weights():
    torch = torch_or_skip()
    model, _ = tiny_model()
    aa.inject_lora(model, RECIPE)
    base_before = {
        name: p.detach().clone()
        for name, p in model.named_parameters()
        if not name.endswith(("lora_a", "lora_b"))
    }
    lora_before = aa.adapter_state_dict(model)

    optimizer = aa.make_optimizer(model, RECIPE)
    aa.training_step(model, tiny_batch(), optimizer, RECIPE)

    for name, p in model.named_parameters():
        if name in base_before:
            assert torch.equal(base_before[name], p), f"frozen base tensor {name} moved"
    lora_after = aa.adapter_state_dict(model)
    assert any(
        not torch.equal(lora_before[key], lora_after[key]) for key in lora_before
    ), "no LoRA tensor moved during the step"


def test_repeated_batch_loss_decreases():
    """The smallest honest signal that the path can learn at all."""
    torch_or_skip()
    model, _ = tiny_model()
    aa.inject_lora(model, RECIPE)
    optimizer = aa.make_optimizer(model, RECIPE)
    batch = tiny_batch()
    losses = [aa.training_step(model, batch, optimizer, RECIPE) for _ in range(30)]
    assert all(loss == loss for loss in losses), "loss went NaN"
    assert losses[-1] < losses[0], f"loss did not decrease: {losses[0]} -> {losses[-1]}"


def test_adapter_save_load_round_trip_is_exact():
    import tempfile

    torch = torch_or_skip()
    model, _ = tiny_model()
    aa.inject_lora(model, RECIPE)
    optimizer = aa.make_optimizer(model, RECIPE)
    aa.training_step(model, tiny_batch(), optimizer, RECIPE)
    trained = aa.adapter_state_dict(model)
    with torch.no_grad():
        reference = model(**tiny_batch()).logits.clone()

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "adapter.pt"
        aa.save_adapter(model, path, RECIPE, extra={"stage": "unit-test"})

        payload = torch.load(path, map_location="cpu", weights_only=False)
        assert set(payload["tensors"]) == set(trained)
        assert not any(
            key.endswith(("SelfAttention.k.weight", "DenseReluDense.wo.weight"))
            for key in payload["tensors"]
        ), "the adapter file must never carry base weights"

        fresh, _ = tiny_model()
        aa.inject_lora(fresh, RECIPE)
        meta = aa.load_adapter(fresh, path, RECIPE)
        assert meta == {"stage": "unit-test"}
        for key, value in aa.adapter_state_dict(fresh).items():
            assert torch.equal(value, trained[key]), f"{key} did not round-trip"
        with torch.no_grad():
            restored = fresh(**tiny_batch()).logits
        assert torch.equal(reference, restored)


def test_adapter_load_fails_closed_on_recipe_drift():
    import tempfile

    torch = torch_or_skip()
    model, _ = tiny_model()
    aa.inject_lora(model, RECIPE)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "adapter.pt"
        aa.save_adapter(model, path, RECIPE)

        other_recipe = copy.deepcopy(RECIPE)
        other_recipe["recipe_id"] = "autocorrect-flan-t5-small-lora-v2"
        fresh, _ = tiny_model()
        aa.inject_lora(fresh, RECIPE)
        for bad_recipe, reason in ((other_recipe, "recipe id"),):
            try:
                aa.load_adapter(fresh, path, bad_recipe)
            except aa.AdapterError:
                pass
            else:
                raise AssertionError(f"{reason} drift must refuse to load")

        payload = torch.load(path, map_location="cpu", weights_only=False)
        payload["rank"] = 4
        torch.save(payload, path)
        try:
            aa.load_adapter(fresh, path, RECIPE)
        except aa.AdapterError:
            pass
        else:
            raise AssertionError("rank drift must refuse to load")


class StubTokenizer:
    """Minimal tokenizer stand-in: one id per character, no truncation."""

    def __init__(self):
        import torch

        self.torch = torch

    def __call__(self, texts, padding=True, return_tensors="pt"):
        torch = self.torch
        ids = [[ord(c) % 60 + 3 for c in text] for text in texts]
        width = max(len(row) for row in ids)
        mask = [[1] * len(row) + [0] * (width - len(row)) for row in ids]
        padded = [row + [0] * (width - len(row)) for row in ids]
        return {
            "input_ids": torch.tensor(padded),
            "attention_mask": torch.tensor(mask),
        }


def test_encode_batch_masks_padding_and_refuses_to_truncate():
    torch = torch_or_skip()
    tokenizer = StubTokenizer()
    ignore = RECIPE["data"]["label_padding_ignore_index"]

    examples = [
        {"source": "abc", "target": "abcd"},
        {"source": "ab", "target": "ab"},
    ]
    batch = aa.encode_batch(tokenizer, examples, RECIPE)
    assert batch["labels"].shape == (2, 4)
    assert int(batch["labels"][1][-1]) == ignore, "pad positions must be ignored in the loss"
    assert int(batch["labels"][0][-1]) != ignore
    assert torch.equal(batch["attention_mask"][1], torch.tensor([1, 1, 0]))

    tight = copy.deepcopy(RECIPE)
    tight["data"]["max_source_tokens"] = 2
    try:
        aa.encode_batch(tokenizer, examples, tight)
    except aa.AdapterError as exc:
        assert "truncation_policy" in str(exc)
    else:
        raise AssertionError("an over-length source batch must raise, not truncate")

    tight = copy.deepcopy(RECIPE)
    tight["data"]["max_target_tokens"] = 2
    try:
        aa.encode_batch(tokenizer, examples, tight)
    except aa.AdapterError:
        pass
    else:
        raise AssertionError("an over-length target batch must raise, not truncate")


def test_untargeted_architecture_fails_loudly():
    torch_or_skip()
    import torch

    class NotAnEncoderDecoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.proj = torch.nn.Linear(4, 4)

    try:
        aa.inject_lora(NotAnEncoderDecoder(), RECIPE)
    except aa.AdapterError as exc:
        assert "does not look like the frozen encoder-decoder" in str(exc)
    else:
        raise AssertionError("injecting into a non-matching model must raise")


def main() -> int:
    tests = [
        test_recipe_is_internally_consistent,
        test_recipe_drift_is_detected,
        test_target_resolution_is_exact_suffix_matching,
        test_expected_lora_size_matches_the_real_base_config,
        test_examples_are_prompted_frozen_and_split_safe,
        test_learning_rate_warms_up_then_holds,
        test_checkpoint_schedule_always_includes_the_last_step,
        test_stop_rules_fire_and_map_to_decisions,
        test_plan_is_resolved_but_never_authorized,
        test_zero_initialized_adapter_is_bit_identical_to_the_base,
        test_injection_freezes_the_base_and_trains_only_lora,
        test_injection_is_deterministic_and_order_independent,
        test_gradients_are_finite_and_reach_a_after_the_first_step,
        test_one_step_changes_only_lora_weights,
        test_repeated_batch_loss_decreases,
        test_adapter_save_load_round_trip_is_exact,
        test_adapter_load_fails_closed_on_recipe_drift,
        test_encode_batch_masks_padding_and_refuses_to_truncate,
        test_untargeted_architecture_fails_loudly,
    ]
    failures = skipped = 0
    for test in tests:
        print(f"-- {test.__name__}")
        try:
            test()
            print("  ok")
        except Skip as exc:
            print(f"  SKIP: {exc}")
            skipped += 1
        except Exception as exc:
            print(f"  FAIL: {type(exc).__name__}: {exc}")
            failures += 1
    print()
    if failures:
        print(f"{failures}/{len(tests)} tests failed ({skipped} skipped)")
        return 1
    print(f"{len(tests) - skipped}/{len(tests)} tests passed ({skipped} skipped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
