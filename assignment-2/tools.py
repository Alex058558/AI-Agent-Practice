import ast
import operator
import os

from tavily import TavilyClient


tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

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


def search(query: str) -> str:
    """Search the web using Tavily API."""
    try:
        response = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=3,
            include_answer=True,
        )

        parts = []
        if response.get("answer"):
            parts.append(f"Summary: {response['answer']}")

        for i, result in enumerate(response.get("results", []), 1):
            title = result.get("title", "")
            url = result.get("url", "")
            content = result.get("content", "")
            parts.append(f"\n[{i}] {title}\n    URL: {url}\n    {content}")

        return "\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"Search error: {e}"


TOOL_REGISTRY = {
    "search": search,
    "calculate": calculate,
}
