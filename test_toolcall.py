"""Setup check: can qwen3 call tools through LangChain?

Run inside the activated .venv with the Ollama app running:
    python test_toolcall.py
"""
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

MODEL = "qwen3:1.7b"

# Simulated read-only records (test data only)
ORDERS = {"ORD-1001": {"status": "delivered", "delivered_on": "2026-11-02"}}
EVENTS = {"ORD-1001": ["2026-10-30 shipped", "2026-11-01 out for delivery",
                       "2026-11-02 delivered - left at front door"]}


@tool
def get_order_status(order_id: str) -> str:
    """Return the current status of an order."""
    return str(ORDERS.get(order_id, "Order not found"))


@tool
def get_delivery_events(order_id: str) -> str:
    """Return the delivery tracking events for an order."""
    return str(EVENTS.get(order_id, "No delivery events found"))


TOOLS = {t.name: t for t in [get_order_status, get_delivery_events]}

llm = ChatOllama(model=MODEL, temperature=0, reasoning=False)
llm_with_tools = llm.bind_tools(list(TOOLS.values()))

messages = [
    SystemMessage(content="You are a support assistant. Use the tools to check "
                          "order status and delivery events before answering."),
    HumanMessage(content="Order ORD-1001 says delivered but I never got it. What happened?"),
]

ai_msg = llm_with_tools.invoke(messages)
messages.append(ai_msg)

print("Tool calls made by the model:")
if not ai_msg.tool_calls:
    print("  NONE - the model answered without calling tools.")
for call in ai_msg.tool_calls:
    result = TOOLS[call["name"]].invoke(call["args"])
    print(f"  {call['name']}({call['args']}) -> {result}")
    messages.append(ToolMessage(content=result, tool_call_id=call["id"]))

final = llm.invoke(messages)
print("\nFinal answer:\n" + final.content)
