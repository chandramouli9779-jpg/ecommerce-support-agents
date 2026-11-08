"""Tests for the Streamlit UI (streamlit.testing AppTest; no browser or Ollama needed)."""
import json
import shutil

import pytest
from streamlit.testing.v1 import AppTest

import agents.learning as learning
import agents.llm_agent as llm_module
from agents import classical_agents
from agents.base import Decision
from comparison import agreement_summary, comparison_rows
from scenarios import EXPECTED_ACTIONS, SCENARIOS, get_case_file


@pytest.fixture(autouse=True)
def temp_learning_data(tmp_path, monkeypatch):
    """Point the Learning agent at a temp copy so tests never touch data/experience.json."""
    shutil.copyfile(learning.DATA_DIR / "experience_seed.json", tmp_path / "experience_seed.json")
    monkeypatch.setattr(learning, "DATA_DIR", tmp_path)
    return tmp_path


class FakeLLMAgent:
    """Stands in for the real LLM agent so the UI can be tested without Ollama."""

    def __init__(self, model="fake"):
        self.model = model

    def decide(self, case):
        return Decision("LLM (Ollama + tools)", "fake", "share_tracking", ["fake reasoning"],
                        {"model": self.model, "seconds": 0.1, "tool_calls": [
                            {"round": 1, "tool": "get_order_status",
                             "args": {"order_id": case["order_id"]}, "result": {}, "repeated": False}],
                         "nudges": 0, "repeated_calls": 0, "evidence_check": False,
                         "claim_issues": [], "action_issues": ["example issue"],
                         "safety_warnings": [], "raw_final": {"action": "share_tracking"}},
                        "fake summary")


def load(scenario="A"):
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.session_state["scenario"] = scenario
    return at.run()


@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_app_renders_every_scenario_without_errors(sid):
    at = load(sid)
    assert not at.exception
    assert any("agents recommend" in m.value for m in at.markdown)


def test_learning_feedback_button_updates_experience(temp_learning_data):
    at = load("B")
    before = json.loads((temp_learning_data / "experience.json").read_text())
    at.button(key="ok_B").click().run()
    after = json.loads((temp_learning_data / "experience.json").read_text())
    key = ("refund_overdue", "escalate_to_payments")
    assert after[key[0]][key[1]]["success"] == before[key[0]][key[1]]["success"] + 1
    assert not at.exception


def test_llm_button_shows_result_and_check_warnings(monkeypatch):
    monkeypatch.setattr(llm_module, "LLMAgent", FakeLLMAgent)
    at = load("D")
    at.button(key="run_llm_D").click().run()
    assert not at.exception
    assert any("example issue" in w.value for w in at.warning)
    assert any("6 of 6" in m.value or "5 of 6" in m.value for m in at.markdown)


def test_comparison_rows_include_placeholder_until_llm_runs():
    case = get_case_file("B")
    decisions = [a.decide(case) for a in classical_agents()]
    expected = EXPECTED_ACTIONS["B"][0]
    rows = comparison_rows(decisions, expected, None)
    assert len(rows) == 6 and rows[-1]["Recommended action"] == "Not run yet"
    assert [r["Matches policy"] for r in rows[:5]] == ["✘", "✔", "✔", "✔", "✔"]
    assert agreement_summary(decisions, expected, None).startswith("4 of 5")
