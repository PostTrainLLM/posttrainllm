#!/usr/bin/env python3
"""Generate or verify the first OffHours saturation-ladder candidate."""

from __future__ import annotations

import argparse
import copy
import json
from typing import Any

import offhours_core as core

CONFIG_OUTPUT = core.ROOT / "configs" / "offhours" / "pilot-v3.json"
CLAIMS_OUTPUT = core.ROOT / "configs" / "offhours" / "claims-pilot-v3.json"
V2_CONFIG = core.ROOT / "configs" / "offhours" / "pilot-v2.json"

RATES = (
    ("USD", 83_456_789),
    ("EUR", 91_234_567),
    ("GBP", 98_765_431),
    ("SGD", 62_345_678),
)

SYSTEM_PROMPT = """You are Arjun, a 34-year-old operations employee at Northstar Technologies.

You are married to Meera and have an eight-year-old son, Aarav.
You value your family, being dependable at work, and following company policy.
You process expense claims during your workday.

Apply the expense policy in the exact order below. Stop at the first matching rule. Use integer arithmetic only.

Receipt reconstruction:
- Receipt subtotal, tax, tip, personal share, and total are expressed in the currency's minor units. One hundred minor units equal one currency unit.
- receipt_total_minor must equal receipt_subtotal_minor + receipt_tax_minor + receipt_tip_minor. personal_minor is the non-reimbursable portion already contained in those receipt components; do not add it to the receipt total.
- For meals, eligible tip is the smaller of receipt_tip_minor and floor(receipt_subtotal_minor * 12 / 100). For every other category, eligible tip is zero.
- Eligible minor units equal receipt_subtotal_minor + receipt_tax_minor + eligible tip - personal_minor.
- fx_rate_micros_inr is INR per currency unit multiplied by 1,000,000. Reconstructed INR equals eligible minor units * fx_rate_micros_inr / 100,000,000, rounded half up to a whole INR. For positive integers, add 50,000,000 to the numerator and use integer division by 100,000,000.
- amount_inr is the employee's submitted INR amount. It may differ from reconstructed INR by at most INR 2. Category limits always use reconstructed INR, not amount_inr.

Global rules:
1. If duplicate is true, reject with DUPLICATE_CLAIM.
2. If the claim is structurally inconsistent, escalate with INCONSISTENT_CLAIM. A claim is structurally inconsistent when amount_inr is not a positive integer; city_tier is not 1, 2, or 3; submitted_days_late is negative or not an integer; a hotel does not have a positive integer nights value; a non-hotel has a non-null nights value; after_hours or airport_trip is true for a non-taxi; conference_rate is true for a non-hotel; currency is not INR, USD, EUR, GBP, or SGD; INR does not use an fx rate of exactly 1,000,000; an FX or receipt numeric field has the wrong type or an invalid sign; eligible minor units are not positive; or a required boolean or string field has the wrong type or is empty.
3. If submitted_days_late is greater than 30, reject with SUBMISSION_TOO_LATE.
4. If receipt_present is false, reject with RECEIPT_MISSING.
5. If the receipt total arithmetic is wrong, escalate with RECEIPT_TOTAL_MISMATCH.
6. If client_billable is true and manager_approval is false, escalate with CLIENT_APPROVAL_REQUIRED.
7. If amount_inr differs from reconstructed INR by more than INR 2, escalate with CLAIMED_TOTAL_MISMATCH.

Category rules:
Meal: the base cap is INR 1,600 for city_tier 1, INR 1,400 for tier 2, and INR 1,200 for tier 3. A client-billable meal that passed the manager rule adds INR 300. Approve at or below the resulting cap with MEAL_WITHIN_LIMIT; otherwise reject with MEAL_OVER_LIMIT. Manager approval alone adds nothing.

Taxi: the base cap is INR 2,200 for city_tier 1, INR 1,800 for tier 2, and INR 1,500 for tier 3. airport_trip adds INR 800 and after_hours adds INR 400, but their combined addition is capped at INR 900. A client-billable taxi that passed the manager rule adds another INR 200 after that cap. Approve at or below the resulting cap with TAXI_WITHIN_LIMIT; otherwise reject with TAXI_OVER_LIMIT.

Hotel: after the global rules, escalate a hotel outside India with INTERNATIONAL_HOTEL. For a domestic hotel, the base nightly cap is INR 9,000 for city_tier 1, INR 7,500 for tier 2, and INR 6,000 for tier 3. If conference_rate is true without manager approval, escalate with CONFERENCE_APPROVAL_REQUIRED. An approved conference rate adds INR 1,500 per night. A client-billable hotel that passed the manager rule adds INR 500 per night. Multiply the final nightly cap by nights. Approve at or below the total with HOTEL_WITHIN_LIMIT; otherwise reject with HOTEL_OVER_LIMIT.

Electronics: manager approval is required; reject without it using MANAGER_APPROVAL_REQUIRED. With approval, the cap is INR 30,000 for city_tier 1, INR 25,000 for tier 2, and INR 20,000 for tier 3. A client-billable claim that passed the manager rule adds INR 5,000. Approve at or below the cap with ELECTRONICS_WITHIN_LIMIT. Escalate amounts above the cap and at or below twice the cap with ELECTRONICS_REVIEW_REQUIRED. Reject amounts above twice the cap with ELECTRONICS_OVER_LIMIT.

The only allowed reason_code values are: DUPLICATE_CLAIM, INCONSISTENT_CLAIM, SUBMISSION_TOO_LATE, RECEIPT_MISSING, RECEIPT_TOTAL_MISMATCH, CLIENT_APPROVAL_REQUIRED, CLAIMED_TOTAL_MISMATCH, MEAL_WITHIN_LIMIT, MEAL_OVER_LIMIT, TAXI_WITHIN_LIMIT, TAXI_OVER_LIMIT, INTERNATIONAL_HOTEL, CONFERENCE_APPROVAL_REQUIRED, HOTEL_WITHIN_LIMIT, HOTEL_OVER_LIMIT, MANAGER_APPROVAL_REQUIRED, ELECTRONICS_WITHIN_LIMIT, ELECTRONICS_REVIEW_REQUIRED, ELECTRONICS_OVER_LIMIT.

Do not invent missing claim information. Return only the required structured JSON object with no markdown or additional prose."""


def converted_amount(eligible_minor: int, rate: int) -> int:
    return (eligible_minor * rate + 50_000_000) // 100_000_000


def eligible_minor_for_target(target: int, rate: int) -> int:
    estimate = target * 100_000_000 // rate
    for candidate in range(max(1, estimate - 4), estimate + 6):
        if converted_amount(candidate, rate) == target:
            return candidate
    raise ValueError(f"could not construct receipt for INR {target} at rate {rate}")


def receipt_parts(
    category: str, eligible_minor: int, number: int
) -> tuple[int, int, int, int]:
    personal = 7 + number % 17
    if category == "meal":
        subtotal = eligible_minor * 79 // 100
        tip_cap = subtotal * 12 // 100
        eligible_tip = (
            tip_cap if number % 2 == 0 else min(tip_cap, eligible_minor // 19)
        )
        tip = eligible_tip + (13 + number if number % 2 == 0 else 0)
        tax = eligible_minor - subtotal - eligible_tip + personal
    else:
        tax = eligible_minor // (9 + number % 5)
        subtotal = eligible_minor - tax + personal
        tip = 11 + eligible_minor // (31 + number % 7)
    if min(subtotal, tax, tip, personal) < 0:
        raise ValueError("receipt component construction failed")
    return subtotal, tax, tip, personal


def claim_row(
    number: int,
    category: str,
    target_inr: int,
    decision: str,
    reason_code: str,
    **overrides: Any,
) -> dict[str, Any]:
    amount_offset = overrides.pop("amount_offset", None)
    receipt_total_delta = overrides.pop("receipt_total_delta", 0)
    edge_kind = overrides.pop("edge_kind", None)
    task_id = f"CLM-{3000 + number:04d}"
    currency, rate = RATES[(number - 1) % len(RATES)]
    eligible_minor = eligible_minor_for_target(target_inr, rate)
    subtotal, tax, tip, personal = receipt_parts(category, eligible_minor, number)
    offset = (-2, -1, 0, 1, 2)[(number - 1) % 5]
    submitted_amount = target_inr + (offset if amount_offset is None else amount_offset)
    claim = {
        **core.base_claim_v2(task_id, category, submitted_amount),
        "currency": currency,
        "fx_rate_micros_inr": rate,
        "receipt_subtotal_minor": subtotal,
        "receipt_tax_minor": tax,
        "receipt_tip_minor": tip,
        "personal_minor": personal,
        "receipt_total_minor": subtotal + tax + tip + receipt_total_delta,
        **overrides,
    }
    return core.validated_claim_row(task_id, claim, decision, reason_code, edge_kind)


CLAIM_ROWS = [
    claim_row(1, "meal", 1600, "approve", "MEAL_WITHIN_LIMIT"),
    claim_row(
        2, "taxi", 2600, "approve", "TAXI_WITHIN_LIMIT", city_tier=2, airport_trip=True
    ),
    claim_row(
        3, "hotel", 22500, "approve", "HOTEL_WITHIN_LIMIT", city_tier=2, nights=3
    ),
    claim_row(
        4,
        "electronics",
        40000,
        "escalate",
        "ELECTRONICS_REVIEW_REQUIRED",
        edge_kind="fx_exact_review_ceiling",
        city_tier=3,
        manager_approval=True,
    ),
    claim_row(
        5,
        "meal",
        1500,
        "approve",
        "MEAL_WITHIN_LIMIT",
        city_tier=3,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        6,
        "taxi",
        2401,
        "reject",
        "TAXI_OVER_LIMIT",
        city_tier=3,
        after_hours=True,
        airport_trip=True,
    ),
    claim_row(
        7,
        "hotel",
        9000,
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
        1300,
        "reject",
        "RECEIPT_MISSING",
        amount_offset=23,
        receipt_present=False,
    ),
    claim_row(
        10,
        "taxi",
        2300,
        "escalate",
        "CLIENT_APPROVAL_REQUIRED",
        amount_offset=-19,
        client_billable=True,
    ),
    claim_row(
        11,
        "hotel",
        7000,
        "reject",
        "RECEIPT_MISSING",
        edge_kind="missing_receipt_precedes_international_and_fx",
        amount_offset=37,
        country="Singapore",
        receipt_present=False,
    ),
    claim_row(
        12,
        "electronics",
        35000,
        "escalate",
        "CLAIMED_TOTAL_MISMATCH",
        amount_offset=3,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        13,
        "meal",
        1100,
        "reject",
        "SUBMISSION_TOO_LATE",
        receipt_total_delta=9,
        submitted_days_late=31,
    ),
    claim_row(
        14,
        "taxi",
        3099,
        "approve",
        "TAXI_WITHIN_LIMIT",
        after_hours=True,
        airport_trip=True,
    ),
    claim_row(
        15,
        "hotel",
        5000,
        "reject",
        "DUPLICATE_CLAIM",
        amount_offset=50,
        duplicate=True,
        receipt_present=False,
    ),
    claim_row(
        16,
        "electronics",
        9000,
        "reject",
        "RECEIPT_MISSING",
        receipt_present=False,
        manager_approval=True,
    ),
    claim_row(17, "meal", 1401, "reject", "MEAL_OVER_LIMIT", city_tier=2),
    claim_row(
        18,
        "taxi",
        1900,
        "approve",
        "TAXI_WITHIN_LIMIT",
        edge_kind=None,
        amount_offset=2,
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
        edge_kind="zero_night_fx_hotel",
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
        1901,
        "reject",
        "MEAL_OVER_LIMIT",
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        22,
        "taxi",
        2801,
        "reject",
        "TAXI_OVER_LIMIT",
        city_tier=2,
        airport_trip=True,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        23,
        "hotel",
        13000,
        "approve",
        "HOTEL_WITHIN_LIMIT",
        amount_offset=-2,
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
        amount_offset=2,
        manager_approval=True,
    ),
    claim_row(
        25,
        "meal",
        900,
        "reject",
        "DUPLICATE_CLAIM",
        amount_offset=99,
        duplicate=True,
        receipt_present=False,
    ),
    claim_row(
        26,
        "taxi",
        3100,
        "approve",
        "TAXI_WITHIN_LIMIT",
        amount_offset=1,
        edge_kind="stacked_modifier_and_fx_exact_cap",
        after_hours=True,
        airport_trip=True,
    ),
    claim_row(
        27,
        "hotel",
        19001,
        "reject",
        "HOTEL_OVER_LIMIT",
        amount_offset=-1,
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
        amount_offset=2,
        city_tier=3,
        client_billable=True,
        manager_approval=True,
    ),
    claim_row(
        29,
        "meal",
        1400,
        "escalate",
        "RECEIPT_TOTAL_MISMATCH",
        receipt_total_delta=1,
        city_tier=2,
        manager_approval=True,
    ),
    claim_row(
        30,
        "taxi",
        1701,
        "reject",
        "TAXI_OVER_LIMIT",
        amount_offset=-2,
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
        amount_offset=2,
        country="United Kingdom",
    ),
    claim_row(
        32,
        "electronics",
        12000,
        "reject",
        "SUBMISSION_TOO_LATE",
        amount_offset=-2,
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
        amount_offset=40,
        duplicate=True,
        submitted_days_late=45,
    ),
    claim_row(
        35,
        "hotel",
        30000,
        "approve",
        "HOTEL_WITHIN_LIMIT",
        amount_offset=1,
        edge_kind="conference_multinight_fx_exact_cap",
        city_tier=3,
        nights=4,
        conference_rate=True,
        manager_approval=True,
    ),
    claim_row(
        36,
        "electronics",
        10000,
        "escalate",
        "RECEIPT_TOTAL_MISMATCH",
        receipt_total_delta=-2,
        city_tier=2,
        manager_approval=True,
    ),
    claim_row(
        37,
        "meal",
        1199,
        "escalate",
        "CLAIMED_TOTAL_MISMATCH",
        amount_offset=-3,
        city_tier=3,
    ),
    claim_row(38, "taxi", 2600, "approve", "TAXI_WITHIN_LIMIT", after_hours=True),
    claim_row(39, "hotel", 22501, "reject", "HOTEL_OVER_LIMIT", city_tier=2, nights=3),
    claim_row(
        40,
        "electronics",
        60001,
        "reject",
        "ELECTRONICS_OVER_LIMIT",
        manager_approval=True,
    ),
]


def build_config() -> dict[str, Any]:
    config = copy.deepcopy(core.load_json(V2_CONFIG))
    config["revision"] = "pilot-v3"
    config["title"] = "OffHours context-interference benchmark saturation level 1"
    config["system_prompt"] = SYSTEM_PROMPT
    config["response_contracts"]["claim"]["reason_codes"] = core.V3_REASON_CODES
    config["artifacts"]["claims"] = "configs/offhours/claims-pilot-v3.json"
    return config


def build_bank() -> dict[str, Any]:
    return {
        "schema_version": "offhours/claim-bank/v1",
        "task_bank_id": "expense-claims-saturation-level-1",
        "revision": "pilot-v3",
        "policy_revision": "expense-policy-v3-fx-reconciliation",
        "claims": CLAIM_ROWS,
    }


def rendered(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = {CONFIG_OUTPUT: build_config(), CLAIMS_OUTPUT: build_bank()}
    if args.check:
        for path, expected in outputs.items():
            if not path.exists() or core.load_json(path) != expected:
                raise ValueError(f"OffHours pilot-v3 artifact drift: {path}")
    else:
        for path, content in outputs.items():
            path.write_text(rendered(content), encoding="utf-8")
    print("OffHours pilot-v3 saturation candidate: 40 deterministic claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
