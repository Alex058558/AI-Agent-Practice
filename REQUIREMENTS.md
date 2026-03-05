# Assignment 1: Build Your First Question Answering Agent

> Raw Python & Function Calling (No LangChain)

## Basic Info

- **Due Date**: 2026/03/12 23:30
- **Late Policy**: 7 grace days total for semester, max 2 days per assignment
- **Penalty**: Final Grade = Original Grade × (1 - (days late × 0.1))

---

## Objective

Build a CLI chatbot "Financial Assistant" that answers questions about exchange rates and stock prices using OpenAI Function Calling. No high-level frameworks allowed.

---

## Technical Requirements

### 1. System Setup

- Model: `gpt-4o-mini` (Required for Structured Outputs)
- Use `python-dotenv` to manage API keys
- API keys must NOT be hardcoded or uploaded to Git

### 2. Mock Data Functions (Standardized)

#### Function 1: `get_exchange_rate(currency_pair: str)`

| currency_pair | rate   |
|---------------|--------|
| USD_TWD       | 32.0   |
| JPY_TWD       | 0.2    |
| EUR_USD       | 1.2    |

- Return format: `{"currency_pair": "USD_TWD", "rate": "32.0"}`
- Not found: `{"error": "Data not found"}`

#### Function 2: `get_stock_price(symbol: str)`

| symbol | price  |
|--------|--------|
| AAPL   | 260.00 |
| TSLA   | 430.00 |
| NVDA   | 190.00 |

- Return format: `{"symbol": "AAPL", "price": "260.00"}`
- Not found: `{"error": "Data not found"}`

### 3. Tool Schema (Structured Outputs)

- Use OpenAI `tools` parameter (standard format)
- Must set `"strict": true` in each function definition
- All parameters must include `"additionalProperties": false`

### 4. Robust Agent Loop

- **Function Map**: Use Python Dictionary for dispatch (NO if-else chains)
  - e.g., `available_functions = {"get_stock_price": get_stock_price}`
- **Parallel Tool Calls**: Handle multiple tool calls in one turn
  - Execute ALL pending tool calls, append ALL results before next LLM call
- **Context Window**: Agent must remember previous turns (conversation history)

---

## Required Deliverables

1. GitHub Repository Link
2. Demo Video Link (YouTube/Google Drive, < 3 minutes)

### Required Files in Repo

- `main.py` - Main chatbot code
- `.env` - API key (NOT uploaded to Git, add to `.gitignore`)
- `requirements.txt` - All dependencies

---

## Demo Video Tasks (Must Show All 5)

| Task | Prompt | Expected Result |
|------|--------|-----------------|
| A (Persona) | "Who are you?" | Replies as Financial Assistant |
| B (Single Tool) | "What is the price of NVDA?" | Returns 190.00 |
| C (Parallel Tools) | "Compare the stock prices of AAPL and TSLA." | Debug log shows 2 tool calls in 1 turn; compares 260.00 vs 430.00 |
| D (Memory Test) | Step 1: "My name is [Name]." Step 2: "What is my name?" | Correctly recalls name |
| E (Error Handling) | "What is the price of GOOG?" | Returns "Data not found" gracefully, no crash |

---

## Grading Rubric

| Item | Checkpoints | Weight |
|------|-------------|--------|
| Environment & Security | No hardcoded API keys; `requirements.txt` complete | 10% |
| Code Structure | Function Map (Dictionary) for routing; no if-else chains | 10% |
| Tool Schema | Correct `tools` definitions; proper types; `strict: true` | 10% |
| Task A & B (Single Query) | USD_TWD → 32.0; NVDA → 190.00 | 20% |
| Task C (Parallel Calls) | 2 tool calls in 1 turn; integrates both results | 20% |
| Task D (Memory & Persona) | Recalls user info; maintains Financial Assistant persona | 10% |
| Task E (Robustness) | Unknown data → polite error; no crash | 20% |
