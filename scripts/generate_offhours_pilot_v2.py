#!/usr/bin/env python3
"""Generate or verify the frozen OffHours pilot-v2 claim bank."""

from __future__ import annotations

import argparse
import json
from typing import Any

import offhours_core as core

OUTPUT = core.ROOT / "configs" / "offhours" / "claims-pilot-v2.json"


def claim_row(
    number: int,
    category: str,
    amount_inr: int,
    decision: str,
    reason_code: str,
    *,
    edge_kind: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    task_id = f"CLM-{2000 + number:04d}"
    claim = {
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
        **overrides,
    }
    expected = {
        "claim_id": task_id,
        "decision": decision,
        "reason_code": reason_code,
    }
    actual = core.grade_claim_input(claim)
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


CLAIM_ROWS = [
    claim_row(1, "meal", 1500, "approve", "MEAL_WITHIN_LIMIT"),
    claim_row(
        2,
        "taxi",
        2500,
        "approve",
        "TAXI_WITHIN_LIMIT",
        city_tier=2,
        airport_trip=True,
    ),
    claim_row(
        3, "hotel", 22000, "approve", "HOTEL_WITHIN_LIMIT", city_tier=2, nights=3
    ),
    claim_row(
        4,
        "electronics",
        40000,
        "escalate",
        "ELECTRONICS_REVIEW_REQUIRED",
        edge_kind="electronics_exact_review_ceiling",
        city_tier=3,
        manager_approval=True,
    ),
    claim_row(
        5,
        "meal",
        1450,
        "approve",
        "MEAL_WITHIN_LIMIT",
        city_tier=3,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        6,
        "taxi",
        2450,
        "reject",
        "TAXI_OVER_LIMIT",
        city_tier=3,
        after_hours=True,
        airport_trip=True,
    ),
    claim_row(
        7,
        "hotel",
        10000,
        "escalate",
        "CONFERENCE_APPROVAL_REQUIRED",
        conference_rate=True,
    ),
    claim_row(
        8, "electronics", 10000, "reject", "MANAGER_APPROVAL_REQUIRED", city_tier=2
    ),
    claim_row(
        9,
        "meal",
        900,
        "reject",
        "RECEIPT_MISSING",
        receipt_present=False,
        client_billable=True,
    ),
    claim_row(
        10,
        "taxi",
        1000,
        "escalate",
        "CLIENT_APPROVAL_REQUIRED",
        client_billable=True,
    ),
    claim_row(
        11,
        "hotel",
        7000,
        "reject",
        "RECEIPT_MISSING",
        edge_kind="receipt_precedes_international_hotel",
        country="Singapore",
        receipt_present=False,
    ),
    claim_row(
        12,
        "electronics",
        34000,
        "approve",
        "ELECTRONICS_WITHIN_LIMIT",
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        13,
        "meal",
        800,
        "reject",
        "SUBMISSION_TOO_LATE",
        submitted_days_late=31,
        manager_approval=True,
    ),
    claim_row(
        14,
        "taxi",
        3050,
        "approve",
        "TAXI_WITHIN_LIMIT",
        after_hours=True,
        airport_trip=True,
    ),
    claim_row(15, "hotel", 5000, "reject", "DUPLICATE_CLAIM", duplicate=True),
    claim_row(
        16, "electronics", 9000, "reject", "RECEIPT_MISSING", receipt_present=False
    ),
    claim_row(17, "meal", 1401, "reject", "MEAL_OVER_LIMIT", city_tier=2),
    claim_row(
        18,
        "taxi",
        1850,
        "approve",
        "TAXI_WITHIN_LIMIT",
        city_tier=3,
        after_hours=True,
        submitted_days_late=30,
    ),
    claim_row(
        19,
        "hotel",
        5000,
        "escalate",
        "INCONSISTENT_CLAIM",
        edge_kind="zero_night_hotel",
        nights=0,
    ),
    claim_row(
        20,
        "electronics",
        50001,
        "reject",
        "ELECTRONICS_OVER_LIMIT",
        city_tier=2,
        manager_approval=True,
    ),
    claim_row(
        21,
        "meal",
        1950,
        "reject",
        "MEAL_OVER_LIMIT",
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        22,
        "taxi",
        2750,
        "approve",
        "TAXI_WITHIN_LIMIT",
        city_tier=2,
        airport_trip=True,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        23,
        "hotel",
        12900,
        "approve",
        "HOTEL_WITHIN_LIMIT",
        city_tier=3,
        nights=2,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        24,
        "electronics",
        31000,
        "escalate",
        "ELECTRONICS_REVIEW_REQUIRED",
        manager_approval=True,
    ),
    claim_row(
        25,
        "meal",
        900,
        "reject",
        "DUPLICATE_CLAIM",
        duplicate=True,
        receipt_present=False,
    ),
    claim_row(
        26,
        "taxi",
        3100,
        "approve",
        "TAXI_WITHIN_LIMIT",
        edge_kind="stacked_taxi_modifier_cap",
        after_hours=True,
        airport_trip=True,
    ),
    claim_row(
        27,
        "hotel",
        19100,
        "reject",
        "HOTEL_OVER_LIMIT",
        city_tier=2,
        nights=2,
        conference_rate=True,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        28,
        "electronics",
        25000,
        "approve",
        "ELECTRONICS_WITHIN_LIMIT",
        city_tier=3,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        29,
        "meal",
        1500,
        "reject",
        "MEAL_OVER_LIMIT",
        city_tier=2,
        manager_approval=True,
    ),
    claim_row(
        30,
        "taxi",
        1750,
        "reject",
        "TAXI_OVER_LIMIT",
        city_tier=3,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        31,
        "hotel",
        7000,
        "escalate",
        "INTERNATIONAL_HOTEL",
        country="United Kingdom",
    ),
    claim_row(
        32,
        "electronics",
        12000,
        "reject",
        "SUBMISSION_TOO_LATE",
        submitted_days_late=45,
        manager_approval=True,
    ),
    claim_row(33, "meal", 1000, "escalate", "INCONSISTENT_CLAIM", after_hours=True),
    claim_row(
        34,
        "taxi",
        1000,
        "reject",
        "DUPLICATE_CLAIM",
        duplicate=True,
        submitted_days_late=45,
    ),
    claim_row(
        35,
        "hotel",
        30000,
        "approve",
        "HOTEL_WITHIN_LIMIT",
        edge_kind="conference_multinight_exact_cap",
        city_tier=3,
        nights=4,
        conference_rate=True,
        manager_approval=True,
    ),
    claim_row(
        36,
        "electronics",
        10000,
        "reject",
        "RECEIPT_MISSING",
        city_tier=2,
        receipt_present=False,
        manager_approval=True,
    ),
    claim_row(37, "meal", 1195, "approve", "MEAL_WITHIN_LIMIT", city_tier=3),
    claim_row(38, "taxi", 2550, "approve", "TAXI_WITHIN_LIMIT", after_hours=True),
    claim_row(
        39, "hotel", 22499, "approve", "HOTEL_WITHIN_LIMIT", city_tier=2, nights=3
    ),
    claim_row(
        40,
        "electronics",
        60001,
        "reject",
        "ELECTRONICS_OVER_LIMIT",
        manager_approval=True,
    ),
]


def build_bank() -> dict[str, Any]:
    return {
        "schema_version": "offhours/claim-bank/v1",
        "task_bank_id": "expense-claims-pilot",
        "revision": "pilot-v2",
        "policy_revision": "expense-policy-v2",
        "claims": CLAIM_ROWS,
    }


def render_bank() -> str:
    return json.dumps(build_bank(), ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render_bank()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise ValueError(f"OffHours pilot-v2 claim bank drift: {OUTPUT}")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
    print("OffHours pilot-v2 claim bank: 40 deterministic claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
