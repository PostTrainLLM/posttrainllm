"""Portable regressions for the pilot's grader and prompt leakage boundary."""

import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def probe(code):
    setup = "import sys;sys.path.insert(0,'scripts/repair_selection');"
    result = subprocess.run(
        [sys.executable, "-c", setup + code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


class RepairSelectionContract(unittest.TestCase):
    def test_valid_dictionary_repair_and_restricted_syntax(self):
        sources = [
            "def candidate(xs):\n    return list(dict.fromkeys(xs))\n",
            "def candidate(xs):\n    import os\n    return xs\n",
            'def candidate(xs):\n    return open("test.py").read()\n',
            "def candidate(xs):\n    return xs.__class__\n",
            "def candidate(:\n",
            "def candidate(x):\n    return x\n" + "#" * 4096,
        ]
        actual = probe(
            "from executor import inspect;import json;"
            f'print(json.dumps([inspect(s)["valid"] for s in {sources!r}]))'
        )
        self.assertEqual(actual, [True, False, False, False, False, False])

    def test_hidden_cases_cannot_enter_the_coder_request(self):
        actual = probe(
            "from calibrate import request;from prepare import TASKS;import json;"
            'task={**TASKS[0],"hidden":[{"secret":"heldout-sentinel"}]};'
            "print(json.dumps(request(task)))"
        )
        self.assertNotIn("hidden", actual)
        self.assertNotIn("heldout-sentinel", json.dumps(actual))
        self.assertIn("public_examples", actual)

    def test_problem_templates_are_disjoint_across_frozen_splits(self):
        actual = probe(
            "from prepare import TASKS;import json;"
            'print(json.dumps([{k:t[k] for k in ["id","template","split"]} for t in TASKS]))'
        )
        self.assertEqual(len({row["template"] for row in actual}), 18)
        self.assertEqual(len({row["id"] for row in actual}), 18)
        self.assertEqual(
            {
                split: sum(r["split"] == split for r in actual)
                for split in ["train", "dev", "test"]
            },
            {"train": 8, "dev": 4, "test": 6},
        )


if __name__ == "__main__":
    unittest.main()
