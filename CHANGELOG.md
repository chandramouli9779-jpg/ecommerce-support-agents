# Changelog

Version history of the E-commerce Order and Refund Support Assistant (Mini Project 1).
Test results for each version are in `docs/TEST_LOG.md`.

## [Planned] v0.5 - Fixes from LLM test run 9

Based on findings in `docs/TEST_LOG.md`, Run 9:

1. `search_return_policy` (LLM tool): return all policies ranked by keyword match, so the
   verification policy is always visible to the model.
2. Claim check: flag "no tracking" statements when tracking events exist, and "delivered"
   statements when the record says otherwise.
3. New action-condition check: confirm the chosen action's conditions are present in the data.
4. Reuse the earlier result when the model repeats an identical tool call.

The model's own decision is not forced or overridden; checks only report problems.

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
