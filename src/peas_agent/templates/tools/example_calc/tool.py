"""Example workspace tool — copy this folder and customize."""

from langchain_core.tools import tool


@tool
def example_add(a: float, b: float) -> str:
    """兩個數字相加（範例自訂 tool）。"""
    return f"{a} + {b} = {a + b}"
