"""Restricted repair syntax plus the already qualified fail-closed Mac executor."""

import ast
import hashlib
import json
import subprocess
import time
from pathlib import Path

from prepare import OUT, write

FORBIDDEN = {
    "open",
    "eval",
    "exec",
    "compile",
    "__import__",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "breakpoint",
    "input",
    "exit",
    "quit",
}
METHODS = {
    "fromkeys",
    "items",
    "values",
    "keys",
    "append",
    "extend",
    "setdefault",
    "get",
    "startswith",
    "endswith",
    "count",
    "split",
    "join",
    "replace",
    "sort",
    "reverse",
    "lower",
    "upper",
    "isdigit",
    "isalpha",
    "strip",
    "lstrip",
    "rstrip",
    "copy",
    "pop",
    "insert",
    "index",
}


def clean(text):
    if "```" in text:
        text = text.split("```", 2)[1]
        if text.startswith("python"):
            text = text[6:]
    return text.strip() + "\n"


def valid_root(tree, code):
    if len(code) > 4096 or len(tree.body) != 1:
        return False
    root = tree.body[0]
    return (
        isinstance(root, ast.FunctionDef)
        and root.name == "candidate"
        and not root.decorator_list
    )


def forbidden_node(node):
    if isinstance(
        node, (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal)
    ):
        return True
    if isinstance(node, ast.Name):
        return node.id in FORBIDDEN or node.id.startswith("__")
    if isinstance(node, ast.Attribute):
        return node.attr not in METHODS
    return False


def inspect(code):
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return {
            "valid": False,
            "nodes": 0,
            "pass_raise": 0,
            "ifs": 0,
            "comparisons": 0,
            "literals": 0,
        }
    nodes = list(ast.walk(tree))
    valid = (
        valid_root(tree, code)
        and len(nodes) <= 500
        and not any(forbidden_node(node) for node in nodes)
    )
    return {
        "valid": bool(valid),
        "nodes": len(nodes),
        "pass_raise": sum(isinstance(n, (ast.Pass, ast.Raise)) for n in nodes),
        "ifs": sum(isinstance(n, (ast.If, ast.IfExp)) for n in nodes),
        "comparisons": sum(isinstance(n, ast.Compare) for n in nodes),
        "literals": sum(isinstance(n, ast.Constant) for n in nodes),
    }


def execute(code, cases, label):
    info = inspect(code)
    if not info["valid"]:
        return {
            "passed": False,
            "calls": 0,
            "seconds": 0,
            "invalid": True,
            "stop_reason": "restricted_syntax",
        }
    folder = OUT / "executions" / label
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "code.py").write_text(code)
    assertions = [
        f"    assert function(*{case['args']!r}) == {case['expected']!r}"
        for case in cases
    ]
    (folder / "test.py").write_text(
        "def check(function):\n" + "\n".join(assertions) + "\n"
    )
    started = time.monotonic()
    runner = Path(json.loads((OUT / "contract.json").read_text())["executor"]["path"])
    result = subprocess.run(
        [
            str(runner),
            "--code",
            str(folder / "code.py"),
            "--test",
            str(folder / "test.py"),
            "--timeout",
            "2",
            "--memory-mb",
            "256",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    elapsed = time.monotonic() - started
    if result.returncode:
        raise RuntimeError(
            "Qualified executor infrastructure failed; do not turn it into model failure: "
            + result.stderr[-500:]
        )
    raw = json.loads(result.stdout)
    response = {
        "passed": raw["passed"] is True and raw["stop_reason"] is None,
        "calls": 1,
        "seconds": elapsed,
        "invalid": False,
        "stop_reason": raw["stop_reason"],
        "child_peak_rss_bytes": raw["max_owned_child_rss_bytes"],
        "raw": raw,
    }
    write(folder / "receipt.json", response)
    return response


def verify_executor(contract):
    assert (
        hashlib.sha256(Path(contract["executor"]["path"]).read_bytes()).hexdigest()
        == contract["executor"]["sha256"]
    )
    result = execute(
        "def candidate(x):\n    return x + 1\n",
        [{"args": [4], "expected": 5}],
        "preflight",
    )
    assert result["passed"]
    return result
