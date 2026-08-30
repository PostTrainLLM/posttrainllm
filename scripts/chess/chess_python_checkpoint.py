#!/usr/bin/env python3
"""Legal-candidate chess policy for a Python-reference byte-model checkpoint."""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from chess_sft_corpus import compact_prompt

REPO = Path(__file__).resolve().parents[2]
PYTHON_REF = REPO / "python_ref"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PythonCheckpointChessPolicy:
    """Score only legal UCI continuations under the owned causal byte model."""

    revision = "python-checkpoint-legal-candidate/v1"

    def __init__(
        self,
        checkpoint: str | Path,
        model_ref: str,
        policy_id: str,
        *,
        device: str = "auto",
        candidate_batch_size: int = 8,
    ):
        if candidate_batch_size < 1:
            raise ValueError("candidate_batch_size must be positive")
        checkpoint = Path(checkpoint)
        weights = checkpoint / "checkpoint.pt"
        if not weights.is_file():
            raise ValueError(f"Python reference checkpoint not found: {weights}")
        if str(PYTHON_REF) not in sys.path:
            sys.path.insert(0, str(PYTHON_REF))

        import torch
        from sample import load_model
        from train import pick_device

        resolved_device = pick_device(device)
        started = time.perf_counter_ns()
        self.model = load_model(checkpoint, device=resolved_device)
        self.model_load_time_ms = (time.perf_counter_ns() - started) / 1_000_000
        if self.model.cfg.vocab_size != 256:
            raise ValueError("Character Chess checkpoint must use the byte vocabulary")

        self._torch = torch
        self._device = resolved_device
        self.device = str(resolved_device)
        self.candidate_batch_size = candidate_batch_size
        self.checkpoint_sha256 = sha256_file(weights)
        self.model_ref = model_ref
        self.policy_id = policy_id
        self.last_scores: dict[str, float] = {}

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> str:
        if not legal_moves:
            raise ValueError("candidate received no legal moves")
        prompt = compact_prompt(state["fen"])
        prompt_ids = list(prompt.encode("utf-8"))
        candidates = sorted(set(legal_moves))
        scores: dict[str, float] = {}

        for start in range(0, len(candidates), self.candidate_batch_size):
            chunk = candidates[start : start + self.candidate_batch_size]
            suffixes = [list(f"{move}\n".encode("ascii")) for move in chunk]
            lengths = [len(prompt_ids) + len(suffix) for suffix in suffixes]
            if max(lengths) > self.model.cfg.context_length:
                raise ValueError("candidate sequence exceeds checkpoint context length")
            padded = [
                prompt_ids + suffix + [0] * (max(lengths) - len(prompt_ids) - len(suffix))
                for suffix in suffixes
            ]
            tokens = self._torch.tensor(padded, dtype=self._torch.long, device=self._device)
            with self._torch.inference_mode():
                logits, _ = self.model(tokens)
                log_probs = self._torch.log_softmax(logits, dim=-1)
            for row_index, (move, suffix) in enumerate(zip(chunk, suffixes, strict=True)):
                total = 0.0
                for suffix_index, target in enumerate(suffix):
                    prediction_index = len(prompt_ids) - 1 + suffix_index
                    total += float(log_probs[row_index, prediction_index, target].item())
                scores[move] = total

        self.last_scores = scores
        return max(candidates, key=lambda move: (scores[move], move))
