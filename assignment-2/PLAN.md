# Implementation Plan: Assignment 2 - ReAct Agent

## Context

Build a ReAct (Reasoning + Acting) Agent from scratch using Python + gpt-4o-mini via OpenRouter. The agent must answer complex queries by iterating through a Thought -> Action -> Observation loop, demonstrating Reflection (self-correction) and Planning (task decomposition). Uses Tavily Search API for external knowledge.

---

## Project Structure

```
assignment-2/
├── agent.py          # ReActAgent class with ReAct loop
├── tools.py          # Search + calculate tool wrappers
├── main.py           # CLI entry point with prompt_toolkit
├── .env.example      # API key template
└── requirements.txt  # Dependencies
```

---

## Step-by-Step Implementation

### Step 1: Create `tools.py` with tool registry

Two tools exposed via dictionary dispatch (same pattern as Assignment 1):

```python
def search(query: str) -> str:
    # Tavily SDK: search_depth="basic", max_results=3, include_answer=True
    # Returns formatted string: Summary + Title/URL/Content per result
    # Errors returned as strings (let agent reflect)

def calculate(expression: str) -> str:
    # Safe math eval using ast module (no raw eval)
    # Supports +, -, *, /, **
    # Task 1 needs this for population ratio calculation

TOOL_REGISTRY = {"search": search, "calculate": calculate}
```

### Step 2: Build `agent.py` with ReAct loop

Core architecture:

1. **System Prompt** with Few-Shot Example (One-shot):
   - Define available tools: `search[query]`, `calculate[expression]`
   - Define format: Thought -> Action -> PAUSE -> Observation -> ... -> Answer
   - Include one full example showing task decomposition (two searches + one calculation)
   - Instruct: "If search returns poor results, reflect and try a different query"

2. **Stop Sequence**: `stop=["PAUSE", "Observation:"]` in API call
   - Prevents LLM from hallucinating observations after emitting an Action
   - Append `PAUSE` back to message history after truncation

3. **Parse Logic** (regex):
   - `Answer: (.+)` -> return final answer
   - `Action: (\w+)\[(.+?)\]` -> dispatch tool
   - Fallback: append a nudge message and ask the model to continue with a valid `Action:` or `Answer:`

4. **ReAct Loop** (`run` method):
   ```
   messages = [system_prompt, user_query]
   for iteration in 1..5:
     a. call LLM (with stop sequence, temperature=0)
     b. parse response
     c. if answer -> return
     d. if action -> dispatch tool -> append observation -> continue
     e. if neither action nor answer -> append a nudge message and retry
   return fallback message
   ```

5. **History**: Reset messages per `run()` call (tasks are independent)

### Step 3: Build `main.py` with CLI

Reuse Assignment 1's prompt_toolkit + SlashCommandCompleter pattern:

- `/help` — Show available commands
- `/clear` — Reset agent instance
- `/run 1|2|3` — Execute preset tasks
- `/exit` — Exit
- Free text input -> `agent.run(input)`

Print each iteration's Thought/Action/Observation to console for easy trace capture.

### Step 4: Create config files

- **`requirements.txt`**: `openai`, `python-dotenv`, `tavily-python`, `prompt_toolkit`
- **`.env.example`**: `OPENROUTER_API_KEY=your-key-here` + `TAVILY_API_KEY=your-key-here`

---

## Verification (Demo Tasks)

| Task | Input                                                          | Expected Behavior                                      |
|------|----------------------------------------------------------------|--------------------------------------------------------|
| 1    | "What fraction of Japan's population is Taiwan's population?"  | Decomposes: search Japan -> search Taiwan -> calculate |
| 2    | "Compare the main display specs of iPhone 15 and Samsung S24." | Retrieves specific specs (60Hz vs 120Hz, etc.)         |
| 3    | "Who is the CEO of the startup 'Morphic' AI search?"           | Reflects on poor results, retries with different query |

---

## Files to Create

- `assignment-2/tools.py` (new) - Tool wrappers + TOOL_REGISTRY
- `assignment-2/agent.py` (new) - ReActAgent class
- `assignment-2/main.py` (new) - CLI with prompt_toolkit
- `assignment-2/requirements.txt` (new)
- `assignment-2/.env.example` (new)
