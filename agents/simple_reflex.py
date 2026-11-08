"""Simple Reflex Agent.

Mechanism: fixed condition -> action rules applied to the CURRENT percept only.
The first matching rule fires. No internal state, no timing model, no goals,
no consistency check - so it reacts to surface keywords and status values.
"""
from agents.base import Decision
from agents.percepts import extract_percepts

# (rule name, condition on percepts, action) - checked in this order
RULES = [
    ("Customer says not received and status is delivered",
     lambda p: p["reports_not_received"] and p["status"] == "delivered",
     "open_carrier_investigation"),
    ("Refund status is pending",
     lambda p: p["refund_pending"],
     "inform_refund_in_progress"),
    ("Customer asks for a refund / money back",
     lambda p: p["requests_refund"],
     "advise_return_process"),
    ("Order status is in transit",
     lambda p: p["status"] == "in_transit",
     "share_tracking"),
]


class SimpleReflexAgent:
    name = "Simple Reflex"
    mechanism = "Condition-action rules on the current percept; first match wins"

    def decide(self, case: dict) -> Decision:
        p = extract_percepts(case)
        reasoning = []
        for rule_name, condition, action in RULES:
            if condition(p):
                reasoning.append(f"Rule matched: '{rule_name}' -> {action}.")
                reasoning.append("No history, timing or record-consistency check is performed.")
                return Decision(self.name, self.mechanism, action, reasoning,
                                {"rule_fired": rule_name},
                                f"Rule fired: {rule_name}")
            reasoning.append(f"Rule not matched: '{rule_name}'.")
        reasoning.append("No rule matched -> default escalation.")
        return Decision(self.name, self.mechanism, "escalate_to_human", reasoning,
                        {"rule_fired": None}, "No rule matched")
