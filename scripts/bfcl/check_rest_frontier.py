#!/usr/bin/env python3
"""Fail closed unless Codex reaches the exact ceiling on both frozen ReST suites."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", required=True, type=Path)
    parser.add_argument("--breadth", required=True, type=Path)
    args = parser.parse_args()
    depth = json.loads(args.depth.read_text())
    breadth = json.loads(args.breadth.read_text())
    gates = (
        ("depth", depth, 12, 12),
        ("breadth", breadth, 45, 44),
    )
    for name, result, expected_count, minimum_passed in gates:
        if (
            result.get("count") != expected_count
            or result.get("passed", 0) < minimum_passed
        ):
            print(
                f"frontier ceiling failed: {name}="
                f"{result.get('passed')}/{result.get('count')} "
                f"(required at least {minimum_passed}/{expected_count})"
            )
            return 1
    print("frontier ceiling passed: depth=12/12 breadth>=44/45")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
