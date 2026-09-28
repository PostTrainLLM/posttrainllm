"""Single-pass CPU evidence for the Q4 inference curriculum Week 1.

Uses the unchanged Python reference from python_ref/model.py. This is a
correctness and shape exercise, not a throughput benchmark or mastery grader.
See docs/learn/inference-systems-13w.md for the learner's prediction and
explanation requirements.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python_ref"))

import torch  # noqa: E402

from model import ModelConfig, posttrainllm  # noqa: E402


def main() -> None:
    torch.set_num_threads(1)
    torch.manual_seed(2026)
    cfg = ModelConfig.from_json(REPO / "configs/model.byte-tinygpt-v0.json")
    model = posttrainllm(cfg).cpu().eval()
    original = torch.tensor([[10, 20, 30, 40]], dtype=torch.long)
    changed_earlier = original.clone()
    changed_earlier[0, 0] = 11
    changed_future = original.clone()
    changed_future[0, -1] = 41

    with torch.inference_mode():
        token_vectors = model.token_embedding(original)
        start = perf_counter()
        logits, _ = model(original)
        elapsed_ms = (perf_counter() - start) * 1000
        earlier_logits, _ = model(changed_earlier)
        future_logits, _ = model(changed_future)

    prefix_difference = (logits[:, :-1] - future_logits[:, :-1]).abs().max().item()
    last_difference = (logits[:, -1] - earlier_logits[:, -1]).abs().max().item()
    assert tuple(token_vectors.shape) == (1, 4, cfg.d_model)
    assert tuple(logits.shape) == (1, 4, cfg.vocab_size)
    assert torch.allclose(logits[:, :-1], future_logits[:, :-1], atol=1e-6)
    assert last_difference > 0

    print(
        json.dumps(
            {
                "kind": "week1-single-pass-correctness-smoke",
                "config": "configs/model.byte-tinygpt-v0.json",
                "device": "cpu",
                "torch_version": torch.__version__,
                "input_shape": list(original.shape),
                "embedding_shape": list(token_vectors.shape),
                "logits_shape": list(logits.shape),
                "parameters": model.num_params(),
                "one_forward_ms_unstable": round(elapsed_ms, 3),
                "future_token_prefix_max_delta": prefix_difference,
                "earlier_token_last_max_delta": last_difference,
                "checks": "passed",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
