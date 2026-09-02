#!/usr/bin/env python3
"""Focused checks for the paired ASR decision gate."""

from __future__ import annotations

import unittest

from compare_asr import compare


def scored(wer: float, rtfx: float, repetitions: int, nouns: float) -> dict:
    return {
        "summary": {
            "wer": wer,
            "median_realtime_factor": rtfx,
            "hypothesis_repetition_events": repetitions,
            "proper_noun_accuracy": nouns,
        }
    }


class CompareAsrTests(unittest.TestCase):
    def test_promotes_only_when_every_gate_passes(self) -> None:
        result = compare(
            scored(0.05, 20, 1, 0.5),
            scored(0.06, 60, 1, 0.75),
            {"external_warm_requests": [], "model_download_bytes": 10, "adapter": {}},
        )
        self.assertEqual(result["decision"], "promote")
        self.assertAlmostEqual(result["gates"]["wer_delta_points"]["value"], 1)

    def test_rejects_a_fast_but_inaccurate_candidate(self) -> None:
        result = compare(
            scored(0.05, 20, 0, 1),
            scored(0.08, 100, 0, 1),
            {"external_warm_requests": [], "model_download_bytes": 10, "adapter": {}},
        )
        self.assertEqual(result["decision"], "reject")


if __name__ == "__main__":
    unittest.main()
