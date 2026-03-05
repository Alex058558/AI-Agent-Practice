import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
MODEL = "openai/gpt-4o-mini"

# ============================================================
# Mock Data Functions
# ============================================================

def get_exchange_rate(currency_pair: str) -> str:
    """Get the exchange rate for a given currency pair."""
    rates = {
        "USD_TWD": "32.0",
        "JPY_TWD": "0.2",
        "EUR_USD": "1.2",
    }
    rate = rates.get(currency_pair.upper())
    if rate:
        return json.dumps({"currency_pair": currency_pair.upper(), "rate": rate})
    return json.dumps({"error": "Data not found"})


def get_stock_price(symbol: str) -> str:
    """Get the stock price for a given symbol."""
    prices = {
        "AAPL": "260.00",
        "TSLA": "430.00",
        "NVDA": "190.00",
    }
    price = prices.get(symbol.upper())
    if price:
        return json.dumps({"symbol": symbol.upper(), "price": price})
    return json.dumps({"error": "Data not found"})


# ============================================================
# Function Map (Dictionary Dispatch - NO if-else chains)
# ============================================================

available_functions = {
    "get_exchange_rate": get_exchange_rate,
    "get_stock_price": get_stock_price,
}

# ============================================================
# Tool Schemas (Structured Outputs with strict: true)
# ============================================================

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": "Get the exchange rate for a currency pair. Use format like USD_TWD, JPY_TWD, EUR_USD.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "currency_pair": {
                        "type": "string",
                        "description": "The currency pair, e.g. USD_TWD, JPY_TWD, EUR_USD.",
                    }
                },
                "required": ["currency_pair"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "Get the current stock price for a given ticker symbol, e.g. AAPL, TSLA, NVDA.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The stock ticker symbol, e.g. AAPL, TSLA, NVDA.",
                    }
                },
                "required": ["symbol"],
                "additionalProperties": False,
            },
        },
    },
]

# ============================================================
# System Prompt
# ============================================================

SYSTEM_PROMPT = (
    "You are a helpful Financial Assistant. "
    "You can help users check exchange rates and stock prices. "
    "When users ask about exchange rates or stock prices, use the provided tools to look up the data. "
    "Always be polite and professional. "
    "If a tool returns an error, relay the information gracefully to the user."
)

# ============================================================
# Agent Loop
# ============================================================

def run_agent():
    """Main agent loop with conversation memory and parallel tool call support."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    print("=" * 50)
    print("  Financial Assistant (type 'exit' to quit)")
    print("=" * 50)

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye"):
            print("\nAssistant: Goodbye! Have a great day!")
            break

        messages.append({"role": "user", "content": user_input})

        # Call the LLM
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
        )
        response_message = response.choices[0].message
        messages.append(response_message)

        # Handle tool calls (including parallel calls)
        while response_message.tool_calls:
            print(f"\n[Debug] Model requested {len(response_message.tool_calls)} tool call(s):")

            for tool_call in response_message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                print(f"  -> Calling: {func_name}({func_args})")

                # Dispatch using function map
                func = available_functions.get(func_name)
                if func:
                    result = func(**func_args)
                else:
                    result = json.dumps({"error": f"Unknown function: {func_name}"})

                print(f"  <- Result: {result}")

                # Append tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                })

            # Call the LLM again with tool results
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
            )
            response_message = response.choices[0].message
            messages.append(response_message)

        # Print the final assistant response
        print(f"\nAssistant: {response_message.content}")


if __name__ == "__main__":
    run_agent()
