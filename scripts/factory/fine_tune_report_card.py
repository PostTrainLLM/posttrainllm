#!/usr/bin/env python3
"""Fine-Tune Report Card schema, validation, and static rendering.

This module is the canonical Python side of the report-card contract described
in `docs/factory/report-card.md`. It is deliberately:

- **offline** — no model load, training, generation, eval, registry, or network
  call happens anywhere in this file;
- **deterministic** — no wall-clock timestamp, no live `git` invocation, and no
  randomness enters a payload, so recompiling the same sources byte-for-byte
  reproduces the same JSON and the same HTML;
- **fail-closed** — a value that cannot be traced to a source artifact is
  recorded as `missing`/`skipped`, never inferred, defaulted, or zero-filled.

The typed Swift mirror lives in
`native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift`. Keep the two in sync;
`evals/fine-tune-report-card-smoke.sh` compiles the Swift decoder against the
JSON this module emits so the contracts cannot silently diverge.
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

# ---------------------------------------------------------------------------
# Contract identity
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1
COMPILER = "scripts/factory/build_fine_tune_report_card.py"
COMPILER_VERSION = "1.0.0"

GITHUB_BLOB = "https://github.com/PostTrainLLM/posttrainllm/blob/main"

# ---------------------------------------------------------------------------
# Measurement states
# ---------------------------------------------------------------------------

#: Every numeric or categorical observation in a report card carries one of
#: these states. `null` alone cannot distinguish skipped work, a legacy import,
#: an unavailable hardware metric, and an inapplicable check.
MEASUREMENT_STATES = (
    "measured",
    "derived",
    "historical",
    "skipped",
    "missing",
    "not-applicable",
)

#: States that MUST carry a value and at least one source.
VALUED_STATES = ("measured", "derived", "historical")

#: States that MUST carry `value: null` and an explanatory note.
UNVALUED_STATES = ("skipped", "missing", "not-applicable")

#: States whose provenance is weaker than a current measurement. A ship
#: decision leaning on one of these cannot be labeled fully verified.
WEAK_STATES = ("historical", "skipped", "missing")

# ---------------------------------------------------------------------------
# Decision + outcome vocabulary
# ---------------------------------------------------------------------------

#: Canonical factory decisions. Mirrors `FactoryRun.Decision` and
#: `check_factory_run_publish.ALLOWED_DECISIONS`.
DECISIONS = ("ship", "reject", "retry-data", "retry-training", "retry-eval", "park")

#: Mirrors `check_factory_run_publish.ALLOWED_CONFIDENCE`.
CONFIDENCES = ("exact", "inferred", "missing-evidence", "not-applicable")

#: Public outcome labels. `shipped-specialist` and `routed-ship` are the only
#: labels that may appear on a `ship` decision; nothing else may read as
#: shipped.
OUTCOME_LABELS = ("shipped-specialist", "routed-ship", "report-only", "rejected")

SHIP_LABELS = ("shipped-specialist", "routed-ship")

GATE_ROLES = ("primary", "regression", "breadth")

#: Field names that must never appear in a public report card. A report card is
#: a proof surface, not a data dump: prompts, completions, golds, predictions,
#: weights, and credentials stay in the private run folder.
DENYLISTED_KEYS = (
    "prompt",
    "prompts",
    "completion",
    "completions",
    "gold",
    "golds",
    "prediction",
    "predictions",
    "weights",
    "weights_bytes",
    "adapter_bytes",
    "optimizer_state",
    "checkpoint",
    "api_key",
    "secret",
    "password",
    "credential",
)


class ReportCardError(ValueError):
    """Raised when a report card cannot be compiled from its sources."""


# ---------------------------------------------------------------------------
# Measurement-state field constructors
# ---------------------------------------------------------------------------


def _field(
    state: str,
    value: Any,
    sources: Sequence[str] | None,
    unit: str | None,
    note: str | None,
    derived_from: Sequence[str] | None = None,
) -> dict[str, Any]:
    field: dict[str, Any] = {"state": state, "value": value}
    if unit is not None:
        field["unit"] = unit
    field["sources"] = list(sources or [])
    if derived_from is not None:
        field["derived_from"] = list(derived_from)
    if note is not None:
        field["note"] = note
    return field


def measured(
    value: Any,
    sources: Sequence[str],
    unit: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """A value read directly out of a source artifact."""
    return _field("measured", value, sources, unit, note)


def derived(
    value: Any,
    derived_from: Sequence[str],
    sources: Sequence[str] | None = None,
    unit: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """A value computed from other recorded fields (e.g. a delta)."""
    return _field("derived", value, sources or derived_from, unit, note, derived_from)


def historical(
    value: Any,
    sources: Sequence[str],
    note: str,
    unit: str | None = None,
) -> dict[str, Any]:
    """A legacy value that lacks current canonical run provenance."""
    return _field("historical", value, sources, unit, note)


def skipped(note: str, sources: Sequence[str] | None = None) -> dict[str, Any]:
    """Work that was deliberately not done for this run."""
    return _field("skipped", None, sources, None, note)


def missing(note: str, sources: Sequence[str] | None = None) -> dict[str, Any]:
    """Evidence that should exist but does not. Never rendered as a number."""
    return _field("missing", None, sources, None, note)


def not_applicable(note: str, sources: Sequence[str] | None = None) -> dict[str, Any]:
    """A check that does not apply to this candidate."""
    return _field("not-applicable", None, sources, None, note)


def has_value(field: Any) -> bool:
    """True when `field` is a field wrapper carrying a usable value."""
    return (
        isinstance(field, dict)
        and field.get("state") in VALUED_STATES
        and field.get("value") is not None
    )


def field_value(field: Any) -> Any:
    return field.get("value") if isinstance(field, dict) else None


def is_weak(field: Any) -> bool:
    """True when the field's provenance is weaker than a current measurement."""
    return isinstance(field, dict) and field.get("state") in WEAK_STATES


def delta_field(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    baseline_source: str,
    candidate_source: str,
    unit: str | None = None,
) -> dict[str, Any]:
    """Derive `candidate - baseline`, or record why it cannot be derived.

    A delta is never zero-filled: if either side lacks a value the delta is
    `missing`, because "no change measured" and "change not measurable" are
    different claims.
    """
    if not (has_value(baseline) and has_value(candidate)):
        absent = []
        if not has_value(baseline):
            absent.append("baseline")
        if not has_value(candidate):
            absent.append("candidate")
        return missing(
            "Delta cannot be derived: "
            + " and ".join(absent)
            + " has no recorded value. No change is implied.",
            sources=[baseline_source, candidate_source],
        )
    value = round(float(candidate["value"]) - float(baseline["value"]), 6)
    note = None
    if is_weak(baseline) or is_weak(candidate):
        note = (
            "Derived from at least one non-current value; inherits the weaker "
            "provenance of its inputs."
        )
    return derived(
        value,
        derived_from=[baseline_source, candidate_source],
        unit=unit,
        note=note,
    )


# ---------------------------------------------------------------------------
# Hashing helpers (content provenance; no git, no clock)
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Derivation: outcome label and verification status
# ---------------------------------------------------------------------------


def outcome_label(decision: str, routing_constraint: Any) -> str:
    """Map a canonical decision onto a public outcome label.

    Only a `ship` decision may produce a ship-shaped label, and a ship that is
    safe for a named route reads as `routed-ship`, never as a general
    replacement.
    """
    if decision == "ship":
        return "routed-ship" if has_value(routing_constraint) else "shipped-specialist"
    if decision == "reject":
        return "rejected"
    return "report-only"


def verification_blockers(card: dict[str, Any]) -> list[str]:
    """List every reason this card cannot present a *fully verified* ship.

    An empty list means the ship decision is traceable end to end: a current
    measured primary gate, a frontier-validated benchmark, frozen-eval
    identity, a passing leakage check, and no open blockers.
    """
    blockers: list[str] = []
    decision = card.get("decision", {})
    if decision.get("decision") != "ship":
        blockers.append(
            f"Decision is `{decision.get('decision')}`, not `ship`; "
            "verification applies to ship claims only."
        )

    primary = primary_gate(card)
    if primary is None:
        blockers.append("No primary gate is recorded.")
    else:
        for key in ("baseline", "candidate", "threshold", "passed"):
            field = primary.get(key)
            if not has_value(field):
                blockers.append(
                    f"Primary gate `{primary.get('name')}` has no {key} value "
                    f"(state `{(field or {}).get('state')}`)."
                )
            elif is_weak(field):
                blockers.append(
                    f"Primary gate `{primary.get('name')}` {key} is "
                    f"`{field.get('state')}`, not a current measurement."
                )
        # Recording the failure as *measured* is not the same as passing it. A
        # candidate that missed its own target gate can never be a verified ship.
        if has_value(primary.get("passed")) and field_value(primary["passed"]) is False:
            blockers.append(
                f"Primary gate `{primary.get('name')}` did not pass; the "
                "candidate missed its own target."
            )
        ceiling = primary.get("frontier_ceiling")
        if not has_value(ceiling):
            blockers.append(
                f"Primary gate `{primary.get('name')}` has no frontier-ceiling "
                "evidence, so the eval is unverified as a ruler."
            )
        elif not _ceiling_passes(field_value(ceiling)):
            blockers.append(
                f"Primary gate `{primary.get('name')}` frontier ceiling is "
                f"{field_value(ceiling)}; the benchmark does not pass the "
                "frontier-ceiling gate."
            )

    validity = card.get("eval_validity", {})
    frozen = validity.get("frozen_eval")
    if not has_value(frozen) or is_weak(frozen):
        blockers.append(
            "Frozen-eval identity is not recorded as a current measurement."
        )
    leakage = validity.get("leakage")
    if not has_value(leakage) or is_weak(leakage):
        blockers.append(
            "Train/eval overlap (leakage) was not checked with current evidence."
        )
    elif field_value(leakage) != "no-overlap":
        blockers.append(f"Leakage check reports `{field_value(leakage)}`.")

    for blocker in decision.get("blocked_by") or []:
        blockers.append(f"Open blocker: {blocker}")

    return blockers


def _ceiling_passes(value: Any) -> bool:
    """A benchmark passes the frontier-ceiling gate when frontier ~aces it."""
    if isinstance(value, bool):
        return value
    try:
        return float(value) >= 0.99
    except (TypeError, ValueError):
        return False


def primary_gate(card: dict[str, Any]) -> dict[str, Any] | None:
    for gate in card.get("gates") or []:
        if gate.get("role") == "primary":
            return gate
    return None


def failing_gates(card: dict[str, Any], roles: Iterable[str]) -> list[dict[str, Any]]:
    """Gates in `roles` recorded as failing. A `missing` result is not a pass."""
    roles = tuple(roles)
    out = []
    for gate in card.get("gates") or []:
        if gate.get("role") not in roles:
            continue
        passed = gate.get("passed")
        if has_value(passed) and field_value(passed) is False:
            out.append(gate)
    return out


def finalize(card: dict[str, Any]) -> dict[str, Any]:
    """Fill the derived decision fields and return the completed card."""
    routing = card.get("subject", {}).get("artifact", {}).get("routing_constraint")
    decision = card["decision"]
    decision["outcome_label"] = outcome_label(decision["decision"], routing)
    blockers = verification_blockers(card)
    decision["verified"] = not blockers
    decision["verification_blockers"] = blockers
    return card


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_field(field: Any, path: str, errors: list[str]) -> None:
    if not isinstance(field, dict):
        errors.append(f"{path}: must be a measurement-state object")
        return
    state = field.get("state")
    if state not in MEASUREMENT_STATES:
        errors.append(f"{path}.state must be one of {list(MEASUREMENT_STATES)}")
        return
    sources = field.get("sources")
    if not isinstance(sources, list):
        errors.append(f"{path}.sources must be a list")
        sources = []
    note = field.get("note")
    if state in VALUED_STATES:
        if field.get("value") is None:
            errors.append(f"{path}: state `{state}` requires a non-null value")
        elif not isinstance(field["value"], (int, float, str, bool)):
            # The Swift mirror decodes this as number | string | bool. A list or
            # object here would emit a card the typed contract cannot read.
            errors.append(
                f"{path}.value must be a number, string, or boolean, not "
                f"{type(field['value']).__name__}"
            )
        if not sources:
            errors.append(f"{path}: state `{state}` requires at least one source")
        if state == "historical" and not (note and str(note).strip()):
            errors.append(
                f"{path}: state `historical` requires a note recording the caveat"
            )
        if state == "derived":
            if not field.get("derived_from"):
                errors.append(f"{path}: state `derived` requires derived_from")
    else:
        if field.get("value") is not None:
            errors.append(
                f"{path}: state `{state}` must carry value null, not "
                f"{field.get('value')!r}"
            )
        if not (note and str(note).strip()):
            errors.append(f"{path}: state `{state}` requires an explanatory note")


def _denylist_scan(node: Any, path: str, errors: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = str(key).lower()
            if any(
                lowered == bad or lowered.endswith("_" + bad)
                for bad in DENYLISTED_KEYS
            ):
                errors.append(f"{path}.{key}: denylisted private field name")
            _denylist_scan(value, f"{path}.{key}", errors)
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            _denylist_scan(value, f"{path}[{idx}]", errors)


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _as_number(value: Any) -> float | None:
    """Coerce a JSON number, refusing bools and numeric-looking strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _check_delta(holder: dict[str, Any], path: str, errors: list[str]) -> None:
    """A recorded delta must equal `candidate - baseline`.

    Applies to gates and slices alike: this is what blocks a hand-typed number
    that contradicts the measurements it claims to summarize.
    """
    delta, base, cand = holder.get("delta"), holder.get("baseline"), holder.get("candidate")
    if not (has_value(delta) and has_value(base) and has_value(cand)):
        return
    delta_n, base_n, cand_n = (
        _as_number(field_value(delta)),
        _as_number(field_value(base)),
        _as_number(field_value(cand)),
    )
    if delta_n is None or base_n is None or cand_n is None:
        errors.append(
            f"{path}: baseline, candidate, and delta must be numbers to be "
            "comparable"
        )
        return
    expected = round(cand_n - base_n, 6)
    if abs(delta_n - expected) > 1e-6:
        errors.append(
            f"{path}.delta {field_value(delta)} does not equal candidate - "
            f"baseline ({expected})"
        )


def _nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def validate(card: Any, allow_report_only: bool = False) -> list[str]:
    """Validate a report card payload. Returns a list of failures (empty = ok).

    `allow_report_only=True` permits non-ship cards with open blockers. Ship
    claims stay strict in both modes.
    """
    errors: list[str] = []
    if not isinstance(card, dict):
        return ["report card must be a JSON object"]

    # --- contract identity -------------------------------------------------
    _require(
        card.get("schema_version") == SCHEMA_VERSION,
        f"schema_version must be {SCHEMA_VERSION}",
        errors,
    )
    _require(_nonempty(card.get("report_card_id")), "report_card_id is required", errors)
    _require(_nonempty(card.get("title")), "title is required", errors)

    compiled = card.get("compiled_from")
    if not isinstance(compiled, dict):
        errors.append("compiled_from is required")
        compiled = {}
    _require(_nonempty(compiled.get("compiler")), "compiled_from.compiler is required", errors)
    _require(
        _nonempty(compiled.get("compiler_version")),
        "compiled_from.compiler_version is required",
        errors,
    )
    _require(
        compiled.get("source_kind") in ("factory-run", "specialist-package"),
        "compiled_from.source_kind must be factory-run or specialist-package",
        errors,
    )
    _require(_nonempty(compiled.get("source_id")), "compiled_from.source_id is required", errors)
    for idx, entry in enumerate(compiled.get("dataset_hashes") or []):
        _require(
            _nonempty(entry.get("path")),
            f"compiled_from.dataset_hashes[{idx}].path is required",
            errors,
        )
        _require(
            len(str(entry.get("sha256") or "")) == 64,
            f"compiled_from.dataset_hashes[{idx}].sha256 must be a sha256 hex digest",
            errors,
        )
        # The Swift mirror types this as `Int?`. Letting a string through here
        # would emit a card the typed contract cannot decode.
        rows = entry.get("rows")
        _require(
            rows is None or (isinstance(rows, int) and not isinstance(rows, bool)),
            f"compiled_from.dataset_hashes[{idx}].rows must be an integer or null",
            errors,
        )

    # --- subject -----------------------------------------------------------
    subject = card.get("subject")
    if not isinstance(subject, dict):
        errors.append("subject is required")
        subject = {}
    for key in ("target", "owner_goal", "base_model", "candidate_model", "method"):
        validate_field(subject.get(key), f"subject.{key}", errors)
    artifact = subject.get("artifact")
    if not isinstance(artifact, dict):
        errors.append("subject.artifact is required")
        artifact = {}
    else:
        _require(
            _nonempty(artifact.get("artifact_id")),
            "subject.artifact.artifact_id is required",
            errors,
        )
        _require(_nonempty(artifact.get("kind")), "subject.artifact.kind is required", errors)
        _require(
            isinstance(artifact.get("shipped"), bool),
            "subject.artifact.shipped must be a boolean",
            errors,
        )
        validate_field(artifact.get("routing_constraint"), "subject.artifact.routing_constraint", errors)

    # --- decision ----------------------------------------------------------
    decision = card.get("decision")
    if not isinstance(decision, dict):
        errors.append("decision is required")
        decision = {}
    value = decision.get("decision")
    _require(value in DECISIONS, f"decision.decision must be one of {list(DECISIONS)}", errors)
    label = decision.get("outcome_label")
    _require(
        label in OUTCOME_LABELS,
        f"decision.outcome_label must be one of {list(OUTCOME_LABELS)}",
        errors,
    )
    if value != "ship" and label in SHIP_LABELS:
        errors.append(
            f"decision.outcome_label `{label}` claims a ship for decision `{value}`"
        )
    if value == "ship" and label not in SHIP_LABELS:
        errors.append(f"decision.outcome_label `{label}` does not reflect a ship decision")
    _require(_nonempty(decision.get("reason")), "decision.reason is required", errors)
    _require(
        decision.get("failure_reason_confidence") in CONFIDENCES,
        f"decision.failure_reason_confidence must be one of {list(CONFIDENCES)}",
        errors,
    )
    if value == "ship":
        _require(
            decision.get("failure_reason_confidence") == "not-applicable",
            "ship decision must use failure_reason_confidence=not-applicable",
            errors,
        )
    elif value is not None:
        _require(
            _nonempty(decision.get("failure_reason")),
            "non-ship decision.failure_reason is required",
            errors,
        )
        _require(_nonempty(decision.get("lesson")), "non-ship decision.lesson is required", errors)
        _require(
            decision.get("failure_reason_confidence") != "not-applicable",
            "non-ship decision requires a real failure_reason_confidence",
            errors,
        )
    validate_field(decision.get("next_action"), "decision.next_action", errors)
    _require(
        isinstance(decision.get("evidence_sources"), list)
        and bool(decision.get("evidence_sources")),
        "decision.evidence_sources must be a non-empty list",
        errors,
    )
    _require(
        isinstance(decision.get("blocked_by"), list),
        "decision.blocked_by must be a list",
        errors,
    )
    _require(
        isinstance(decision.get("verified"), bool),
        "decision.verified must be a boolean",
        errors,
    )
    blockers = decision.get("verification_blockers")
    if not isinstance(blockers, list):
        errors.append("decision.verification_blockers must be a list")
        blockers = []
    if decision.get("verified") and blockers:
        errors.append("decision.verified=true contradicts a non-empty verification_blockers")
    if decision.get("verified") is False and not blockers:
        errors.append("decision.verified=false requires at least one verification blocker")
    # Self-consistency is not enough: a hand-edited or third-party payload could
    # claim `verified: true` with an empty blocker list. Recompute from the
    # evidence and reject any disagreement, so the gate never takes the
    # payload's word for its own verification status.
    gates_well_formed = isinstance(card.get("gates"), list) and all(
        isinstance(gate, dict) for gate in card["gates"]
    )
    if gates_well_formed and isinstance(card.get("eval_validity"), dict):
        recomputed = verification_blockers(card)
        if bool(decision.get("verified")) != (not recomputed):
            errors.append(
                "decision.verified does not match the evidence: recomputing gives "
                f"verified={not recomputed} with {len(recomputed)} blocker(s)"
            )
        elif set(recomputed) != set(blockers or []):
            errors.append(
                "decision.verification_blockers does not match the evidence; "
                f"recomputing gives: {sorted(recomputed)}"
            )

    # --- gates -------------------------------------------------------------
    gates = card.get("gates")
    if not isinstance(gates, list) or not gates:
        errors.append("gates must be a non-empty list")
        gates = []
    roles = [gate.get("role") for gate in gates if isinstance(gate, dict)]
    _require(roles.count("primary") == 1, "exactly one gate must have role `primary`", errors)
    for idx, gate in enumerate(gates):
        path = f"gates[{idx}]"
        if not isinstance(gate, dict):
            errors.append(f"{path}: must be an object")
            continue
        _require(gate.get("role") in GATE_ROLES, f"{path}.role must be one of {list(GATE_ROLES)}", errors)
        _require(_nonempty(gate.get("name")), f"{path}.name is required", errors)
        _require(_nonempty(gate.get("metric")), f"{path}.metric is required", errors)
        for key in (
            "baseline",
            "candidate",
            "delta",
            "threshold",
            "passed",
            "sample_size",
            "frontier_ceiling",
        ):
            validate_field(gate.get(key), f"{path}.{key}", errors)
        identity = gate.get("eval_identity")
        if not isinstance(identity, dict):
            errors.append(f"{path}.eval_identity is required")
        else:
            _require(_nonempty(identity.get("suite")), f"{path}.eval_identity.suite is required", errors)
            for key in ("command", "date", "frozen"):
                validate_field(identity.get(key), f"{path}.eval_identity.{key}", errors)
        _check_delta(gate, path, errors)

    # --- slices ------------------------------------------------------------
    slices = card.get("slices")
    if not isinstance(slices, list):
        errors.append("slices must be a list")
        slices = []
    for idx, item in enumerate(slices):
        path = f"slices[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{path}: must be an object")
            continue
        _require(_nonempty(item.get("name")), f"{path}.name is required", errors)
        _require(_nonempty(item.get("metric")), f"{path}.metric is required", errors)
        for key in ("baseline", "candidate", "delta", "passed", "sample_size"):
            validate_field(item.get(key), f"{path}.{key}", errors)
        # Slices get the same delta consistency check as gates: a per-slice
        # number is just as publishable, so it is just as fabricable.
        _check_delta(item, path, errors)

    # --- performance -------------------------------------------------------
    performance = card.get("performance")
    if not isinstance(performance, dict):
        errors.append("performance is required")
    else:
        for key in PERFORMANCE_FIELDS:
            validate_field(performance.get(key), f"performance.{key}", errors)

    # --- eval validity -----------------------------------------------------
    validity = card.get("eval_validity")
    if not isinstance(validity, dict):
        errors.append("eval_validity is required")
    else:
        for key in ("frontier_ceiling", "frozen_eval", "leakage"):
            validate_field(validity.get(key), f"eval_validity.{key}", errors)
        _require(
            isinstance(validity.get("known_limitations"), list),
            "eval_validity.known_limitations must be a list",
            errors,
        )
        leak = validity.get("leakage")
        if has_value(leak) and field_value(leak) not in ("no-overlap", "overlap-detected"):
            errors.append(
                "eval_validity.leakage value must be `no-overlap` or `overlap-detected`"
            )

    # --- evidence + caveats ------------------------------------------------
    evidence = card.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        errors.append("evidence must be a non-empty list")
        evidence = []
    for idx, item in enumerate(evidence):
        path = f"evidence[{idx}]"
        if not isinstance(item, dict):
            errors.append(f"{path}: must be an object")
            continue
        _require(_nonempty(item.get("label")), f"{path}.label is required", errors)
        _require(_nonempty(item.get("path")), f"{path}.path is required", errors)
        _require(_nonempty(item.get("kind")), f"{path}.kind is required", errors)
    _require(isinstance(card.get("caveats"), list), "caveats must be a list", errors)

    # --- public-safety ------------------------------------------------------
    _denylist_scan(card, "report_card", errors)

    # --- publication policy -------------------------------------------------
    errors.extend(_publication_errors(card, allow_report_only))
    return errors


def _publication_errors(card: dict[str, Any], allow_report_only: bool) -> list[str]:
    errors: list[str] = []
    decision = card.get("decision") or {}
    artifact = (card.get("subject") or {}).get("artifact") or {}
    value = decision.get("decision")
    validity = card.get("eval_validity") or {}

    # Leakage that was actually detected fails publication outright, but the
    # measured candidate numbers stay in the payload rather than being hidden.
    leak = validity.get("leakage")
    if has_value(leak) and field_value(leak) == "overlap-detected":
        detail = (leak.get("note") or "").strip()
        errors.append(
            "leakage check reports overlap-detected; publication is blocked"
            + (f" ({detail})" if detail else "")
        )

    if value == "ship":
        if not artifact.get("shipped"):
            errors.append("ship decision requires subject.artifact.shipped=true")
        if not _nonempty(artifact.get("package_dir")):
            errors.append("ship decision requires subject.artifact.package_dir")
        if decision.get("blocked_by"):
            errors.append("ship decision must not have open blockers")
        primary = primary_gate(card)
        if primary is None or not has_value(primary.get("baseline")) or not has_value(
            primary.get("candidate")
        ):
            errors.append(
                "ship decision requires a primary gate with baseline and candidate "
                "values; an incomplete ship claim fails closed"
            )
        elif failing_gates(card, ("primary",)):
            errors.append(
                f"ship decision whose primary gate `{primary.get('name')}` is "
                "recorded as failing cannot publish: the candidate missed its own "
                "target"
            )
        # A ship whose regression/breadth gate fails is not an unconditional
        # win: it may only publish with an explicit routing constraint.
        regressed = failing_gates(card, ("regression", "breadth"))
        if regressed and not has_value(artifact.get("routing_constraint")):
            names = ", ".join(str(g.get("name")) for g in regressed)
            errors.append(
                f"ship decision with failing gate(s) [{names}] requires "
                "subject.artifact.routing_constraint disclosing the safe envelope"
            )
        if decision.get("verified") and decision.get("verification_blockers"):
            errors.append("ship decision claims verified while blockers remain")
    else:
        if artifact.get("shipped"):
            errors.append(
                f"decision `{value}` must not carry subject.artifact.shipped=true"
            )
        # A non-ship decision is only honest when it names the one thing to do
        # next; a ship may legitimately have nothing left to do.
        if not has_value(decision.get("next_action")):
            errors.append(
                f"decision `{value}` requires exactly one next action with a value"
            )
        if not allow_report_only and decision.get("blocked_by"):
            errors.append(
                f"decision `{value}` has open blockers; pass --allow-report-only to "
                "publish it as a report-only artifact"
            )
    return errors


PERFORMANCE_FIELDS = (
    "latency_ms",
    "peak_rss_mb",
    "tokens_per_second",
    "training_time_seconds",
    "training_cost_usd",
    "eval_time_seconds",
)

PERFORMANCE_LABELS = {
    "latency_ms": "Latency",
    "peak_rss_mb": "RAM / peak RSS",
    "tokens_per_second": "Decode throughput",
    "training_time_seconds": "Training time",
    "training_cost_usd": "Training cost",
    "eval_time_seconds": "Eval time",
}


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def dumps(card: dict[str, Any]) -> str:
    """Deterministic JSON: sorted keys, stable indent, trailing newline."""
    return json.dumps(card, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Static rendering
# ---------------------------------------------------------------------------

STATE_LABELS = {
    "measured": "measured",
    "derived": "derived",
    "historical": "historical",
    "skipped": "skipped",
    # "not recorded" rather than "not measured": the same label has to read
    # correctly for an absent number *and* an absent text field.
    "missing": "not recorded",
    "not-applicable": "not applicable",
}

STATE_LEGEND = (
    ("measured", "Read directly from a source artifact for this candidate."),
    ("derived", "Computed from other recorded values (for example a delta)."),
    (
        "historical",
        "Imported from a legacy record without current canonical provenance. "
        "Treat as weaker than a measurement.",
    ),
    ("skipped", "Deliberately not run for this candidate."),
    ("missing", "Evidence should exist but does not. No number is implied."),
    ("not-applicable", "The check does not apply to this candidate."),
)

DECISION_HEADLINE = {
    "ship": "Shipped",
    "reject": "Rejected",
    "retry-data": "Retry — data",
    "retry-training": "Retry — training",
    "retry-eval": "Retry — eval",
    "park": "Parked",
}

OUTCOME_HEADLINE = {
    "shipped-specialist": "Shipped specialist",
    "routed-ship": "Shipped for a named route only",
    "report-only": "Report-only artifact — no model to use",
    "rejected": "Rejected candidate",
}


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _num(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        # Fixed 4dp, matching report.md and FactoryRun.markdownReport(), so a
        # column of scores lines up instead of mixing 1.0000 with 0.7.
        return f"{value:.4f}"
    return str(value)


def _link_for(path: str) -> str | None:
    """Turn a recorded evidence path into a public URL where one exists."""
    if path.startswith(("http://", "https://")):
        return path
    if path.startswith("hf://models/"):
        return "https://huggingface.co/" + path[len("hf://models/") :]
    if path.startswith("hf://datasets/"):
        return "https://huggingface.co/datasets/" + path[len("hf://datasets/") :]
    if path.startswith("runs/"):
        # Local run folders are gitignored: there is nothing public to link to.
        return None
    if "#" in path:
        base, anchor = path.split("#", 1)
        return f"{GITHUB_BLOB}/{base}#{anchor}"
    return f"{GITHUB_BLOB}/{path}"


def render_field(field: Any, unit_suffix: bool = True) -> str:
    """Render one measurement-state field as accessible HTML.

    The state is always emitted as text, never as colour alone, so a value with
    weak provenance cannot read like a current measurement.
    """
    if not isinstance(field, dict):
        return '<span class="v-missing">—</span>'
    state = field.get("state", "missing")
    label = STATE_LABELS.get(state, state)
    note = field.get("note")
    if state in VALUED_STATES and field.get("value") is not None:
        text = _num(field["value"])
        unit = field.get("unit")
        if unit and unit_suffix:
            text = f"{text} {unit}"
        body = f'<span class="v-value">{_esc(text)}</span>'
        if state != "measured":
            body += f' <span class="state" data-state="{_esc(state)}">{_esc(label)}</span>'
    else:
        body = (
            f'<span class="v-absent">—</span> '
            f'<span class="state" data-state="{_esc(state)}">{_esc(label)}</span>'
        )
    if note:
        body += f'<span class="note">{_esc(note)}</span>'
    return body


def _sources_cell(field: Any) -> str:
    if not isinstance(field, dict):
        return "—"
    sources = field.get("sources") or []
    if not sources:
        return "—"
    return ", ".join(f"<code>{_esc(s)}</code>" for s in sources)


def render_html(card: dict[str, Any], canonical_url: str | None = None) -> str:
    """Render the deterministic, self-contained public report page.

    The page is rendered from the same validated payload as the JSON, has no
    runtime dependency, and stays readable without repository access.
    """
    decision = card["decision"]
    subject = card["subject"]
    artifact = subject["artifact"]
    validity = card["eval_validity"]
    label = decision["outcome_label"]

    out: list[str] = []
    w = out.append

    title = f"Fine-Tune Report Card — {card['title']}"
    summary = (
        f"{DECISION_HEADLINE.get(decision['decision'], decision['decision'])}: "
        f"{decision['reason']}"
    )
    meta_summary = summary
    if len(meta_summary) > 160:
        meta_summary = meta_summary[:157].rsplit(" ", 1)[0].rstrip() + "…"

    w("<!doctype html>")
    w('<html lang="en">')
    w("<head>")
    w('<meta charset="utf-8">')
    w('<meta name="viewport" content="width=device-width, initial-scale=1">')
    w(f"<title>{_esc(title)}</title>")
    w(f'<meta name="description" content="{_esc(meta_summary)}">')
    if canonical_url:
        structured_data = json.dumps(
            {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": title,
                "description": meta_summary,
                "url": canonical_url,
                "isPartOf": {
                    "@type": "WebSite",
                    "name": "posttrainllm",
                    "url": "https://posttrainllm.com",
                },
                "about": {
                    "@type": "SoftwareSourceCode",
                    "name": card["title"],
                    "codeRepository": "https://github.com/PostTrainLLM/posttrainllm",
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).replace("<", "\\u003c")
        w(f'<link rel="canonical" href="{_esc(canonical_url)}">')
        w('<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1">')
        w('<meta property="og:type" content="article">')
        w('<meta property="og:site_name" content="posttrainllm">')
        w(f'<meta property="og:url" content="{_esc(canonical_url)}">')
        w(f'<meta property="og:title" content="{_esc(title)}">')
        w(f'<meta property="og:description" content="{_esc(meta_summary)}">')
        w('<meta property="og:image" content="https://posttrainllm.com/og-image.png">')
        w('<meta name="twitter:card" content="summary_large_image">')
        w(f'<meta name="twitter:title" content="{_esc(title)}">')
        w(f'<meta name="twitter:description" content="{_esc(meta_summary)}">')
        w('<meta name="twitter:image" content="https://posttrainllm.com/og-image.png">')
        w(f'<script type="application/ld+json">{structured_data}</script>')
    w(f"<style>{_CSS}</style>")
    w("</head>")
    w("<body>")
    w('<a class="skip-link" href="#main">Skip to content</a>')
    w('<main id="main">')

    # --- header ------------------------------------------------------------
    w("<header>")
    w(
        '<p class="eyebrow">posttrainllm fine-tune report card '
        f'· schema v{card["schema_version"]} · compiler {_esc(card["compiled_from"]["compiler_version"])}</p>'
    )
    w(f"<h1>{_esc(card['title'])}</h1>")
    w(f'<p class="lede">{render_field(subject["owner_goal"])}</p>')
    w('<dl class="ident">')
    for key, heading in (
        ("target", "Target"),
        ("base_model", "Base model"),
        ("candidate_model", "Candidate"),
        ("method", "Method"),
    ):
        w(f"<div><dt>{_esc(heading)}</dt><dd>{render_field(subject[key])}</dd></div>")
    w(
        "<div><dt>Compiled from</dt><dd>"
        f"<code>{_esc(card['compiled_from']['source_id'])}</code> "
        f"({_esc(card['compiled_from']['source_kind'])})</dd></div>"
    )
    w("</dl>")
    w("</header>")

    # --- decision ----------------------------------------------------------
    w('<section id="decision" aria-labelledby="decision-h">')
    w('<h2 id="decision-h">Decision</h2>')
    w(f'<p class="verdict" data-decision="{_esc(decision["decision"])}">')
    w(
        f'<strong>{_esc(DECISION_HEADLINE.get(decision["decision"], decision["decision"]))}</strong>'
        f' <span class="chip">{_esc(OUTCOME_HEADLINE.get(label, label))}</span>'
    )
    w("</p>")
    w(f"<p>{_esc(decision['reason'])}</p>")

    if has_value(artifact.get("routing_constraint")):
        w('<div class="callout" role="note">')
        w("<h3>Routing constraint</h3>")
        w(f"<p>{render_field(artifact['routing_constraint'])}</p>")
        w(
            "<p>This candidate is safe only inside that envelope. It is not a "
            "general replacement for the base model.</p>"
        )
        w("</div>")

    w('<h3 id="verification-h">Verification status</h3>')
    if decision["verified"]:
        w(
            '<p class="verified" data-verified="true">Fully verified: the ship '
            "decision traces to a current measured primary gate, a "
            "frontier-validated benchmark, frozen-eval identity, and a passing "
            "leakage check.</p>"
        )
    else:
        w(
            '<p class="verified" data-verified="false">Not fully verified. This '
            "report does not claim a verified ship. Reasons:</p>"
        )
        w('<ul class="blockers">')
        for blocker in decision["verification_blockers"]:
            w(f"<li>{_esc(blocker)}</li>")
        w("</ul>")

    w('<dl class="ident">')
    w(
        "<div><dt>Failure reason</dt><dd>"
        f"{_esc(decision.get('failure_reason') or 'Not applicable')}</dd></div>"
    )
    w(
        "<div><dt>Failure-reason confidence</dt><dd>"
        f"{_esc(decision.get('failure_reason_confidence'))}</dd></div>"
    )
    w(
        "<div><dt>Lesson</dt><dd>"
        f"{_esc(decision.get('lesson') or 'Not recorded')}</dd></div>"
    )
    w("</dl>")

    if decision.get("blocked_by"):
        w("<h3>Open blockers</h3>")
        w("<ul>")
        for blocker in decision["blocked_by"]:
            w(f"<li>{_esc(blocker)}</li>")
        w("</ul>")

    w("<h3>Next action</h3>")
    w(f'<p class="next-action">{render_field(decision["next_action"])}</p>')
    w("</section>")

    # --- gates -------------------------------------------------------------
    w('<section id="gates" aria-labelledby="gates-h">')
    w('<h2 id="gates-h">Before and after</h2>')
    regressed = failing_gates(card, ("regression", "breadth"))
    if regressed:
        w('<p class="warn" role="note">')
        w(
            "This candidate does not present an unconditional win: "
            + _esc(
                ", ".join(str(g.get("name")) for g in regressed)
            )
            + " failed. Target and regression gates are reported independently below."
        )
        w("</p>")
    w('<div class="table-wrap">')
    w("<table>")
    w(
        "<caption>Every gate with baseline, candidate, derived delta, threshold, "
        "result, sample size, and frontier-ceiling evidence.</caption>"
    )
    w("<thead><tr>")
    for heading in (
        "Gate",
        "Role",
        "Metric",
        "Baseline",
        "Candidate",
        "Delta",
        "Threshold",
        "Result",
        "n",
        "Frontier ceiling",
    ):
        w(f'<th scope="col">{_esc(heading)}</th>')
    w("</tr></thead>")
    w("<tbody>")
    for gate in card["gates"]:
        w("<tr>")
        w(f'<th scope="row">{_esc(gate["name"])}</th>')
        w(f'<td>{_esc(gate["role"])}</td>')
        w(f'<td>{_esc(gate["metric"])}</td>')
        for key in ("baseline", "candidate", "delta", "threshold", "passed", "sample_size", "frontier_ceiling"):
            w(f"<td>{render_field(gate[key])}</td>")
        w("</tr>")
    w("</tbody>")
    w("</table>")
    w("</div>")

    w("<h3>Eval identity</h3>")
    w('<div class="table-wrap">')
    w("<table>")
    w("<caption>Which suite produced each gate, how it was invoked, and whether it is frozen.</caption>")
    w("<thead><tr>")
    for heading in ("Gate", "Suite", "Command", "Date", "Frozen"):
        w(f'<th scope="col">{_esc(heading)}</th>')
    w("</tr></thead>")
    w("<tbody>")
    for gate in card["gates"]:
        identity = gate["eval_identity"]
        w("<tr>")
        w(f'<th scope="row">{_esc(gate["name"])}</th>')
        w(f'<td>{_esc(identity["suite"])}</td>')
        w(f"<td>{render_field(identity['command'])}</td>")
        w(f"<td>{render_field(identity['date'])}</td>")
        w(f"<td>{render_field(identity['frozen'])}</td>")
        w("</tr>")
    w("</tbody>")
    w("</table>")
    w("</div>")
    w("</section>")

    # --- slices ------------------------------------------------------------
    w('<section id="slices" aria-labelledby="slices-h">')
    w('<h2 id="slices-h">Per-slice evidence</h2>')
    if card["slices"]:
        w('<div class="table-wrap">')
        w("<table>")
        w("<caption>Primary metric broken down by task slice, so an overall win cannot hide a weak slice.</caption>")
        w("<thead><tr>")
        for heading in ("Slice", "Metric", "Baseline", "Candidate", "Delta", "Result", "n"):
            w(f'<th scope="col">{_esc(heading)}</th>')
        w("</tr></thead>")
        w("<tbody>")
        for item in card["slices"]:
            w("<tr>")
            w(f'<th scope="row">{_esc(item["name"])}</th>')
            w(f'<td>{_esc(item["metric"])}</td>')
            for key in ("baseline", "candidate", "delta", "passed", "sample_size"):
                w(f"<td>{render_field(item[key])}</td>")
            w("</tr>")
        w("</tbody>")
        w("</table>")
        w("</div>")
    else:
        w("<p>No slice evidence was recorded for this candidate.</p>")
    w("</section>")

    # --- performance -------------------------------------------------------
    w('<section id="performance" aria-labelledby="performance-h">')
    w('<h2 id="performance-h">Cost and performance</h2>')
    w('<div class="table-wrap">')
    w("<table>")
    w(
        "<caption>Latency, memory, throughput, and training cost/time. Absent "
        "evidence is reported as not measured, never as zero.</caption>"
    )
    w('<thead><tr><th scope="col">Metric</th><th scope="col">Value</th><th scope="col">Source</th></tr></thead>')
    w("<tbody>")
    for key in PERFORMANCE_FIELDS:
        field = card["performance"][key]
        w("<tr>")
        w(f'<th scope="row">{_esc(PERFORMANCE_LABELS[key])}</th>')
        w(f"<td>{render_field(field)}</td>")
        w(f"<td>{_sources_cell(field)}</td>")
        w("</tr>")
    w("</tbody>")
    w("</table>")
    w("</div>")
    w("</section>")

    # --- eval validity -----------------------------------------------------
    w('<section id="eval-validity" aria-labelledby="validity-h">')
    w('<h2 id="validity-h">Eval validity and leakage</h2>')
    w('<div class="table-wrap">')
    w("<table>")
    w(
        "<caption>Whether the benchmark is a trustworthy ruler: frontier "
        "ceiling, frozen-eval identity, and train/eval overlap.</caption>"
    )
    w('<thead><tr><th scope="col">Check</th><th scope="col">Result</th><th scope="col">Source</th></tr></thead>')
    w("<tbody>")
    for key, heading in (
        ("frontier_ceiling", "Frontier ceiling"),
        ("frozen_eval", "Frozen eval"),
        ("leakage", "Train/eval overlap"),
    ):
        field = validity[key]
        w("<tr>")
        w(f'<th scope="row">{_esc(heading)}</th>')
        w(f"<td>{render_field(field)}</td>")
        w(f"<td>{_sources_cell(field)}</td>")
        w("</tr>")
    w("</tbody>")
    w("</table>")
    w("</div>")
    if validity["known_limitations"]:
        w("<h3>Known eval limitations</h3>")
        w("<ul>")
        for item in validity["known_limitations"]:
            w(f"<li>{_esc(item)}</li>")
        w("</ul>")
    w("</section>")

    # --- caveats -----------------------------------------------------------
    w('<section id="caveats" aria-labelledby="caveats-h">')
    w('<h2 id="caveats-h">Caveats</h2>')
    if card["caveats"]:
        w("<ul>")
        for item in card["caveats"]:
            w(f"<li>{_esc(item)}</li>")
        w("</ul>")
    else:
        w("<p>No additional caveats were recorded.</p>")
    w("</section>")

    # --- evidence ----------------------------------------------------------
    w('<section id="evidence" aria-labelledby="evidence-h">')
    w('<h2 id="evidence-h">Source evidence</h2>')
    w(
        "<p>Every number above traces to one of these artifacts. Content "
        "hashes are recorded where the source file is committed.</p>"
    )
    w("<ul class=\"evidence\">")
    for item in card["evidence"]:
        href = _link_for(item["path"])
        name = (
            f'<a href="{_esc(href)}">{_esc(item["label"])}</a>'
            if href
            else _esc(item["label"])
        )
        detail = f"<code>{_esc(item['path'])}</code> · {_esc(item['kind'])}"
        if item.get("sha256"):
            detail += f' · sha256 <code>{_esc(item["sha256"][:16])}…</code>'
        if item.get("note"):
            detail += f" · {_esc(item['note'])}"
        w(f"<li>{name}<span class=\"detail\">{detail}</span></li>")
    w("</ul>")
    hashes = card["compiled_from"].get("dataset_hashes") or []
    if hashes:
        w("<h3>Dataset hashes</h3>")
        w('<div class="table-wrap">')
        w("<table>")
        w("<caption>SHA-256 of each dataset the run recorded, for independent reproduction.</caption>")
        w('<thead><tr><th scope="col">Dataset</th><th scope="col">Rows</th><th scope="col">SHA-256</th></tr></thead>')
        w("<tbody>")
        for entry in hashes:
            rows = entry.get("rows")
            w("<tr>")
            w(f'<th scope="row"><code>{_esc(entry["path"])}</code></th>')
            w(f"<td>{_esc(rows) if rows is not None else '—'}</td>")
            w(f'<td><code>{_esc(entry["sha256"])}</code></td>')
            w("</tr>")
        w("</tbody>")
        w("</table>")
        w("</div>")
    w("</section>")

    # --- legend ------------------------------------------------------------
    w('<section id="legend" aria-labelledby="legend-h">')
    w('<h2 id="legend-h">How to read the evidence states</h2>')
    w('<dl class="legend">')
    for state, meaning in STATE_LEGEND:
        w(
            f'<div><dt><span class="state" data-state="{_esc(state)}">'
            f'{_esc(STATE_LABELS[state])}</span></dt><dd>{_esc(meaning)}</dd></div>'
        )
    w("</dl>")
    w("</section>")

    w("<footer>")
    w(
        "<p>Compiled offline by <code>"
        f"{_esc(card['compiled_from']['compiler'])}</code> from recorded factory "
        "evidence. No model was loaded, trained, or evaluated to produce this "
        "page. Reproduce the factory loop with the "
        f'<a href="{GITHUB_BLOB}/docs/factory/report-card.md">report-card docs</a>.</p>'
    )
    w("</footer>")
    w("</main>")
    w("</body>")
    w("</html>")
    return "\n".join(out) + "\n"


_CSS = """
:root{--bg:#0a0c0f;--panel:#12161c;--line:#242c36;--ink:#e8edf4;--muted:#9aa7b8;
--ok:#5ad19b;--warn:#ffb454;--bad:#ff7b72;--chip:#1b2430}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:64rem;margin:0 auto;padding:2rem 1.25rem 4rem}
.skip-link{position:absolute;left:-9999px}
.skip-link:focus{left:1rem;top:1rem;z-index:9;background:var(--panel);
padding:.5rem .75rem;border:1px solid var(--line);border-radius:.375rem}
a{color:#8ab4ff}
a:focus-visible,[tabindex]:focus-visible{outline:2px solid #8ab4ff;outline-offset:2px}
h1{font-size:clamp(1.6rem,4vw,2.4rem);line-height:1.2;margin:.25rem 0 .75rem}
h2{font-size:1.3rem;margin:2.5rem 0 .75rem;padding-bottom:.35rem;
border-bottom:1px solid var(--line)}
h3{font-size:1.02rem;margin:1.5rem 0 .5rem;color:var(--muted);
text-transform:uppercase;letter-spacing:.06em}
.eyebrow{color:var(--muted);font-size:.8rem;text-transform:uppercase;
letter-spacing:.1em;margin:0}
.lede{font-size:1.08rem;color:#c9d4e2}
.ident{display:grid;gap:.5rem 1.5rem;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));
margin:1.25rem 0;padding:0}
.ident div{border-top:1px solid var(--line);padding-top:.5rem}
.ident dt{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.06em}
.ident dd{margin:.15rem 0 0}
.verdict{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center;font-size:1.2rem;
background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--muted);
border-radius:.5rem;padding:.85rem 1rem}
.verdict[data-decision="ship"]{border-left-color:var(--ok)}
.verdict[data-decision="reject"]{border-left-color:var(--bad)}
.verdict[data-decision^="retry"],.verdict[data-decision="park"]{border-left-color:var(--warn)}
.chip{background:var(--chip);border:1px solid var(--line);border-radius:999px;
padding:.15rem .6rem;font-size:.82rem;color:#c9d4e2}
.callout,.warn{background:var(--panel);border:1px solid var(--line);
border-left:4px solid var(--warn);border-radius:.5rem;padding:.75rem 1rem;margin:1.25rem 0}
.callout h3{margin-top:0}
.verified[data-verified="false"]{color:var(--warn)}
.verified[data-verified="true"]{color:var(--ok)}
.blockers li{margin:.3rem 0}
.next-action{background:var(--panel);border:1px solid var(--line);
border-radius:.5rem;padding:.75rem 1rem}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:.5rem;margin:1rem 0}
table{border-collapse:collapse;width:100%;font-size:.9rem}
caption{caption-side:top;text-align:left;color:var(--muted);font-size:.82rem;
padding:.6rem .75rem;border-bottom:1px solid var(--line)}
th,td{padding:.5rem .75rem;text-align:left;vertical-align:top;
border-bottom:1px solid var(--line)}
thead th{background:var(--panel);color:var(--muted);font-size:.78rem;
text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
tbody tr:last-child th,tbody tr:last-child td{border-bottom:0}
tbody th[scope=row]{font-weight:600}
code{font:.86em ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--chip);
border-radius:.25rem;padding:.05rem .3rem;word-break:break-word}
.v-value{font-variant-numeric:tabular-nums;font-weight:600}
.v-absent,.v-missing{color:var(--muted)}
.state{display:inline-block;font-size:.72rem;text-transform:uppercase;
letter-spacing:.05em;border:1px solid var(--line);border-radius:999px;
padding:.05rem .45rem;color:var(--muted);white-space:nowrap}
.state[data-state="historical"],.state[data-state="skipped"]{color:var(--warn);
border-color:#4a3a1e}
.state[data-state="missing"]{color:var(--bad);border-color:#4a2422}
.note{display:block;color:var(--muted);font-size:.8rem;margin-top:.2rem}
.evidence{list-style:none;padding:0}
.evidence li{border-top:1px solid var(--line);padding:.6rem 0}
.detail{display:block;color:var(--muted);font-size:.82rem;margin-top:.2rem}
.legend{display:grid;gap:.6rem;padding:0;margin:1rem 0}
.legend div{display:grid;grid-template-columns:9rem 1fr;gap:.75rem;
border-top:1px solid var(--line);padding-top:.6rem}
.legend dd{margin:0;color:#c9d4e2}
footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--line);
color:var(--muted);font-size:.86rem}
@media (max-width:34rem){.legend div{grid-template-columns:1fr}}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
""".strip()
