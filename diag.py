"""Diagnostic: why are replies empty / no tool calls?

Run inside the activated .venv with the Ollama app running:
    python diag.py
"""
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

MODEL = "qwen3:1.7b"


@tool
def get_order_status(order_id: str) -> str:
    """Return the current status of an order."""
    return "delivered"


def show(label, msg):
    print(f"\n=== {label}")
    print("content          :", repr(msg.content[:300]))
    print("tool_calls       :", msg.tool_calls)
    print("reasoning (part) :", repr(str(msg.additional_kwargs.get("reasoning_content", ""))[:200]))
    print("done_reason      :", msg.response_metadata.get("done_reason"))


question = "What is the status of order ORD-1001?"

# 1. Plain chat, default thinking
show("1. plain, default thinking", ChatOllama(model=MODEL).invoke("Say hello in one word."))

# 2. Plain chat, thinking off
show("2. plain, reasoning=False",
     ChatOllama(model=MODEL, reasoning=False).invoke("Say hello in one word."))

# 3. Tools, default thinking
show("3. tools, default thinking",
     ChatOllama(model=MODEL, temperature=0).bind_tools([get_order_status]).invoke(question))

# 4. Tools, thinking off
show("4. tools, reasoning=False",
     ChatOllama(model=MODEL, temperature=0, reasoning=False).bind_tools([get_order_status]).invoke(question))
