# Implementation Plan: Assignment 1 - Financial Assistant Agent

## Context

Build a CLI chatbot "Financial Assistant" using raw Python + OpenAI Function Calling (gpt-4o-mini). The agent must handle exchange rate and stock price queries with mock data, support parallel tool calls, maintain conversation memory, and handle errors gracefully.

---

## Project Structure

```
assigment-1/
├── main.py              # Main chatbot code
├── .env                 # API key (gitignored)
├── .env.example         # Template for .env (safe to commit)
├── .gitignore           # Exclude .env
└── requirements.txt     # Dependencies
```

---

## Step-by-Step Implementation

### Step 1: Create project scaffolding files

Create the following files:
- **`requirements.txt`**: `openai`, `python-dotenv`
- **`.env.example`**: Template with `OPENAI_API_KEY=your-key-here`
- **`.gitignore`**: Exclude `.env`

### Step 2: Implement mock data functions in `main.py`

Two functions with hardcoded data dictionaries:

```python
def get_exchange_rate(currency_pair: str) -> str:
    # Data: USD_TWD->32.0, JPY_TWD->0.2, EUR_USD->1.2
    # Return JSON string: {"currency_pair": "...", "rate": "..."} or {"error": "Data not found"}

def get_stock_price(symbol: str) -> str:
    # Data: AAPL->260.00, TSLA->430.00, NVDA->190.00
    # Return JSON string: {"symbol": "...", "price": "..."} or {"error": "Data not found"}
```

### Step 3: Define tool schemas (Structured Outputs)

Define `tools` list with two function definitions for OpenAI API:
- Each tool has `"strict": true`
- Each parameters object has `"additionalProperties": false`
- Proper `type`, `description` for each parameter

### Step 4: Build the agent loop

Core architecture:

1. **System Prompt**: Define Financial Assistant persona
2. **Function Map** (dictionary dispatch):
   ```python
   available_functions = {
       "get_exchange_rate": get_exchange_rate,
       "get_stock_price": get_stock_price,
   }
   ```
3. **Conversation history**: `messages` list persists across turns
4. **Main loop**:
   - Read user input
   - Append to messages
   - Call OpenAI API with tools
   - If response has `tool_calls`:
     - Loop through ALL tool calls (handles parallel)
     - Use function map to dispatch each call
     - Append each tool result as `role: "tool"` message
     - Call OpenAI API again with updated messages
   - Print assistant response
   - Continue loop

### Step 5: Add debug logging for parallel tool calls

Print tool call info (function name, arguments) so demo video can show parallel execution clearly.

---

## Verification (Demo Tasks)

| Task | Input                                        | Expected                                 |
|------|----------------------------------------------|------------------------------------------|
| A    | "Who are you?"                               | Responds as Financial Assistant          |
| B    | "What is the price of NVDA?"                 | 190.00                                   |
| C    | "Compare the stock prices of AAPL and TSLA." | 2 tool calls in 1 turn, 260.00 vs 430.00 |
| D    | "My name is Hina" then "What is my name?"    | Recalls "Hina"                           |
| E    | "What is the price of GOOG?"                 | Graceful "Data not found"                |

---

## Files to Create/Modify

- `assigment-1/main.py` (new) - All chatbot logic
- `assigment-1/requirements.txt` (new)
- `assigment-1/.env.example` (new)
- `assigment-1/.gitignore` (new)
