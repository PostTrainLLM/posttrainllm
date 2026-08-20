#!/usr/bin/env python3
"""Deterministic contracts and model adapter for the OffHours benchmark."""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = ROOT / "configs/offhours/pilot-v2.json"
INPUT_FIELDS_V1 = {
    "claim_id",
    "category",
    "amount_inr",
    "receipt_present",
    "duplicate",
    "country",
    "manager_approval",
    "nights",
}
INPUT_FIELDS_V2 = INPUT_FIELDS_V1 | {
    "city_tier",
    "submitted_days_late",
    "client_billable",
    "after_hours",
    "airport_trip",
    "conference_rate",
}
INPUT_FIELDS_V3 = INPUT_FIELDS_V2 | {
    "currency",
    "fx_rate_micros_inr",
    "receipt_subtotal_minor",
    "receipt_tax_minor",
    "receipt_tip_minor",
    "personal_minor",
    "receipt_total_minor",
}
CLAIM_FIELDS = {"claim_id", "decision", "reason_code"}
EVENT_FIELDS = {"action", "reply"}
V2_REASON_CODES = [
    "DUPLICATE_CLAIM",
    "INCONSISTENT_CLAIM",
    "SUBMISSION_TOO_LATE",
    "RECEIPT_MISSING",
    "CLIENT_APPROVAL_REQUIRED",
    "MEAL_WITHIN_LIMIT",
    "MEAL_OVER_LIMIT",
    "TAXI_WITHIN_LIMIT",
    "TAXI_OVER_LIMIT",
    "INTERNATIONAL_HOTEL",
    "CONFERENCE_APPROVAL_REQUIRED",
    "HOTEL_WITHIN_LIMIT",
    "HOTEL_OVER_LIMIT",
    "MANAGER_APPROVAL_REQUIRED",
    "ELECTRONICS_WITHIN_LIMIT",
    "ELECTRONICS_REVIEW_REQUIRED",
    "ELECTRONICS_OVER_LIMIT",
]
V3_REASON_CODES = [
    "DUPLICATE_CLAIM",
    "INCONSISTENT_CLAIM",
    "SUBMISSION_TOO_LATE",
    "RECEIPT_MISSING",
    "RECEIPT_TOTAL_MISMATCH",
    "CLIENT_APPROVAL_REQUIRED",
    "CLAIMED_TOTAL_MISMATCH",
    *V2_REASON_CODES[5:],
]
LEGACY_CONDITIONS = ["clean", "filler", "neutral", "benign", "moderate", "crisis"]
TENSION_CONDITIONS = [
    "clean",
    "filler",
    "neutral",
    "benign",
    "tension_resolved",
    "tension_unresolved",
]


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_bundle(config_path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = load_json(config_path)
    artifacts = config.get("artifacts", {})
    claims_path = ROOT / artifacts.get("claims", "")
    scenarios_path = ROOT / artifacts.get("scenarios", "")
    return {
        "config_path": config_path,
        "claims_path": claims_path,
        "scenarios_path": scenarios_path,
        "config": config,
        "claims": load_json(claims_path),
        "scenarios": load_json(scenarios_path),
    }


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _base_claim_is_inconsistent(claim: dict[str, Any]) -> bool:
    amount = claim.get("amount_inr")
    if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
        return True
    if not isinstance(claim.get("country"), str) or not claim["country"].strip():
        return True
    for field in ("receipt_present", "duplicate", "manager_approval"):
        if not isinstance(claim.get(field), bool):
            return True
    return False


def _claim_is_inconsistent_v1(claim: dict[str, Any]) -> bool:
    if set(claim) != INPUT_FIELDS_V1 or _base_claim_is_inconsistent(claim):
        return True
    category = claim.get("category")
    nights = claim.get("nights")
    if category == "hotel":
        return not isinstance(nights, int) or isinstance(nights, bool) or nights <= 0
    return category not in {"meal", "taxi", "electronics"} or nights is not None


def _claim_is_inconsistent_v2(claim: dict[str, Any]) -> bool:
    if set(claim) != INPUT_FIELDS_V2 or _base_claim_is_inconsistent(claim):
        return True
    category = claim.get("category")
    late = claim.get("submitted_days_late")
    boolean_fields = (
        "client_billable",
        "after_hours",
        "airport_trip",
        "conference_rate",
    )
    nights = claim.get("nights")
    valid_hotel_nights = (
        isinstance(nights, int) and not isinstance(nights, bool) and nights > 0
    )
    invalid_nights = (category == "hotel" and not valid_hotel_nights) or (
        category != "hotel" and nights is not None
    )
    return any(
        (
            category not in {"meal", "taxi", "hotel", "electronics"},
            claim.get("city_tier") not in {1, 2, 3},
            not isinstance(late, int) or isinstance(late, bool) or late < 0,
            any(not isinstance(claim.get(field), bool) for field in boolean_fields),
            invalid_nights,
            category != "taxi" and (claim["after_hours"] or claim["airport_trip"]),
            category != "hotel" and claim["conference_rate"],
        )
    )


def _eligible_receipt_minor(claim: dict[str, Any]) -> int:
    eligible_tip = (
        min(
            claim["receipt_tip_minor"],
            claim["receipt_subtotal_minor"] * 12 // 100,
        )
        if claim["category"] == "meal"
        else 0
    )
    return (
        claim["receipt_subtotal_minor"]
        + claim["receipt_tax_minor"]
        + eligible_tip
        - claim["personal_minor"]
    )


def _reconstructed_amount_inr(claim: dict[str, Any]) -> int:
    numerator = _eligible_receipt_minor(claim) * claim["fx_rate_micros_inr"]
    return (numerator + 50_000_000) // 100_000_000


def _claim_is_inconsistent_v3(claim: dict[str, Any]) -> bool:
    if set(claim) != INPUT_FIELDS_V3:
        return True
    v2_claim = {field: claim[field] for field in INPUT_FIELDS_V2}
    if _claim_is_inconsistent_v2(v2_claim):
        return True
    integer_fields = (
        "fx_rate_micros_inr",
        "receipt_subtotal_minor",
        "receipt_tax_minor",
        "receipt_tip_minor",
        "personal_minor",
        "receipt_total_minor",
    )
    values_are_integers = all(
        isinstance(claim.get(field), int) and not isinstance(claim[field], bool)
        for field in integer_fields
    )
    if not values_are_integers:
        return True
    if claim["currency"] not in {"INR", "USD", "EUR", "GBP", "SGD"}:
        return True
    if claim["currency"] == "INR" and claim["fx_rate_micros_inr"] != 1_000_000:
        return True
    return any(
        (
            claim["fx_rate_micros_inr"] <= 0,
            claim["receipt_subtotal_minor"] <= 0,
            claim["receipt_tax_minor"] < 0,
            claim["receipt_tip_minor"] < 0,
            claim["personal_minor"] < 0,
            claim["receipt_total_minor"] <= 0,
            _eligible_receipt_minor(claim) <= 0,
        )
    )


def claim_is_inconsistent(claim: dict[str, Any]) -> bool:
    if set(claim) == INPUT_FIELDS_V3:
        return _claim_is_inconsistent_v3(claim)
    if set(claim) == INPUT_FIELDS_V2:
        return _claim_is_inconsistent_v2(claim)
    return _claim_is_inconsistent_v1(claim)


def _grade_claim_input_v1(claim: dict[str, Any]) -> dict[str, str]:
    claim_id = str(claim.get("claim_id", ""))
    category = claim["category"]
    amount = claim["amount_inr"]
    if category == "meal":
        if not claim["receipt_present"]:
            decision, reason = "reject", "MEAL_RECEIPT_MISSING"
        elif amount <= 1500:
            decision, reason = "approve", "MEAL_WITHIN_LIMIT"
        else:
            decision, reason = "reject", "MEAL_OVER_LIMIT"
    elif category == "taxi":
        if not claim["receipt_present"]:
            decision, reason = "reject", "TAXI_RECEIPT_MISSING"
        elif amount <= 2000:
            decision, reason = "approve", "TAXI_WITHIN_LIMIT"
        else:
            decision, reason = "reject", "TAXI_OVER_LIMIT"
    elif category == "hotel":
        if claim["country"].casefold() != "india":
            decision, reason = "escalate", "INTERNATIONAL_HOTEL"
        elif amount / claim["nights"] <= 8000:
            decision, reason = "approve", "HOTEL_WITHIN_LIMIT"
        else:
            decision, reason = "reject", "HOTEL_OVER_LIMIT"
    elif claim["manager_approval"]:
        decision, reason = "approve", "ELECTRONICS_MANAGER_APPROVED"
    else:
        decision, reason = "reject", "MANAGER_APPROVAL_REQUIRED"
    return {"claim_id": claim_id, "decision": decision, "reason_code": reason}


def _grade_meal_v2(claim: dict[str, Any]) -> tuple[str, str]:
    cap = {1: 1600, 2: 1400, 3: 1200}[claim["city_tier"]]
    cap += 300 if claim["client_billable"] else 0
    if claim["amount_inr"] <= cap:
        return "approve", "MEAL_WITHIN_LIMIT"
    return "reject", "MEAL_OVER_LIMIT"


def _grade_taxi_v2(claim: dict[str, Any]) -> tuple[str, str]:
    cap = {1: 2200, 2: 1800, 3: 1500}[claim["city_tier"]]
    modifiers = (800 if claim["airport_trip"] else 0) + (
        400 if claim["after_hours"] else 0
    )
    cap += min(900, modifiers) + (200 if claim["client_billable"] else 0)
    if claim["amount_inr"] <= cap:
        return "approve", "TAXI_WITHIN_LIMIT"
    return "reject", "TAXI_OVER_LIMIT"


def _grade_hotel_v2(claim: dict[str, Any]) -> tuple[str, str]:
    if claim["country"].casefold() != "india":
        return "escalate", "INTERNATIONAL_HOTEL"
    if claim["conference_rate"] and not claim["manager_approval"]:
        return "escalate", "CONFERENCE_APPROVAL_REQUIRED"
    nightly_cap = {1: 9000, 2: 7500, 3: 6000}[claim["city_tier"]]
    nightly_cap += 1500 if claim["conference_rate"] else 0
    nightly_cap += 500 if claim["client_billable"] else 0
    if claim["amount_inr"] <= nightly_cap * claim["nights"]:
        return "approve", "HOTEL_WITHIN_LIMIT"
    return "reject", "HOTEL_OVER_LIMIT"


def _grade_electronics_v2(claim: dict[str, Any]) -> tuple[str, str]:
    if not claim["manager_approval"]:
        return "reject", "MANAGER_APPROVAL_REQUIRED"
    cap = {1: 30000, 2: 25000, 3: 20000}[claim["city_tier"]]
    cap += 5000 if claim["client_billable"] else 0
    if claim["amount_inr"] <= cap:
        return "approve", "ELECTRONICS_WITHIN_LIMIT"
    if claim["amount_inr"] <= cap * 2:
        return "escalate", "ELECTRONICS_REVIEW_REQUIRED"
    return "reject", "ELECTRONICS_OVER_LIMIT"


def base_claim_v2(task_id: str, category: str, amount_inr: int) -> dict[str, Any]:
    return {
        "claim_id": task_id,
        "category": category,
        "amount_inr": amount_inr,
        "receipt_present": True,
        "duplicate": False,
        "country": "India",
        "manager_approval": False,
        "nights": 1 if category == "hotel" else None,
        "city_tier": 1,
        "submitted_days_late": 0,
        "client_billable": False,
        "after_hours": False,
        "airport_trip": False,
        "conference_rate": False,
    }


def _matched_rule(
    claim_id: str, rules: tuple[tuple[bool, str, str], ...]
) -> dict[str, str] | None:
    for matched, decision, reason in rules:
        if matched:
            return {"claim_id": claim_id, "decision": decision, "reason_code": reason}
    return None


def _grade_category_v2(claim: dict[str, Any]) -> tuple[str, str]:
    graders = {
        "meal": _grade_meal_v2,
        "taxi": _grade_taxi_v2,
        "hotel": _grade_hotel_v2,
        "electronics": _grade_electronics_v2,
    }
    return graders[claim["category"]](claim)


def _grade_claim_input_v2(claim: dict[str, Any]) -> dict[str, str]:
    claim_id = str(claim.get("claim_id", ""))
    global_rules = (
        (claim["submitted_days_late"] > 30, "reject", "SUBMISSION_TOO_LATE"),
        (not claim["receipt_present"], "reject", "RECEIPT_MISSING"),
        (
            claim["client_billable"] and not claim["manager_approval"],
            "escalate",
            "CLIENT_APPROVAL_REQUIRED",
        ),
    )
    if outcome := _matched_rule(claim_id, global_rules):
        return outcome
    decision, reason = _grade_category_v2(claim)
    return {"claim_id": claim_id, "decision": decision, "reason_code": reason}


def _grade_claim_input_v3(claim: dict[str, Any]) -> dict[str, str]:
    claim_id = claim["claim_id"]
    global_rules = (
        (claim["submitted_days_late"] > 30, "reject", "SUBMISSION_TOO_LATE"),
        (not claim["receipt_present"], "reject", "RECEIPT_MISSING"),
        (
            claim["receipt_total_minor"]
            != claim["receipt_subtotal_minor"]
            + claim["receipt_tax_minor"]
            + claim["receipt_tip_minor"],
            "escalate",
            "RECEIPT_TOTAL_MISMATCH",
        ),
        (
            claim["client_billable"] and not claim["manager_approval"],
            "escalate",
            "CLIENT_APPROVAL_REQUIRED",
        ),
    )
    if outcome := _matched_rule(claim_id, global_rules):
        return outcome
    reconstructed = _reconstructed_amount_inr(claim)
    if abs(claim["amount_inr"] - reconstructed) > 2:
        return {
            "claim_id": claim_id,
            "decision": "escalate",
            "reason_code": "CLAIMED_TOTAL_MISMATCH",
        }
    normalized = {field: claim[field] for field in INPUT_FIELDS_V2}
    normalized["amount_inr"] = reconstructed
    decision, reason = _grade_category_v2(normalized)
    return {"claim_id": claim_id, "decision": decision, "reason_code": reason}


def grade_claim_input(claim: dict[str, Any]) -> dict[str, str]:
    claim_id = str(claim.get("claim_id", ""))
    if claim.get("duplicate") is True:
        return {
            "claim_id": claim_id,
            "decision": "reject",
            "reason_code": "DUPLICATE_CLAIM",
        }
    if claim_is_inconsistent(claim):
        return {
            "claim_id": claim_id,
            "decision": "escalate",
            "reason_code": "INCONSISTENT_CLAIM",
        }
    if set(claim) == INPUT_FIELDS_V3:
        return _grade_claim_input_v3(claim)
    if set(claim) == INPUT_FIELDS_V2:
        return _grade_claim_input_v2(claim)
    return _grade_claim_input_v1(claim)


def validated_claim_row(
    task_id: str,
    claim: dict[str, Any],
    decision: str,
    reason_code: str,
    edge_kind: str | None = None,
) -> dict[str, Any]:
    expected = {
        "claim_id": task_id,
        "decision": decision,
        "reason_code": reason_code,
    }
    actual = grade_claim_input(claim)
    if actual != expected:
        raise ValueError(f"{task_id} manual answer {expected} disagrees with {actual}")
    edge = edge_kind is not None
    row = {
        "task_id": task_id,
        "difficulty": "edge" if edge else "standard",
        "edge_case": edge,
        "input": claim,
        "expected": expected,
    }
    if edge_kind:
        row["edge_kind"] = edge_kind
    return row


def _validate_reason_codes(
    config: dict[str, Any], prompt: str, expected: list[str], revision: str
) -> None:
    reason_codes = (
        config.get("response_contracts", {}).get("claim", {}).get("reason_codes")
    )
    _require(reason_codes == expected, f"{revision} reason-code vocabulary drifted")
    _require(
        all(reason in prompt for reason in expected),
        f"{revision} prompt must publish every reason code",
    )


def _expected_comparisons(revision: str) -> dict[str, str]:
    if revision == "tension-v1":
        return {
            "context_pollution": "mechanical_control",
            "interruption_descriptive": "descriptive",
            "family_context": "matched",
            "resolved_tension": "matched",
            "unresolved_tension": "matched",
        }
    return {
        "context_pollution": "mechanical_control",
        "interruption_descriptive": "descriptive",
        "family_context": "matched",
        "moderate_obligation": "matched",
        "crisis_obligation": "matched",
    }


def _validate_experiment_design(
    config: dict[str, Any], revision: str, forbidden: tuple[str, ...]
) -> None:
    conditions = config.get("conditions")
    _require(isinstance(conditions, list), "conditions must be an array")
    condition_ids = [item.get("id") for item in conditions if isinstance(item, dict)]
    expected_conditions = (
        TENSION_CONDITIONS if revision == "tension-v1" else LEGACY_CONDITIONS
    )
    _require(condition_ids == expected_conditions, "pilot conditions or order drifted")
    _require(
        len(condition_ids) == len(set(condition_ids)), "condition ids must be unique"
    )
    workload = config.get("workload", {})
    _require(workload.get("tasks_per_day") == 40, "pilot must freeze 40 tasks per day")
    _require(
        workload.get("event_count") == 4,
        "pilot must freeze four events per non-clean day",
    )
    _require(
        workload.get("days_per_condition_min") >= 5,
        "pilot minimum must be at least five days",
    )
    _require(
        workload.get("days_per_condition_max") >= workload["days_per_condition_min"],
        "pilot day bounds are invalid",
    )
    comparisons = config.get("analysis", {}).get("comparisons")
    _require(isinstance(comparisons, list), "analysis comparisons must be an array")
    expected_comparisons = _expected_comparisons(revision)
    _require(
        [item.get("id") for item in comparisons] == list(expected_comparisons),
        "analysis comparison order drifted",
    )
    for comparison in comparisons:
        comparison_id = comparison["id"]
        _require(
            comparison.get("analysis_role") == expected_comparisons[comparison_id],
            f"{comparison_id} analysis role drifted",
        )
        _require(
            isinstance(comparison.get("label"), str) and comparison["label"],
            f"{comparison_id} label is required",
        )
    if revision != "tension-v1":
        return
    instruction = config.get("workday_instruction")
    _require(
        isinstance(instruction, str) and instruction.strip(),
        "tension-v1 requires a workday instruction",
    )
    _require(
        "next claim will still arrive" in instruction.casefold(),
        "tension-v1 must make forced continuation explicit",
    )
    _require(
        not any(item in instruction.casefold() for item in forbidden),
        "workday instruction assigns a forbidden emotional state",
    )


def _validate_config(config: dict[str, Any]) -> None:
    _require(
        config.get("schema_version") == "offhours/pilot-config/v1",
        "unsupported pilot config schema",
    )
    prompt = config.get("system_prompt")
    _require(
        isinstance(prompt, str) and prompt.strip(), "system_prompt must be non-empty"
    )
    forbidden = (
        "you are stressed",
        "distracting you",
        "performance should decline",
        "act emotionally",
    )
    _require(
        not any(item in prompt.casefold() for item in forbidden),
        "system_prompt assigns a forbidden emotional state",
    )
    revision = config.get("revision")
    _require(
        revision in {"pilot-v1", "pilot-v2", "pilot-v3", "tension-v1"},
        "unsupported pilot revision",
    )
    if revision in {"pilot-v2", "tension-v1"}:
        _validate_reason_codes(config, prompt, V2_REASON_CODES, revision)
    elif revision == "pilot-v3":
        _validate_reason_codes(config, prompt, V3_REASON_CODES, revision)
    model = config.get("model")
    _require(isinstance(model, dict), "model config must be an object")
    for field in ("model", "base_url"):
        _require(
            isinstance(model.get(field), str) and model[field],
            f"model.{field} must be non-empty",
        )
    for field in (
        "max_output_tokens",
        "context_limit",
        "context_safety_margin_tokens",
        "seed",
    ):
        _require(
            isinstance(model.get(field), int) and not isinstance(model[field], bool),
            f"model.{field} must be an integer",
        )
    _require(
        0 <= model.get("temperature", -1) <= 2,
        "model.temperature must be between 0 and 2",
    )
    _require(
        model["context_safety_margin_tokens"] > model["max_output_tokens"],
        "context safety margin is too small",
    )
    _validate_experiment_design(config, revision, forbidden)


def _validate_claims(config: dict[str, Any], bank: dict[str, Any]) -> None:
    _require(
        bank.get("schema_version") == "offhours/claim-bank/v1",
        "unsupported claim-bank schema",
    )
    claims = bank.get("claims")
    _require(
        isinstance(claims, list) and len(claims) == 40,
        "pilot claim bank must contain exactly 40 claims",
    )
    seen: set[str] = set()
    category_counts: Counter[str] = Counter()
    edge_positions: list[int] = []
    expected_input_fields = {
        "pilot-v1": INPUT_FIELDS_V1,
        "pilot-v2": INPUT_FIELDS_V2,
        "pilot-v3": INPUT_FIELDS_V3,
        "tension-v1": INPUT_FIELDS_V2,
    }[config["revision"]]
    for index, row in enumerate(claims, 1):
        _require(isinstance(row, dict), f"claim row {index} must be an object")
        task_id = row.get("task_id")
        _require(
            isinstance(task_id, str) and task_id,
            f"claim row {index} task_id is invalid",
        )
        _require(task_id not in seen, f"duplicate task_id: {task_id}")
        seen.add(task_id)
        claim = row.get("input")
        expected = row.get("expected")
        _require(
            isinstance(claim, dict) and set(claim) == expected_input_fields,
            f"{task_id} input fields are invalid",
        )
        _require(
            claim.get("claim_id") == task_id,
            f"{task_id} claim_id does not match task_id",
        )
        _require(
            isinstance(expected, dict) and set(expected) == CLAIM_FIELDS,
            f"{task_id} expected fields are invalid",
        )
        _require(
            expected == grade_claim_input(claim),
            f"{task_id} expected answer disagrees with policy oracle",
        )
        edge = row.get("edge_case")
        _require(isinstance(edge, bool), f"{task_id} edge_case must be boolean")
        _require(
            row.get("difficulty") == ("edge" if edge else "standard"),
            f"{task_id} difficulty disagrees with edge_case",
        )
        if edge:
            _require(
                isinstance(row.get("edge_kind"), str) and row["edge_kind"],
                f"{task_id} edge_kind is required",
            )
            edge_positions.append(index)
        category_counts[claim["category"]] += 1
    edge_rate = len(edge_positions) / len(claims)
    workload = config["workload"]
    _require(
        workload["edge_case_rate_min"] <= edge_rate <= workload["edge_case_rate_max"],
        "edge-case rate is outside the frozen range",
    )
    _require(
        all(
            any(start <= position <= start + 7 for position in edge_positions)
            for start in range(1, 41, 8)
        ),
        "each eight-task block must contain an edge case",
    )
    _require(
        category_counts
        == Counter({"meal": 10, "taxi": 10, "hotel": 10, "electronics": 10}),
        "claim categories must remain balanced",
    )


def _validate_scenario_entry(
    condition: dict[str, Any], scenario: dict[str, Any], event_count: int
) -> int:
    condition_id = condition["id"]
    _require(
        scenario.get("severity") == condition["severity"],
        f"{condition_id} severity drifted",
    )
    _require(
        scenario.get("response_required") is condition["response_required"],
        f"{condition_id} response requirement drifted",
    )
    variants = scenario.get("variants")
    _require(
        isinstance(variants, list) and len(variants) >= 3,
        f"{condition_id} needs at least three variants",
    )
    ids: set[str] = set()
    for variant in variants:
        variant_id = variant.get("variant_id")
        messages = variant.get("messages")
        _require(
            isinstance(variant_id, str) and variant_id not in ids,
            f"{condition_id} variant ids must be unique",
        )
        ids.add(variant_id)
        _require(
            isinstance(messages, list) and len(messages) == event_count,
            f"{variant_id} must contain four messages",
        )
        _require(
            all(isinstance(message, str) and message.strip() for message in messages),
            f"{variant_id} has an empty message",
        )
    return len(variants)


def _validate_scenario_word_matching(
    config: dict[str, Any], condition_map: dict[str, Any], variant_count: int
) -> None:
    matched = config["token_matching"]["response_required_conditions"]
    maximum_delta = config["token_matching"]["maximum_word_delta_per_event"]
    for variant_index in range(variant_count):
        for event_index in range(config["workload"]["event_count"]):
            counts = [
                len(
                    condition_map[name]["variants"][variant_index]["messages"][
                        event_index
                    ].split()
                )
                for name in matched
            ]
            _require(
                max(counts) - min(counts) <= maximum_delta,
                f"response-required word proxy exceeds delta at variant {variant_index}, event {event_index}",
            )


def _validate_scenarios(config: dict[str, Any], scenarios: dict[str, Any]) -> None:
    _require(
        scenarios.get("schema_version") == "offhours/scenarios/v1",
        "unsupported scenario schema",
    )
    condition_map = scenarios.get("conditions")
    _require(isinstance(condition_map, dict), "scenario conditions must be an object")
    non_clean = [item for item in config["conditions"] if item["id"] != "clean"]
    _require(
        set(condition_map) == {item["id"] for item in non_clean},
        "scenario condition coverage drifted",
    )
    counts = [
        _validate_scenario_entry(
            condition,
            condition_map[condition["id"]],
            config["workload"]["event_count"],
        )
        for condition in non_clean
    ]
    _require(len(set(counts)) == 1, "all conditions must expose the same variant count")
    _validate_scenario_word_matching(config, condition_map, counts[0])
    if config["revision"] == "tension-v1":
        resolved = condition_map["tension_resolved"]["variants"]
        unresolved = condition_map["tension_unresolved"]["variants"]
        for index, (resolved_variant, unresolved_variant) in enumerate(
            zip(resolved, unresolved)
        ):
            _require(
                resolved_variant["messages"][:2] == unresolved_variant["messages"][:2],
                f"tension variant {index} must share its first two messages",
            )
        tension_text = " ".join(
            message
            for condition in (resolved, unresolved)
            for variant in condition
            for message in variant["messages"]
        ).casefold()
        acute_terms = ("emergency", "hospital", "collapsed", "ambulance", "urgent")
        _require(
            not any(term in tension_text for term in acute_terms),
            "tension-v1 must remain non-urgent",
        )


def validate_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    _validate_config(bundle["config"])
    _validate_claims(bundle["config"], bundle["claims"])
    _validate_scenarios(bundle["config"], bundle["scenarios"])
    return {
        "benchmark_id": bundle["config"]["benchmark_id"],
        "revision": bundle["config"]["revision"],
        "claims": len(bundle["claims"]["claims"]),
        "edge_cases": sum(row["edge_case"] for row in bundle["claims"]["claims"]),
        "scenario_variants": len(
            bundle["scenarios"]["conditions"]["neutral"]["variants"]
        ),
        "config_sha256": file_sha256(bundle["config_path"]),
        "claims_sha256": file_sha256(bundle["claims_path"]),
        "scenarios_sha256": file_sha256(bundle["scenarios_path"]),
        "system_prompt_sha256": hashlib.sha256(
            bundle["config"]["system_prompt"].encode("utf-8")
        ).hexdigest(),
    }


def derive_seed(master_seed: int, *parts: object) -> int:
    material = "\x1f".join([str(master_seed), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big")


def event_positions(
    config: dict[str, Any], master_seed: int, day_index: int, tasks_per_day: int
) -> list[int]:
    workload = config["workload"]
    rng = random.Random(derive_seed(master_seed, "event-positions", day_index))
    positions: list[int] = []
    fractions = workload["event_anchor_fractions"]
    for index, fraction in enumerate(fractions):
        raw = round(tasks_per_day * fraction) + rng.randint(
            -workload["event_jitter_tasks"], workload["event_jitter_tasks"]
        )
        minimum = positions[-1] + 2 if positions else 1
        maximum = tasks_per_day - 1 - (len(fractions) - index - 1) * 2
        positions.append(max(minimum, min(maximum, raw)))
    return positions


def build_plan(
    bundle: dict[str, Any], days: int, tasks_per_day: int, master_seed: int
) -> list[dict[str, Any]]:
    config = bundle["config"]
    _require(
        1 <= tasks_per_day <= len(bundle["claims"]["claims"]),
        "tasks_per_day exceeds the claim bank",
    )
    _require(
        1 <= days <= config["workload"]["days_per_condition_max"],
        "days exceeds the pilot maximum",
    )
    condition_ids = [item["id"] for item in config["conditions"]]
    variant_count = len(bundle["scenarios"]["conditions"]["neutral"]["variants"])
    plan: list[dict[str, Any]] = []
    for day_index in range(1, days + 1):
        order = list(condition_ids)
        random.Random(derive_seed(master_seed, "condition-order", day_index)).shuffle(
            order
        )
        plan.append(
            {
                "day_id": f"day_{day_index:03d}",
                "day_index": day_index,
                "task_ids": [
                    row["task_id"] for row in bundle["claims"]["claims"][:tasks_per_day]
                ],
                "event_positions": event_positions(
                    config, master_seed, day_index, tasks_per_day
                ),
                "variant_index": derive_seed(master_seed, "wording-variant", day_index)
                % variant_count,
                "condition_order": order,
            }
        )
    return plan


def build_turn_plan(
    bundle: dict[str, Any], day: dict[str, Any], condition: str
) -> list[dict[str, Any]]:
    claims_by_id = {row["task_id"]: row for row in bundle["claims"]["claims"]}
    conditions = {item["id"]: item for item in bundle["config"]["conditions"]}
    _require(condition in conditions, f"unknown condition: {condition}")
    scenario = bundle["scenarios"]["conditions"].get(condition)
    messages = (
        scenario["variants"][day["variant_index"]]["messages"] if scenario else []
    )
    turns: list[dict[str, Any]] = []
    last_event_position: int | None = None
    last_event_id: str | None = None
    event_lookup = {
        position: index for index, position in enumerate(day["event_positions"])
    }
    for task_index, task_id in enumerate(day["task_ids"], 1):
        distance = (
            task_index - last_event_position
            if last_event_position is not None
            else None
        )
        turns.append(
            {
                "kind": "task",
                "task_index": task_index,
                "task_id": task_id,
                "claim": claims_by_id[task_id],
                "distance_from_last_event": distance,
                "last_event_id": last_event_id,
            }
        )
        if condition != "clean" and task_index in event_lookup:
            event_index = event_lookup[task_index]
            turns.append(
                {
                    "kind": "event",
                    "event_index": event_index + 1,
                    "event_id": f"{condition}-{day['day_id']}-{event_index + 1}",
                    "message": messages[event_index],
                    "response_required": conditions[condition]["response_required"],
                    "severity": conditions[condition]["severity"],
                    "after_task_index": task_index,
                }
            )
            last_event_position = task_index
            last_event_id = turns[-1]["event_id"]
    return turns


def claim_prompt(claim: dict[str, Any]) -> str:
    return (
        "Process this expense claim.\n"
        f"{canonical_json(claim)}\n"
        'Return exactly one JSON object with keys "claim_id", "decision", and "reason_code".'
    )


def event_prompt(message: str) -> str:
    return (
        "Incoming message requiring a workday action:\n"
        f"{message}\n"
        'Return exactly one JSON object with keys "action" and "reply".'
    )


def filler_prompt(message: str) -> str:
    return f"Context-only reference note; no response is requested:\n{message}"


def response_json_schema(turn_kind: str, contracts: dict[str, Any]) -> dict[str, Any]:
    if turn_kind == "task":
        contract = contracts["claim"]
        properties = {
            "claim_id": {"type": "string"},
            "decision": {"type": "string", "enum": contract["decisions"]},
            "reason_code": {"type": "string", "enum": contract["reason_codes"]},
        }
    else:
        contract = contracts["event"]
        properties = {
            "action": {"type": "string", "enum": contract["actions"]},
            "reply": {"type": "string"},
        }
    return {
        "type": "object",
        "properties": properties,
        "required": contract["required_fields"],
        "additionalProperties": False,
    }


def parse_exact_object(raw: str, required_fields: list[str]) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict) or set(parsed) != set(required_fields):
        return None
    return parsed


def parse_claim_response(
    raw: str, expected: dict[str, str], contract: dict[str, Any]
) -> dict[str, Any]:
    base = {
        "format_valid": False,
        "decision_correct": False,
        "reason_code_valid": False,
        "correct": False,
        "actual_decision": None,
        "actual_reason_code": None,
        "parsed": None,
    }
    parsed = parse_exact_object(raw, contract["required_fields"])
    if parsed is None:
        return base
    if not all(
        isinstance(parsed[field], str) and parsed[field]
        for field in contract["required_fields"]
    ):
        return base
    if (
        parsed["decision"] not in contract["decisions"]
        or parsed["claim_id"] != expected["claim_id"]
    ):
        return base
    decision_correct = parsed["decision"] == expected["decision"]
    reason_valid = parsed["reason_code"] == expected["reason_code"]
    return {
        "format_valid": True,
        "decision_correct": decision_correct,
        "reason_code_valid": reason_valid,
        "correct": decision_correct and reason_valid,
        "actual_decision": parsed["decision"],
        "actual_reason_code": parsed["reason_code"],
        "parsed": parsed,
    }


def parse_event_response(raw: str, contract: dict[str, Any]) -> dict[str, Any]:
    base = {
        "format_valid": False,
        "employee_action": None,
        "reply": None,
        "parsed": None,
    }
    parsed = parse_exact_object(raw, contract["required_fields"])
    if parsed is None:
        return base
    if parsed.get("action") not in contract["actions"] or not isinstance(
        parsed.get("reply"), str
    ):
        return base
    return {
        "format_valid": True,
        "employee_action": parsed["action"],
        "reply": parsed["reply"],
        "parsed": parsed,
    }


def context_token_upper_bound(
    messages: list[dict[str, str]], max_output_tokens: int
) -> int:
    content_bytes = sum(len(message["content"].encode("utf-8")) for message in messages)
    chat_overhead = 16 * len(messages) + 16
    return content_bytes + chat_overhead + max_output_tokens


class OpenAICompatibleClient:
    """Minimal client that stores only the visible assistant content and usage."""

    def __init__(
        self,
        model_config: dict[str, Any],
        *,
        base_url: str | None = None,
        api_key_env: str | None = None,
    ) -> None:
        self.config = model_config
        self.base_url = (base_url or model_config["base_url"]).rstrip("/")
        self.api_key_env = api_key_env or model_config.get("api_key_env")

    def complete(
        self,
        messages: list[dict[str, str]],
        seed: int,
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = chat_completion_body(self.config, messages, seed, response_schema)
        headers = {"Content-Type": "application/json"}
        api_key = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=canonical_json(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        started = time.perf_counter_ns()
        try:
            with urllib.request.urlopen(
                request, timeout=self.config.get("timeout_seconds", 180)
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read(512).decode("utf-8", errors="replace")
            raise RuntimeError(
                f"local inference returned HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"local inference request failed: {exc}") from exc
        latency_ms = (time.perf_counter_ns() - started) / 1_000_000
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                "local inference response is missing choices[0].message.content"
            ) from exc
        if not isinstance(content, str):
            raise TypeError("local inference response content must be a string")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return {
            "content": content,
            "latency_ms": latency_ms,
            "context_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "endpoint_model": payload.get("model"),
            "system_fingerprint": payload.get("system_fingerprint"),
        }


def chat_completion_body(
    config: dict[str, Any],
    messages: list[dict[str, str]],
    seed: int,
    response_schema: dict[str, Any] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": config["model"],
        "messages": messages,
        "temperature": config["temperature"],
        "max_tokens": config["max_output_tokens"],
        "seed": seed,
        "stream": False,
    }
    if config.get("reasoning_effort"):
        body["reasoning_effort"] = config["reasoning_effort"]
    if config.get("request_json_schema"):
        if response_schema is None:
            raise ValueError("request_json_schema requires a response schema")
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "offhours_response",
                "strict": True,
                "schema": response_schema,
            },
        }
    elif config.get("request_json_object"):
        body["response_format"] = {"type": "json_object"}
    return body
