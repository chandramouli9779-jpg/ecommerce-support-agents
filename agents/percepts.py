"""Turn the shared case file into percepts (facts) the classical agents can use.

Thresholds below are copied by hand from the policy text in data/records.json.
That hand-coding is a known limitation of the classical agents: if the policy
text changes, these numbers must be updated manually.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

DNR_REPORT_WINDOW_DAYS = 7      # POL-DNR
REFUND_SLA_BUSINESS_DAYS = 5    # POL-REF
TRACE_AFTER_BUSINESS_DAYS = 5   # POL-TRK
RETURN_WINDOW_DAYS = 30         # POL-RET

NOT_RECEIVED_PHRASES = ["not received", "never received", "never got", "didn't receive",
                        "did not receive", "nothing was at my door", "missing"]
REFUND_PHRASES = ["refund", "money back"]
DAMAGE_PHRASES = ["damaged", "broken", "defective"]
ITEM_CLAIM = re.compile(r"\b(?:ordered|returned|bought)\s+(?:a|an|the)\s+([a-z][a-z ]*?)\s+(?:on|for|and|from)\b")


def business_days(start: str, end: date) -> int:
    current, days = date.fromisoformat(start), 0
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def add_business_days(start: str, n: int) -> date:
    current = date.fromisoformat(start)
    while n > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            n -= 1
    return current


def _has(text: str, phrases: list[str]) -> bool:
    return any(p in text for p in phrases)


def extract_percepts(case: dict) -> dict:
    """Derive facts from the case file. Pure function: never modifies `case`."""
    today = date.fromisoformat(case["reference_date"])
    msg = case["customer_message"].lower()
    order, delivery, refund = case["order"], case["delivery"], case["refund"]

    p = {
        "order_found": order.get("found", False),
        "status": order.get("status"),
        "reports_not_received": _has(msg, NOT_RECEIVED_PHRASES),
        "requests_refund": _has(msg, REFUND_PHRASES),
        "reports_damage": _has(msg, DAMAGE_PHRASES),
        "message_says_delivered": "delivered" in msg,
        "tracking_event_count": delivery.get("event_count", 0),
    }

    # Item named by the customer vs item on the record
    claim = ITEM_CLAIM.search(msg)
    p["item_record"] = order.get("item")
    p["item_claimed"] = claim.group(1).strip() if claim else None
    if p["item_claimed"] and p["item_record"]:
        overlap = set(p["item_claimed"].split()) & set(p["item_record"].lower().split())
        p["item_mismatch"] = not overlap
    else:
        p["item_mismatch"] = False

    # Customer says "delivered" but the record says it is not
    p["status_conflict"] = (p["message_says_delivered"]
                            and p["status"] not in ("delivered", "returned"))
    # Record says the parcel moved but there is no tracking at all
    p["tracking_missing"] = (p["status"] in ("shipped", "in_transit", "delivered")
                             and p["tracking_event_count"] == 0)
    p["record_consistent"] = (p["order_found"] and not p["item_mismatch"]
                              and not p["status_conflict"] and not p["tracking_missing"])

    # Delivery facts
    delivered_on = order.get("delivered_on")
    p["days_since_delivery"] = (today - date.fromisoformat(delivered_on)).days if delivered_on else None
    pod = order.get("proof_of_delivery") or {}
    p["has_proof_of_delivery"] = bool(pod.get("photo") or pod.get("signature"))
    p["reported_within_dnr_window"] = (p["days_since_delivery"] is not None
                                       and p["days_since_delivery"] <= DNR_REPORT_WINDOW_DAYS)
    expected = order.get("expected_delivery")
    p["within_expected_delivery"] = bool(expected) and today <= date.fromisoformat(expected)
    if p["tracking_event_count"]:
        p["bdays_since_last_tracking"] = delivery.get("business_days_since_last_event", 0)
    elif order.get("order_date"):
        p["bdays_since_last_tracking"] = business_days(order["order_date"], today)
    else:
        p["bdays_since_last_tracking"] = None
    p["tracking_stalled"] = (p["status"] in ("shipped", "in_transit")
                             and (p["bdays_since_last_tracking"] or 0) > TRACE_AFTER_BUSINESS_DAYS)

    # Return / refund facts
    ret, ref = refund.get("return"), refund.get("refund")
    p["inspection_passed"] = bool(ret and ret.get("inspection_status") == "passed")
    p["inspection_date"] = ret.get("inspection_date") if ret else None
    p["refund_status"] = ref.get("status") if ref else None
    p["refund_pending"] = p["refund_status"] == "pending"
    p["bdays_since_inspection"] = refund.get("business_days_since_inspection")
    p["refund_overdue"] = (p["refund_pending"] and p["inspection_passed"]
                           and (p["bdays_since_inspection"] or 0) > REFUND_SLA_BUSINESS_DAYS)
    return p
