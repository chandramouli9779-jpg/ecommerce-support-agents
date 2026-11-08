"""Build the comparison table rows shared by the Streamlit UI and its tests."""
from __future__ import annotations

from agents.base import ACTIONS, Decision


def comparison_rows(decisions: list[Decision], expected_action: str,
                    llm_decision: Decision | None) -> list[dict]:
    rows = []
    for d in decisions + ([llm_decision] if llm_decision else []):
        rows.append({
            "Agent": d.agent,
            "Decision mechanism": d.mechanism,
            "Recommended action": d.action_label,
            "Matches policy": "✔" if d.action == expected_action else "✘",
            "Key reason": d.summary,
        })
    if llm_decision is None:
        rows.append({"Agent": "LLM (Ollama + tools)",
                     "Decision mechanism": "Local LLM via LangChain with tool calling",
                     "Recommended action": "Not run yet",
                     "Matches policy": "–", "Key reason": "Use the Run LLM agent button."})
    return rows


def agreement_summary(decisions: list[Decision], expected_action: str,
                      llm_decision: Decision | None) -> str:
    all_d = decisions + ([llm_decision] if llm_decision else [])
    matches = sum(d.action == expected_action for d in all_d)
    return (f"{matches} of {len(all_d)} agents recommend the policy-expected action: "
            f"{ACTIONS[expected_action]}.")
