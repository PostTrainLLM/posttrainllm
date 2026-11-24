"""Deterministic checks for shell readiness before freezing recorder input."""

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/specialists"))
from terminal_codec import Screen
from terminal_record import capture


class RecorderReadyPromptTests(unittest.TestCase):
    def setUp(self):
        self.ready = Screen.custom("lab$ ", 8, 48).as_dict()
        self.recipe = {
            "id": "synthetic-recorder-example",
            "rows": 8,
            "cols": 48,
            "events": [{"keys": [112]}],
        }

    def test_waits_for_a_clean_prompt_after_setup(self):
        after_key = Screen.custom("lab$ p", 8, 48).as_dict()
        snapshot = Mock(
            side_effect=[
                Screen.custom("", 8, 48).as_dict(),
                self.ready,
                self.ready,
                Screen.custom("stty rows 8 cols 48", 8, 48).as_dict(),
                self.ready,
                after_key,
            ]
        )
        marker_id = "a" * 32
        title = Mock(side_effect=["", "posttrainllm-ready-" + marker_id])
        with (
            patch("terminal_record.os.write") as write,
            patch("terminal_record.uuid.uuid4", return_value=Mock(hex=marker_id)),
        ):
            episode = capture(
                self.recipe, Mock(), Mock(), snapshot, 42, "trusted-image", title
            )
        self.assertEqual(episode["initial_screen"], self.ready)
        self.assertEqual(
            episode["frames"], [{"event": {"keys": [112]}, "screen": after_key}]
        )
        self.assertEqual(write.call_count, 2)
        self.assertTrue(write.call_args_list[0].args[1].startswith(b"stty "))
        self.assertIn(marker_id.encode(), write.call_args_list[0].args[1])
        self.assertEqual(write.call_args_list[1].args[1], b"p")

    def test_timeout_leaves_user_keys_unsent(self):
        with (
            patch("terminal_record.time.monotonic", side_effect=[0, 0, 0, 0, 11]),
            patch("terminal_record.os.write") as write,
        ):
            snapshot = Mock(return_value=self.ready)
            with self.assertRaisesRegex(RuntimeError, "ready prompt"):
                capture(
                    self.recipe,
                    Mock(),
                    Mock(),
                    snapshot,
                    42,
                    "trusted-image",
                    lambda: "",
                )
        write.assert_called_once()
        self.assertTrue(write.call_args.args[1].startswith(b"stty "))
