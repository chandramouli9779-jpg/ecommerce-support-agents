"""Diagnostic 2: which difference from diag.py stops tool calls?

Run inside the activated .venv with the Ollama app running:
    python diag2.py
"""
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

MODEL = "qwen3:1.7b"


@tool
def get_order_status(order_id: str) -> str:
    """Return the current status of an order."""
    return "delivered"


@tool
def get_delivery_events(order_id: str) -> str:
    """Return the delivery tracking events for an order."""
    return "2026-11-02 delivered - left at front door"


SYSTEM = SystemMessage(content="You are a support assistant. Use the tools to check "
                               "order status and delivery events before answering.")
SHORT_Q = "What is the status of order ORD-1001?"
LONG_Q = "Order ORD-1001 says delivered but I never got it. What happened?"

VARIANTS = {
    "A. original: system + long question + 2 tools": ([SYSTEM, HumanMessage(LONG_Q)], 2),
    "B. no system + long question + 2 tools": ([HumanMessage(LONG_Q)], 2),
    "C. system + long question + 1 tool": ([SYSTEM, HumanMessage(LONG_Q)], 1),
    "D. system + short question + 2 tools": ([SYSTEM, HumanMessage(SHORT_Q)], 2),
}

tools_all = [get_order_status, get_delivery_events]

for label, (messages, n_tools) in VARIANTS.items():
    llm = ChatOllama(model=MODEL, temperature=0, reasoning=False).bind_tools(tools_all[:n_tools])
    print(f"\n=== {label}")
    for attempt in (1, 2):
        msg = llm.invoke(messages)
        names = [c["name"] for c in msg.tool_calls] or "NONE"
        print(f"  attempt {attempt}: tool_calls={names} | content={msg.content[:120]!r} "
              f"| done_reason={msg.response_metadata.get('done_reason')}")
