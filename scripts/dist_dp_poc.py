"""Distributed-boundary PoC — data parallelism on one Mac via mlx.distributed.

The point: learn the core distributed primitive (gradient all-reduce) hands-on, without a cluster.
N processes each train the SAME model on DIFFERENT data shards; after each step we average the
gradients across ranks with `all_sum` — so every replica takes the identical update and the models
stay bit-identical (that's data parallelism). We prove it by checksumming the params per rank at the
end: all ranks must match.

Run:
  mlx.launch -n 1 scripts/dist_dp_poc.py     # baseline (1 process)
  mlx.launch -n 2 scripts/dist_dp_poc.py     # 2-way data parallel on this Mac
  mlx.launch -n 4 scripts/dist_dp_poc.py     # 4-way

What to observe:
  - loss falls the same (synced) on every rank;
  - final per-rank param checksums are IDENTICAL (all-reduce kept replicas in lockstep);
  - effective batch = per-rank batch * world size (the DP scaling knob).
The *concepts* (all-reduce, sharded data, lockstep replicas, comm/compute overlap) are exactly the
cluster ones; only the scale needs real hardware. Next rung = toy ZeRO (shard optimizer state with
sum_scatter + re-gather with all_gather) — see the TODO at the bottom.
"""
import time
import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
from mlx.utils import tree_map, tree_flatten

world = mx.distributed.init()
rank, size = world.rank(), world.size()

class MLP(nn.Module):
    def __init__(self):
        super().__init__()
        self.l1 = nn.Linear(32, 64); self.l2 = nn.Linear(64, 1)
    def __call__(self, x):
        return self.l2(nn.relu(self.l1(x)))

model = MLP()
mx.eval(model.parameters())

def shard(step, n=64):  # each rank sees a DIFFERENT slice of the data stream
    key = mx.random.key(rank * 100003 + step)
    x = mx.random.normal((n, 32), key=key)
    y = x.sum(axis=1, keepdims=True) * 0.1          # target: y = 0.1 * sum(x)
    return x, y

def loss_fn(m, x, y):
    return ((m(x) - y) ** 2).mean()

opt = optim.Adam(learning_rate=1e-2)
lvg = nn.value_and_grad(model, loss_fn)

t0 = time.time()
for step in range(200):
    x, y = shard(step)
    loss, grads = lvg(model, x, y)
    # THE distributed primitive: average gradients across all ranks (all-reduce / all_sum).
    if size > 1:
        grads = tree_map(lambda g: mx.distributed.all_sum(g) / size, grads)
    opt.update(model, grads)
    mx.eval(model.parameters(), opt.state)
    if step % 50 == 0 and rank == 0:
        print(f"[rank {rank}/{size}] step {step}  loss {loss.item():.5f}", flush=True)

# Prove replicas stayed in lockstep: every rank's param checksum must be identical.
chk = sum(float(p.sum().item()) for _, p in tree_flatten(model.parameters()))
print(f"[rank {rank}/{size}] final loss {loss.item():.5f}  param_checksum {chk:.6f}  "
      f"({time.time()-t0:.1f}s, effective_batch={64*size})", flush=True)

# TODO (toy ZeRO-1): instead of all_sum'ing full grads, sum_scatter so each rank owns a shard of
# the optimizer state, step locally, then all_gather the updated params. Same math, less memory/rank.
