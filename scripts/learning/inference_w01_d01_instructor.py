"""Instructor-only correctness fixture for the Week 1 Day 1 learner starter.

Run one bounded CPU pass. This checks the toy's shape and dependency contract;
it is not learner evidence, a training run, or an inference benchmark.
"""

import torch
from torch import nn


def check_case(batch: int, length: int, vocab: int, width: int) -> None:
    torch.manual_seed(0)
    ids = torch.arange(batch * length, dtype=torch.long).reshape(batch, length) % vocab
    embedding = nn.Embedding(vocab, width, dtype=torch.float32)
    output_head = nn.Linear(width, vocab, bias=False, dtype=torch.float32)

    @torch.inference_mode()
    def evaluate(inputs: torch.Tensor):
        x = embedding(inputs)
        logits = output_head(x)
        probabilities = torch.softmax(logits[:, -1, :], dim=-1)
        next_ids = probabilities.argmax(dim=-1)
        return x, logits, probabilities, next_ids

    x, logits, probabilities, next_ids = evaluate(ids)
    assert tuple(x.shape) == (batch, length, width)
    assert tuple(logits.shape) == (batch, length, vocab)
    assert tuple(probabilities.shape) == (batch, vocab)
    assert tuple(next_ids.shape) == (batch,)
    assert x.dtype == torch.float32 and logits.dtype == torch.float32
    torch.testing.assert_close(
        probabilities.sum(dim=-1), torch.ones(batch), rtol=1e-6, atol=1e-7
    )
    assert bool(((next_ids >= 0) & (next_ids < vocab)).all())

    changed = ids.clone()
    changed[0, 0] = (int(changed[0, 0]) + 1) % vocab
    _, _, changed_probabilities, _ = evaluate(changed)
    torch.testing.assert_close(
        probabilities[0], changed_probabilities[0], rtol=1e-6, atol=1e-7
    )


if __name__ == "__main__":
    torch.set_num_threads(1)
    check_case(2, 4, 32, 8)
    check_case(1, 3, 16, 4)
    print("Day 1 instructor fixture: passed on CPU")
