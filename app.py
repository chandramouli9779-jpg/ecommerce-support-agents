"""Streamlit UI: compare six agents on the same order/refund support case.

    streamlit run app.py
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from agents import classical_agents
from agents.base import ACTIONS, Decision
from agents.learning import LearningAgent
from agents.llm_agent import MODEL as DEFAULT_MODEL
from agents.llm_agent import LLMAgent
from comparison import agreement_summary, comparison_rows
from scenarios import EXPECTED_ACTIONS, SCENARIOS, get_case_file

st.set_page_config(page_title="Order & refund support agents", page_icon="📦", layout="wide")
st.session_state.setdefault("llm_results", {})   # {(scenario_id, model): Decision}
st.session_state.setdefault("flash", None)


# ---- Sidebar -------------------------------------------------------------------
with st.sidebar:
    st.header("Case")
    scenario_id = st.radio(
        "Choose a scenario",
        list(SCENARIOS),
        format_func=lambda s: f"{s}: {SCENARIOS[s]['title']}",
        key="scenario",
    )
    st.caption(f"Test type: {SCENARIOS[scenario_id]['test_type']}")
    st.divider()
    st.header("LLM agent")
    model = st.text_input("Ollama model", value=DEFAULT_MODEL,
                          help="Must already be pulled with `ollama pull`.")
    st.caption("The LLM agent runs only when you press its button, because each run "
               "takes about 30-45 seconds on a laptop CPU.")
    st.divider()
    st.header("Learning agent")
    if st.button("Reset learning history", help="Restore data/experience_seed.json"):
        LearningAgent().reset()
        st.session_state.flash = "Learning history reset to the seed data."
        st.rerun()
    st.caption("All tools are read-only. No agent issues refunds or changes orders.")

if st.session_state.flash:
    st.toast(st.session_state.flash)
    st.session_state.flash = None


# ---- Helpers -------------------------------------------------------------------
def run_classical(case: dict) -> list[Decision]:
    return [agent.decide(case) for agent in classical_agents()]


def verdict(d: Decision, expected: str) -> str:
    return "✔ matches policy" if d.action == expected else "✘ differs from policy"


def show_details(d: Decision) -> None:
    """Agent-specific view of how the decision was reached."""
    det = d.details
    if "internal_state" in det:
        st.markdown("**Internal state built from history**")
        st.dataframe(pd.DataFrame([(k, str(v)) for k, v in det["internal_state"].items()],
                                  columns=["State", "Value"]),
                     hide_index=True, width="stretch")
    if "plan" in det:
        st.markdown(f"**Plan found by search** (cost {det['plan_cost']})")
        st.markdown("\n".join(f"{i}. `{step}`" for i, step in enumerate(det["plan"], 1)))
    if "scores" in det:
        st.markdown("**Utility of every action**")
        df = pd.DataFrame(det["scores"]).T.sort_values("utility", ascending=False)
        df.index = [ACTIONS[a] for a in df.index]
        st.dataframe(df, width="stretch")
    if "experience" in det and det["experience"]:
        st.markdown(f"**Past outcomes for situation `{det['situation']}`**")
        df = pd.DataFrame(det["experience"]).T.sort_values("success_rate", ascending=False)
        st.dataframe(df, width="stretch")
    st.markdown("**Reasoning**")
    st.markdown("\n".join(f"- {line}" for line in d.reasoning))


def learning_feedback(d: Decision) -> None:
    situation = d.details.get("situation")
    if not situation:
        return
    st.caption("Record how this recommendation turned out. This updates "
               "data/experience.json and can change future decisions.")
    c1, c2 = st.columns(2)
    if c1.button("It worked", key=f"ok_{scenario_id}", width="stretch"):
        stats = LearningAgent().record_outcome(situation, d.action, True)
        st.session_state.flash = f"Recorded success: {stats['success']}/{stats['success'] + stats['failure']}."
        st.rerun()
    if c2.button("It didn't work", key=f"fail_{scenario_id}", width="stretch"):
        stats = LearningAgent().record_outcome(situation, d.action, False)
        st.session_state.flash = f"Recorded failure: {stats['success']}/{stats['success'] + stats['failure']}."
        st.rerun()


def show_llm_details(d: Decision) -> None:
    det = d.details
    if "error" in det:
        st.error("The LLM agent could not run. Start the Ollama app and check that the "
                 f"model is pulled (`ollama pull {model}`).\n\nError: {det['error']}")
        return
    st.caption(f"Model `{det['model']}`, {det['seconds']} s, "
               f"{len(det['tool_calls'])} tool calls, {det['nudges']} nudges, "
               f"{det['repeated_calls']} repeated")
    checks = {
        "Evidence (2+ distinct tools)": "PASS" if det["evidence_check"] else "FAIL",
        "Claims supported by tool results": "No issues" if not det["claim_issues"] else
        f"{len(det['claim_issues'])} issue(s)",
        "Action conditions met by data": "Yes" if not det["action_issues"] else
        f"{len(det['action_issues'])} issue(s)",
        "Safety warnings": "None" if not det["safety_warnings"] else
        f"{len(det['safety_warnings'])} warning(s)",
    }
    st.dataframe(pd.DataFrame(checks.items(), columns=["Check", "Result"]),
                 hide_index=True, width="stretch")
    for issue in det["claim_issues"] + det["action_issues"] + det["safety_warnings"]:
        st.warning(issue)
    with st.expander("Tool calls"):
        st.dataframe(pd.DataFrame([{"Round": t["round"], "Tool": t["tool"],
                                    "Arguments": json.dumps(t["args"]),
                                    "Repeated": t["repeated"]} for t in det["tool_calls"]]),
                     hide_index=True, width="stretch")
        for t in det["tool_calls"]:
            st.markdown(f"`{t['tool']}` result")
            st.json(t["result"], expanded=False)
    with st.expander("Model's raw JSON answer"):
        st.json(det["raw_final"])
    st.markdown("**Reasoning**")
    st.markdown("\n".join(f"- {line}" for line in d.reasoning))


def run_llm(sid: str) -> Decision:
    d = LLMAgent(model=model).decide(get_case_file(sid))
    st.session_state.llm_results[(sid, model)] = d
    return d


# ---- Main: selected scenario --------------------------------------------------
case = get_case_file(scenario_id)
expected, expected_why = EXPECTED_ACTIONS[scenario_id]
decisions = run_classical(case)
llm_decision = st.session_state.llm_results.get((scenario_id, model))

st.title("Order and refund support agents")
st.caption("Six agents receive the same case and recommend the next support action. "
           "Data is simulated.")

tab_case, tab_all = st.tabs(["Selected scenario", "All scenarios"])

with tab_case:
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.subheader(f"Scenario {scenario_id}: {SCENARIOS[scenario_id]['title']}")
        st.markdown(f"> {case['customer_message']}")
        o = case["order"]
        st.markdown(f"**Order {case['order_id']}**: {o.get('item')}, status "
                    f"`{o.get('status')}`, ordered {o.get('order_date')}"
                    + (f", delivered {o['delivered_on']}" if o.get("delivered_on") else "")
                    + (f", expected {o['expected_delivery']}" if o.get("expected_delivery") else ""))
    with right:
        events = case["delivery"].get("events", [])
        st.markdown("**Tracking events**")
        if events:
            st.dataframe(pd.DataFrame(events), hide_index=True, width="stretch")
        else:
            st.info("No tracking events on record.")
        refund = case["refund"]
        if refund.get("refund") or refund.get("return"):
            r = refund.get("refund") or {}
            ret = refund.get("return") or {}
            st.markdown(f"**Return/refund**: inspection `{ret.get('inspection_status')}` on "
                        f"{ret.get('inspection_date')}, refund `{r.get('status')}`")
    with st.expander("Shared case file given to every agent (JSON)"):
        st.json(case)
    st.caption(f"Evaluation reference (never shown to agents): policy expects "
               f"**{ACTIONS[expected]}** ({expected_why}).")

    st.divider()
    st.subheader("Decisions")
    st.markdown(agreement_summary(decisions, expected, llm_decision))
    st.dataframe(pd.DataFrame(comparison_rows(decisions, expected, llm_decision)),
                 hide_index=True, width="stretch")

    st.divider()
    st.subheader("How each agent decided")
    for d in decisions:
        with st.container(border=True):
            st.markdown(f"**{d.agent}**: {d.action_label}  \n"
                        f"{verdict(d, expected)}  \n{d.mechanism}")
            with st.expander("Show reasoning"):
                show_details(d)
            if d.agent == "Learning":
                learning_feedback(d)

    with st.container(border=True):
        st.markdown(f"**LLM agent** (`{model}` with tool calling)")
        if st.button("Run LLM agent", type="primary", key=f"run_llm_{scenario_id}"):
            with st.spinner(f"Running {model}. This takes about 30-45 seconds..."):
                llm_decision = run_llm(scenario_id)
            st.rerun()
        if llm_decision:
            st.markdown(f"{llm_decision.action_label}  \n{verdict(llm_decision, expected)}")
            show_llm_details(llm_decision)
        else:
            st.caption("Not run yet for this scenario and model.")

with tab_all:
    st.subheader("All scenarios at a glance")
    st.caption("Classical agents are recomputed live. LLM results appear for scenarios "
               "you have run in this session.")
    if st.button("Run LLM agent on all scenarios (about 2-3 minutes)"):
        progress = st.progress(0.0)
        for i, sid in enumerate(SCENARIOS, 1):
            with st.spinner(f"Scenario {sid}..."):
                run_llm(sid)
            progress.progress(i / len(SCENARIOS))
        st.rerun()

    matrix, totals = {}, {}
    for sid in SCENARIOS:
        exp = EXPECTED_ACTIONS[sid][0]
        col = {d.agent: ("✔ " if d.action == exp else "✘ ") + d.action
               for d in run_classical(get_case_file(sid))}
        llm_d = st.session_state.llm_results.get((sid, model))
        col["LLM (Ollama + tools)"] = (("✔ " if llm_d.action == exp else "✘ ") + llm_d.action
                                       if llm_d else "not run")
        col["Policy-expected"] = exp
        matrix[f"Scenario {sid}"] = col
    df = pd.DataFrame(matrix)
    st.dataframe(df, width="stretch")
    agents_only = df.drop(index="Policy-expected")
    totals = agents_only.apply(lambda row: sum(str(v).startswith("✔") for v in row), axis=1)
    run_counts = agents_only.apply(lambda row: sum(not str(v).startswith("not run") for v in row), axis=1)
    st.markdown("**Matches with policy per agent**")
    st.dataframe(pd.DataFrame({"Matches": totals, "Scenarios run": run_counts}),
                 width="stretch")
