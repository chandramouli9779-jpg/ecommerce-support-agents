"""Read-only support tools over the simulated records in data/records.json.

These functions only READ data. None of them issues refunds or changes orders,
as required by the mini project problem statement.

The same functions are used by the LLM agent (wrapped as LangChain tools) and
by the shared case-file builder in scenarios.py, so every agent sees the same
underlying data.
"""
from __future__ import annotations

import copy
import json
from datetime import date, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "records.json"


def load_records() -> dict:
    """Load the simulated records (fresh copy each call, so nothing is mutated)."""
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def reference_date() -> date:
    """The fixed 'today' used by the simulation, so results are reproducible."""
    return date.fromisoformat(load_records()["reference_date"])


def business_days_between(start: str, end: date | None = None) -> int:
    """Count Mon-Fri days after `start` up to and including `end`."""
    start_d = date.fromisoformat(start)
    end_d = end or reference_date()
    days, current = 0, start_d
    while current < end_d:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def get_order_status(order_id: str) -> dict:
    """Return the order record for an order ID."""
    order = load_records()["orders"].get(order_id.strip().upper())
    if order is None:
        return {"found": False, "order_id": order_id, "message": "Order not found"}
    return {"found": True, "order_id": order_id.strip().upper(), **copy.deepcopy(order)}


def get_delivery_events(order_id: str) -> dict:
    """Return the delivery tracking events for an order ID."""
    records = load_records()
    oid = order_id.strip().upper()
    if oid not in records["orders"]:
        return {"found": False, "order_id": order_id, "message": "Order not found"}
    events = records["delivery_events"].get(oid, [])
    result = {"found": True, "order_id": oid, "events": events, "event_count": len(events)}
    if events:
        result["last_event"] = events[-1]
        result["business_days_since_last_event"] = business_days_between(events[-1]["date"])
    return result


def search_return_policy(query: str) -> dict:
    """Return policy sections whose title or keywords match words in the query."""
    words = query.lower()
    matches = []
    for policy in load_records()["policies"]:
        hits = [k for k in policy["keywords"] if k in words]
        if policy["title"].lower() in words:
            hits.append(policy["title"].lower())
        if hits:
            matches.append({"id": policy["id"], "title": policy["title"],
                            "text": policy["text"], "matched_on": hits})
    matches.sort(key=lambda p: len(p["matched_on"]), reverse=True)
    return {"query": query, "match_count": len(matches), "policies": matches}


def get_refund_status(order_id: str) -> dict:
    """Return return-inspection and refund records for an order ID."""
    records = load_records()
    oid = order_id.strip().upper()
    if oid not in records["orders"]:
        return {"found": False, "order_id": order_id, "message": "Order not found"}
    ret = records["returns"].get(oid)
    refund = records["refunds"].get(oid)
    result = {"found": True, "order_id": oid,
              "return": copy.deepcopy(ret), "refund": copy.deepcopy(refund)}
    if ret and ret.get("inspection_status") == "passed" and refund:
        result["business_days_since_inspection"] = business_days_between(ret["inspection_date"])
    if ret is None and refund is None:
        result["message"] = "No return or refund record for this order"
    return result
