import json
import os
import re
from typing import Optional

from openai import OpenAI

from tools import TOOL_REGISTRY


client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)
MODEL = os.getenv("MODEL", "openai/gpt-4o-mini")
MAX_ITERATIONS = 5
MAX_TRACE_BLOCKS = 12

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
- When you have enough information to answer, you MUST start your response with "Answer:" on its own line. Everything after "Answer:" is your final answer. Do NOT output your conclusion as plain text, bullet points, or a comparison table without the "Answer:" prefix — the system cannot parse it otherwise.
- After writing an Action line, you MUST write PAUSE and stop. Do NOT write Observation yourself.
- The system will provide the Observation after your PAUSE.
- Treat search summaries as hints, not as verified facts. Prefer source titles, domains, and snippets.
- Only assert a fact if you can point to a specific snippet from the Observations that states it. If no snippet explicitly supports a claim, treat it as unverified.
- If a search returns poor, conflicting, or off-topic results, reflect on why and try a DIFFERENT query angle.
- When different search results appear to refer to different entities with the same name, list the distinct entities and refine your query with neutral qualifiers (industry, product type, headquarters, or domain) before answering.
- AVOID CONFIRMATION BIAS: When following up on ambiguous results, do NOT embed a candidate answer (e.g., a person's name you saw) into your query. This biases the search engine toward confirming that candidate. Instead, add neutral contextual filters like the product category or industry.
  Bad:  Action: search[Morphic CEO John Doe]  (embeds a candidate name — biased)
  Good: Action: search[Morphic AI search engine founder]  (uses neutral product descriptors)
- If ambiguity remains after a reasonable retry, give an Answer that says the evidence is inconclusive and briefly list the conflicting entities you found, instead of guessing.
- Break complex questions into sub-questions and solve them step by step.

Example session:
Question: What is the population ratio of Japan to France?
Thought: I need to find the populations of both Japan and France. Let me start with Japan.
Action: search[Japan population 2024]
PAUSE

Observation:
[1] RESULT
Title: Japan Demographics
Domain: example.com
URL: https://example.com/japan
Snippet: Japan's population was estimated at 123.3 million in 2024, continuing a declining trend.

Search summary (unverified hint; prefer the source snippets above if they conflict): Japan's population is approximately 123.3 million as of 2024.

Thought: Japan's population is about 123.3 million. Now I need France's population.
Action: search[France population 2024]
PAUSE

Observation:
[1] RESULT
Title: France Demographics
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

FINALIZE_SYSTEM_PROMPT = """You are now in the FINALIZE phase for a ReAct agent.

You will receive:
- the original question,
- a draft answer (if one was produced),
- and the ReAct trace containing Action/Observation records.

Your task:
1) Produce a best-effort final answer using only claims grounded in the provided observations.
2) If the question asks about a specific person (e.g., CEO, founder), verify that the answer is directly supported by a verbatim snippet before asserting it.
3) If evidence is conflicting, ambiguous, or insufficient, say so explicitly.
4) Verify entity match: if the question specifies a product type or industry (e.g., "AI search"), confirm the entity in the observations actually operates in that domain. If the observations describe a different entity with the same name (e.g., an anime company vs. a search engine), set answer_type to "inconclusive" and list the conflicting entities.

Rules:
- Never invent facts not found in the observations.
- `supporting_quotes` must be copied verbatim from observation snippets.
- Only set `selected_person` if the question specifically asks for a person AND a snippet directly names them in that role.
- If `selected_person` is set but no verbatim quote supports it, set `answer_type` to `inconclusive`.
- For non-person questions (numbers, comparisons, facts), leave `selected_person` empty and set `answer_type` to `resolved` if the observations support the answer.

Output format (required, JSON only):
{
  "answer_type": "resolved" | "inconclusive",
  "selected_person": "<name, or empty if not applicable>",
  "selected_entity": "<entity name or empty>",
  "supporting_quotes": ["<exact quote 1>", "<exact quote 2>"],
  "conflicting_entities": ["<entity | domain | product>", "..."],
  "final_answer": "<polished final answer in natural language, 1-3 short paragraphs>"
}
"""

REVIEW_SYSTEM_PROMPT = """You are the EVIDENCE REVIEW gate for a ReAct agent.

You will receive:
- the original question,
- a draft answer,
- and the ReAct trace (Action/Observation records only).

Decide whether the draft answer is sufficiently supported by observations.

General rules:
- Use only the provided observations.
- Set `decision` to `accept` if the draft answer is clearly supported by the observation snippets.
- Set `decision` to `revise` only if evidence is clearly missing, contradicted, or ambiguous.
- If revising, `next_query` MUST be non-empty. Propose ONE specific, targeted query that directly addresses the evidence gap.
- Leave `next_query` empty when `decision` is `accept`.

Additional rules for person-identity questions (when the question asks for a CEO, founder, or named individual):
- Start with `decision` = `revise` by default. Upgrade to `accept` only if every acceptance condition below is satisfied.
- Set `selected_person` to the candidate name found in observations (or empty if none).
- Set `descriptor_match` to true only if the observations clearly refer to the same product/entity described in the question.
- Set `ambiguity_detected` to true if multiple different entities share the same name in the observations.
- Accept only when ALL are true: `descriptor_match` is true, `ambiguity_detected` is false, and `selected_person` is directly supported by a verbatim quote that explicitly links the person to the requested role/entity.
- Force `decision` to `revise` if any acceptance condition fails.
- Do NOT embed a candidate person's name in `next_query`; use neutral product/domain qualifiers instead.

For all other question types (numerical, comparative, factual):
- Leave `selected_person` empty.
- Set `descriptor_match` to true and `ambiguity_detected` to false unless there is a concrete reason otherwise.

Example for entity mismatch (person-identity case):
Question: Who is the CEO of "Acme AI search engine"?
Observation snippet: "Acme is a no-code website builder for landing pages."
Draft answer: "The CEO is Jane Doe."
Expected judgment:
- `descriptor_match` = false (product type mismatch: AI search engine vs website builder)
- `decision` = `revise`
- `next_query` = "Acme AI search engine CEO founder official team"

Return JSON only:
{
  "decision": "accept" | "revise",
  "reason": "<short reason>",
  "next_query": "<targeted query or empty>",
  "selected_person": "<name or empty>",
  "supporting_quotes": ["<exact snippet quote>", "..."],
  "descriptor_match": true | false,
  "ambiguity_detected": true | false
}
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
        draft_answer = None
        review_budget = 2

        for i in range(1, MAX_ITERATIONS + 1):
            self.on_step("iteration", f"--- Step {i}/{MAX_ITERATIONS} ---")

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                stop=["PAUSE", "Observation:"],
                temperature=0.2,
            )

            raw = (response.choices[0].message.content or "").strip()
            if not raw:
                self.on_step("error", "Empty model response, nudging LLM...")
                messages.append({
                    "role": "user",
                    "content": (
                        "You returned an empty response. Continue with either "
                        "Action: tool[arg] then PAUSE, or Answer: <final answer>."
                    ),
                })
                continue

            self._emit_thoughts(raw)

            answer_match = ANSWER_RE.search(raw)
            if answer_match:
                messages.append({"role": "assistant", "content": raw})
                draft_answer = answer_match.group(1).strip()
                review = self._review_draft(question, messages, draft_answer)
                decision = review.get("decision", "revise")
                reason = review.get("reason", "The draft answer is not sufficiently supported.")
                next_query = review.get("next_query", "")

                if decision == "accept":
                    self.on_step("thought", "Thought: Draft answer passed evidence review.")
                    self.on_step("answer", draft_answer)
                    return draft_answer

                if i < MAX_ITERATIONS and review_budget > 0 and next_query:
                    review_budget -= 1
                    self.on_step("error", f"Evidence review requested more search: {reason}")
                    query_to_run = next_query
                    self.on_step("thought", "Thought: Running one targeted disambiguation search from review gate.")
                    self.on_step("action", f"search[{query_to_run}]")

                    search_tool = TOOL_REGISTRY.get("search")
                    if search_tool:
                        observation = search_tool(query_to_run)
                    else:
                        observation = "Error: search tool is unavailable."

                    self.on_step("observation", observation)
                    messages.append({
                        "role": "assistant",
                        "content": (
                            "Thought: The previous draft answer was not sufficiently supported.\n"
                            f"Action: search[{query_to_run}]\n"
                            "PAUSE"
                        ),
                    })
                    messages.append({"role": "user", "content": f"Observation: {observation}"})
                    draft_answer = None
                    continue

                self.on_step(
                    "error",
                    "Evidence review found gaps; review budget exhausted. Moving to final synthesis.",
                )
                draft_answer = None
                break

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

        has_observation = any(
            message["role"] == "user" and message["content"].startswith("Observation:")
            for message in messages
        )
        if not draft_answer and not has_observation:
            answer = (
                "I was unable to verify a complete answer within the allowed steps. "
                "The evidence may still be ambiguous or incomplete."
            )
            self.on_step("answer", answer)
            return answer

        final_answer = self._finalize_answer(question, messages, draft_answer)
        self.on_step("answer", final_answer)
        return final_answer

    def _finalize_answer(self, question: str, messages, draft_answer: Optional[str]) -> str:
        fallback = draft_answer or (
            "I was unable to verify a complete answer within the allowed steps. "
            "The evidence may still be ambiguous or incomplete."
        )

        self.on_step("iteration", "--- Finalize ---")
        self.on_step("thought", "Thought: Synthesizing evidence and resolving ambiguity.")

        trace = self._build_trace(messages)
        final_messages = [
            {"role": "system", "content": FINALIZE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Draft answer:\n{draft_answer or 'None'}\n\n"
                    f"ReAct trace:\n{trace}"
                ),
            },
        ]

        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=final_messages,
                temperature=0.3,
            )
        except Exception as exc:
            self.on_step("error", f"Finalize stage failed: {exc}")
            return fallback

        raw = (response.choices[0].message.content or "").strip()
        payload = self._parse_finalize_payload(raw)
        if not payload:
            self.on_step("error", "Finalize payload parsing failed. Falling back to draft answer.")
            return fallback

        answer_type = str(payload.get("answer_type", "")).strip().lower()
        final_answer = str(payload.get("final_answer", "")).strip()

        if answer_type == "inconclusive":
            return self._build_inconclusive_answer(payload)

        if final_answer:
            return final_answer
        return fallback

    def _review_draft(self, question: str, messages, draft_answer: str) -> dict:
        trace = self._build_trace(messages)
        review_messages = [
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Draft answer:\n{draft_answer}\n\n"
                    f"ReAct trace:\n{trace}"
                ),
            },
        ]
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=review_messages,
                temperature=0.0,
            )
        except Exception as exc:
            self.on_step("error", f"Evidence review failed: {exc}")
            return {
                "decision": "revise",
                "reason": "Evidence review call failed.",
                "next_query": "",
            }

        raw = (response.choices[0].message.content or "").strip()
        payload = self._parse_finalize_payload(raw)
        if not payload:
            self.on_step("error", "Evidence review payload parsing failed.")
            return {
                "decision": "revise",
                "reason": "Evidence review payload is invalid JSON.",
                "next_query": "",
            }

        decision = str(payload.get("decision", "")).strip().lower()
        reason = str(payload.get("reason", "")).strip()
        next_query = str(payload.get("next_query", "")).strip()

        if decision not in {"accept", "revise"}:
            decision = "revise"

        return {
            "decision": decision,
            "reason": reason or "The draft answer is not sufficiently supported.",
            "next_query": next_query,
        }

    def _parse_finalize_payload(self, raw: str) -> Optional[dict]:
        if not raw:
            return None

        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None

        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None

    def _build_inconclusive_answer(self, payload: dict) -> str:
        final_answer = str(payload.get("final_answer", "")).strip()
        if final_answer:
            return final_answer

        entities = [
            str(entity).strip()
            for entity in payload.get("conflicting_entities", [])
            if str(entity).strip()
        ]
        if entities:
            entity_text = "; ".join(entities[:3])
            return (
                "The retrieved evidence is inconclusive. "
                f"Conflicting or ambiguous entities found: {entity_text}."
            )
        return "The retrieved evidence is inconclusive."

    def _build_trace(self, messages) -> str:
        blocks = []
        for message in messages[2:]:
            role = message["role"]
            content = message["content"].strip()
            if not content:
                continue

            if role == "assistant":
                lines = []
                for line in content.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith(("Thought:", "Action:")):
                        lines.append(stripped)
                if lines:
                    blocks.append("\n".join(lines))
                continue

            if role == "user" and content.startswith("Observation:"):
                blocks.append(content)

        if not blocks:
            return "No observations were collected."
        return "\n\n".join(blocks[-MAX_TRACE_BLOCKS:])

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
