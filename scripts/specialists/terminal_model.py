"""Trainable terminal world-model reference and exact speculative verification.

Tiny random initialization establishes correctness, not WorldTUI quality. The
model has no filesystem or command dispatcher. Contract: docs/factory/specialist-labs.md.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import torch
from torch import nn

from common import ROOT, digest, file_hash, read_json, write_json
from terminal_codec import (
    CURSOR,
    OUTPUT,
    OUTPUT_END,
    PAD,
    ROW,
    ROW_END,
    Screen,
    allowed,
    apply_delta,
    delta,
    event_tokens,
    snapshot,
)
from terminal_data import identity


@dataclasses.dataclass
class ModelConfig:
    vocab_size: int
    context_length: int
    d_model: int
    n_heads: int
    n_layers: int
    d_mlp: int
    dropout: float


class TerminalModel(nn.Module):
    def __init__(self, config):
        super().__init__()
        if config.vocab_size != 333 or config.d_model % config.n_heads:
            raise ValueError("invalid terminal model config")
        self.config = config
        self.embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.position = nn.Embedding(config.context_length, config.d_model)
        layer = nn.TransformerEncoderLayer(
            config.d_model,
            config.n_heads,
            config.d_mlp,
            dropout=config.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            layer, config.n_layers, enable_nested_tensor=False
        )
        self.norm = nn.LayerNorm(config.d_model)
        self.head = nn.Linear(config.d_model, config.vocab_size, bias=False)
        self.head.weight = self.embedding.weight

    def forward(self, tokens, mask=None):
        length = tokens.shape[1]
        if length > self.config.context_length:
            raise ValueError("terminal history exceeds model context")
        positions = torch.arange(length, device=tokens.device)
        x = self.embedding(tokens) + self.position(positions)
        if mask is None:
            mask = torch.ones(
                length, length, dtype=torch.bool, device=tokens.device
            ).triu(1)
        x = self.transformer(x, mask=mask, is_causal=False)
        return self.head(self.norm(x))


def row_mask(tokens, output_start):
    """Rows attend history and their own prefix; final cursor sees every row."""
    length = len(tokens)
    mask = torch.ones(length, length, dtype=torch.bool).triu(1)
    start = output_start + 1
    for index in range(start, length):
        token = tokens[index]
        if ROW <= token < ROW + 64:
            start = index
        if token == CURSOR:
            break
        mask[index, output_start + 1 : start] = True
    return mask


def examples(episodes, max_context):
    output = []
    ids = set()
    for episode in episodes:
        if episode["id"] in ids:
            raise ValueError("duplicate terminal episode id")
        ids.add(episode["id"])
        screen = Screen.from_dict(episode["initial_screen"])
        history = snapshot(screen)
        for index, frame in enumerate(episode["frames"]):
            after = Screen.from_dict(frame["screen"])
            event = event_tokens(frame["event"])
            target = delta(screen, after)
            prefix = history + event
            if len(prefix) + len(target) > max_context:
                # A fresh visible snapshot is explicit context loss, not memory.
                prefix = snapshot(screen) + event
            if len(prefix) + len(target) > max_context:
                raise ValueError("screen/event cannot fit this model's context")
            output.append(
                {
                    "id": f"{episode['id']}:{index}",
                    "prefix": prefix,
                    "target": target,
                    "episode_identity": identity(episode),
                }
            )
            history = prefix + target
            screen = after
    if not output:
        raise ValueError("terminal training requires at least one transition")
    return output


def correction_examples(episodes, predictions, max_context, max_changed_cells=8):
    """On-policy screen → next oracle screen; prohibit unobserved word repairs."""
    by_id = {row["id"]: row for row in predictions}
    if len(by_id) != len(predictions):
        raise ValueError("duplicate correction predictions")
    result = []
    for episode in episodes:
        seen = "\n".join(episode["initial_screen"]["lines"])
        frames = episode["frames"]
        for index, frame in enumerate(frames[:-1]):
            seen += "\n" + bytes(frame["event"].get("keys", [])).decode(
                "ascii", errors="ignore"
            )
            previous_knowledge = seen
            seen += "\n" + "\n".join(frame["screen"]["lines"])
            prediction = by_id.get(f"{episode['id']}:{index}")
            if prediction is None:
                continue
            wrong = Screen.from_dict(prediction["screen"])
            real = Screen.from_dict(frame["screen"])
            if (wrong.rows, wrong.cols) != (real.rows, real.cols):
                raise ValueError("predicted screen size mismatch")
            cells = sum(
                a != b
                for left, right in zip(wrong.lines, real.lines)
                for a, b in zip(left, right)
            )
            if not 0 < cells <= max_changed_cells:
                continue
            following = frames[index + 1]
            next_screen = Screen.from_dict(following["screen"])
            # Check only repaired text from the erroneous frame, not legitimate
            # novel oracle output produced by the following user action.
            repaired_words = set(
                re.findall(r"[A-Za-z0-9_]+", "\n".join(real.lines))
            ) - set(re.findall(r"[A-Za-z0-9_]+", "\n".join(wrong.lines)))
            if not repaired_words.issubset(
                set(re.findall(r"[A-Za-z0-9_]+", previous_knowledge))
            ):
                continue
            prefix = snapshot(wrong) + event_tokens(following["event"])
            target = delta(wrong, next_screen)
            if len(prefix) + len(target) <= max_context:
                result.append(
                    {
                        "id": f"repair:{episode['id']}:{index}",
                        "prefix": prefix,
                        "target": target,
                        "episode_identity": identity(episode),
                    }
                )
    return result


def train(model, samples, out, steps, budget, learning_rate=1e-3):
    if not 1 <= steps <= 10000 or not samples:
        raise ValueError("need training samples and 1–10000 steps")
    if Path(out).exists():
        raise FileExistsError(out)
    budget.torch()
    torch.manual_seed(7)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    losses = []
    identities = {
        row["episode_identity"]["sha256"]: row["episode_identity"]
        for row in samples
        if "episode_identity" in row
    }
    sampled = {}
    model.train()
    for step in range(steps):
        budget.check()
        row = samples[step % len(samples)]
        episode = row.get("episode_identity")
        if episode:
            sampled[episode["sha256"]] = sampled.get(episode["sha256"], 0) + 1
        sequence = row["prefix"] + row["target"]
        tokens = torch.tensor([sequence[:-1]])
        target = torch.tensor([sequence[1:]])
        target[:, : len(row["prefix"]) - 1] = -100
        # Alternate ordinary causal and independent-row training. The verifier
        # always uses the ordinary causal distribution.
        mask = row_mask(sequence[:-1], len(row["prefix"])) if step % 2 else None
        optimizer.zero_grad()
        logits = model(tokens, mask)
        loss = nn.functional.cross_entropy(logits.reshape(-1, 333), target.reshape(-1))
        if not torch.isfinite(loss):
            raise ValueError("nonfinite terminal training loss")
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        losses.append(float(loss.detach()))
        budget.progress(step + 1, steps, losses[-1])
    model.eval()
    prior = getattr(model, "training_episode_identities", None)
    if prior is not None and all("episode_identity" in row for row in samples):
        identities.update({row["sha256"]: row for row in prior})
        training_identities = list(identities.values())
    else:
        training_identities = None
    save(
        model,
        out,
        {
            "steps": steps,
            "losses": losses,
            "data_sha256": digest(samples),
            "training_episode_identities": training_identities,
            "sampled_episode_steps": sampled,
            **budget.measurements(),
        },
    )
    model.training_episode_identities = training_identities
    model.source_identity = digest(
        {
            "weights": file_hash(Path(out) / "model.safetensors"),
            "config": file_hash(Path(out) / "config.json"),
        }
    )
    return losses


def save(model, out, metadata):
    from safetensors.torch import save_file

    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    # Tied head is reconstructed, so serialize each storage only once.
    state = {
        k: v.detach().contiguous()
        for k, v in model.state_dict().items()
        if k != "head.weight"
    }
    save_file(state, out / "model.safetensors")
    write_json(out / "config.json", dataclasses.asdict(model.config))
    write_json(
        out / "specialist.json",
        {
            "kind": "terminal",
            "codec": "posttrainllm-terminal-v1",
            "quality": "tiny-reference-unqualified",
            "weights_sha256": file_hash(out / "model.safetensors"),
            "config_sha256": file_hash(out / "config.json"),
            "worldtui_weights": False,
            **metadata,
        },
    )


def load(path):
    from safetensors.torch import load_file

    path = Path(path)
    metadata = read_json(path / "specialist.json")
    if metadata["weights_sha256"] != file_hash(path / "model.safetensors"):
        raise ValueError("terminal weights do not match the artifact identity")
    if metadata.get("config_sha256") != file_hash(path / "config.json"):
        raise ValueError("terminal config does not match the artifact identity")
    model = TerminalModel(ModelConfig(**read_json(path / "config.json")))
    state = load_file(path / "model.safetensors")
    state["head.weight"] = state["embedding.weight"]
    model.load_state_dict(state, strict=True)
    model.source_identity = digest(
        {"weights": metadata["weights_sha256"], "config": metadata["config_sha256"]}
    )
    model.training_episode_identities = metadata.get("training_episode_identities")
    return model.eval()


@torch.no_grad()
def next_logits(model, prefixes):
    length = max(map(len, prefixes))
    tokens = torch.full((len(prefixes), length), PAD, dtype=torch.long)
    for index, prefix in enumerate(prefixes):
        tokens[index, : len(prefix)] = torch.tensor(prefix)
    logits = model(tokens)
    return [logits[index, len(prefix) - 1] for index, prefix in enumerate(prefixes)]


def choose(logits, candidates):
    if not candidates:
        raise ValueError("no grammar continuation")
    values = logits[candidates]
    if not torch.isfinite(values).all():
        raise ValueError("nonfinite terminal logits")
    return candidates[int(values.argmax())]


def decode(model, prefix, screen, budget):
    model.eval()
    result = []
    while candidates := allowed(result, screen):
        budget.check()
        if len(prefix) + len(result) >= model.config.context_length:
            raise ValueError("context exhausted during a screen update")
        result.append(choose(next_logits(model, [prefix + result])[0], candidates))
    apply_delta(screen, result)
    return result


def parallel_draft(model, prefix, screen, budget):
    """One batch element per row, followed by a cursor conditioned on all rows."""
    rows = [[OUTPUT, ROW + index] for index in range(screen.rows)]
    active = list(range(screen.rows))
    while active:
        budget.check()
        logits = next_logits(model, [prefix + rows[index] for index in active])
        for index, values in zip(active, logits):
            rows[index].append(choose(values, allowed(rows[index], screen)))
        active = [index for index in active if rows[index][-1] != ROW_END]
    draft = [OUTPUT] + [token for row in rows for token in row[1:]] + [CURSOR]
    while draft[-1] != OUTPUT_END:
        budget.check()
        draft.append(
            choose(next_logits(model, [prefix + draft])[0], allowed(draft, screen))
        )
    return draft


@torch.no_grad()
def verify_draft(model, prefix, screen, draft, budget):
    """Exact greedy speculative verification, correcting the first disagreement.

    An entire remaining draft is checked in one causal forward. Only the logits
    before the first disagreement are valid; recompute after every correction.
    """
    result, verified, corrections = [], 0, 0
    while candidates := allowed(result, screen):
        budget.check()
        tail = draft[len(result) :] or [OUTPUT_END]
        room = model.config.context_length - len(prefix) - len(result)
        if room <= 0:
            raise ValueError("context exhausted during speculative verification")
        tail = tail[:room]
        logits = model(torch.tensor([prefix + result + tail[:-1]]))[0]
        start = len(prefix) + len(result) - 1
        for offset, proposed in enumerate(tail):
            candidates = allowed(result, screen)
            if not candidates:
                break
            token = choose(logits[start + offset], candidates)
            result.append(token)
            if token != proposed:
                corrections += 1
                break
            verified += 1
    apply_delta(screen, result)
    return result, {
        "accepted_draft_tokens": verified,
        "corrected_draft_tokens": corrections,
    }


class Session:
    def __init__(self, model, screen):
        self.model, self.screen = model, screen
        self.history = snapshot(screen)
        self.context_resets = 0

    def step(self, event, budget, parallel=False):
        prefix = self.history + event_tokens(event)
        # Reserve enough room for the grammar's largest possible complete frame.
        reserve = self.screen.rows * (self.screen.cols + 6) + 6
        if len(prefix) + reserve > self.model.config.context_length:
            prefix = snapshot(self.screen) + event_tokens(event)
            self.context_resets += 1
        if len(prefix) + reserve > self.model.config.context_length:
            raise ValueError("screen too large for this terminal model")
        stats = {}
        if parallel:
            draft = parallel_draft(self.model, prefix, self.screen, budget)
            tokens, stats = verify_draft(self.model, prefix, self.screen, draft, budget)
        else:
            tokens = decode(self.model, prefix, self.screen, budget)
        self.screen = apply_delta(self.screen, tokens)
        self.history = prefix + tokens
        return {
            "screen": self.screen.as_dict(),
            "tokens": tokens,
            "context_resets": self.context_resets,
            **stats,
        }


def new_model(config=None):
    torch.manual_seed(7)
    config = config or read_json(ROOT / "configs" / "model.terminal-tiny-v1.json")
    model = TerminalModel(ModelConfig(**config))
    model.training_episode_identities = []  # Explicit random, untrained baseline.
    model.source_identity = digest({"random_seed": 7, "config": config})
    return model
