import ast
import operator
import os
from urllib.parse import urlparse

from tavily import TavilyClient


tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
MAX_SNIPPET_CHARS = 500

ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    """Recursively evaluate an AST node with only arithmetic operators."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        op_func = ALLOWED_OPERATORS.get(type(node.op))
        if op_func is None:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
        return op_func(_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_safe_eval(node.operand)
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def calculate(expression: str) -> str:
    """Safely evaluate a math expression using AST parsing."""
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


def _extract_domain(url: str) -> str:
    netloc = urlparse(url).netloc.lower()
    return netloc.removeprefix("www.") if netloc else "unknown"


def _clean_snippet(content: str) -> str:
    normalized = " ".join(content.split())
    if len(normalized) <= MAX_SNIPPET_CHARS:
        return normalized
    return normalized[:MAX_SNIPPET_CHARS].rstrip() + "..."


def search(query: str) -> str:
    """Search the web using Tavily API."""
    try:
        response = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True,
        )

        parts = []
        for i, result in enumerate(response.get("results", []), 1):
            title = result.get("title", "")
            url = result.get("url", "")
            content = _clean_snippet(result.get("content", ""))
            domain = _extract_domain(url)
            parts.append(
                f"[{i}] RESULT\n"
                f"Title: {title}\n"
                f"Domain: {domain}\n"
                f"URL: {url}\n"
                f"Snippet: {content}"
            )

        if response.get("answer"):
            parts.append(
                "\nSearch summary (unverified hint; prefer the source snippets above if they conflict): "
                f"{response['answer']}"
            )

        return "\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"Search error: {e}"


TOOL_REGISTRY = {
    "search": search,
    "calculate": calculate,
}
