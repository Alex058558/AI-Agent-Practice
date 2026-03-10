import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter, NestedCompleter, FuzzyWordCompleter, Completer, Completion

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
# Slash Commands
# ============================================================

SLASH_COMMANDS = {
    "/exit": {
        "description": "Exit the program",
        "usage": "/exit",
    },
    "/help": {
        "description": "Show available commands",
        "usage": "/help",
    },
    "/price": {
        "description": "Quick stock price lookup",
        "usage": "/price <symbol>",
        "example": "/price AAPL",
    },
    "/rate": {
        "description": "Quick exchange rate lookup",
        "usage": "/rate <pair>",
        "example": "/rate USD_TWD",
    },
    "/clear": {
        "description": "Clear conversation memory",
        "usage": "/clear",
    },
}

# Valid options for autocomplete
VALID_STOCKS = ["AAPL", "TSLA", "NVDA"]
VALID_PAIRS = ["USD_TWD", "JPY_TWD", "EUR_USD"]

# ============================================================
# Slash Command Handlers
# ============================================================

def handle_exit():
    """Handle /exit command."""
    print("\nAssistant: Goodbye! Have a great day!")
    return "exit"


def handle_help():
    """Handle /help command - display available commands."""
    print("\n[Available Commands]")
    print("-" * 40)
    for cmd, info in SLASH_COMMANDS.items():
        print(f"  {cmd:10} - {info['description']}")
    print("-" * 40)
    print("\nYou can also chat naturally with me about:")
    print("  - Stock prices (AAPL, TSLA, NVDA)")
    print("  - Exchange rates (USD_TWD, JPY_TWD, EUR_USD)")
    return "continue"


def handle_price(symbol: str) -> str:
    """Handle /price command - quick stock lookup."""
    if not symbol:
        print("\n[Error] Please provide a symbol. Usage: /price <symbol>")
        print("  Example: /price AAPL")
        return "continue"

    result = get_stock_price(symbol.upper())
    data = json.loads(result)

    if "error" in data:
        print(f"\n[Error] {data['error']}")
        print(f"  Valid symbols: {', '.join(VALID_STOCKS)}")
    else:
        print(f"\n[Stock Price] {data['symbol']}: ${data['price']}")
    return "continue"


def handle_rate(pair: str) -> str:
    """Handle /rate command - quick exchange rate lookup."""
    if not pair:
        print("\n[Error] Please provide a currency pair. Usage: /rate <pair>")
        print("  Example: /rate USD_TWD")
        return "continue"

    result = get_exchange_rate(pair.upper())
    data = json.loads(result)

    if "error" in data:
        print(f"\n[Error] {data['error']}")
        print(f"  Valid pairs: {', '.join(VALID_PAIRS)}")
    else:
        print(f"\n[Exchange Rate] {data['currency_pair']}: {data['rate']}")
    return "continue"


def handle_clear(messages: list) -> tuple:
    """Handle /clear command - reset conversation memory."""
    messages.clear()
    messages.append({"role": "system", "content": SYSTEM_PROMPT})
    print("\n[System] Conversation memory cleared.")
    return "continue", messages


# ============================================================
# Autocomplete Completer
# ============================================================

class SlashCommandCompleter(Completer):
    """
    Custom completer for slash commands with fuzzy matching.
    Shows matching commands even with partial input like /cl -> /clear.
    """

    def __init__(self):
        self.commands = {
            "/exit": None,
            "/help": None,
            "/price": WordCompleter(VALID_STOCKS, meta_dict={
                "AAPL": "Apple Inc.",
                "TSLA": "Tesla Inc.",
                "NVDA": "NVIDIA Corp.",
            }),
            "/rate": WordCompleter(VALID_PAIRS, meta_dict={
                "USD_TWD": "US Dollar to Taiwan Dollar",
                "JPY_TWD": "Japanese Yen to Taiwan Dollar",
                "EUR_USD": "Euro to US Dollar",
            }),
            "/clear": None,
        }
        self.command_list = list(self.commands.keys())

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()

        # Only show completions when input starts with /
        if not text.startswith("/"):
            return

        # Check if we're typing a command with argument (e.g., "/price ")
        parts = text.split(maxsplit=1)
        if len(parts) == 2 or (len(parts) == 1 and text.endswith(" ")):
            # We have a command, delegate to its completer for arguments
            command = parts[0].lower()
            if command in self.commands:
                sub_completer = self.commands[command]
                if sub_completer:
                    yield from sub_completer.get_completions(document, complete_event)
            return

        # Filter commands that match the current input (fuzzy prefix match)
        for cmd in self.command_list:
            if cmd.startswith(text) or text in cmd:
                # Calculate display position
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                )


def build_completer():
    """Build custom completer for slash commands with fuzzy matching."""
    return SlashCommandCompleter()


# ============================================================
# Command Parser
# ============================================================

def parse_and_execute_command(user_input: str, messages: list) -> tuple:
    """
    Parse slash commands and execute them.

    Returns:
        tuple: (action, messages)
        - action: "exit" | "continue" | "chat"
        - messages: updated messages list
    """
    stripped = user_input.strip()

    # Check for legacy exit commands (backward compatibility)
    if stripped.lower() in ("exit", "quit", "bye"):
        return handle_exit(), messages

    # Not a slash command, send to LLM
    if not stripped.startswith("/"):
        return "chat", messages

    parts = stripped.split(maxsplit=1)
    command = parts[0].lower()
    argument = parts[1] if len(parts) > 1 else ""

    # Check if command exists
    if command not in SLASH_COMMANDS:
        print(f"\n[Error] Unknown command: {command}")
        print("  Type /help for available commands.")
        return "continue", messages

    # Handle each command
    if command == "/exit":
        return handle_exit(), messages
    elif command == "/help":
        return handle_help(), messages
    elif command == "/price":
        return handle_price(argument), messages
    elif command == "/rate":
        return handle_rate(argument), messages
    elif command == "/clear":
        return handle_clear(messages)

    return "continue", messages


# ============================================================
# Agent Loop
# ============================================================

def run_agent():
    """Main agent loop with conversation memory and parallel tool call support."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Initialize slash command completer
    completer = build_completer()

    print("=" * 50)
    print("  Financial Assistant")
    print("  Type '/' for commands, '/help' for help")
    print("=" * 50)

    while True:
        try:
            # Use prompt_toolkit for input with autocomplete
            user_input = prompt(
                "\nYou: ",
                completer=completer,
                complete_while_typing=True,
            ).strip()
        except KeyboardInterrupt:
            print("\n\nAssistant: Goodbye! Have a great day!")
            break
        except EOFError:
            print("\n\nAssistant: Goodbye! Have a great day!")
            break

        if not user_input:
            continue

        # Parse and execute slash commands
        action, messages = parse_and_execute_command(user_input, messages)

        if action == "exit":
            break
        elif action == "continue":
            continue

        # If not a slash command, process through LLM
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
            print(f"\n[Tool] Model requested {len(response_message.tool_calls)} tool call(s):")

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