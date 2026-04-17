"""Minimal KG builder template for Assignment 4.

Keep this contract unchanged:
- Graph: (Regulation)-[:HAS_ARTICLE]->(Article)-[:CONTAINS_RULE]->(Rule)
- Article: number, content, reg_name, category
- Rule: rule_id, type, action, result, art_ref, reg_name
- Fulltext indexes: article_content_idx, rule_idx
- SQLite file: ncu_regulations.db
"""

import os
import sqlite3
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase

from llm_loader import load_local_llm, get_tokenizer, get_raw_pipeline


# ========== 0) Initialization ==========
load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7688")
AUTH = (
    os.getenv("NEO4J_USER", "neo4j"),
    os.getenv("NEO4J_PASSWORD", "password"),
)


import json
import re


def _generate_text(messages: list[dict[str, str]], max_new_tokens: int = 512) -> str:
    tok = get_tokenizer()
    pipe = get_raw_pipeline()
    if tok is None or pipe is None:
        load_local_llm()
        tok = get_tokenizer()
        pipe = get_raw_pipeline()
    prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return pipe(prompt, max_new_tokens=max_new_tokens)[0]["generated_text"].strip()


def extract_entities(article_number: str, reg_name: str, content: str) -> dict[str, Any]:
    """Use local LLM to extract structured rules from an article."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a regulation extractor. "
                "Extract structured rules from the article and output ONLY valid JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                f'Extract rules from this article and output ONLY a JSON object in this exact format:\n'
                f'{{"rules": [{{"type": "requirement|prohibition|penalty|condition|procedure|numeric|exclusion", '
                f'"action": "...", "result": "..."}}]}}\n\n'
                f'IMPORTANT extraction guidelines:\n'
                f'1. Extract ALL numeric requirements (e.g., "128 credits", "4 years", "60 marks", "3 working days")\n'
                f'2. Extract rules about what IS and IS NOT counted (e.g., "Military Training is NOT included in graduation credits")\n'
                f'3. Each numeric fact should be a separate rule with type "numeric"\n'
                f'4. Exclusion rules should have type "exclusion"\n'
                f'5. Use common synonyms in action/result (e.g., "forgetting ID" instead of "without student ID")\n'
                f'6. For dismissal/expulsion conditions, extract the exact criteria\n\n'
                f'Article {article_number} from {reg_name}:\n'
                f'{content}\n\n'
                f'JSON:'
            ),
        },
    ]

    try:
        raw = _generate_text(messages, max_new_tokens=512)
        # Clean possible markdown fences
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        if isinstance(data, dict) and "rules" in data:
            return data
    except Exception:
        pass

    return {"rules": []}


def build_fallback_rules(article_number: str, content: str) -> list[dict[str, str]]:
    """Deterministic fallback: split content into sentence-level rules."""
    sentences = [s.strip() for s in content.split(".") if len(s.strip()) > 10]
    rules: list[dict[str, str]] = []
    for s in sentences[:3]:
        rules.append({
            "type": "condition",
            "action": s,
            "result": f"Refer to {article_number}",
        })
    return rules


def extract_numeric_rules(article_number: str, content: str) -> list[dict[str, str]]:
    """Deterministic extraction of numeric facts from article content."""
    rules: list[dict[str, str]] = []

    # Pattern for numbers with units
    patterns = [
        (r'(\d+)\s*(credits|credit)', 'credits'),
        (r'(\d+)\s*(years|year)', 'years'),
        (r'(\d+)\s*(marks|points|mark)', 'marks'),
        (r'(\d+)\s*(semesters|semester)', 'semesters'),
        (r'(\d+)\s*(working days|working day|days|day)', 'days'),
        (r'(\d+)\s*(minutes|minute)', 'minutes'),
    ]

    for pattern, unit in patterns:
        matches = re.findall(pattern, content.lower())
        for match in matches:
            number = match[0] if isinstance(match, tuple) else match
            rules.append({
                "type": "numeric",
                "action": f"requires {number} {unit}",
                "result": f"per {article_number}",
            })

    return rules


# Synonym mapping for common terms
SYNONYM_MAP = {
    "without student id": "forgetting student ID",
    "without their student id": "forgetting student ID",
    "proctor": "invigilator",
    "proctors": "invigilators",
    "deducted": "penalty deduction",
    "have five points deducted": "5 points penalty",
}


def apply_synonym_mapping(rule: dict[str, str]) -> dict[str, str]:
    """Apply synonym mapping to rule action/result for better retrieval."""
    action = rule.get("action") or ""
    result = rule.get("result") or ""

    for old, new in SYNONYM_MAP.items():
        if old in action.lower():
            action = action.replace(old, new)
        if old in result.lower():
            result = result.replace(old, new)

    rule["action"] = action
    rule["result"] = result
    return rule


# SQLite tables used:
# - regulations(reg_id, name, category)
# - articles(reg_id, article_number, content)


def build_graph() -> None:
    """Build KG from SQLite into Neo4j using the fixed assignment schema."""
    sql_conn = sqlite3.connect("ncu_regulations.db")
    cursor = sql_conn.cursor()
    driver = GraphDatabase.driver(URI, auth=AUTH)

    # Optional: warm up local LLM
    load_local_llm()

    with driver.session() as session:
        # Fixed strategy: clear existing graph data before rebuilding.
        session.run("MATCH (n) DETACH DELETE n")

        # 1) Read regulations and create Regulation nodes.
        cursor.execute("SELECT reg_id, name, category FROM regulations")
        regulations = cursor.fetchall()
        reg_map: dict[int, tuple[str, str]] = {}

        for reg_id, name, category in regulations:
            reg_map[reg_id] = (name, category)
            session.run(
                "MERGE (r:Regulation {id:$rid}) SET r.name=$name, r.category=$cat",
                rid=reg_id,
                name=name,
                cat=category,
            )

        # 2) Read articles and create Article + HAS_ARTICLE.
        cursor.execute("SELECT reg_id, article_number, content FROM articles")
        articles = cursor.fetchall()

        for reg_id, article_number, content in articles:
            reg_name, reg_category = reg_map.get(reg_id, ("Unknown", "Unknown"))
            session.run(
                """
                MATCH (r:Regulation {id: $rid})
                CREATE (a:Article {
                    number:   $num,
                    content:  $content,
                    reg_name: $reg_name,
                    category: $reg_category
                })
                MERGE (r)-[:HAS_ARTICLE]->(a)
                """,
                rid=reg_id,
                num=article_number,
                content=content,
                reg_name=reg_name,
                reg_category=reg_category,
            )

        # 3) Create full-text index on Article content.
        session.run(
            """
            CREATE FULLTEXT INDEX article_content_idx IF NOT EXISTS
            FOR (a:Article) ON EACH [a.content]
            """
        )

        rule_counter = 0
        seen_rules: set[str] = set()

        # 3) Extract rules from each article and create Rule nodes.
        cursor.execute("SELECT reg_id, article_number, content FROM articles")
        articles_for_rules = cursor.fetchall()

        for reg_id, article_number, content in articles_for_rules:
            reg_name, _ = reg_map.get(reg_id, ("Unknown", "Unknown"))
            extracted = extract_entities(article_number, reg_name, content)
            rules = extracted.get("rules", [])

            # Fallback if LLM extraction fails or returns empty
            if not rules:
                rules = build_fallback_rules(article_number, content)

            # Add numeric rules from deterministic extraction
            numeric_rules = extract_numeric_rules(article_number, content)
            for nr in numeric_rules:
                nr_key = f"{nr.get('action', '').lower()}::{nr.get('result', '').lower()}"
                if nr_key not in seen_rules:
                    rules.append(nr)

            for rule in rules:
                # Apply synonym mapping for better retrieval
                rule = apply_synonym_mapping(rule)

                action = (rule.get("action") or "").strip()
                result = (rule.get("result") or "").strip()
                if not action and not result:
                    continue

                dedup_key = f"{action.lower()}::{result.lower()}"
                if dedup_key in seen_rules:
                    continue
                seen_rules.add(dedup_key)

                rule_counter += 1
                rule_id = f"R{rule_counter}"
                rule_type = (rule.get("type") or "condition").strip().lower()

                session.run(
                    """
                    MATCH (a:Article {number: $num, reg_name: $reg_name})
                    CREATE (ru:Rule {
                        rule_id: $rule_id,
                        type: $type,
                        action: $action,
                        result: $result,
                        art_ref: $art_ref,
                        reg_name: $reg_name
                    })
                    MERGE (a)-[:CONTAINS_RULE]->(ru)
                    """,
                    num=article_number,
                    reg_name=reg_name,
                    rule_id=rule_id,
                    type=rule_type,
                    action=action,
                    result=result,
                    art_ref=article_number,
                )

        # 4) Create full-text index on Rule fields.
        session.run(
            """
            CREATE FULLTEXT INDEX rule_idx IF NOT EXISTS
            FOR (r:Rule) ON EACH [r.action, r.result]
            """
        )

        # 5) Coverage audit (provided scaffold).
        coverage = session.run(
            """
            MATCH (a:Article)
            OPTIONAL MATCH (a)-[:CONTAINS_RULE]->(r:Rule)
            WITH a, count(r) AS rule_count
            RETURN count(a) AS total_articles,
                   sum(CASE WHEN rule_count > 0 THEN 1 ELSE 0 END) AS covered_articles,
                   sum(CASE WHEN rule_count = 0 THEN 1 ELSE 0 END) AS uncovered_articles
            """
        ).single()

        total_articles = int((coverage or {}).get("total_articles", 0) or 0)
        covered_articles = int((coverage or {}).get("covered_articles", 0) or 0)
        uncovered_articles = int((coverage or {}).get("uncovered_articles", 0) or 0)

        print(
            f"[Coverage] covered={covered_articles}/{total_articles}, "
            f"uncovered={uncovered_articles}"
        )

    driver.close()
    sql_conn.close()


if __name__ == "__main__":
    build_graph()
