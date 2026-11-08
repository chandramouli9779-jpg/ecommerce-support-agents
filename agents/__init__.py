"""The five classical agents. All take the same case file and return a Decision."""
from agents.goal_based import GoalBasedAgent
from agents.learning import LearningAgent
from agents.model_based import ModelBasedReflexAgent
from agents.simple_reflex import SimpleReflexAgent
from agents.utility_based import UtilityBasedAgent


def classical_agents(learning_kwargs: dict | None = None) -> list:
    return [SimpleReflexAgent(), ModelBasedReflexAgent(), GoalBasedAgent(),
            UtilityBasedAgent(), LearningAgent(**(learning_kwargs or {}))]
