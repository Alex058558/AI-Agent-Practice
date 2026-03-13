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
- Treat search summaries as hints, not as verified facts. Prefer source titles, domains, and snippets.
- Only assert a fact if you can point to a specific snippet from the Observations that states it. If no snippet explicitly supports a claim, treat it as unverified.
- If a search returns poor, conflicting, or off-topic results, reflect on why and try a DIFFERENT query angle.
- When different search results appear to refer to different entities with the same name, explicitly list the distinct entities you see before continuing. Then refine your search using a distinguishing qualifier (e.g., industry, product type, or headquarters) to isolate the correct entity.
- AVOID CONFIRMATION BIAS: When following up on ambiguous results, do NOT embed a candidate answer (e.g., a person's name you saw) into your query. This biases the search engine toward confirming that candidate. Instead, add neutral contextual filters like the product category or industry.
- If ambiguity remains after a reasonable retry, give an Answer that says the evidence is inconclusive and briefly list the conflicting entities you found, instead of guessing.
- Break complex questions into sub-questions and solve them step by step.

Example session:
Question: What is the population ratio of Japan to France?
Thought: I need to find the populations of both Japan and France. Let me start with Japan.
Action: search[Japan population 2024]
PAUSE

Observation:
[1] Japan Demographics
    Domain: example.com
    URL: https://example.com/japan
    Snippet: Japan's population was estimated at 123.3 million in 2024, continuing a declining trend.

Search summary (unverified hint; prefer the source snippets above if they conflict): Japan's population is approximately 123.3 million as of 2024.

Thought: Japan's population is about 123.3 million. Now I need France's population.
Action: search[France population 2024]
PAUSE

Observation:
[1] France Demographics
    Domain: example.com
    URL: https://example.com/france
    Snippet: France's population reached 68.4 million in 2024.

Search summary (unverified hint; prefer the source snippets above if they conflict): France has a population of approximately 68.4 million as of 2024.

Thought: Now I can calculate the ratio. Japan: 123.3 million, France: 68.4 million.
Action: calculate[123.3 / 68.4]
PAUSE

Observation: 1.8026315789473686

Thought: The ratio is approximately 1.80. I have all the information needed.
Answer: The population ratio of Japan to France is approximately 1.80:1. Japan (123.3 million) has about 1.8 times the population of France (68.4 million).
"""

ACTION_RE = re.compile(r"Action:\s*(\w+)\[(.+?)\]", re.DOTALL)
ANSWER_RE = re.compile(r"Answer:\s*(.+)", re.DOTALL)


class ReActAgent:
    def __init__(self, on_step=None):
        self.on_step = on_step or (lambda *_: None)

    def run(self, question: str) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Question: {question}"},
        ]
        answer_reviewed = False

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

            answer_match = ANSWER_RE.search(raw)
            if answer_match:
                messages.append({"role": "assistant", "content": raw})
                answer = answer_match.group(1).strip()

                if not answer_reviewed and i < MAX_ITERATIONS:
                    answer_reviewed = True
                    self.on_step("error", "Reviewing whether the observations really support this answer...")
                    messages.append({
                        "role": "user",
                        "content": (
                            "STOP. Before finalizing, you MUST complete this verification. "
                            "Your default answer is INCONCLUSIVE unless the evidence passes ALL checks.\n\n"
                            "STEP A — List distinct entities:\n"
                            "For each entity in the results, write:\n"
                            "  Entity: <name> | Product: <what they make> | Source: <domain>\n\n"
                            "STEP B — Quote evidence:\n"
                            "Copy the EXACT snippet text that supports your proposed answer. No paraphrasing.\n\n"
                            "STEP C — Find the mismatch (MANDATORY):\n"
                            "  Question asks about: <extract the product/industry descriptor>\n"
                            "  Your quote describes: <extract the product/industry from the snippet>\n"
                            "  Are these the SAME specific product category? Default is NO.\n"
                            "  Only write YES if they are clearly the same (e.g., both say 'search engine').\n"
                            "  'AI search' is NOT the same as 'AI website builder' or 'AI anime' or 'AI content'.\n"
                            "  Reason: <one sentence explaining why they match or differ>\n\n"
                            "STEP D — Decision:\n"
                            "- If STEP C is YES with a clear reason, confirm your Answer.\n"
                            "- If STEP C is NO, try ONE more search using the exact product descriptor "
                            "from the question (e.g., if the question says 'AI search', search for "
                            "'<company name> AI search engine startup'). Do NOT include any person's name.\n"
                            "- Only give an inconclusive Answer if you have already retried and still cannot "
                            "find a matching entity. List the distinct entities you found."
                        ),
                    })
                    continue

                self.on_step("answer", answer)
                return answer

            messages.append({"role": "assistant", "content": raw + "\nPAUSE"})

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

            self.on_step("error", "No Action or Answer detected, nudging LLM...")
            messages.append({
                "role": "user",
                "content": (
                    "You must respond with either an Action (using Action: toolname[arg] then PAUSE) "
                    "or a final Answer (using Answer: your answer). If the evidence is conflicting, "
                    "say so explicitly in your Answer."
                ),
            })

        answer = (
            "I was unable to verify a complete answer within the allowed steps. "
            "The evidence may still be ambiguous or incomplete."
        )
        self.on_step("answer", answer)
        return answer

    def _emit_thoughts(self, raw: str):
        for line in raw.split("\n"):
            stripped = line.strip()
            if stripped.startswith("Thought:"):
                self.on_step("thought", stripped)
            elif stripped.startswith("Action:"):
                pass
            elif stripped.startswith("Answer:"):
                pass
            elif stripped:
                self.on_step("thought", stripped)
