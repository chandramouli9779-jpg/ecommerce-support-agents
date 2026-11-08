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


def test_policy_tool_falls_back_to_all_policies():
    from agents.llm_agent import search_return_policy
    result = json.loads(search_return_policy.invoke({"query": "zzz unrelated words"}))
    assert result["match_count"] == 0 and len(result["policies"]) == 5


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
