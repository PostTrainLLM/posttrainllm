"""Deterministic no-model fixture for OffHours tests and report previews."""

from __future__ import annotations

import json
from typing import Any

import offhours_core as core
import offhours_store as store


class PerfectFixtureClient:
    """Return oracle-perfect structured outputs without loading a model."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages: list[dict[str, str]], seed: int) -> dict[str, Any]:
        del seed
        self.calls += 1
        prompt = messages[-1]["content"]
        if prompt.startswith("Process this expense claim."):
            claim = json.loads(prompt.splitlines()[1])
            output = core.grade_claim_input(claim)
        else:
            output = {
                "action": "reply_and_continue",
                "reply": "Acknowledged. I will continue the current batch.",
            }
        content = core.canonical_json(output)
        prompt_tokens = sum(len(message["content"].split()) + 4 for message in messages)
        return {
            "content": content,
            "latency_ms": 1.25,
            "context_tokens": prompt_tokens,
            "output_tokens": len(content.split()),
            "endpoint_model": "fixture-perfect",
            "system_fingerprint": "fixture-v1",
        }


def build_fixture_provenance(bundle: dict[str, Any]) -> dict[str, Any]:
    provenance = store.build_provenance(bundle)
    provenance["model"]["model"] = "fixture-perfect"
    provenance["model"]["model_file"] = {
        "path": None,
        "sha256": "f" * 64,
        "unavailable_reason": None,
    }
    provenance["model"]["quantization"] = "fixture-exact"
    provenance["model"]["quantization_unavailable_reason"] = None
    provenance["model"]["inference_server"] = {
        "name": "fixture-server",
        "version": "1.0",
        "version_unavailable_reason": None,
    }
    return provenance
