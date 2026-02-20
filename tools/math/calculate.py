import ast
import operator

from tools.responses import tool_response
from tools.schemas import CalculatorInput


ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}


def eval_node(node):
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)):
            raise ValueError("Only numeric constants allowed")
        return node.value

    if isinstance(node, ast.BinOp):
        left = eval_node(node.left)
        right = eval_node(node.right)

        op = ALLOWED_OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"Unsupported operator: {type(node.op).__name__}")

        if isinstance(node.op, ast.Div) and right == 0:
            raise ZeroDivisionError("Division by zero")

        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        operand = eval_node(node.operand)
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError("Unsupported unary operator")

    raise ValueError(f"Unsupported syntax: {type(node).__name__}")


def calculate(data: CalculatorInput):
    try:
        tree = ast.parse(data.expression, mode="eval")
        value = eval_node(tree.body)

        return tool_response(
            tool="calculator",
            success=True,
            data=value,
            meta=data.expression
        )

    except Exception as e:
        return tool_response(
            tool="calculator",
            success=False,
            error=str(e)
        )


