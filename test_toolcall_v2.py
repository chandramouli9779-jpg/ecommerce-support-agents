"""Setup check v2: structured task prompt + tool loop + nudge + evidence check.

Run inside the activated .venv with the Ollama app running:
    python test_toolcall_v2.py
"""
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import ChatOllama

MODEL = "qwen3:1.7b"
MAX_ROUNDS = 5
MIN_DISTINCT_TOOLS = 2

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

customer_message = "Order ORD-1001 says delivered but I never got it. What happened?"

# Change 1: the raw customer message is wrapped in a direct, structured task.
task = (
    f"Order ID: ORD-1001\n"
    f"Customer message: {customer_message}\n\n"
    f"Task: Call get_order_status and get_delivery_events for this order ID. "
    f"Do not answer until you have the tool results."
)
messages = [
    SystemMessage(content="You are a support assistant. You must use tools to get "
                          "facts. Never describe a tool call; make it."),
    HumanMessage(content=task),
]

tools_used = []
nudges = 0

# Change 2: loop until the model stops calling tools (ReAct-style).
for round_no in range(1, MAX_ROUNDS + 1):
    ai_msg = llm_with_tools.invoke(messages)
    messages.append(ai_msg)

    if ai_msg.tool_calls:
        for call in ai_msg.tool_calls:
            result = TOOLS[call["name"]].invoke(call["args"])
            tools_used.append(call["name"])
            print(f"Round {round_no}: {call['name']}({call['args']}) -> {result}")
            messages.append(ToolMessage(content=result, tool_call_id=call["id"]))
        continue

    # Change 3: if it talked instead of calling tools, nudge it once per round.
    missing = [n for n in TOOLS if n not in tools_used]
    if len(set(tools_used)) < MIN_DISTINCT_TOOLS and missing:
        nudges += 1
        print(f"Round {round_no}: no tool call (said: {ai_msg.content[:80]!r}) -> nudging")
        messages.append(HumanMessage(content=f"Call {missing[0]} now with order_id ORD-1001."))
        continue
    break

# Final answer grounded in the collected tool results
messages.append(HumanMessage(content="Using only the tool results above, explain the "
                                     "situation and recommend the next support action."))
final = llm.invoke(messages)

# Change 4: evidence check (the marking table asks that evidence is checked).
distinct = sorted(set(tools_used))
print("\nDistinct tools used:", distinct, "| nudges needed:", nudges)
print("Evidence check:", "PASS" if len(distinct) >= MIN_DISTINCT_TOOLS else "FAIL")
print("\nFinal answer:\n" + (final.content or "(empty)"))
