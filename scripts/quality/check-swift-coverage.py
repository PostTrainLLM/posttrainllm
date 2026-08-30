#!/usr/bin/env python3

import json
import sys
from pathlib import Path

MINIMUM_PRODUCTION_LINE_COVERAGE = 0.3235
PRODUCTION_TARGETS = {"TinyGPTIO", "TinyGPTModel", "TinyGPTServe"}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check-swift-coverage.py COVERAGE_JSON", file=sys.stderr)
        return 2
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    targets = {target.get("name"): target for target in report.get("targets", [])}
    missing = sorted(PRODUCTION_TARGETS - targets.keys())
    if missing:
        print(
            f"missing production coverage targets: {', '.join(missing)}",
            file=sys.stderr,
        )
        return 1
    covered = sum(
        int(targets[name].get("coveredLines", 0)) for name in PRODUCTION_TARGETS
    )
    executable = sum(
        int(targets[name].get("executableLines", 0)) for name in PRODUCTION_TARGETS
    )
    if executable <= 0:
        print("Swift coverage contains no executable production lines", file=sys.stderr)
        return 1
    coverage = covered / executable
    print(
        f"Swift production coverage: {coverage * 100:.4f}% ({covered}/{executable} lines)"
    )
    if coverage < MINIMUM_PRODUCTION_LINE_COVERAGE:
        print(
            f"coverage regressed below {MINIMUM_PRODUCTION_LINE_COVERAGE * 100:.2f}%",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
