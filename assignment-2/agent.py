import os
import re

from openai import OpenAI

from tools import TOOL_REGISTRY


client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
MODEL = "openai/gpt-4o-mini"
MAX_ITERATIONS = 5

SYSTEM_PROMPT = """You are a research assistant that answers questions using a Thought -> Action -> Observation loop (ReAct pattern).

You have access to the following tools:
- search[query]: Search the web for current information. Use specific, targeted queries.
- calculate[expression]: Evaluate a math expression (supports +, -, *, /, **).

On each step you MUST output exactly ONE of:
1. A Thought line followed by an Action line, then PAUSE (wait for observation)
2. An Answer line (when you have enough information)

Format rules:
- Thought: <your reasoning>
- Action: <toolname>[<argument>]
- PAUSE
- Answer: <your final answer>

IMPORTANT:
- After writing an Action line, you MUST write PAUSE and stop. Do NOT write Observation yourself.
- The system will provide the Observation after your PAUSE.
- If a search returns poor results, reflect on why and try a different query.
- Break complex questions into sub-questions and solve them step by step.

Example session:
Question: What is the population ratio of Japan to France?
Thought: I need to find the populations of both Japan and France. Let me start with Japan.
Action: search[Japan population 2024]
PAUSE

Observation: Summary: Japan's population is approximately 123.3 million as of 2024.
[1] Japan Demographics
    URL: https://example.com/japan
    Japan's population was estimated at 123.3 million in 2024, continuing a declining trend.

Thought: Japan's population is about 123.3 million. Now I need France's population.
Action: search[France population 2024]
PAUSE

Observation: Summary: France has a population of approximately 68.4 million as of 2024.
[1] France Demographics
    URL: https://example.com/france
    France's population reached 68.4 million in 2024.

Thought: Now I can calculate the ratio. Japan: 123.3 million, France: 68.4 million.
Action: calculate[123.3 / 68.4]
PAUSE

Observation: 1.8026315789473686

Thought: The ratio is approximately 1.80. I have all the information needed.
Answer: The population ratio of Japan to France is approximately 1.80:1. Japan (123.3 million) has about 1.8 times the population of France (68.4 million).
"""

# Regex patterns for parsing LLM output
ACTION_RE = re.compile(r"Action:\s*(\w+)\[(.+?)\]", re.DOTALL)
ANSWER_RE = re.compile(r"Answer:\s*(.+)", re.DOTALL)


class ReActAgent:
    def __init__(self, on_step=None):
        """
        Args:
            on_step: callback(step_type, content) for real-time trace output.
                     step_type is one of: "thought", "action", "observation", "answer", "error"
        """
        self.on_step = on_step or (lambda *_: None)

    def run(self, question: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {question}"},
        ]

        for i in range(1, MAX_ITERATIONS + 1):
            self.on_step("iteration", f"--- Step {i}/{MAX_ITERATIONS} ---")

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                stop=["PAUSE", "Observation:"],
                temperature=0.2,
            )

            raw = response.choices[0].message.content.strip()
            self._emit_thoughts(raw)

            # Check for final answer first (don't append PAUSE for answers)
            answer_match = ANSWER_RE.search(raw)
            if answer_match:
                messages.append({"role": "assistant", "content": raw})
                answer = answer_match.group(1).strip()
                self.on_step("answer", answer)
                return answer

            # Append raw + PAUSE to history so LLM sees consistent format
            messages.append({"role": "assistant", "content": raw + "\nPAUSE"})

            # Check for action
            action_match = ACTION_RE.search(raw)
            if action_match:
                tool_name = action_match.group(1)
                tool_arg = action_match.group(2)
                self.on_step("action", f"{tool_name}[{tool_arg}]")

                tool_func = TOOL_REGISTRY.get(tool_name)
                if tool_func:
                    observation = tool_func(tool_arg)
                else:
                    observation = f"Error: Unknown tool '{tool_name}'. Available: {', '.join(TOOL_REGISTRY)}"

                self.on_step("observation", observation)
                messages.append({"role": "user", "content": f"Observation: {observation}"})
                continue

            # No action and no answer — LLM wrote free text without proper format
            # Nudge it to either take an action or give a final answer
            self.on_step("error", "No Action or Answer detected, nudging LLM...")
            messages.append({
                "role": "user",
                "content": "You must respond with either an Action (using Action: toolname[arg] then PAUSE) or a final Answer (using Answer: your answer). Please continue.",
            })

        return "I was unable to find a complete answer within the allowed steps. Please try rephrasing your question."

    def _emit_thoughts(self, raw: str):
        """Extract and emit Thought lines from raw LLM output."""
        for line in raw.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Thought:"):
                self.on_step("thought", stripped)
            elif stripped.startswith("Action:"):
                pass  # handled separately
            elif stripped.startswith("Answer:"):
                pass  # handled separately
            elif stripped:
                self.on_step("thought", stripped)
