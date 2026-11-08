"""Utility-Based Agent.

Mechanism: scores EVERY candidate action with a utility function that trades
off several outcomes, then picks the highest utility:

    U = 0.35*satisfaction + 0.40*compliance - 0.10*cost - 0.15*risk

Each outcome is estimated in [0, 1] from the percepts. The weights are a design
choice (a stated limitation): different weights can change the decision.
"""
from agents.base import ACTIONS, Decision
from agents.percepts import RETURN_WINDOW_DAYS, extract_percepts

WEIGHTS = {"satisfaction": 0.35, "compliance": 0.40, "cost": -0.10, "risk": -0.15}


def estimate_outcomes(action: str, p: dict) -> dict:
    c = p["record_consistent"]
    dnr_case = (p["status"] == "delivered" and p["reports_not_received"]
                and p["reported_within_dnr_window"])
    if action == "share_tracking":
        ok = p["status"] == "in_transit" and p["within_expected_delivery"]
        return dict(satisfaction=0.6 if p["status"] == "in_transit" else 0.2,
                    compliance=1.0 if ok else 0.2, cost=0.05, risk=0.1 if c else 0.5)
    if action == "open_carrier_investigation":
        return dict(satisfaction=0.6 if p["reports_not_received"] else 0.2,
                    compliance=1.0 if dnr_case and not p["has_proof_of_delivery"] else 0.2,
                    cost=0.3, risk=0.1 if c else 0.6)
    if action == "open_carrier_trace":
        return dict(satisfaction=0.5, compliance=1.0 if p["tracking_stalled"] and c else 0.3,
                    cost=0.3, risk=0.2)
    if action == "offer_replacement_now":
        wants = p["reports_not_received"] or p["requests_refund"]
        return dict(satisfaction=0.95 if wants else 0.3,
                    compliance=0.2 if dnr_case else 0.0,  # policy requires investigation first
                    cost=0.9, risk=0.5 if c else 0.8)
    if action == "escalate_to_payments":
        return dict(satisfaction=0.8 if p["refund_overdue"] else 0.3,
                    compliance=1.0 if p["refund_overdue"] else 0.2, cost=0.3, risk=0.1)
    if action == "inform_refund_in_progress":
        within = p["refund_pending"] and not p["refund_overdue"]
        return dict(satisfaction=0.5 if within else 0.2,
                    compliance=1.0 if within else (0.3 if p["refund_pending"] else 0.0),
                    cost=0.05, risk=0.2)
    if action == "advise_return_process":
        ok = (c and p["status"] == "delivered" and p["requests_refund"]
              and (p["days_since_delivery"] or 99) <= RETURN_WINDOW_DAYS)
        return dict(satisfaction=0.6 if p["requests_refund"] else 0.2,
                    compliance=0.8 if ok else 0.1, cost=0.2, risk=0.3 if c else 0.7)
    if action == "request_clarification_and_flag":
        return dict(satisfaction=0.4 if not c else 0.2, compliance=1.0 if not c else 0.4,
                    cost=0.1, risk=0.05)
    if action == "escalate_to_human":
        return dict(satisfaction=0.5, compliance=0.6, cost=0.6, risk=0.1)
    raise ValueError(action)


def utility(outcomes: dict) -> float:
    return round(sum(WEIGHTS[k] * outcomes[k] for k in WEIGHTS), 4)


class UtilityBasedAgent:
    name = "Utility-Based"
    mechanism = "Scores every action with a weighted utility function; picks the maximum"

    def decide(self, case: dict) -> Decision:
        p = extract_percepts(case)
        scores = {a: {**estimate_outcomes(a, p), "utility": utility(estimate_outcomes(a, p))}
                  for a in ACTIONS}
        ranked = sorted(scores, key=lambda a: scores[a]["utility"], reverse=True)
        best, second = ranked[0], ranked[1]
        r = [f"Utility = {WEIGHTS}.",
             f"Best: {best} (U={scores[best]['utility']}); "
             f"runner-up: {second} (U={scores[second]['utility']}).",
             f"Margin: {round(scores[best]['utility'] - scores[second]['utility'], 4)}."]
        if "offer_replacement_now" in scores:
            o = scores["offer_replacement_now"]
            r.append(f"Immediate replacement scores high satisfaction ({o['satisfaction']}) "
                     f"but low compliance ({o['compliance']}) and high cost ({o['cost']}), "
                     f"so U={o['utility']}.")
        return Decision(self.name, self.mechanism, best, r,
                        {"scores": scores, "ranking": ranked}, r[1])
