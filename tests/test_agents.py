"""Tests for the five classical agents."""
import copy

import pytest

from agents import (GoalBasedAgent, ModelBasedReflexAgent, SimpleReflexAgent,
                    UtilityBasedAgent)
from agents.base import ACTIONS
from agents.learning import LearningAgent, classify_situation
from agents.percepts import extract_percepts
from scenarios import EXPECTED_ACTIONS, SCENARIOS, get_case_file


@pytest.fixture
def learner(tmp_path):
    # Use a temporary experience file so tests never touch data/experience.json
    return LearningAgent(experience_path=tmp_path / "experience.json")


@pytest.fixture
def all_agents(learner):
    return [SimpleReflexAgent(), ModelBasedReflexAgent(), GoalBasedAgent(),
            UtilityBasedAgent(), learner]


@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_every_agent_returns_valid_decision_and_leaves_input_unchanged(sid, all_agents):
    case = get_case_file(sid)
    snapshot = copy.deepcopy(case)
    for agent in all_agents:
        d = agent.decide(case)
        assert d.action in ACTIONS
        assert d.reasoning, f"{agent.name} gave no reasoning"
    assert case == snapshot


@pytest.mark.parametrize("sid", list(SCENARIOS))
@pytest.mark.parametrize("agent_cls", [ModelBasedReflexAgent, GoalBasedAgent, UtilityBasedAgent])
def test_state_goal_utility_agents_match_policy(sid, agent_cls):
    assert agent_cls().decide(get_case_file(sid)).action == EXPECTED_ACTIONS[sid][0]


@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_learning_agent_matches_policy_with_seed_experience(sid, learner):
    assert learner.decide(get_case_file(sid)).action == EXPECTED_ACTIONS[sid][0]


def test_simple_reflex_known_limitations():
    agent = SimpleReflexAgent()
    # B: sees "pending" and ignores the 5-business-day limit
    assert agent.decide(get_case_file("B")).action == "inform_refund_in_progress"
    # C: reacts to "money back" without checking the record conflict
    assert agent.decide(get_case_file("C")).action == "advise_return_process"


def test_percepts_detect_scenario_c_conflicts():
    p = extract_percepts(get_case_file("C"))
    assert p["item_mismatch"] and p["status_conflict"] and p["tracking_missing"]
    assert p["record_consistent"] is False


def test_goal_based_plan_starts_with_verification():
    d = GoalBasedAgent().decide(get_case_file("A"))
    assert d.details["plan"][0] == "verify_record"
    assert d.details["plan"][-1] == "notify_customer"


def test_utility_scores_all_actions():
    d = UtilityBasedAgent().decide(get_case_file("A"))
    assert set(d.details["scores"]) == set(ACTIONS)
    ranked = d.details["ranking"]
    assert d.details["scores"][ranked[0]]["utility"] >= d.details["scores"][ranked[1]]["utility"]


def test_learning_agent_updates_counts(learner):
    before = learner.load()["refund_overdue"]["escalate_to_payments"]["success"]
    learner.record_outcome("refund_overdue", "escalate_to_payments", True)
    assert learner.load()["refund_overdue"]["escalate_to_payments"]["success"] == before + 1


def test_learning_agent_changes_decision_after_repeated_failures(learner):
    case = get_case_file("A")
    situation = classify_situation(extract_percepts(case))
    assert learner.decide(case).action == "open_carrier_investigation"
    for _ in range(15):
        learner.record_outcome(situation, "open_carrier_investigation", False)
    assert learner.decide(case).action != "open_carrier_investigation"


def test_learning_agent_reset_restores_seed(learner):
    learner.record_outcome("in_transit", "share_tracking", False)
    learner.reset()
    assert learner.load()["in_transit"]["share_tracking"]["failure"] == 2
