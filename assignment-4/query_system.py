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

URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
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

# Short keywords whitelist - keep meaningful 2-letter words
_SHORT_KEYWORDS = {"id", "pe", "ntd", "no", "yes"}


def _build_article_snippet(content: str, terms: list[str], max_chars: int = 220) -> str:
    """Extract a short snippet from article content centered around matching terms."""
    compact = re.sub(r"\s+", " ", content or "").strip()
    if not compact:
        return ""
    lower = compact.lower()
    hit_pos = [lower.find(t) for t in terms if t and lower.find(t) >= 0]
    start = 0
    if hit_pos:
        start = max(0, min(hit_pos) - 60)
    end = min(len(compact), start + max_chars)
    snippet = compact[start:end]
    if start > 0:
        snippet = "..." + snippet
    if end < len(compact):
        snippet += "..."
    return snippet


def _attach_article_snippets(session: Any, candidates: list[dict[str, Any]], terms: list[str]) -> None:
    """Batch-fetch article content and attach snippets to rule candidates."""
    pairs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for rule in candidates:
        art_ref = str(rule.get("art_ref") or "")
        reg_name = str(rule.get("reg_name") or "")
        if not art_ref or not reg_name:
            continue
        key = (art_ref, reg_name)
        if key in seen:
            continue
        seen.add(key)
        pairs.append({"art_ref": art_ref, "reg_name": reg_name})
    if not pairs:
        return

    rows = session.run(
        """
        UNWIND $pairs AS p
        MATCH (a:Article {number: p.art_ref, reg_name: p.reg_name})
        RETURN a.number AS art_ref, a.reg_name AS reg_name, a.content AS content
        """,
        pairs=pairs,
    )
    article_map: dict[tuple[str, str], str] = {}
    for row in rows:
        article_map[(str(row["art_ref"]), str(row["reg_name"]))] = str(row["content"] or "")

    for rule in candidates:
        key = (str(rule.get("art_ref") or ""), str(rule.get("reg_name") or ""))
        content = article_map.get(key, "")
        if content:
            rule["article_snippet"] = _build_article_snippet(content, terms)



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
    # Keep words: not in STOP_WORDS, len>=3 OR in SHORT_KEYWORDS whitelist
    subject_terms = [
        w for w in words
        if w not in _STOP_WORDS and (len(w) >= 3 or w in _SHORT_KEYWORDS)
    ]
    # Remove duplicates while preserving order
    seen = set()
    subject_terms = [w for w in subject_terms if not (w in seen or seen.add(w))]

    # Limit to top 5 keywords to avoid score dilution
    subject_terms = subject_terms[:5]

    question_type = _classify_question(question)
    aspect = "general"
    if subject_terms:
        aspect = subject_terms[-1]

    return {
        "question_type": question_type,
        "subject_terms": subject_terms,
        "aspect": aspect,
    }


def build_typed_cypher(entities: dict[str, Any], question: str = "") -> tuple[str, str]:
    """Return (typed_query, broad_query) with score boost for relevant Rule types."""
    terms = entities.get("subject_terms", [])
    q_type = entities.get("question_type", "general")

    # Inject domain keywords based on question context
    domain_keywords = []
    q_lower = question.lower()

    # Exam-related questions: inject "exam" keyword
    if q_type == "penalty" or "penalty" in q_lower or "exam" in q_lower:
        domain_keywords.append("exam")

    # Invigilator/proctor: inject both synonyms
    if "invigilator" in q_lower or "proctor" in q_lower:
        domain_keywords.append("proctor")

    # Student ID related: ensure "id" is included
    if "id" in q_lower and "id" not in terms:
        domain_keywords.append("id")

    # Graduate/Master/PhD -> inject "postgraduate" (KG uses this term in Article content)
    if "graduate" in q_lower or "master" in q_lower or "phd" in q_lower:
        domain_keywords.append("postgraduate")

    # Passing score questions: inject "marks" keyword
    if "passing" in q_lower and ("score" in q_lower or "grade" in q_lower):
        domain_keywords.append("marks")

    # Make-up exam: inject "exam"
    if "make-up exam" in q_lower:
        domain_keywords.append("exam")

    # Extension period: inject "extension"
    if "extension" in q_lower:
        domain_keywords.append("extension")

    # Combine terms with domain keywords (avoid duplicates)
    all_terms = list(set(terms + domain_keywords))

    # Use OR for fulltext search; if no terms, fall back to wildcard
    if all_terms:
        query_text = " OR ".join(all_terms)
    else:
        query_text = "*"

    # Determine preferred Rule types based on question context
    preferred_types = []
    if q_type == "quantitative" or "how many" in q_lower or "how much" in q_lower:
        preferred_types.append("numeric")
    if "passing" in q_lower or "score" in q_lower or "marks" in q_lower:
        preferred_types.extend(["numeric", "requirement"])
    if q_type == "penalty" or "penalty" in q_lower:
        preferred_types.append("penalty")
    if "minutes" in q_lower or "late" in q_lower:
        preferred_types.append("numeric")
    if "semesters" in q_lower or "pe" in q_lower:
        preferred_types.extend(["requirement", "numeric"])
    if "dismissed" in q_lower or "expelled" in q_lower:
        preferred_types.append("dismissal condition")

    # Build type boost condition for Cypher
    type_boost = ""
    if preferred_types:
        type_conditions = [f"node.type = '{t}'" for t in preferred_types]
        type_boost = f"CASE WHEN ({' OR '.join(type_conditions)}) THEN score * 1.5 ELSE score END AS boosted_score"

    # Safe to embed because terms are regex-cleaned alphanumeric words
    if type_boost:
        cypher_typed = (
            "CALL db.index.fulltext.queryNodes('rule_idx', '" + query_text + "') YIELD node, score\n"
            "WITH node, " + type_boost + "\n"
            "RETURN node.rule_id AS rule_id, node.type AS type, node.action AS action,\n"
            "       node.result AS result, node.art_ref AS art_ref, node.reg_name AS reg_name, boosted_score AS score\n"
            "ORDER BY score DESC\n"
            "LIMIT 25"
        )
    else:
        cypher_typed = (
            "CALL db.index.fulltext.queryNodes('rule_idx', '" + query_text + "') YIELD node, score\n"
            "RETURN node.rule_id AS rule_id, node.type AS type, node.action AS action,\n"
            "       node.result AS result, node.art_ref AS art_ref, node.reg_name AS reg_name, score\n"
            "ORDER BY score DESC\n"
            "LIMIT 25"
        )

    # Broad search with full weight - Article content can contain context keywords
    # that are not in Rule action/result fields (e.g., "postgraduate students")
    cypher_broad = (
        "CALL db.index.fulltext.queryNodes('article_content_idx', '" + query_text + "') YIELD node, score\n"
        "MATCH (node)-[:CONTAINS_RULE]->(r:Rule)\n"
        "RETURN r.rule_id AS rule_id, r.type AS type, r.action AS action,\n"
        "       r.result AS result, r.art_ref AS art_ref, r.reg_name AS reg_name, score AS score\n"
        "ORDER BY score DESC\n"
        "LIMIT 25"
    )

    return cypher_typed, cypher_broad


def get_relevant_articles(question: str) -> list[dict[str, Any]]:
    """Run typed+broad retrieval and return merged rule dicts."""
    if driver is None:
        return []

    entities = extract_entities(question)
    cypher_typed, cypher_broad = build_typed_cypher(entities, question)

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
            if rid in merged:
                # Boost rules found by both typed and broad search
                merged[rid]["score"] += float(record["score"]) * 0.35
                merged[rid]["source"] = "typed+broad"
            else:
                merged[rid] = {
                    "rule_id": rid,
                    "type": record["type"],
                    "action": record["action"],
                    "result": record["result"],
                    "art_ref": record["art_ref"],
                    "reg_name": record["reg_name"],
                    "score": float(record["score"]),
                    "source": "broad",
                }

        results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        _attach_article_snippets(session, results[:12], entities.get("subject_terms", []))
    return results


def generate_answer(question: str, rule_results: list[dict[str, Any]]) -> str:
    """Generate grounded answer from retrieved rules only."""
    if not rule_results:
        return "Insufficient rule evidence to answer this question."

    context_lines = []
    for i, r in enumerate(rule_results[:5], 1):
        line = (
            f"{i}. [{r.get('reg_name')} - {r.get('art_ref')}] "
            f"{r.get('action')} -> {r.get('result')}"
        )
        snippet = str(r.get("article_snippet") or "").strip()
        if snippet:
            line += f"\n   Article snippet: {snippet}"
        context_lines.append(line)
    context = "\n".join(context_lines)

    # Detect question type for prompt customization
    q_lower = question.lower()
    is_quantitative = q_lower.startswith("how many") or q_lower.startswith("how much")
    is_numeric_question = any(word in q_lower for word in ["credits", "years", "marks", "points", "days", "minutes", "semesters"])

    system_prompt = (
        "You are a university regulation assistant. "
        "Answer the question concisely in a complete, natural sentence based ONLY on the provided rules. "
        "Do not make up facts. If the rules do not contain the answer, say 'Insufficient rule evidence to answer this question'.\n"
        "Important Guidelines:\n"
        "1. Read ALL the provided rules and their 'Article snippet' before making a conclusion.\n"
        "2. The snippet often contains the exact answer (like numbers, scores, or time limits) which might be missing from the rule action/result.\n"
        "3. If different rules give different numbers, carefully select the one whose snippet perfectly matches the specific student type (graduate/postgraduate vs undergraduate) or specific condition (lateness vs leaving)."
    )

    # Add specific instructions for numeric/quantitative questions
    if is_quantitative or is_numeric_question:
        system_prompt += (
            " For questions asking for specific numbers, carefully verify whether the number in the snippet corresponds precisely to the action asked about. "
            "Extract the exact numeric value directly into your complete sentence."
        )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
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