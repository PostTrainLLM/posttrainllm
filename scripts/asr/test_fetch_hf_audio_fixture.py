#!/usr/bin/env python3
"""Focused checks for frozen ASR fixture validation."""

from __future__ import annotations

import unittest

from fetch_hf_audio_fixture import validate_fixture


def fixture(digest: str | None = "a" * 64) -> dict:
    return {
        "source": {"total_audio_bytes": 10, "total_audio_seconds": 1.5},
        "items": [
            {
                "id": "sample",
                "row_index": 1,
                "audio_bytes": 10,
                "audio_seconds": 1.5,
                "audio_sha256": digest,
            }
        ],
    }


class FixtureValidationTests(unittest.TestCase):
    def test_frozen_fixture_passes(self) -> None:
        validate_fixture(fixture())

    def test_unpinned_fixture_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "audio_sha256 is not frozen"):
            validate_fixture(fixture(None))

    def test_unpinned_bootstrap_requires_explicit_override(self) -> None:
        validate_fixture(fixture(None), allow_unpinned=True)

    def test_metadata_drift_fails(self) -> None:
        candidate = fixture()
        candidate["source"]["total_audio_bytes"] = 11
        with self.assertRaisesRegex(ValueError, "byte total"):
            validate_fixture(candidate)


if __name__ == "__main__":
    unittest.main()
