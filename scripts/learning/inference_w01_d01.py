"""Week 1 Day 1 learner starter: embedding and output scores.

Complete evaluate before running this file. The teaching contract and answer
guide are in /learn/session?route=inference-systems-13w&session=inference-w01-d01.
This uses small random CPU tensors, without attention, training, or downloads.
"""

import torch
from torch import nn

torch.manual_seed(0)
B, T, V, D = 2, 4, 32, 8
ids = torch.tensor([[2, 5, 2, 9], [3, 5, 3, 8]], dtype=torch.long)
embedding = nn.Embedding(V, D, dtype=torch.float32)
output_head = nn.Linear(D, V, bias=False, dtype=torch.float32)


@torch.inference_mode()
def evaluate(inputs: torch.Tensor):
    # TODO: lookup -> logits -> last-position softmax -> argmax.
    # Return x, logits, probabilities, next_ids in that order.
    raise NotImplementedError("Complete the four-step forward calculation")


if __name__ == "__main__":
    results = evaluate(ids)
    for name, tensor in zip(["x", "logits", "probabilities", "next_ids"], results):
        print(name, tuple(tensor.shape))
