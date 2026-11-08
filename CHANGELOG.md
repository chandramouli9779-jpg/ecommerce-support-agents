# Changelog

Version history of the E-commerce Order and Refund Support Assistant (Mini Project 1).
Test results for each version are in `docs/TEST_LOG.md`.

## v0.7 - 2026-11-08 - README

- Added `README.md`: requirements checklist, project structure, Windows setup, run
  instructions, scenarios, the six agents, results and comparison, why decisions differ,
  evidence checking, limitations, testing and version history.

## v0.6 - 2026-11-08 - Streamlit UI

- Added `app.py` (run with `streamlit run app.py`):
  - Scenario picker showing the customer message, order record, tracking events, refund
    record and the full shared case file.
  - The five classical agents run on every page load; each shows its decision, whether it
    matches policy, and agent-specific reasoning (internal state, search plan, utility
    table, past-outcome table).
  - The LLM agent runs on a button press (about 30-45 s) and shows its tool calls, raw JSON
    answer and the evidence, claim, action and safety check results. Results are kept for
    the session.
  - Comparison table of all six agents against the policy-expected action.
  - "It worked" / "It didn't work" buttons for the Learning agent, which update
    `data/experience.json`; sidebar button to reset it from the seed.
  - "All scenarios" tab: decision matrix across Scenarios A-D and matches per agent, with
    a button to run the LLM agent on all four.
- Added `comparison.py` (table helpers) and `.streamlit/config.toml` (theme).
- Added `tests/test_app.py` (7 tests using Streamlit's AppTest; a stand-in LLM agent and a
  temporary learning file are used, so tests need no Ollama and never change
  `data/experience.json`).
- Tests: 64 passed.

## v0.5 - 2026-11-08 - Fixes from LLM test run 9

Based on findings in `docs/TEST_LOG.md`, Run 9. All changes are in `agents/llm_agent.py`.

1. `search_return_policy` (LLM tool): now returns all 5 policies, keyword matches ranked
   first, so the verification policy (POL-VER) is always visible to the model.
2. Claim check: flags "no tracking" statements when tracking events exist, and statements
   treating the order as delivered when the record says otherwise (negations such as
   "not been delivered" are ignored).
3. New action-condition check (`check_action_conditions`): confirms the data meets the
   chosen action's conditions, and flags actions that ignore a record conflict.
4. Repeated identical tool calls reuse the earlier result and are counted. This does not
   remove the extra model round, so it saves little time.

The model's own decision is still not forced or overridden; all checks only report.

Tests: 57 passed (5 new; the policy-fallback test was updated). The new regression tests use
the model's actual Run 9 explanations: the Scenario C and D explanations are now flagged,
while the correct A answer and the correct action for every scenario raise no issues.

Known limitation: the "delivered" claim rule can flag an explanation that only repeats the
customer's words (e.g. "the customer says it was delivered damaged").

## v0.4 - 2026-11-08 - LLM agent

- Added `agents/llm_agent.py`: LangChain + Ollama (`qwen3:1.7b`), four read-only tools,
  structured task prompt, ReAct-style tool loop with nudging, JSON decision from the shared
  action list.
- Added evidence check (minimum 2 distinct tools), claim check and safety check.
- Safe fallback when Ollama is unavailable; policy tool returns all policies when no keyword matches.
- Added `run_llm.py` and `tests/test_llm_agent.py` (12 tests, scripted stand-in model).
- Tests: 52 passed. LLM run: 2 of 4 scenarios match policy.

## v0.3 - 2026-11-06 - Five classical agents

- Added `agents/` package: Simple Reflex, Model-Based Reflex, Goal-Based (uniform-cost plan
  search), Utility-Based (weighted utility), Learning (success/failure counts with updates).
- Shared action vocabulary and `Decision` format (`agents/base.py`); percept extraction
  (`agents/percepts.py`).
- Added `EXPECTED_ACTIONS` to `scenarios.py` (evaluation only; agents never see it).
- Added `data/experience_seed.json`, `run_classical.py`, `tests/test_agents.py`, `.gitignore`.
- Tests: 40 passed. Classical comparison: Simple Reflex differs from policy in B and C.

## v0.2 - 2026-11-06 - Shared data and tools

- Added `data/records.json` (orders, delivery events, returns, refunds, 5 policies; fixed
  reference date 2026-11-06).
- Added `tools.py` with four read-only tools and `scenarios.py` with Scenarios A-D and the
  shared case file builder.
- Added `tests/test_tools.py`, `requirements.txt` (pinned), `pytest.ini`.
- Tests: 13 passed.

## v0.1 - 2026-11-06 - Environment setup

- Installed Ollama 0.40.13 and `qwen3:1.7b`; Python 3.14.3 virtual environment with
  LangChain, Streamlit, pandas, pytest.
- Verified LangChain tool calling; diagnosed that a long conversational prompt stopped tool
  calls and that a structured task prompt fixed it (scratch scripts, not part of submission).
