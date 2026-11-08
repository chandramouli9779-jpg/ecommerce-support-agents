"""Run the LLM agent on every scenario (needs the Ollama app running).

    python run_llm.py            # all scenarios
    python run_llm.py A          # one scenario
"""
import copy
import sys

from agents.llm_agent import LLMAgent
from scenarios import EXPECTED_ACTIONS, SCENARIOS, get_case_file


def main(ids: list[str]) -> None:
    agent = LLMAgent()
    for sid in ids:
        case = get_case_file(sid)
        snapshot = copy.deepcopy(case)
        d = agent.decide(case)
        assert case == snapshot, "LLM agent modified the shared input"
        expected = EXPECTED_ACTIONS[sid][0]
        print(f"\n=== Scenario {sid}: {SCENARIOS[sid]['title']}")
        print(f"  Policy-expected: {expected}")
        print(f"  [{'OK ' if d.action == expected else 'DIFF'}] LLM -> {d.action}"
              f"   ({d.details.get('seconds', '?')} s)")
        for t in d.details.get("tool_calls", []):
            print(f"    round {t['round']}: {t['tool']}({t['args']})")
        for line in d.reasoning:
            print(f"  - {line}")


if __name__ == "__main__":
    main([a.upper() for a in sys.argv[1:]] or list(SCENARIOS))
