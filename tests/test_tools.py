"""Tests for the read-only tools and shared scenario data."""
import json

import pytest

from scenarios import SCENARIOS, get_case_file
from tools import (DATA_FILE, business_days_between, get_delivery_events,
                   get_order_status, get_refund_status, search_return_policy)


def test_order_found_and_case_insensitive():
    result = get_order_status(" ord-1001 ")
    assert result["found"] is True
    assert result["status"] == "delivered"


def test_unknown_order():
    assert get_order_status("ORD-9999")["found"] is False
    assert get_delivery_events("ORD-9999")["found"] is False
    assert get_refund_status("ORD-9999")["found"] is False


def test_scenario_a_delivery_has_no_proof():
    order = get_order_status("ORD-1001")
    events = get_delivery_events("ORD-1001")
    assert order["proof_of_delivery"] == {"photo": False, "signature": False}
    assert "front door" in events["last_event"]["event"]


def test_scenario_b_refund_overdue():
    refund = get_refund_status("ORD-1002")
    assert refund["return"]["inspection_status"] == "passed"
    assert refund["refund"]["status"] == "pending"
    # Inspection 2026-10-27 (Tue) to reference date 2026-11-06 (Fri) = 8 business days
    assert refund["business_days_since_inspection"] == 8


def test_scenario_c_record_conflicts_with_message():
    case = get_case_file("C")
    assert "backpack" in case["customer_message"].lower()
    assert "backpack" not in case["order"]["item"].lower()
    assert case["order"]["status"] == "shipped"
    assert case["delivery"]["event_count"] == 0


def test_scenario_d_in_transit():
    order = get_order_status("ORD-1004")
    assert order["status"] == "in_transit"
    assert order["expected_delivery"] == "2026-11-08"


@pytest.mark.parametrize("query,expected", [
    ("package not received", "POL-DNR"),
    ("refund pending after inspection", "POL-REF"),
    ("order record mismatch", "POL-VER"),
    ("tracking for in transit order", "POL-TRK"),
])
def test_policy_search(query, expected):
    result = search_return_policy(query)
    assert result["match_count"] >= 1
    assert result["policies"][0]["id"] == expected


def test_business_days_skip_weekends():
    from datetime import date
    # Fri 2026-10-30 -> Mon 2026-11-02 is 1 business day
    assert business_days_between("2026-10-30", date(2026, 11, 2)) == 1


def test_all_scenarios_build_same_shape():
    keys = None
    for sid in SCENARIOS:
        case = get_case_file(sid)
        if keys is None:
            keys = set(case)
        assert set(case) == keys


def test_tools_do_not_modify_records():
    before = DATA_FILE.read_text(encoding="utf-8")
    for sid in SCENARIOS:
        get_case_file(sid)
    search_return_policy("refund")
    assert DATA_FILE.read_text(encoding="utf-8") == before
    json.loads(before)
