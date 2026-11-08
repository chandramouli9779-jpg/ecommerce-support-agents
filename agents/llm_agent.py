"""LLM-Based Agent (LangChain + local Ollama, tool calling).

Mechanism:
  1. A structured task prompt (raw customer messages alone made qwen3:1.7b
     describe tool calls instead of making them - see diag2 results).
  2. A ReAct-style loop: the model calls tools, gets results, may call more.
     If it talks instead of calling a required tool, it is nudged.
  3. A final step asks for ONE action from the shared action list, as JSON,
     using only the tool results.
  4. Two checks on the output:
       - Evidence check: were at least 2 distinct tools actually called?
       - Claim check: does the explanation state things the tool results
         do not support (e.g. a "delay" when tracking shows none)?

All tools are read-only. The agent recommends; it never issues refunds or
changes orders.
"""
from __future__ import annotations

import json
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

import tools as store
from agents.base import ACTIONS, Decision
from agents.percepts import extract_percepts

MODEL = "qwen3:1.7b"
MAX_ROUNDS = 6
MIN_DISTINCT_TOOLS = 2
REQUIRED_TOOLS = ["get_order_status", "search_return_policy"]
NUDGE_ORDER = ["get_order_status", "search_return_policy",
               "get_delivery_events", "get_refund_status"]


# ---- LangChain tools (thin wrappers over the shared read-only tools) -------
@tool
def get_order_status(order_id: str) -> str:
    """Get the order record: item, status, dates and proof of delivery."""
    return json.dumps(store.get_order_status(order_id))


@tool
def get_delivery_events(order_id: str) -> str:
    """Get the delivery tracking events for an order."""
    return json.dumps(store.get_delivery_events(order_id))


@tool
def get_refund_status(order_id: str) -> str:
    """Get the return inspection and refund records for an order."""
    return json.dumps(store.get_refund_status(order_id))


@tool
def search_return_policy(query: str) -> str:
    """Search the support policies using a short description of the issue."""
    # v0.5: return ALL policies, keyword matches ranked first. In v0.4 only keyword
    # matches were returned, so in Scenario C the verification policy (POL-VER)
    # was never shown to the model (TEST_LOG Run 9, finding 2).
    result = store.search_return_policy(query)
    matched_ids = [m["id"] for m in result["policies"]]
    others = [{"id": x["id"], "title": x["title"], "text": x["text"], "matched_on": []}
              for x in store.load_records()["policies"] if x["id"] not in matched_ids]
    return json.dumps({
        "query": query, "match_count": result["match_count"],
        "note": "All policies are listed; keyword matches come first. "
                "Check which policy's conditions the tool results actually meet.",
        "policies": result["policies"] + others,
    })


LC_TOOLS = {t.name: t for t in [get_order_status, get_delivery_events,
                                get_refund_status, search_return_policy]}

SYSTEM_PROMPT = (
    "You are an e-commerce order and refund support assistant. You must use the "
    "tools to get facts. Never describe a tool call; make it. Base every statement "
    "only on tool results. You only recommend actions; you cannot issue refunds or "
    "change orders."
)


def build_task(case: dict) -> str:
    return (
        f"Order ID: {case['order_id']}\n"
        f"Customer message: {case['customer_message']}\n\n"
        "Task: Call get_order_status, get_delivery_events and get_refund_status for "
        "this order ID, and call search_return_policy with a short description of "
        "the customer's issue. Do not answer until you have the tool results."
    )


def build_final_prompt() -> str:
    options = "\n".join(f"- {k}: {v}" for k, v in ACTIONS.items())
    return (
        "Using ONLY the tool results above, choose exactly ONE next support action "
        f"from this list:\n{options}\n\n"
        "Respond with JSON only, in this form:\n"
        '{"action": "<one action key from the list>", '
        '"explanation": "<2-4 sentences>", '
        '"evidence": ["<fact from a tool result>", "..."]}'
    )


# ---- Output checks ----------------------------------------------------------
def parse_final(text: str) -> dict:
    """Extract the JSON object from the model's final reply."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return {"_parse_error": "no JSON object found", "_raw": text}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return {"_parse_error": str(exc), "_raw": text}


def check_claims(text: str, case: dict) -> list[str]:
    """Flag statements in the explanation that the case data does not support."""
    t = (text or "").lower()
    p = extract_percepts(case)
    issues = []
    delay_supported = p["refund_overdue"] or p["tracking_stalled"] or (
        p["status"] == "in_transit" and not p["within_expected_delivery"])
    if re.search(r"\bdela(y|yed|ys)\b", t) and not delay_supported:
        issues.append("Mentions a delay, but tracking and refund data show no delay.")
    if re.search(r"\b(refunded|refund (has been|was) (processed|issued|completed))\b", t) \
            and p["refund_status"] != "completed":
        issues.append(f"Says the refund was processed, but refund status is '{p['refund_status']}'.")
    if re.search(r"\b(signature|photo)\b", t) and p["has_proof_of_delivery"] is False \
            and not re.search(r"\bno (signature|photo)|without (a )?(signature|photo)", t):
        issues.append("Refers to photo/signature proof, but the record has none.")
    if re.search(r"\b(stolen|theft)\b", t):
        issues.append("Mentions theft, which no tool result can confirm.")
    if re.search(r"\b(wrong|incorrect) address\b", t):
        issues.append("Mentions a wrong address, but no address data exists in the records.")
    # v0.5: false "no tracking" statements (TEST_LOG Run 9, finding 3)
    no_tracking = re.search(r"no tracking|no (delivery |tracking )?(events|updates)|"
                            r"tracking (details |information )?(is |are )?(not available|unavailable)", t)
    if no_tracking and p["tracking_event_count"] > 0:
        issues.append(f"Says there is no tracking, but {p['tracking_event_count']} "
                      "tracking events were returned.")
    # v0.5: treating a non-delivered order as delivered (TEST_LOG Run 9, finding 2)
    cleaned = re.sub(r"\bundelivered\b|\b(not|never|yet to be)\b(\s+\w+){0,2}?\s+delivered\b", "", t)
    if re.search(r"\bdelivered\b", cleaned) and p["status"] not in ("delivered", "returned"):
        issues.append(f"Treats the order as delivered, but the record status is '{p['status']}'.")
    other_ids = set(re.findall(r"ord-\d{4}", t)) - {case["order_id"].lower()}
    if other_ids:
        issues.append(f"Mentions other order IDs: {sorted(other_ids)}.")
    return issues


def check_safety(action: str, case: dict) -> list[str]:
    """Flag actions that would be risky given the record (reported, not overridden)."""
    p = extract_percepts(case)
    warnings = []
    if not p["record_consistent"] and action in ("offer_replacement_now", "advise_return_process"):
        warnings.append("Recommends a refund/return path although the record conflicts "
                        "with the customer's message.")
    if action == "offer_replacement_now":
        warnings.append("Immediate replacement/refund bypasses the investigation step in policy.")
    return warnings


def check_action_conditions(action: str, case: dict) -> list[str]:
    """v0.5: confirm the data meets the chosen action's conditions (reported, not overridden)."""
    p = extract_percepts(case)
    rules = {
        "open_carrier_investigation": [
            (p["status"] == "delivered", f"order status is '{p['status']}', not delivered"),
            (p["reports_not_received"], "customer does not report non-receipt"),
            (p["reported_within_dnr_window"], "not reported within 7 days of delivery"),
        ],
        "open_carrier_trace": [
            (p["tracking_stalled"], "tracking is not stalled beyond 5 business days"),
        ],
        "share_tracking": [
            (p["status"] == "in_transit", f"order status is '{p['status']}', not in transit"),
            (p["tracking_event_count"] > 0, "there are no tracking events to share"),
        ],
        "escalate_to_payments": [
            (p["refund_overdue"], "refund is not overdue"),
        ],
        "inform_refund_in_progress": [
            (p["refund_pending"], "there is no pending refund"),
            (not p["refund_overdue"], "refund is overdue, so 'in progress' understates it"),
        ],
        "advise_return_process": [
            (p["status"] == "delivered", f"order status is '{p['status']}', not delivered"),
        ],
        "request_clarification_and_flag": [
            (not p["record_consistent"], "record is consistent; clarification may be unnecessary"),
        ],
    }
    issues = [f"{action}: {why}." for ok, why in rules.get(action, []) if not ok]
    if not p["record_consistent"] and action not in ("request_clarification_and_flag",
                                                      "escalate_to_human"):
        issues.append("Record conflicts with the customer's message (item, status or "
                      "tracking), but the action does not address it.")
    return issues


# ---- The agent ----------------------------------------------------------------
class LLMAgent:
    name = "LLM (Ollama + tools)"
    mechanism = "Local LLM via LangChain; ReAct tool loop over read-only tools, then a JSON decision"

    def __init__(self, model: str = MODEL, llm=None, final_llm=None):
        self.model = model
        self._llm = llm
        self._final_llm = final_llm

    def _models(self):
        if self._llm is None:
            from langchain_ollama import ChatOllama
            self._llm = ChatOllama(model=self.model, temperature=0, reasoning=False)
            self._final_llm = ChatOllama(model=self.model, temperature=0,
                                         reasoning=False, format="json")
        return self._llm.bind_tools(list(LC_TOOLS.values())), self._final_llm or self._llm

    def decide(self, case: dict) -> Decision:
        start = time.perf_counter()
        trace, nudges, cache, duplicates = [], 0, {}, 0
        try:
            llm_tools, final_llm = self._models()
            messages = [SystemMessage(content=SYSTEM_PROMPT),
                        HumanMessage(content=build_task(case))]

            for round_no in range(1, MAX_ROUNDS + 1):
                ai = llm_tools.invoke(messages)
                messages.append(ai)
                if ai.tool_calls:
                    for call in ai.tool_calls:
                        key = (call["name"], json.dumps(call["args"], sort_keys=True))
                        repeated = key in cache
                        if repeated:  # v0.5: reuse result of an identical earlier call
                            duplicates += 1
                            result = cache[key]
                            content = json.dumps({"note": "Identical call already made; "
                                                  "same result as before.",
                                                  "result": json.loads(result)})
                        else:
                            fn = LC_TOOLS.get(call["name"])
                            result = fn.invoke(call["args"]) if fn else json.dumps(
                                {"error": f"unknown tool {call['name']}"})
                            cache[key] = result
                            content = result
                        trace.append({"round": round_no, "tool": call["name"],
                                      "args": call["args"], "result": json.loads(result),
                                      "repeated": repeated})
                        messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
                    continue
                used = {t["tool"] for t in trace}
                missing = [n for n in NUDGE_ORDER if n not in used]
                needs_more = (len(used) < MIN_DISTINCT_TOOLS
                              or any(r not in used for r in REQUIRED_TOOLS))
                if needs_more and missing:
                    nudges += 1
                    target = next((r for r in REQUIRED_TOOLS if r not in used), missing[0])
                    arg = (f"query describing the issue" if target == "search_return_policy"
                           else f"order_id {case['order_id']}")
                    messages.append(HumanMessage(content=f"Call {target} now with {arg}."))
                    continue
                break

            messages.append(HumanMessage(content=build_final_prompt()))
            final_msg = final_llm.invoke(messages)
            parsed = parse_final(final_msg.content)
        except Exception as exc:  # e.g. Ollama not running
            return Decision(self.name, self.mechanism, "escalate_to_human",
                            [f"LLM agent could not run: {type(exc).__name__}: {exc}",
                             "Is the Ollama app running and the model pulled?"],
                            {"error": str(exc), "tool_calls": trace},
                            "LLM unavailable - escalated")

        distinct = sorted({t["tool"] for t in trace})
        evidence_ok = len(distinct) >= MIN_DISTINCT_TOOLS
        action = parsed.get("action")
        notes = []
        if action not in ACTIONS:
            notes.append(f"Model returned invalid action {action!r}; defaulted to escalate_to_human.")
            action = "escalate_to_human"
        explanation = str(parsed.get("explanation", ""))
        evidence = parsed.get("evidence", [])
        claim_issues = check_claims(explanation + " " + " ".join(map(str, evidence)), case)
        safety = check_safety(action, case)
        action_issues = check_action_conditions(action, case)

        reasoning = [f"Tools called ({len(trace)} calls, {duplicates} repeated, {nudges} nudges): "
                     f"{', '.join(distinct) or 'none'}.",
                     f"Evidence check: {'PASS' if evidence_ok else 'FAIL'} "
                     f"({len(distinct)} distinct tools, minimum {MIN_DISTINCT_TOOLS}).",
                     f"Model explanation: {explanation or '(none)'}"]
        reasoning += notes
        reasoning += [f"Claim check: {i}" for i in claim_issues] or ["Claim check: no unsupported claims found."]
        reasoning += [f"Safety check: {w}" for w in safety]
        reasoning += ([f"Action check: {i}" for i in action_issues]
                      or ["Action check: the data meets this action's conditions."])

        return Decision(
            self.name, self.mechanism, action, reasoning,
            {"model": self.model, "tool_calls": trace, "distinct_tools": distinct,
             "nudges": nudges, "evidence_check": evidence_ok,
             "claim_issues": claim_issues, "safety_warnings": safety,
             "action_issues": action_issues, "repeated_calls": duplicates,
             "model_evidence": evidence, "raw_final": parsed,
             "seconds": round(time.perf_counter() - start, 1)},
            f"{len(distinct)} tools, {nudges} nudges, evidence {'PASS' if evidence_ok else 'FAIL'}, "
            f"{len(claim_issues)} claim issue(s), {len(action_issues)} action issue(s)")
