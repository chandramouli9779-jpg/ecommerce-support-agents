"""Shared test scenarios.

Every agent (five classical + the LLM agent) receives the SAME case file for a
selected scenario, built by get_case_file(). This is what makes the decisions
comparable, as the mini project instructions require.
"""
from __future__ import annotations

from tools import (get_delivery_events, get_order_status, get_refund_status,
                   reference_date)

SCENARIOS = {
    "A": {
        "title": "Delivered but not received",
        "test_type": "critical / failure",
        "order_id": "ORD-1001",
        "customer_message": ("My order ORD-1001 shows as delivered on 2 November, "
                             "but I never received the package. Nothing was at my door."),
    },
    "B": {
        "title": "Refund not updated after passed inspection",
        "test_type": "failure (service-level breach)",
        "order_id": "ORD-1002",
        "customer_message": ("I returned the running shoes for ORD-1002 and was told they "
                             "passed inspection, but my refund still shows pending."),
    },
    "C": {
        "title": "Conflicting / incomplete information",
        "test_type": "edge / ambiguous",
        "order_id": "ORD-1003",
        "customer_message": ("I ordered a brown backpack on ORD-1003 and it was delivered "
                             "damaged. I want my money back."),
    },
    "D": {
        "title": "Order in transit, within expected date",
        "test_type": "normal",
        "order_id": "ORD-1004",
        "customer_message": "Where is my order ORD-1004? I placed it on 3 November.",
    },
}


def get_case_file(scenario_id: str) -> dict:
    """Build the single shared input that all six agents receive."""
    scenario = SCENARIOS[scenario_id]
    oid = scenario["order_id"]
    return {
        "scenario_id": scenario_id,
        "title": scenario["title"],
        "test_type": scenario["test_type"],
        "reference_date": reference_date().isoformat(),
        "order_id": oid,
        "customer_message": scenario["customer_message"],
        "order": get_order_status(oid),
        "delivery": get_delivery_events(oid),
        "refund": get_refund_status(oid),
    }


# Expected next action for each scenario, taken from the policy sections in
# data/records.json. Used ONLY for evaluation/comparison - agents never see it.
EXPECTED_ACTIONS = {
    "A": ("open_carrier_investigation", "POL-DNR: reported within 7 days, no photo/signature proof"),
    "B": ("escalate_to_payments", "POL-REF: refund pending 8 business days after inspection (limit 5)"),
    "C": ("request_clarification_and_flag", "POL-VER: item and status conflict with record; tracking missing"),
    "D": ("share_tracking", "POL-TRK: in transit and within expected delivery date"),
}
