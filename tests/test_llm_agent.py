"""Tests for the LLM agent using a scripted fake model (no Ollama needed)."""
import copy
import json

from langchain_core.messages import AIMessage

from agents.base import ACTIONS
from agents.llm_agent import LLMAgent, check_claims, check_safety, parse_final
from scenarios import get_case_file


class FakeLLM:
    """Returns pre-scripted messages in order; mimics bind_tools/invoke."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def bind_tools(self, _tools):
        return self

    def invoke(self, _messages):
        self.calls += 1
        return self.responses.pop(0)


def call(name, args, i):
    return {"name": name, "args": args, "id": f"call-{i}", "type": "tool_call"}


def final(action, explanation="Based on the tool results."):
    return AIMessage(content=json.dumps({"action": action, "explanation": explanation,
                                         "evidence": ["status delivered"]}))


def test_full_loop_with_two_tools_passes_evidence_check():
    llm = FakeLLM([
        AIMessage(content="", tool_calls=[call("get_order_status", {"order_id": "ORD-1001"}, 1),
                                          call("search_return_policy", {"query": "not received"}, 2)]),
        AIMessage(content="Done."),
    ])
    final_llm = FakeLLM([final("open_carrier_investigation")])
    case = get_case_file("A")
    snapshot = copy.deepcopy(case)
    d = LLMAgent(llm=llm, final_llm=final_llm).decide(case)
    assert case == snapshot
    assert d.action == "open_carrier_investigation"
    assert d.details["evidence_check"] is True
    assert d.details["nudges"] == 0
    assert d.details["tool_calls"][0]["result"]["status"] == "delivered"


def test_agent_nudges_when_model_talks_instead_of_calling_tools():
    llm = FakeLLM([
        AIMessage(content="Let me look that up for you."),
        AIMessage(content="", tool_calls=[call("get_order_status", {"order_id": "ORD-1002"}, 1)]),
        AIMessage(content="", tool_calls=[call("search_return_policy", {"query": "refund pending"}, 2)]),
        AIMessage(content="Done."),
    ])
    d = LLMAgent(llm=llm, final_llm=FakeLLM([final("escalate_to_payments")])).decide(get_case_file("B"))
    assert d.details["nudges"] == 1
    assert d.details["distinct_tools"] == ["get_order_status", "search_return_policy"]


def test_invalid_action_falls_back_to_escalation():
    llm = FakeLLM([AIMessage(content="", tool_calls=[
        call("get_order_status", {"order_id": "ORD-1004"}, 1),
        call("search_return_policy", {"query": "tracking"}, 2)]), AIMessage(content="ok")])
    d = LLMAgent(llm=llm, final_llm=FakeLLM([final("refund_everything")])).decide(get_case_file("D"))
    assert d.action == "escalate_to_human"
    assert any("invalid action" in r for r in d.reasoning)


def test_ollama_unavailable_returns_safe_decision():
    class Broken(FakeLLM):
        def invoke(self, _m):
            raise ConnectionError("connection refused")
    d = LLMAgent(llm=Broken([]), final_llm=Broken([])).decide(get_case_file("A"))
    assert d.action == "escalate_to_human"
    assert "error" in d.details


def test_policy_tool_returns_all_policies_matches_first():
    from agents.llm_agent import search_return_policy
    result = json.loads(search_return_policy.invoke({"query": "zzz unrelated words"}))
    assert result["match_count"] == 0 and len(result["policies"]) == 5
    # v0.4 Scenario C query: POL-DNR matched, but POL-VER must still be visible
    c_query = "I ordered a brown backpack on ORD-1003 and it was delivered damaged."
    result = json.loads(search_return_policy.invoke({"query": c_query}))
    ids = [x["id"] for x in result["policies"]]
    assert ids[0] == "POL-DNR" and "POL-VER" in ids and len(ids) == 5


def test_claim_check_flags_unsupported_delay_in_scenario_a():
    issues = check_claims("It could be due to a delivery delay.", get_case_file("A"))
    assert any("delay" in i for i in issues)


def test_claim_check_allows_supported_delay_in_scenario_b():
    assert check_claims("The refund is delayed beyond the time limit.", get_case_file("B")) == []


def test_claim_check_flags_false_refund_and_other_ids():
    issues = check_claims("Your refund has been processed, like ORD-1001.", get_case_file("B"))
    assert len(issues) == 2


def test_claim_check_accepts_correct_no_proof_statement():
    assert check_claims("There is no signature or photo proof.", get_case_file("A")) == []


def test_safety_check_flags_refund_path_on_conflicting_record():
    assert check_safety("advise_return_process", get_case_file("C"))
    assert check_safety("request_clarification_and_flag", get_case_file("C")) == []


def test_parse_final_handles_think_tags_and_bad_json():
    assert parse_final('<think>x</think>{"action": "share_tracking"}')["action"] == "share_tracking"
    assert "_parse_error" in parse_final("no json here")


def test_all_actions_listed_in_final_prompt():
    from agents.llm_agent import build_final_prompt
    prompt = build_final_prompt()
    assert all(a in prompt for a in ACTIONS)


# ---- v0.5 regression tests using the actual model explanations from TEST_LOG Run 9 ----
RUN9_C = ("The policy indicates that a carrier investigation should be opened if the item is "
          "delivered but not received within 7 days. The customer reported the item as delivered "
          "damaged, and the investigation is eligible once the 3 business day period has passed.")
RUN9_D = ("The order is in transit and has no tracking updates. The tool result indicates no "
          "tracking details are available, so opening a carrier trace is appropriate. The "
          "evidence shows the order is in transit with no tracking events.")
RUN9_A = ("The customer reported their order as delivered but did not receive the package. The "
          "'Delivered but not received' policy indicates a carrier investigation is needed.")


def test_run9_scenario_c_explanation_now_flagged():
    from agents.llm_agent import check_action_conditions
    case = get_case_file("C")
    assert any("record status is 'shipped'" in i for i in check_claims(RUN9_C, case))
    issues = check_action_conditions("open_carrier_investigation", case)
    assert any("not delivered" in i for i in issues)
    assert any("does not address" in i for i in issues)


def test_run9_scenario_d_explanation_now_flagged():
    from agents.llm_agent import check_action_conditions
    case = get_case_file("D")
    assert any("2 tracking events" in i for i in check_claims(RUN9_D, case))
    assert check_action_conditions("open_carrier_trace", case)


def test_run9_correct_answers_stay_clean():
    from agents.llm_agent import check_action_conditions
    assert check_claims(RUN9_A, get_case_file("A")) == []
    for sid, action in [("A", "open_carrier_investigation"), ("B", "escalate_to_payments"),
                        ("C", "request_clarification_and_flag"), ("D", "share_tracking")]:
        assert check_action_conditions(action, get_case_file(sid)) == [], sid


def test_not_delivered_wording_is_not_flagged():
    assert check_claims("The order has not been delivered yet.", get_case_file("D")) == []


def test_repeated_identical_call_reuses_result():
    same = {"query": "not received"}
    llm = FakeLLM([
        AIMessage(content="", tool_calls=[call("get_order_status", {"order_id": "ORD-1001"}, 1),
                                          call("search_return_policy", same, 2)]),
        AIMessage(content="", tool_calls=[call("search_return_policy", same, 3)]),
        AIMessage(content="Done."),
    ])
    d = LLMAgent(llm=llm, final_llm=FakeLLM([final("open_carrier_investigation")])).decide(
        get_case_file("A"))
    assert d.details["repeated_calls"] == 1
    assert [t["repeated"] for t in d.details["tool_calls"]] == [False, False, True]
