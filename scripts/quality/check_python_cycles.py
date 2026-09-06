#!/usr/bin/env python3
"""Deterministic import-cycle check for python_ref.

Replaces pycycle==0.0.8, which walks the filesystem with os.walk() and
seeds its traversal from whichever file happens to be listed first (an
order that depends on the filesystem / checkout method, not on the code).
Its cycle test also increments a shared "marked" counter on every node an
import reaches and calls anything visited a second time a cycle, so a
plain fan-in (two unrelated scripts importing the same leaf module, e.g.
train.py and sample.py both importing model.py) is misreported as a
circular import purely depending on traversal order. See the 2026-09-06
posttrainllm CI investigation: a real `git clone` checkout reproduced a
false-positive "Cycle Found" 10/10 runs, while every other checkout
method (bind mount, tarball) reproduced 0/10 runs, for a project graph
that a manual trace shows is a DAG.

This script parses the same directory with ast, builds the local-module
import graph, and finds real cycles with a standard white/gray/black DFS
that is independent of file discovery order.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def local_modules(root: Path) -> dict[str, Path]:
    return {path.stem: path for path in sorted(root.glob("*.py"))}


def imported_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def build_graph(root: Path) -> dict[str, set[str]]:
    modules = local_modules(root)
    graph: dict[str, set[str]] = {name: set() for name in modules}
    for name, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        graph[name] = {
            imported
            for imported in imported_names(tree)
            if imported in modules and imported != name
        }
    return graph


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in graph}
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        path.append(node)
        for neighbor in sorted(graph[node]):
            if color[neighbor] == GRAY:
                cycle_start = path.index(neighbor)
                return [*path[cycle_start:], neighbor]
            if color[neighbor] == WHITE:
                found = visit(neighbor)
                if found:
                    return found
        path.pop()
        color[node] = BLACK
        return None

    for node in sorted(graph):
        if color[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    graph = build_graph(root)
    cycle = find_cycle(graph)
    if cycle:
        print("Cycle Found :(")
        print(" -> ".join(cycle))
        return 1
    print("No worries, no cycles here!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
