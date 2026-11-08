"""Model-Based Reflex Agent.

Mechanism: builds an INTERNAL STATE (a model of the world) from the percept
history - the tracking timeline and the return/refund timeline - plus a model
of how the world should evolve (policy time limits). Rules then act on that
internal state rather than on raw keywords.
"""
from datetime import date

from agents.base import Decision
from agents.percepts import (REFUND_SLA_BUSINESS_DAYS, add_business_days,
                             extract_percepts)


class ModelBasedReflexAgent:
    name = "Model-Based Reflex"
    mechanism = "Internal state from event history + transition model, then rules on that state"

    def build_state(self, case: dict, p: dict) -> dict:
        events = case["delivery"].get("events", [])
        last_event = events[-1]["event"] if events else None
        if last_event is None:
            parcel = "unknown (no tracking history)"
        elif last_event.startswith("delivered"):
            parcel = "delivered"
        elif "return received" in last_event:
            parcel = "returned to warehouse"
        else:
            parcel = "in transit"

        refund_due_by = None
        if p["inspection_passed"] and p["inspection_date"]:
            refund_due_by = add_business_days(p["inspection_date"], REFUND_SLA_BUSINESS_DAYS)
        today = date.fromisoformat(case["reference_date"])
        if not p["refund_pending"]:
            refund_state = "no pending refund"
        elif refund_due_by and today > refund_due_by:
            refund_state = "overdue"
        else:
            refund_state = "within time limit"

        return {
            "parcel_state_from_history": parcel,
            "last_tracking_event": last_event,
            "record_matches_customer": not (p["item_mismatch"] or p["status_conflict"]),
            "history_complete": not p["tracking_missing"],
            "refund_due_by": refund_due_by.isoformat() if refund_due_by else None,
            "refund_state": refund_state,
        }

    def decide(self, case: dict) -> Decision:
        p = extract_percepts(case)
        s = self.build_state(case, p)
        r = [f"Internal state built from history: parcel = {s['parcel_state_from_history']}, "
             f"refund = {s['refund_state']}."]

        if not s["record_matches_customer"] or not s["history_complete"]:
            r.append("State shows the record does not match the customer's account "
                     "or the tracking history is missing.")
            action = "request_clarification_and_flag"
        elif s["refund_state"] == "overdue":
            r.append(f"Refund was due by {s['refund_due_by']} but is still pending.")
            action = "escalate_to_payments"
        elif s["refund_state"] == "within time limit":
            r.append(f"Refund is pending but not yet due (due by {s['refund_due_by']}).")
            action = "inform_refund_in_progress"
        elif (s["parcel_state_from_history"] == "delivered" and p["reports_not_received"]
              and p["reported_within_dnr_window"] and not p["has_proof_of_delivery"]):
            r.append(f"History says delivered ({s['last_tracking_event']}) but the customer "
                     "says not received; reported in time and no proof of delivery.")
            action = "open_carrier_investigation"
        elif s["parcel_state_from_history"] == "in transit" and not p["tracking_stalled"]:
            r.append("History shows the parcel is moving and tracking is up to date.")
            action = "share_tracking"
        elif p["tracking_stalled"]:
            r.append("History shows no tracking movement beyond the allowed time.")
            action = "open_carrier_trace"
        else:
            r.append("Internal state does not match any rule.")
            action = "escalate_to_human"
        return Decision(self.name, self.mechanism, action, r, {"internal_state": s}, r[-1])
