"""Goal-Based Agent.

Mechanism: has an explicit GOAL STATE and searches for the cheapest sequence of
actions (a plan) whose effects reach that goal. Each action has preconditions
and effects. Uniform-cost search over a small state space.

Goal: the customer's issue is addressed according to policy AND the customer
is informed. The record must be verified before any other action.
"""
import heapq

from agents.base import Decision
from agents.percepts import extract_percepts

GOAL = {"issue_addressed": True, "customer_informed": True}


def _action_models(p: dict) -> list[tuple]:
    """(name, cost, precondition(state), effects) built from the percepts."""
    ok = lambda s: s["verified"] and s["consistent"]
    return [
        ("verify_record", 1, lambda s: not s["verified"],
         {"verified": True, "consistent": p["record_consistent"]}),
        ("request_clarification_and_flag", 1, lambda s: s["verified"] and not s["consistent"],
         {"issue_addressed": True, "customer_informed": True}),
        ("open_carrier_investigation", 2,
         lambda s: ok(s) and p["status"] == "delivered" and p["reports_not_received"]
         and p["reported_within_dnr_window"] and not p["has_proof_of_delivery"],
         {"issue_addressed": True}),
        ("escalate_to_payments", 2, lambda s: ok(s) and p["refund_overdue"],
         {"issue_addressed": True}),
        ("inform_refund_in_progress", 1,
         lambda s: ok(s) and p["refund_pending"] and not p["refund_overdue"],
         {"issue_addressed": True, "customer_informed": True}),
        ("share_tracking", 1,
         lambda s: ok(s) and p["status"] == "in_transit" and p["within_expected_delivery"],
         {"issue_addressed": True, "customer_informed": True}),
        ("open_carrier_trace", 2, lambda s: ok(s) and p["tracking_stalled"],
         {"issue_addressed": True}),
        ("notify_customer", 1, lambda s: s["issue_addressed"] and not s["customer_informed"],
         {"customer_informed": True}),
        ("escalate_to_human", 10, lambda s: s["verified"], {"issue_addressed": True}),
    ]


class GoalBasedAgent:
    name = "Goal-Based"
    mechanism = "Explicit goal state; searches for the cheapest plan of actions that reaches it"

    def plan(self, p: dict) -> tuple[list[str], int, int]:
        start = {"verified": False, "consistent": False,
                 "issue_addressed": False, "customer_informed": False}
        models = _action_models(p)
        frontier = [(0, 0, [], start)]
        seen, explored, tie = set(), 0, 0
        while frontier:
            cost, _, plan, state = heapq.heappop(frontier)
            key = tuple(sorted(state.items()))
            if key in seen:
                continue
            seen.add(key)
            explored += 1
            if all(state[k] == v for k, v in GOAL.items()):
                return plan, cost, explored
            for name, step_cost, pre, effects in models:
                if pre(state):
                    tie += 1
                    heapq.heappush(frontier, (cost + step_cost, tie, plan + [name],
                                              {**state, **effects}))
        return [], -1, explored

    def decide(self, case: dict) -> Decision:
        p = extract_percepts(case)
        plan, cost, explored = self.plan(p)
        main = next((a for a in plan if a not in ("verify_record", "notify_customer")),
                    "escalate_to_human")
        r = [f"Goal: {GOAL}.",
             f"Searched {explored} states; cheapest plan (cost {cost}): {' -> '.join(plan)}.",
             f"Main support action in the plan: {main}."]
        if not p["record_consistent"]:
            r.append("Verification found the record inconsistent, so only clarification "
                     "satisfies the preconditions.")
        return Decision(self.name, self.mechanism, main, r, {"plan": plan, "plan_cost": cost},
                        f"Plan: {' -> '.join(plan)}")
