#!/usr/bin/env python3
"""Focused unit checks for the dependency-free ASR scorer."""

from __future__ import annotations

import unittest

from score_asr import edit_counts, normalize, repetition_events, score


class ScoreAsrTests(unittest.TestCase):
    def test_normalization_and_edit_counts(self) -> None:
        reference = normalize("Café, we're ready.")
        hypothesis = normalize("Cafe we are ready")
        self.assertEqual(reference, ["cafe", "we're", "ready"])
        self.assertEqual(
            edit_counts(reference, hypothesis),
            {"substitutions": 1, "deletions": 0, "insertions": 1},
        )

    def test_longest_adjacent_repetition_is_one_event(self) -> None:
        self.assertEqual(
            repetition_events(normalize("we are ready we are ready now")),
            [{"start": 0, "width": 3, "phrase": "we are ready"}],
        )

    def test_score_reports_wer_nouns_repetition_and_rtfx(self) -> None:
        fixture = {
            "fixture_id": "fixture",
            "normalization": "nfkd-casefold-english-alnum-apostrophe-v1",
            "items": [
                {
                    "id": "a",
                    "reference": "We are leaving on the Abraham Lincoln",
                    "proper_nouns": ["Abraham Lincoln"],
                }
            ],
        }
        prediction = {
            "model_id": "candidate",
            "model_revision": "revision",
            "transcripts": [
                {
                    "id": "a",
                    "text": "We are leaving leaving on the Abraham Lincoln",
                    "audio_seconds": 10,
                    "decode_ms": 200,
                }
            ],
        }
        summary = score(fixture, prediction)["summary"]
        self.assertEqual(summary["insertions"], 1)
        self.assertEqual(summary["proper_noun_accuracy"], 1)
        self.assertEqual(summary["repetition_regression"], 1)
        self.assertEqual(summary["realtime_factor"], 50)


if __name__ == "__main__":
    unittest.main()
