"""Minimal KG query template for Assignment 4.

Keep these APIs unchanged for auto-test:
- generate_text(messages, max_new_tokens=220)
- get_relevant_articles(question)
- generate_answer(question, rule_results)

Keep Rule fields aligned with build_kg output:
rule_id, type, action, result, art_ref, reg_name
"""

import os
import re
from typing import Any

from neo4j import GraphDatabase
from dotenv import load_dotenv

from llm_loader import load_local_llm, get_tokenizer, get_raw_pipeline


# ========== 0) Initialization ==========
load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
AUTH = (
	os.getenv("NEO4J_USER", "neo4j"),
	os.getenv("NEO4J_PASSWORD", "password"),
)

# Avoid local proxy settings interfering with model/Neo4j access.
for key in ["http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"]:
	if key in os.environ:
		del os.environ[key]


try:
	driver = GraphDatabase.driver(URI, auth=AUTH)
	driver.verify_connectivity()
except Exception as e:
	print(f"[WARN] Neo4j connection warning: {e}")
	driver = None


# ========== 1) Public API (query flow order) ==========
# Order: extract_entities -> build_typed_cypher -> get_relevant_articles -> generate_answer

def generate_text(messages: list[dict[str, str]], max_new_tokens: int = 220) -> str:
	"""
	Call local HF model via chat template + raw pipeline.

	Interface:
	- Input:
	  - messages: list[dict[str, str]] (chat messages with role/content)
	  - max_new_tokens: int
	- Output:
	  - str (model generated text, no JSON guarantee)
	"""
	tok = get_tokenizer()
	pipe = get_raw_pipeline()
	if tok is None or pipe is None:
		load_local_llm()
		tok = get_tokenizer()
		pipe = get_raw_pipeline()
	prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
	return pipe(prompt, max_new_tokens=max_new_tokens)[0]["generated_text"].strip()


_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "and", "but", "or", "yet", "so", "if",
    "because", "although", "though", "while", "where", "when", "that",
    "which", "who", "whom", "whose", "what", "this", "these", "those",
    "i", "me", "my", "myself", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "it", "its", "they", "them", "their", "student",
    "students", "they", "them",
}


def _classify_question(question: str) -> str:
    q_lower = question.lower().strip()
    if q_lower.startswith("how many") or q_lower.startswith("how much"):
        return "quantitative"
    if q_lower.startswith("can ") or q_lower.startswith("is ") or q_lower.startswith("are "):
        return "boolean"
    if "penalty" in q_lower or "deduct" in q_lower or "score" in q_lower:
        return "penalty"
    if "fee" in q_lower or "cost" in q_lower or "ntd" in q_lower:
        return "fee"
    if "how" in q_lower:
        return "procedure"
    return "general"


def extract_entities(question: str) -> dict[str, Any]:
    """Parse question to {question_type, subject_terms, aspect}."""
    words = re.findall(r"[a-zA-Z0-9]+", question.lower())
    subject_terms = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
    # Remove duplicates while preserving order
    seen = set()
    subject_terms = [w for w in subject_terms if not (w in seen or seen.add(w))]

    question_type = _classify_question(question)
    aspect = "general"
    if subject_terms:
        aspect = subject_terms[-1]

    return {
        "question_type": question_type,
        "subject_terms": subject_terms,
        "aspect": aspect,
    }


def build_typed_cypher(entities: dict[str, Any]) -> tuple[str, str]:
    """Return (typed_query, broad_query) with score and required fields."""
    terms = entities.get("subject_terms", [])
    # Use OR for fulltext search; if no terms, fall back to wildcard
    if terms:
        query_text = " OR ".join(terms)
    else:
        query_text = "*"

    # Safe to embed because terms are regex-cleaned alphanumeric words
    cypher_typed = (
        "CALL db.index.fulltext.queryNodes('rule_idx', '" + query_text + "') YIELD node, score\n"
        "RETURN node.rule_id AS rule_id, node.type AS type, node.action AS action,\n"
        "       node.result AS result, node.art_ref AS art_ref, node.reg_name AS reg_name, score\n"
        "LIMIT 10"
    )

    cypher_broad = (
        "CALL db.index.fulltext.queryNodes('article_content_idx', '" + query_text + "') YIELD node, score\n"
        "MATCH (node)-[:CONTAINS_RULE]->(r:Rule)\n"
        "RETURN r.rule_id AS rule_id, r.type AS type, r.action AS action,\n"
        "       r.result AS result, r.art_ref AS art_ref, r.reg_name AS reg_name, score\n"
        "LIMIT 10"
    )

    return cypher_typed, cypher_broad


def get_relevant_articles(question: str) -> list[dict[str, Any]]:
    """Run typed+broad retrieval and return merged rule dicts."""
    if driver is None:
        return []

    entities = extract_entities(question)
    cypher_typed, cypher_broad = build_typed_cypher(entities)

    merged: dict[str, dict[str, Any]] = {}

    with driver.session() as session:
        # Typed search on Rules
        typed_results = session.run(cypher_typed)
        for record in typed_results:
            rid = record["rule_id"]
            if rid not in merged:
                merged[rid] = {
                    "rule_id": rid,
                    "type": record["type"],
                    "action": record["action"],
                    "result": record["result"],
                    "art_ref": record["art_ref"],
                    "reg_name": record["reg_name"],
                    "score": float(record["score"]),
                    "source": "typed",
                }

        # Broad search on Articles -> Rules
        broad_results = session.run(cypher_broad)
        for record in broad_results:
            rid = record["rule_id"]
            if rid not in merged:
                merged[rid] = {
                    "rule_id": rid,
                    "type": record["type"],
                    "action": record["action"],
                    "result": record["result"],
                    "art_ref": record["art_ref"],
                    "reg_name": record["reg_name"],
                    "score": float(record["score"]) * 0.9,
                    "source": "broad",
                }

    # Sort by score desc
    results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return results


def generate_answer(question: str, rule_results: list[dict[str, Any]]) -> str:
    """Generate grounded answer from retrieved rules only."""
    if not rule_results:
        return "Insufficient rule evidence to answer this question."

    context_lines = []
    for i, r in enumerate(rule_results[:5], 1):
        context_lines.append(
            f"{i}. [{r.get('reg_name')} - {r.get('art_ref')}] "
            f"{r.get('action')} -> {r.get('result')}"
        )
    context = "\n".join(context_lines)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a university regulation assistant. "
                "Answer the question concisely based ONLY on the provided rules. "
                "Do not make up facts. If the rules do not contain the answer, say so."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Relevant Rules:\n{context}\n\n"
                f"Answer:"
            ),
        },
    ]

    return generate_text(messages, max_new_tokens=220)


def main() -> None:
	"""Interactive CLI (provided scaffold)."""
	if driver is None:
		return

	load_local_llm()

	print("=" * 50)
	print("NCU Regulation Assistant (Template)")
	print("=" * 50)
	print("Try: 'What is the penalty for forgetting student ID?'")
	print("Type 'exit' to quit.\n")

	while True:
		try:
			user_q = input("\nUser: ").strip()
			if not user_q:
				continue
			if user_q.lower() in {"exit", "quit"}:
				print("Bye!")
				break

			results = get_relevant_articles(user_q)
			answer = generate_answer(user_q, results)
			print(f"Bot: {answer}")

		except KeyboardInterrupt:
			print("\nBye!")
			break
		except NotImplementedError as e:
			print(f"[WARN] {e}")
			break
		except Exception as e:
			print(f"[ERROR] {e}")

	driver.close()


if __name__ == "__main__":
	main()

