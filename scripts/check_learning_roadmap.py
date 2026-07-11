#!/usr/bin/env python3
"""Check that the ground-up owner learning roadmap stays complete."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CURRICULUM_NEEDLES = [
    "## 10/10 Bar",
    "## Operating Loop",
    "## Canonical External Anchors",
    "## Master Roadmap",
    "## Where Existing Sessions Fit",
    "## Coverage Beyond the Spine",
    "## Current Starting Point",
    "## Checkpoint Template",
    "concept -> toy implementation -> posttrainllm anchor -> factory consequence",
    "functions, data, parameters",
    "loss and gradient descent",
    "vectors, matrices, tensors",
    "attention and transformer blocks",
    "post-training: SFT, LoRA, preference tuning",
    "evals, rewards, and self-improvement",
    "Mastery Gate",
    # Every module now has a polished session; the curriculum must point at all three
    # gap-filling sessions so they cannot be orphaned.
    "session-09-tensors.md",
    "session-10-attention.md",
    "session-11-evals-rewards.md",
    "coverage-map.md",
]

# Each module maps to exactly one polished session. The three below closed the
# previously reference-only gaps (Modules 3, 7, 10).
SESSION_FILES = [
    ("docs/learn/session-09-tensors.md", "Module 3"),
    ("docs/learn/session-10-attention.md", "Module 7"),
    ("docs/learn/session-11-evals-rewards.md", "Module 10"),
]

# The coverage map is the guarantee that every shipped subsystem has a learning
# anchor, not just the ground-up spine.
COVERAGE_NEEDLES = [
    "# Learning coverage map",
    "## 1. Foundations",
    "## Coverage Guarantee",
    "### Maintenance rule",
    "target -> data -> post-training -> eval -> package -> report",
    "session-09-tensors.md",
    "session-10-attention.md",
    "session-11-evals-rewards.md",
    "interpretability",
    "quantization",
]

PIPELINE_NEEDLES = [
    "math intuition -> tiny neural net -> training loop -> transformer",
    "## Ground-Up Master Roadmap",
    "The SQL factory is the lab, not the starting point.",
    "## Factory-Attached Learning Sequence",
]

PROGRESS_NEEDLES = [
    "## Ground-Up Roadmap Progress",
    "Canonical roadmap: [`learn/curriculum.md`](learn/curriculum.md).",
    "## Factory Lab Progress",
    "The next ground-up focus is **Module 1 -> Module 2**",
]


def require_needles(rel: str, needles: list[str], errors: list[str]) -> str:
    path = ROOT / rel
    if not path.is_file():
        errors.append(f"missing {rel}")
        return ""
    text = path.read_text(encoding="utf-8")
    haystack = text.lower()
    for needle in needles:
        if needle.lower() not in haystack:
            errors.append(f"{rel}: missing {needle!r}")
    return text


def main() -> int:
    errors: list[str] = []

    curriculum = require_needles(
        "docs/learn/curriculum.md", CURRICULUM_NEEDLES, errors
    )
    require_needles("docs/learning-pipeline.md", PIPELINE_NEEDLES, errors)
    progress = require_needles("docs/learning-progress.md", PROGRESS_NEEDLES, errors)
    require_needles(
        "docs/learn/README.md",
        [
            "Start here for ground-up learning",
            "10-module ground-up roadmap",
            "coverage-map.md",
        ],
        errors,
    )

    require_needles("docs/learn/coverage-map.md", COVERAGE_NEEDLES, errors)

    # Every module's polished session must exist and keep the sibling structure
    # (a self-check and a "where this connects" bridge back to the project).
    for rel, module_tag in SESSION_FILES:
        text = require_needles(
            rel,
            [module_tag, "## Self-check", "## Where this connects"],
            errors,
        )
        if text and "posttrainllm" not in text.lower():
            errors.append(f"{rel}: missing posttrainllm project anchor")

    roadmap_rows = re.findall(r"^\| (10|[1-9]) \|", curriculum, flags=re.MULTILINE)
    if sorted(int(row) for row in roadmap_rows) != list(range(1, 11)):
        errors.append("docs/learn/curriculum.md: expected exactly roadmap rows 1-10")

    progress_rows = re.findall(r"^\| (10|[1-9]) \|", progress, flags=re.MULTILINE)
    if sorted(int(row) for row in progress_rows) != list(range(1, 11)):
        errors.append("docs/learning-progress.md: expected exactly progress rows 1-10")

    if "not-started" not in progress or "reading" not in progress:
        errors.append("docs/learning-progress.md: expected explicit status vocabulary use")

    if errors:
        for err in errors:
            print(f"FAIL: {err}", file=sys.stderr)
        return 1
    print("learning roadmap check ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
