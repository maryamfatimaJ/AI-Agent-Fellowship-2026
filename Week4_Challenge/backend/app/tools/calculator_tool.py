"""Calculator Tool — safe arithmetic evaluation for numeric analysis (e.g.
CAGR, percentage deltas) without ever calling `eval` on untrusted input.

Only numeric literals and `+ - * / ** % ()` are permitted; anything else
(names, calls, attribute access, subscripts) raises `ToolExecutionError`.
"""

from __future__ import annotations

import ast
import operator

from app.utils.errors import ToolExecutionError

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_ALLOWED_UNARYOPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def calculate(expression: str) -> float:
    """Evaluate a numeric expression such as "(120 - 100) / 100 * 100"."""

    try:
        tree = ast.parse(expression, mode="eval")
        return _eval_node(tree.body)
    except ToolExecutionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ToolExecutionError(f"Invalid arithmetic expression: {expression!r}", details={"error": str(exc)}) from exc


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand))
    raise ToolExecutionError(f"Disallowed expression element: {ast.dump(node)}")
