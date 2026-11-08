"""Shared decision format and action vocabulary for all agents."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# Every agent chooses from this same set of support actions.
# All actions are recommendations only - nothing here issues refunds or edits orders.
ACTIONS = {
    "share_tracking": "Share tracking details with the customer",
    "open_carrier_investigation": "Open a carrier investigation (delivered but not received)",
    "open_carrier_trace": "Open a carrier trace (no tracking updates)",
    "offer_replacement_now": "Offer an immediate replacement or refund",
    "escalate_to_payments": "Escalate the refund to the payments team",
    "inform_refund_in_progress": "Tell the customer the refund is in progress",
    "advise_return_process": "Advise the customer on the return process",
    "request_clarification_and_flag": "Ask the customer to confirm details and flag the record for review",
    "escalate_to_human": "Escalate to a human support agent",
}


@dataclass
class Decision:
    agent: str
    mechanism: str
    action: str
    reasoning: list[str]
    details: dict = field(default_factory=dict)
    summary: str = ""

    @property
    def action_label(self) -> str:
        return ACTIONS.get(self.action, self.action)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["action_label"] = self.action_label
        return data
