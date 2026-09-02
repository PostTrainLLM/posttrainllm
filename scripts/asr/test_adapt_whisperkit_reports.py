#!/usr/bin/env python3
"""Focused checks for the WhisperKit report adapter."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapt_whisperkit_reports import adapt


class WhisperKitAdapterTests(unittest.TestCase):
    def test_adapts_text_and_pipeline_timing(self) -> None:
        fixture = {
            "fixture_id": "fixture",
            "items": [{"id": "clip", "audio_seconds": 2.5}],
        }
        receipt = {
            "model_id": "whisperkit",
            "model_revision": "revision",
            "execution_seed": 1,
            "execution_order": ["clip"],
        }
        with tempfile.TemporaryDirectory() as directory:
            report_dir = Path(directory)
            (report_dir / "clip.json").write_text(
                json.dumps(
                    {
                        "text": "hello",
                        "timings": {
                            "inputAudioSeconds": 2.5,
                            "fullPipeline": 0.25,
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = adapt(fixture, receipt, report_dir)
        self.assertEqual(result["transcripts"][0]["text"], "hello")
        self.assertEqual(result["transcripts"][0]["decode_ms"], 250)


if __name__ == "__main__":
    unittest.main()
