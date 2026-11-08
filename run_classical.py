"""Run the five classical agents on every scenario and print a comparison.

    python run_classical.py
"""
import copy

from agents import classical_agents
from scenarios import EXPECTED_ACTIONS, SCENARIOS, get_case_file


def main() -> None:
    agents = classical_agents()
    for sid, sc in SCENARIOS.items():
        case = get_case_file(sid)
        expected, why = EXPECTED_ACTIONS[sid]
        print(f"\n=== Scenario {sid}: {sc['title']} ({sc['test_type']})")
        print(f"    Policy-expected action: {expected}  [{why}]")
        for agent in agents:
            snapshot = copy.deepcopy(case)
            d = agent.decide(case)
            assert case == snapshot, f"{agent.name} modified the shared input"
            mark = "OK " if d.action == expected else "DIFF"
            print(f"  [{mark}] {d.agent:<19} -> {d.action}")
            print(f"         {d.summary}")


if __name__ == "__main__":
    main()
