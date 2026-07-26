#!/usr/bin/env python3
"""Minimum encoder-decoder LoRA adapter path for the autocorrect specialist.

This implements task 5.1 of `build-mac-local-autocorrect-specialist`: the
smallest adapter/training path the selected FLAN-T5-small base needs, plus the
offline checks that prove it is wired correctly.

Two layers live here on purpose:

* A stdlib layer (recipe validation, target-module resolution, example
  building, the LR/checkpoint schedule, and the stop-rule state machine) that
  runs with no third-party import at all.
* A torch layer (LoRA injection, adapter save/load, one training step) that is
  imported lazily so this file never adds torch, transformers, or peft to the
  project's dependency surface. LoRA is implemented by hand for the same
  reason -- `peft` is not a dependency of this repository.

Running the actual tiny-overfit or pilot training is NOT authorized by this
file. `train` refuses to start without an explicit operator-approval flag.

Usage:
    python3 scripts/autocorrect_adapter.py validate
    python3 scripts/autocorrect_adapter.py plan --stage tiny_overfit
    python3 scripts/autocorrect_adapter.py selftest
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "evals" / "autocorrect"
RECIPE_PATH = FIXTURE_DIR / "adapter-recipe-v1.json"
THRESHOLDS_PATH = FIXTURE_DIR / "thresholds-v1.json"

STAGES = ("tiny_overfit", "pilot")


class AdapterError(ValueError):
    """Raised when the recipe, the plan, or the adapter wiring is invalid."""


def _foundation() -> Any:
    """Load the no-model foundation module without requiring a package."""
    path = ROOT / "scripts" / "autocorrect_foundation.py"
    spec = importlib.util.spec_from_file_location("autocorrect_foundation", path)
    if not spec or not spec.loader:  # pragma: no cover - import plumbing
        raise AdapterError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Stdlib layer: recipe, targets, examples, schedule, stop rules
# ---------------------------------------------------------------------------


def load_recipe(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or RECIPE_PATH).read_text(encoding="utf-8"))


def validate_recipe(recipe: dict[str, Any] | None = None) -> list[str]:
    """Return every reason the frozen recipe is not internally consistent.

    The recipe is only useful if it cannot silently drift away from the
    thresholds, the manifests, or the measured base selection.
    """
    recipe = recipe if recipe is not None else load_recipe()
    problems: list[str] = []

    if recipe.get("schema_version") != 1:
        problems.append("recipe: schema_version must be 1")

    geometry = recipe.get("geometry", {})
    rank = geometry.get("rank")
    alpha = geometry.get("alpha")
    if not isinstance(rank, int) or rank <= 0:
        problems.append("geometry: rank must be a positive integer")
    if not isinstance(alpha, (int, float)) or alpha <= 0:
        problems.append("geometry: alpha must be positive")
    if geometry.get("base_requires_grad") is not False:
        problems.append("geometry: base_requires_grad must be false")
    if geometry.get("init_policy", {}).get("b") != "exact zeros":
        problems.append("geometry: b must initialize to exact zeros for load parity")
    overlap = set(geometry.get("target_module_suffixes", [])) & set(
        geometry.get("excluded_modules", [])
    )
    if overlap:
        problems.append(f"geometry: modules both targeted and excluded: {sorted(overlap)}")

    # The frozen base must be the one the bake-off actually selected.
    bakeoff_path = FIXTURE_DIR / "base-bakeoff-v1.json"
    if bakeoff_path.exists():
        bakeoff = json.loads(bakeoff_path.read_text(encoding="utf-8"))
        selection = bakeoff.get("selection", {})
        base = recipe.get("base", {})
        selected = next(
            (
                candidate
                for candidate in bakeoff.get("candidates", [])
                if candidate.get("model_key") == selection.get("model_key")
            ),
            {},
        )
        if base.get("model_id") != selected.get("model_id"):
            problems.append(
                f"base: model_id {base.get('model_id')!r} is not the selected "
                f"base {selected.get('model_id')!r}"
            )
        if base.get("revision") != selected.get("revision"):
            problems.append("base: revision does not match the selected bake-off revision")
        if base.get("prompt_template") != selection.get("frozen_prompt_template"):
            problems.append("base: prompt_template drifted from the frozen bake-off prompt")
        if recipe.get("training", {}).get("precision") != selection.get("frozen_precision"):
            problems.append("training: precision drifted from the frozen bake-off precision")

    # Trainable-parameter expectations must match the real base architecture.
    expected_params = geometry.get("expected_trainable_parameters")
    expected_modules = geometry.get("expected_adapted_modules")
    config_path = Path(recipe.get("base", {}).get("local_dir", "")) / "config.json"
    if config_path.exists() and isinstance(rank, int) and rank > 0:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        modules, params = expected_lora_size(config, rank)
        if expected_modules != modules:
            problems.append(
                f"geometry: expected_adapted_modules {expected_modules} != {modules} "
                "derived from the base config"
            )
        if expected_params != params:
            problems.append(
                f"geometry: expected_trainable_parameters {expected_params} != {params} "
                "derived from the base config"
            )

    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    stop = thresholds["training_stop"]
    gates = recipe.get("gates", {})
    training = recipe.get("training", {})

    tiny_gate = gates.get("tiny_overfit", {})
    if tiny_gate.get("dataset_utf8_bytes_max") != stop["tiny_overfit_utf8_bytes_max"]:
        problems.append("gates.tiny_overfit: byte budget disagrees with thresholds-v1")
    if tiny_gate.get("exact_match_min") != stop["tiny_overfit_exact_match_min"]:
        problems.append("gates.tiny_overfit: exact-match bar disagrees with thresholds-v1")

    pilot_gate = gates.get("pilot", {})
    if pilot_gate.get("rows_max") != stop["pilot_rows_max"]:
        problems.append("gates.pilot: rows_max disagrees with thresholds-v1")
    if pilot_gate.get("steps_max") != stop["pilot_steps_max"]:
        problems.append("gates.pilot: steps_max disagrees with thresholds-v1")
    if pilot_gate.get("wall_time_minutes_max") != stop["pilot_wall_time_minutes_max"]:
        problems.append("gates.pilot: wall-time budget disagrees with thresholds-v1")

    if training.get("pilot_max_steps", 0) > stop["pilot_steps_max"]:
        problems.append("training: pilot_max_steps exceeds the frozen pilot step cap")

    # Manifests must still materialize to exactly the bytes the recipe claims.
    foundation = _foundation()
    sources = foundation.load_jsonl(FIXTURE_DIR / "source-documents-v1.jsonl")
    layout = foundation.load_layout()
    data = recipe.get("data", {})
    for stage in STAGES:
        spec = data.get(stage, {})
        manifest_path = ROOT / spec.get("manifest", "")
        if not manifest_path.exists():
            problems.append(f"data.{stage}: missing manifest {spec.get('manifest')!r}")
            continue
        manifest = foundation.load_json(manifest_path)
        _, summary = foundation.materialize_manifest(manifest, sources, layout)
        if summary["dataset_sha256"] != spec.get("dataset_sha256"):
            problems.append(f"data.{stage}: dataset_sha256 drifted from the manifest")
        if summary["rows"] != spec.get("rows"):
            problems.append(f"data.{stage}: row count drifted from the manifest")
        if summary["utf8_bytes"] != spec.get("utf8_bytes"):
            problems.append(f"data.{stage}: utf8_bytes drifted from the manifest")

    tiny_bytes = data.get("tiny_overfit", {}).get("utf8_bytes", 0)
    if tiny_bytes > stop["tiny_overfit_utf8_bytes_max"]:
        problems.append("data.tiny_overfit: dataset exceeds the frozen byte budget")
    pilot_rows = data.get("pilot", {}).get("rows", 0)
    if pilot_rows > stop["pilot_rows_max"]:
        problems.append("data.pilot: dataset exceeds the frozen row budget")

    if data.get("truncation_policy") != "error":
        problems.append(
            "data: truncation_policy must be 'error'; silent truncation fabricates a deletion"
        )

    if not recipe.get("stop_rules"):
        problems.append("stop_rules: at least one stop rule is required")

    # Design defects are fatal for an active recipe. A retired one must name
    # every defect it actually has -- that is what stops the next recipe from
    # inheriting them.
    status = recipe.get("status", "active")
    if status not in ("active", "retired"):
        problems.append(f"status: must be 'active' or 'retired', got {status!r}")
    defects = check_recipe_defects(recipe)
    found = {defect["id"] for defect in defects}
    documented = {entry["id"] for entry in recipe.get("known_defects", [])}

    if status == "active":
        problems += [f"design defect [{d['id']}]: {d['statement']}" for d in defects]
    else:
        if not recipe.get("retired_reason"):
            problems.append("retired recipe: retired_reason is required")
        for defect in defects:
            if defect["id"] not in documented:
                problems.append(
                    f"retired recipe: undocumented design defect [{defect['id']}]: "
                    f"{defect['statement']}"
                )
    for stale in sorted(documented - found):
        problems.append(
            f"known_defects lists [{stale}], which no longer reproduces; remove it "
            "or fix the check so the record stays truthful"
        )

    return problems


# Training stop rules that compare a metric to a bar. Each maps the threshold
# key to the baseline metric it must be satisfiable against. A stop rule the
# BASE model already violates fires at the first evaluation regardless of what
# training does, which silently turns "stop if we regress" into "stop always".
# Learned the hard way: see docs/factory/autocorrect-adapter-recipe.md.
STOP_RULE_BASELINE_KEYS = {
    "stop_on_clean_preservation_below": "clean_byte_exact_preservation_rate",
}


def check_recipe_defects(recipe: dict[str, Any]) -> list[dict[str, str]]:
    """Design defects that make a recipe unrunnable or its gates meaningless.

    These are invariants recovered from real failed runs. They are checked
    mechanically because prose in a post-mortem does not stop a repeat.
    """
    defects: list[dict[str, str]] = []

    bakeoff_path = FIXTURE_DIR / "base-bakeoff-v1.json"
    thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    if bakeoff_path.exists():
        baseline = json.loads(bakeoff_path.read_text(encoding="utf-8"))["selection"][
            "baseline_quality"
        ]
        for threshold_key, metric_key in STOP_RULE_BASELINE_KEYS.items():
            bar = thresholds["training_stop"].get(threshold_key)
            measured = baseline.get(metric_key)
            if bar is None or measured is None:
                continue
            if measured < bar:
                defects.append(
                    {
                        "id": "unsatisfiable-stop-rule",
                        "statement": (
                            f"training stop rule {threshold_key}={bar} is violated by the "
                            f"base model's own zero-shot {metric_key}={measured}, so it "
                            f"fires at the first evaluation regardless of training"
                        ),
                    }
                )

    # A memorization gate whose rows all share one target cannot distinguish
    # "memorized the data" from "emitted a constant".
    try:
        tiny_rows = build_examples("tiny_overfit", recipe)
    except AdapterError:
        tiny_rows = []
    if tiny_rows:
        unique_targets = len({row["target"] for row in tiny_rows})
        if unique_targets <= 1:
            defects.append(
                {
                    "id": "degenerate-memorization-gate",
                    "statement": (
                        f"the tiny-overfit gate has {unique_targets} unique target(s), so "
                        "exact match 1.0 is reachable by emitting one constant and is not "
                        "evidence of memorizing the data"
                    ),
                }
            )
    return defects


def expected_lora_size(config: dict[str, Any], rank: int) -> tuple[int, int]:
    """Derive (adapted module count, trainable parameters) from a T5 config.

    Every adapted projection maps `d_model -> num_heads * d_kv`, so one LoRA
    pair costs `rank * d_model + inner * rank` parameters.
    """
    d_model = config["d_model"]
    inner = config["num_heads"] * config["d_kv"]
    encoder_layers = config["num_layers"]
    decoder_layers = config.get("num_decoder_layers", encoder_layers)
    # encoder self-attn q,v + decoder self-attn q,v + decoder cross-attn q,v
    modules = encoder_layers * 2 + decoder_layers * 4
    per_module = rank * d_model + inner * rank
    return modules, modules * per_module


def resolve_target_names(module_names: Iterable[str], suffixes: Sequence[str]) -> list[str]:
    """Select module names whose dotted path ends with a targeted suffix."""
    selected = [
        name
        for name in module_names
        if any(name == suffix or name.endswith("." + suffix) for suffix in suffixes)
    ]
    return sorted(selected)


def build_examples(stage: str, recipe: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Materialize one stage's manifest into prompted source/target pairs."""
    if stage not in STAGES:
        raise AdapterError(f"unknown stage {stage!r}; expected one of {STAGES}")
    recipe = recipe if recipe is not None else load_recipe()
    foundation = _foundation()
    spec = recipe["data"][stage]
    manifest = foundation.load_json(ROOT / spec["manifest"])
    sources = foundation.load_jsonl(FIXTURE_DIR / "source-documents-v1.jsonl")
    rows, summary = foundation.materialize_manifest(manifest, sources, foundation.load_layout())
    if summary["dataset_sha256"] != spec["dataset_sha256"]:
        raise AdapterError(
            f"{stage}: materialized dataset {summary['dataset_sha256']} does not match the "
            f"frozen {spec['dataset_sha256']}"
        )
    template = recipe["base"]["prompt_template"]
    return [
        {
            "id": row["id"],
            "split": row["split"],
            "error_family": row["error_family"],
            "source": template.format(text=row["noisy"]),
            "target": row["clean"],
        }
        for row in rows
    ]


def learning_rate_at(step: int, total_steps: int, recipe: dict[str, Any]) -> float:
    """Linear warmup then constant, matching the frozen schedule.

    `step` is zero-based. Warmup spans `ceil(total_steps * warmup_ratio)` steps
    and never yields a zero learning rate on the first step.
    """
    optimizer = recipe["optimizer"]
    base_lr = optimizer["learning_rate"]
    if total_steps <= 0:
        raise AdapterError("total_steps must be positive")
    if not 0 <= step < total_steps:
        raise AdapterError(f"step {step} outside [0, {total_steps})")
    warmup = math.ceil(total_steps * optimizer["warmup_ratio"])
    if warmup and step < warmup:
        return base_lr * (step + 1) / warmup
    return base_lr


def checkpoint_steps(total_steps: int, recipe: dict[str, Any]) -> list[int]:
    """One-based steps at which a checkpoint is written, always including the last."""
    cadence = recipe["training"]["checkpoint_every_steps"]
    steps = [s for s in range(cadence, total_steps + 1, cadence)]
    if total_steps and (not steps or steps[-1] != total_steps):
        steps.append(total_steps)
    return steps


class StopRuleState:
    """Frozen stop-rule state machine shared by both future training stages."""

    def __init__(self, recipe: dict[str, Any], stage: str):
        if stage not in STAGES:
            raise AdapterError(f"unknown stage {stage!r}")
        self.recipe = recipe
        self.stage = stage
        self.triggered: str | None = None
        self.detail: str | None = None
        gates = recipe["gates"]
        self.max_steps = recipe["training"][
            "tiny_overfit_max_steps" if stage == "tiny_overfit" else "pilot_max_steps"
        ]
        self.wall_time_minutes_max = gates["pilot"]["wall_time_minutes_max"]
        self.clean_preservation_min = json.loads(
            THRESHOLDS_PATH.read_text(encoding="utf-8")
        )["training_stop"]["stop_on_clean_preservation_below"]

    @property
    def stopped(self) -> bool:
        return self.triggered is not None

    def _fire(self, rule: str, detail: str) -> bool:
        if self.triggered is None:
            self.triggered, self.detail = rule, detail
        return True

    def observe_loss(self, step: int, loss: float) -> bool:
        if not math.isfinite(loss):
            return self._fire("non-finite-loss", f"loss={loss!r} at step {step}")
        return self.stopped

    def observe_eval(self, step: int, metrics: dict[str, float]) -> bool:
        if self.stage == "pilot":
            clean = metrics.get("clean_byte_exact_preservation_rate")
            if clean is not None and clean < self.clean_preservation_min:
                return self._fire(
                    "clean-preservation-collapse",
                    f"clean preservation {clean} < {self.clean_preservation_min} at step {step}",
                )
        return self.stopped

    def observe_wall_time(self, minutes: float) -> bool:
        if minutes > self.wall_time_minutes_max:
            return self._fire(
                "wall-time", f"{minutes:.1f} min > {self.wall_time_minutes_max} min"
            )
        return self.stopped

    def observe_step(self, step: int) -> bool:
        if step >= self.max_steps:
            return self._fire("step-budget", f"reached {self.max_steps} steps")
        return self.stopped

    def finish_tiny_overfit(self, exact_match: float) -> bool:
        bar = self.recipe["gates"]["tiny_overfit"]["exact_match_min"]
        if exact_match < bar:
            return self._fire(
                "tiny-overfit-failure", f"exact match {exact_match} < {bar}"
            )
        return self.stopped

    def decision(self) -> str | None:
        """Map a fired stop rule to the decision the recipe requires."""
        mapping = {
            "non-finite-loss": "retry-training",
            "tiny-overfit-failure": "retry-training",
        }
        return mapping.get(self.triggered or "")


def build_plan(stage: str, recipe: dict[str, Any] | None = None) -> dict[str, Any]:
    """A fully resolved, still-unexecuted description of one training stage."""
    recipe = recipe if recipe is not None else load_recipe()
    examples = build_examples(stage, recipe)
    training = recipe["training"]
    total_steps = training[
        "tiny_overfit_max_steps" if stage == "tiny_overfit" else "pilot_max_steps"
    ]
    return {
        "stage": stage,
        "recipe_id": recipe["recipe_id"],
        "base": recipe["base"]["model_id"],
        "revision": recipe["base"]["revision"],
        "rows": len(examples),
        "dataset_sha256": recipe["data"][stage]["dataset_sha256"],
        "batch_size": training["batch_size"],
        "total_steps": total_steps,
        "warmup_steps": math.ceil(total_steps * recipe["optimizer"]["warmup_ratio"]),
        "first_step_learning_rate": learning_rate_at(0, total_steps, recipe),
        "peak_learning_rate": recipe["optimizer"]["learning_rate"],
        "checkpoint_steps": checkpoint_steps(total_steps, recipe),
        "expected_trainable_parameters": recipe["geometry"]["expected_trainable_parameters"],
        "authorized": False,
        "authorization_note": (
            "Executing this plan requires explicit owner approval and the GPU lock."
        ),
    }


# ---------------------------------------------------------------------------
# Torch layer: LoRA injection, adapter IO, one step
# ---------------------------------------------------------------------------


def _torch():
    try:
        import torch  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise AdapterError(
            "torch is not importable. The adapter layer is intentionally not a project "
            "dependency; run these checks in the pinned disposable runtime."
        ) from exc
    return torch


def make_lora_linear(base: Any, rank: int, alpha: float, dropout: float, seed: int) -> Any:
    """Wrap one frozen `nn.Linear` with a zero-initialized LoRA branch."""
    torch = _torch()
    nn = torch.nn

    class LoRALinear(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.base = base
            self.rank = rank
            self.scaling = alpha / rank
            in_features, out_features = base.in_features, base.out_features
            self.lora_a = nn.Parameter(torch.empty(rank, in_features, dtype=base.weight.dtype))
            self.lora_b = nn.Parameter(
                torch.zeros(out_features, rank, dtype=base.weight.dtype)
            )
            generator = torch.Generator(device="cpu").manual_seed(seed)
            bound = 1.0 / math.sqrt(in_features)
            with torch.no_grad():
                self.lora_a.uniform_(-bound, bound, generator=generator)
            self.dropout = nn.Dropout(dropout) if dropout > 0 else nn.Identity()
            for parameter in self.base.parameters():
                parameter.requires_grad_(False)

        def forward(self, x):  # noqa: ANN001, ANN202 - torch signature
            delta = self.dropout(x) @ self.lora_a.T @ self.lora_b.T
            return self.base(x) + delta * self.scaling

    wrapper = LoRALinear()
    return wrapper.to(base.weight.device)


def inject_lora(model: Any, recipe: dict[str, Any] | None = None) -> list[str]:
    """Freeze the base and replace every targeted projection with a LoRA wrapper.

    Returns the sorted names of the adapted modules. Because `lora_b` starts at
    exactly zero, the adapted model is numerically identical to the base until
    the first optimizer step.
    """
    recipe = recipe if recipe is not None else load_recipe()
    geometry = recipe["geometry"]
    seed = recipe["training"]["seed"]

    for parameter in model.parameters():
        parameter.requires_grad_(False)

    names = resolve_target_names(
        (name for name, _ in model.named_modules()), geometry["target_module_suffixes"]
    )
    if not names:
        raise AdapterError(
            f"no modules matched {geometry['target_module_suffixes']}; the base architecture "
            "does not look like the frozen encoder-decoder"
        )

    for index, name in enumerate(names):
        parent_path, _, attribute = name.rpartition(".")
        parent = model.get_submodule(parent_path) if parent_path else model
        base = getattr(parent, attribute)
        if not hasattr(base, "in_features"):
            raise AdapterError(f"{name}: targeted module is not a linear projection")
        setattr(
            parent,
            attribute,
            make_lora_linear(
                base,
                rank=geometry["rank"],
                alpha=geometry["alpha"],
                dropout=geometry["dropout"],
                # Per-module seed offset keeps injection order-independent.
                seed=seed + index,
            ),
        )
    return names


def trainable_parameters(model: Any) -> list[tuple[str, Any]]:
    return [(name, p) for name, p in model.named_parameters() if p.requires_grad]


def adapter_state_dict(model: Any) -> dict[str, Any]:
    """Only the LoRA tensors -- never the frozen base."""
    return {
        name: parameter.detach().clone()
        for name, parameter in model.named_parameters()
        if name.endswith(("lora_a", "lora_b"))
    }


def save_adapter(model: Any, path: Path, recipe: dict[str, Any], extra: dict[str, Any] | None = None) -> Path:
    torch = _torch()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "autocorrect-lora-v1",
        "recipe_id": recipe["recipe_id"],
        "base_model_id": recipe["base"]["model_id"],
        "base_revision": recipe["base"]["revision"],
        "rank": recipe["geometry"]["rank"],
        "alpha": recipe["geometry"]["alpha"],
        "tensors": adapter_state_dict(model),
        "meta": extra or {},
    }
    torch.save(payload, path)
    return path


def load_adapter(model: Any, path: Path, recipe: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load LoRA tensors into an already-injected model, failing closed on drift."""
    torch = _torch()
    recipe = recipe if recipe is not None else load_recipe()
    payload = torch.load(Path(path), map_location="cpu", weights_only=False)
    if payload.get("format") != "autocorrect-lora-v1":
        raise AdapterError(f"{path}: unexpected adapter format {payload.get('format')!r}")
    if payload.get("recipe_id") != recipe["recipe_id"]:
        raise AdapterError(
            f"{path}: adapter was trained under recipe {payload.get('recipe_id')!r}, "
            f"not {recipe['recipe_id']!r}"
        )
    if payload.get("rank") != recipe["geometry"]["rank"]:
        raise AdapterError(f"{path}: adapter rank does not match the frozen recipe")
    current = adapter_state_dict(model)
    missing = sorted(set(current) - set(payload["tensors"]))
    extra = sorted(set(payload["tensors"]) - set(current))
    if missing or extra:
        raise AdapterError(f"{path}: tensor mismatch missing={missing} extra={extra}")
    with torch.no_grad():
        for name, parameter in model.named_parameters():
            if name in payload["tensors"]:
                parameter.copy_(payload["tensors"][name])
    return payload.get("meta", {})


def encode_batch(tokenizer: Any, examples: Sequence[dict[str, Any]], recipe: dict[str, Any]) -> dict[str, Any]:
    """Tokenize one batch, refusing to silently truncate an over-length row."""
    torch = _torch()
    data = recipe["data"]
    max_source, max_target = data["max_source_tokens"], data["max_target_tokens"]

    sources = [example["source"] for example in examples]
    targets = [example["target"] for example in examples]
    encoded = tokenizer(sources, padding=True, return_tensors="pt")
    labels = tokenizer(targets, padding=True, return_tensors="pt")

    if encoded["input_ids"].shape[1] > max_source:
        raise AdapterError(
            f"batch exceeds max_source_tokens={max_source}; truncation_policy is 'error'"
        )
    if labels["input_ids"].shape[1] > max_target:
        raise AdapterError(
            f"batch exceeds max_target_tokens={max_target}; truncation_policy is 'error'"
        )

    label_ids = labels["input_ids"].clone()
    label_ids[labels["attention_mask"] == 0] = data["label_padding_ignore_index"]
    return {
        "input_ids": encoded["input_ids"],
        "attention_mask": encoded["attention_mask"],
        "labels": label_ids,
    }


def training_step(model: Any, batch: dict[str, Any], optimizer: Any, recipe: dict[str, Any]) -> float:
    """One forward/backward/clip/step. Returns the scalar loss."""
    torch = _torch()
    model.train()
    optimizer.zero_grad(set_to_none=True)
    output = model(**batch)
    loss = output.loss
    loss.backward()
    torch.nn.utils.clip_grad_norm_(
        [p for _, p in trainable_parameters(model)], recipe["optimizer"]["max_grad_norm"]
    )
    optimizer.step()
    return float(loss.detach())


def make_optimizer(model: Any, recipe: dict[str, Any]) -> Any:
    torch = _torch()
    spec = recipe["optimizer"]
    if spec["name"] != "adamw":
        raise AdapterError(f"unsupported optimizer {spec['name']!r}")
    return torch.optim.AdamW(
        [p for _, p in trainable_parameters(model)],
        lr=spec["learning_rate"],
        betas=tuple(spec["betas"]),
        eps=spec["eps"],
        weight_decay=spec["weight_decay"],
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class GPULock:
    """Cooperative cross-process GPU lock, compatible with TinyGPTIO/GPULock.swift.

    Same path and JSON shape as the Swift implementation so the two coordinate.
    Acquisition uses O_CREAT|O_EXCL, which is atomic, and a lock whose PID is
    no longer alive is cleared rather than inherited.
    """

    def __init__(self, command: str):
        self.command = command
        self.path = Path.home() / ".cache" / "posttrainllm" / "gpu.lock"
        self.acquired = False

    @staticmethod
    def _alive(pid: int) -> bool:
        import os  # noqa: PLC0415

        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def __enter__(self) -> "GPULock":
        import datetime as _dt  # noqa: PLC0415
        import os  # noqa: PLC0415

        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                held = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                held = None
            if held and self._alive(int(held.get("pid", -1))):
                raise AdapterError(
                    f"GPU lock held by PID {held.get('pid')} running "
                    f"{held.get('command')!r} since {held.get('startedAt')}"
                )
            self.path.unlink(missing_ok=True)

        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError as exc:
            raise AdapterError(f"GPU lock raced at {self.path}") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": os.getpid(),
                    "command": self.command,
                    "startedAt": _dt.datetime.now(_dt.timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
                handle,
            )
        self.acquired = True
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False


def resolve_device(recipe: dict[str, Any]) -> str:
    torch = _torch()
    for preference in recipe["training"]["device_preference"]:
        if preference == "mps" and torch.backends.mps.is_available():
            return "mps"
        if preference == "cuda" and torch.cuda.is_available():
            return "cuda"
        if preference == "cpu":
            return "cpu"
    return "cpu"


def greedy_predict(
    model: Any,
    tokenizer: Any,
    examples: Sequence[dict[str, Any]],
    recipe: dict[str, Any],
    device: str,
) -> list[str]:
    """Greedy decode with the frozen generation settings from the bake-off."""
    torch = _torch()
    bakeoff = json.loads((FIXTURE_DIR / "base-bakeoff-v1.json").read_text(encoding="utf-8"))
    generation = bakeoff["selection"]["frozen_generation"]

    model.eval()
    predictions: list[str] = []
    with torch.no_grad():
        for example in examples:
            encoded = tokenizer([example["source"]], return_tensors="pt").to(device)
            output = model.generate(
                **encoded,
                do_sample=generation["do_sample"],
                num_beams=generation["num_beams"],
                max_new_tokens=generation["max_new_tokens"],
            )
            predictions.append(tokenizer.decode(output[0], skip_special_tokens=True))
    return predictions


def evaluate_stage(
    model: Any,
    tokenizer: Any,
    stage: str,
    recipe: dict[str, Any],
    device: str,
    examples: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """Score a stage the way its frozen gate says it must be scored.

    `tiny_overfit` is a memorization gate, so it is scored on its own rows.
    `pilot` is scored on the untouched frozen eval fixture through the shared
    foundation evaluator -- the same code path the base bake-off used.
    """
    if stage == "tiny_overfit":
        predictions = greedy_predict(model, tokenizer, examples, recipe, device)
        exact = sum(
            prediction == example["target"]
            for prediction, example in zip(predictions, examples)
        ) / len(examples)
        return {"exact_match": exact, "predictions": predictions}

    foundation = _foundation()
    fixture_rows = foundation.load_jsonl(FIXTURE_DIR / "eval-v1.jsonl")
    template = recipe["base"]["prompt_template"]
    prompted = [
        {"source": template.format(text=row["noisy"]), "target": row["clean"]}
        for row in fixture_rows
    ]
    predictions = greedy_predict(model, tokenizer, prompted, recipe, device)
    report = foundation.evaluate(
        fixture_rows,
        [
            {"id": row["id"], "prediction": prediction}
            for row, prediction in zip(fixture_rows, predictions)
        ],
    )
    overall = report["overall"]
    return {
        "exact_match": overall["exact_match_rate"],
        "error_reduction_rate": overall["error_reduction_rate"],
        "clean_byte_exact_preservation_rate": overall["clean_byte_exact_preservation_rate"],
        "unnecessary_edit_rate": overall["unnecessary_edit_rate"],
        "protected_span_preservation_rate": overall["protected_span_preservation_rate"],
        "residual_character_error_rate": overall["residual_character_error_rate"],
        "foundation_report": report,
        "predictions": predictions,
    }


def run_stage(
    stage: str,
    recipe: dict[str, Any] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute one frozen training stage. Callers must already hold the GPU lock."""
    import resource as _resource  # noqa: PLC0415
    import time as _time  # noqa: PLC0415

    torch = _torch()
    recipe = recipe if recipe is not None else load_recipe()
    from transformers import AutoTokenizer, T5ForConditionalGeneration  # noqa: PLC0415

    plan = build_plan(stage, recipe)
    examples = build_examples(stage, recipe)
    # The pilot manifest records a train/development split on purpose; honour it
    # rather than training on the monitoring rows.
    train_rows = (
        [row for row in examples if row["split"] == "train"]
        if stage == "pilot"
        else examples
    )
    dev_rows = [row for row in examples if row["split"] == "development"]
    if not train_rows:
        raise AdapterError(f"{stage}: no train-split rows to train on")
    training = recipe["training"]
    device = resolve_device(recipe)
    output_dir = Path(output_dir or ROOT / "runs" / f"autocorrect-{stage.replace('_', '-')}-v1")
    output_dir.mkdir(parents=True, exist_ok=True)

    local_dir = str(Path(recipe["base"]["local_dir"]))
    tokenizer = AutoTokenizer.from_pretrained(local_dir)
    torch.manual_seed(training["seed"])
    model = T5ForConditionalGeneration.from_pretrained(local_dir, dtype=torch.float32)
    inject_lora(model, recipe)
    model.to(device)
    optimizer = make_optimizer(model, recipe)

    stop = StopRuleState(recipe, stage)
    generator = torch.Generator().manual_seed(training["seed"])
    batch_size = training["batch_size"]
    total_steps = plan["total_steps"]
    checkpoints = set(plan["checkpoint_steps"])

    history: list[dict[str, Any]] = []
    evaluations: list[dict[str, Any]] = []
    best = {"step": 0, "exact_match": -1.0}
    started = _time.time()
    order: list[int] = []
    step = 0

    while step < total_steps and not stop.stopped:
        if len(order) < batch_size:
            order += torch.randperm(len(train_rows), generator=generator).tolist()
        picked = [train_rows[i] for i in order[:batch_size]]
        order = order[batch_size:]

        batch = encode_batch(tokenizer, picked, recipe)
        batch = {key: value.to(device) for key, value in batch.items()}
        for group in optimizer.param_groups:
            group["lr"] = learning_rate_at(step, total_steps, recipe)

        loss = training_step(model, batch, optimizer, recipe)
        step += 1
        if step % training["log_every_steps"] == 0 or step == 1:
            history.append({"step": step, "loss": loss, "lr": optimizer.param_groups[0]["lr"]})
        if stop.observe_loss(step, loss):
            break
        if stop.observe_wall_time((_time.time() - started) / 60.0):
            break

        if step % training["eval_every_steps"] == 0 or step in checkpoints:
            scored = evaluate_stage(model, tokenizer, stage, recipe, device, examples)
            exact = scored["exact_match"]
            entry = {
                "step": step,
                "loss": loss,
                **{k: v for k, v in scored.items()
                   if k not in ("predictions", "foundation_report")},
            }
            if stage == "pilot" and dev_rows:
                dev_predictions = greedy_predict(model, tokenizer, dev_rows, recipe, device)
                entry["development_exact_match"] = sum(
                    prediction == row["target"]
                    for prediction, row in zip(dev_predictions, dev_rows)
                ) / len(dev_rows)
            evaluations.append(entry)
            summary = "  ".join(
                f"{key} {value:.3f}"
                for key, value in entry.items()
                if isinstance(value, (int, float)) and key not in ("step",)
            )
            print(f"  step {step:>3}  {summary}", flush=True)

            if exact > best["exact_match"]:
                best = {"step": step, "exact_match": exact}
                save_adapter(model, output_dir / "adapter-best.pt", recipe,
                             extra={"stage": stage, "step": step, "exact_match": exact})
            if stop.observe_eval(step, entry):
                break
            if stage == "tiny_overfit" and exact >= recipe["gates"]["tiny_overfit"]["exact_match_min"]:
                break

    final = evaluate_stage(model, tokenizer, stage, recipe, device, examples)
    predictions = final["predictions"]
    final_exact = final["exact_match"]
    save_adapter(model, output_dir / "adapter-last.pt", recipe,
                 extra={"stage": stage, "step": step, "exact_match": final_exact})

    if stage == "tiny_overfit":
        stop.finish_tiny_overfit(final_exact)

    elapsed_minutes = (_time.time() - started) / 60.0
    report = {
        "schema_version": 1,
        "stage": stage,
        "recipe_id": recipe["recipe_id"],
        "base_model_id": recipe["base"]["model_id"],
        "base_revision": recipe["base"]["revision"],
        "dataset_sha256": recipe["data"][stage]["dataset_sha256"],
        "rows": len(examples),
        "device": device,
        "torch": torch.__version__,
        "steps_taken": step,
        "step_budget": total_steps,
        "wall_time_minutes": round(elapsed_minutes, 3),
        "peak_rss_mib": round(
            _resource.getrusage(_resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024), 3
        ),
        "trainable_parameters": sum(p.numel() for _, p in trainable_parameters(model)),
        "first_loss": history[0]["loss"] if history else None,
        "final_loss": history[-1]["loss"] if history else None,
        "loss_history": history,
        "evaluations": evaluations,
        "best": best,
        "final_exact_match": final_exact,
        "final_metrics": {
            key: value
            for key, value in final.items()
            if key not in ("predictions", "foundation_report")
        },
        "stop_rule_triggered": stop.triggered,
        "stop_rule_detail": stop.detail,
        "decision": stop.decision(),
    }

    if stage == "tiny_overfit":
        bar = recipe["gates"]["tiny_overfit"]["exact_match_min"]
        report["evaluated_on"] = "its own training rows (memorization gate)"
        report["gate"] = {"exact_match_min": bar, "passed": final_exact >= bar}
        report["predictions"] = [
            {
                "id": example["id"],
                "error_family": example["error_family"],
                "noisy_source": example["source"],
                "target": example["target"],
                "prediction": prediction,
                "exact_match": prediction == example["target"],
            }
            for example, prediction in zip(examples, predictions)
        ]
    else:
        foundation = _foundation()
        fixture_rows = foundation.load_jsonl(FIXTURE_DIR / "eval-v1.jsonl")
        bakeoff = json.loads(
            (FIXTURE_DIR / "base-bakeoff-v1.json").read_text(encoding="utf-8")
        )
        zero_shot = bakeoff["selection"]["baseline_quality"]
        thresholds = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
        report["evaluated_on"] = "evals/autocorrect/eval-v1.jsonl (frozen, unchanged)"
        report["train_rows"] = len(train_rows)
        report["development_rows"] = len(dev_rows)
        report["split_note"] = (
            "Trained on the manifest's train split only; the development rows were "
            "monitored, never trained on."
        )
        report["foundation_report"] = final["foundation_report"]
        report["comparator_zero_shot"] = zero_shot
        report["delta_vs_zero_shot"] = {
            key: round(report["final_metrics"][key] - zero_shot[key], 6)
            for key in (
                "error_reduction_rate",
                "exact_match_rate" if "exact_match_rate" in report["final_metrics"] else "exact_match",
                "clean_byte_exact_preservation_rate",
                "protected_span_preservation_rate",
            )
            if key in report["final_metrics"] and key in zero_shot
        }
        report["threshold_comparison"] = {
            "natural_error_reduction_rate_min": thresholds["quality"][
                "natural_error_reduction_rate_min"
            ],
            "clean_byte_exact_preservation_min": thresholds["regression"][
                "clean_byte_exact_preservation_min"
            ],
            "protected_span_preservation_min": thresholds["regression"][
                "protected_span_preservation_min"
            ],
            "unnecessary_edit_rate_max": thresholds["regression"]["unnecessary_edit_rate_max"],
        }
        report["gate"] = {
            "passed": None,
            "note": (
                "A pilot has no single pass bar. Task 5.5 reads these slices to decide "
                "whether an edit-aware objective is justified; ship gates are 7.x."
            ),
        }
        report["predictions"] = [
            {
                "id": row["id"],
                "slices": row["slices"],
                "noisy": row["noisy"],
                "clean": row["clean"],
                "prediction": prediction,
                "exact_match": prediction == row["clean"],
            }
            for row, prediction in zip(fixture_rows, predictions)
        ]
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def verify_base(recipe: dict[str, Any] | None = None) -> dict[str, Any]:
    """Load-parity check against the real selected base, on CPU, forward only.

    This loads the pinned FLAN-T5-small checkpoint once and proves that
    injecting the adapter leaves the logits bit-identical and freezes every
    base tensor. It runs no optimizer step and never touches the GPU lock.
    """
    torch = _torch()
    recipe = recipe if recipe is not None else load_recipe()
    local_dir = Path(recipe["base"]["local_dir"])
    if not local_dir.exists():
        raise AdapterError(f"the pinned base is not present at {local_dir}")

    from transformers import AutoTokenizer, T5ForConditionalGeneration  # noqa: PLC0415

    tokenizer = AutoTokenizer.from_pretrained(str(local_dir))
    model = T5ForConditionalGeneration.from_pretrained(
        str(local_dir), dtype=torch.float32
    ).eval()
    base_parameters = sum(p.numel() for p in model.parameters())

    examples = build_examples("tiny_overfit", recipe)[:4]
    batch = encode_batch(tokenizer, examples, recipe)

    with torch.no_grad():
        before = model(**batch).logits.clone()
    base_snapshot = {name: p.detach().clone() for name, p in model.named_parameters()}

    names = inject_lora(model, recipe)
    with torch.no_grad():
        after = model(**batch).logits

    trainable = trainable_parameters(model)
    moved = [
        name
        for name, p in model.named_parameters()
        if name in base_snapshot and not torch.equal(base_snapshot[name], p)
    ]
    return {
        "base_model_id": recipe["base"]["model_id"],
        "base_revision": recipe["base"]["revision"],
        "base_parameters": base_parameters,
        "adapted_modules": len(names),
        "trainable_parameters": sum(p.numel() for _, p in trainable),
        "trainable_fraction": round(
            sum(p.numel() for _, p in trainable) / base_parameters, 6
        ),
        "logits_bit_identical": bool(torch.equal(before, after)),
        "max_absolute_logit_delta": float((before - after).abs().max()),
        "base_tensors_modified": moved,
        "all_trainable_are_lora": all(
            name.endswith(("lora_a", "lora_b")) for name, _ in trainable
        ),
        "torch": torch.__version__,
        "device": "cpu",
        "optimizer_steps_taken": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check the frozen recipe against every other artifact")
    sub.add_parser(
        "verify-base", help="forward-only load parity against the real pinned base (needs torch)"
    )
    plan_parser = sub.add_parser("plan", help="print the resolved, unexecuted training plan")
    plan_parser.add_argument("--stage", choices=STAGES, default="tiny_overfit")
    sub.add_parser("selftest", help="run the offline adapter checks (needs torch)")
    train_parser = sub.add_parser("train", help="refuses without explicit operator approval")
    train_parser.add_argument("--stage", choices=STAGES, default="tiny_overfit")
    train_parser.add_argument("--i-have-operator-approval", action="store_true")
    train_parser.add_argument("--output-dir", type=Path, default=None)

    args = parser.parse_args(argv)

    if args.command == "validate":
        problems = validate_recipe()
        for problem in problems:
            print(f"FAIL {problem}")
        if problems:
            print(f"\n{len(problems)} problem(s)")
            return 1
        print("autocorrect adapter recipe: consistent")
        return 0

    if args.command == "plan":
        print(json.dumps(build_plan(args.stage), indent=2))
        return 0

    if args.command == "verify-base":
        report = verify_base()
        print(json.dumps(report, indent=2))
        ok = (
            report["logits_bit_identical"]
            and not report["base_tensors_modified"]
            and report["all_trainable_are_lora"]
        )
        return 0 if ok else 1

    if args.command == "selftest":
        test_path = ROOT / "tests" / "test_autocorrect_adapter.py"
        spec = importlib.util.spec_from_file_location("test_autocorrect_adapter", test_path)
        if not spec or not spec.loader:
            raise AdapterError(f"cannot load {test_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.main()

    if args.command == "train":
        if not args.i_have_operator_approval:
            print(
                "REFUSED: training the autocorrect adapter needs explicit owner approval and "
                "the GPU lock (~/.cache/posttrainllm/gpu.lock).\n"
                "Tasks 5.3-5.4 of build-mac-local-autocorrect-specialist are still gated.\n"
                "Re-run with --i-have-operator-approval once approval is recorded."
            )
            return 2

        problems = validate_recipe()
        if problems:
            for problem in problems:
                print(f"FAIL {problem}")
            return 1

        recipe = load_recipe()
        if recipe.get("status") == "retired":
            print(
                f"REFUSED: recipe {recipe['recipe_id']} is retired.\n"
                f"  {recipe.get('retired_reason', '')}\n"
                "Known defects that a successor must fix first:"
            )
            for defect in recipe.get("known_defects", []):
                print(f"  - [{defect['id']}] {defect.get('fix_for_v2', defect['statement'])}")
            print("Freeze a new recipe version instead of training under this one.")
            return 5

        with GPULock(f"autocorrect_adapter train --stage {args.stage}"):
            report = run_stage(args.stage, output_dir=args.output_dir)

        skip = {"loss_history", "predictions", "foundation_report"}
        print(json.dumps({k: v for k, v in report.items() if k not in skip}, indent=2))
        passed = report["gate"]["passed"]
        return 0 if passed is not False else 4

    return 1  # pragma: no cover - argparse enforces a command


if __name__ == "__main__":
    raise SystemExit(main())
