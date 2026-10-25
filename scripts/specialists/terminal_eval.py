"""Frozen terminal ceiling and closed-loop screen/memory evaluation.

Real oracle screens are labels, never model inputs after the initial frame.
Contract: docs/factory/specialist-labs.md.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

from common import ROOT, digest, file_hash, frontier_answers, write_json
from terminal_codec import Screen
from terminal_model import Session
from terminal_data import heldout_identities, public_conditions


def ceiling(episodes, out):
    sys.path.insert(0, str(ROOT))
    from scripts.factory.frontier_cli import answer_schema

    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    request = [
        {
            "id": ep["id"],
            "initial_screen": ep["initial_screen"],
            "events": [frame["event"] for frame in ep["frames"]],
            "world_conditions": public_conditions(ep),
        }
        for ep in episodes
    ]
    write_json(out / "request.json", request)
    schema = out / "schema.json"
    write_json(schema, answer_schema())
    prompt = (
        "Predict the monochrome terminal after every event, including raw key bytes and waits. "
        "Return each episode's answer as a JSON string containing an array of screen objects "
        "with lines (fixed-width printable ASCII including spaces), cursor_row, cursor_col, visible. "
        "Use the explicit public world conditions and ordinary program semantics. "
        "Do not execute commands or use tools.\n" + json.dumps(request)
    )
    started = time.monotonic()
    answers, kinds = frontier_answers(schema, out, prompt)
    mapping = {row["id"]: row["answer"] for row in answers}
    valid = len(mapping) == len(answers) == len(episodes)
    for episode in episodes:
        try:
            predicted = json.loads(mapping[episode["id"]])
            valid &= len(predicted) == len(episode["frames"])
            valid &= all(
                Screen.from_dict(a) == Screen.from_dict(b["screen"])
                for a, b in zip(predicted, episode["frames"])
            )
        except (ValueError, KeyError, TypeError):
            valid = False
    write_json(
        out / "ceiling.json",
        {
            "schema": "terminal-ceiling-v1",
            "valid": bool(valid),
            "data_sha256": digest(episodes),
            "validator_sha256": file_hash(__file__),
            "answers_sha256": file_hash(out / "answers.json"),
            "model": "gpt-6.1-sol",
            "observed_item_types": kinds,
            "elapsed_seconds": time.monotonic() - started,
            "paid_usd": 0,
        },
    )
    if not valid:
        raise ValueError(
            "frontier terminal ceiling failed; fix/drop this ruler before local accuracy"
        )


def validate_ceiling(episodes, receipt):
    if (
        receipt.get("schema") != "terminal-ceiling-v1"
        or not receipt.get("valid")
        or receipt.get("data_sha256") != digest(episodes)
        or receipt.get("validator_sha256") != file_hash(__file__)
    ):
        raise ValueError("missing, failed, stale or mismatched terminal ceiling")


def evaluate(model, episodes, receipt, budget, parallel=False):
    validate_ceiling(episodes, receipt)
    identities = heldout_identities(model, episodes)
    exact, cursors, cells, total_cells, tokens = 0, 0, 0, 0, 0
    latencies, memory = [], []
    worlds = []
    families = {}
    for episode in episodes:
        session = Session(model, Screen.from_dict(episode["initial_screen"]))
        probes = []
        world_exact = True
        probe_resets = []
        for frame in episode["frames"]:
            budget.check()
            started = time.monotonic()
            result = session.step(frame["event"], budget, parallel)
            latencies.append(time.monotonic() - started)
            predicted, gold = session.screen, Screen.from_dict(frame["screen"])
            exact += predicted == gold
            world_exact &= predicted == gold
            cursors += (
                predicted.cursor_row,
                predicted.cursor_col,
                predicted.visible,
            ) == (gold.cursor_row, gold.cursor_col, gold.visible)
            cells += sum(
                a == b
                for x, y in zip(predicted.lines, gold.lines)
                for a, b in zip(x, y)
            )
            total_cells += gold.rows * gold.cols
            tokens += len(result["tokens"])
            if "memory_probe_expected" in frame:
                value = frame["memory_probe_expected"]
                # A readback must occupy a complete output line in the oracle;
                # merely echoing it within the typed command is insufficient.
                if value not in [line.strip() for line in gold.lines]:
                    raise ValueError("memory probe lacks an exact oracle output line")
                probes.append(value in [line.strip() for line in predicted.lines])
                probe_resets.append(session.context_resets)
        if probes:
            memory.append(all(probes))
        worlds.append(
            {
                "id": episode["id"],
                "context_resets": session.context_resets,
                "memory_probes": len(probes),
                "all_readbacks_exact": all(probes) if probes else None,
                "all_frames_exact": bool(world_exact),
                "family": episode.get("family", "unspecified"),
                "context_resets_at_probes": probe_resets,
            }
        )
        family = families.setdefault(
            episode.get("family", "unspecified"), {"passed": 0, "total": 0}
        )
        family["total"] += 1
        family["passed"] += int(world_exact and all(probes))
    if not latencies:
        raise ValueError("no terminal evaluation transitions")
    return {
        "kind": "closed-loop-terminal",
        "frames": len(latencies),
        "exact_screen_fraction": exact / len(latencies),
        "cursor_fraction": cursors / len(latencies),
        "cell_fraction": cells / total_cells,
        "memory_world_fraction": float(np.mean(memory)) if memory else None,
        "latency_p50_seconds": float(np.median(latencies)),
        "latency_p95_seconds": float(np.quantile(latencies, 0.95)),
        "generated_tokens_per_second": tokens / sum(latencies),
        "worlds": worlds,
        "complete_world_successes": sum(world["all_frames_exact"] for world in worlds),
        "complete_world_total": len(worlds),
        "families": families,
        "model_identity": getattr(model, "source_identity", None),
        "evaluation_episode_identities": identities,
        "decision": "report-only; no shell competence or parity claim without frozen gates",
        **budget.measurements(),
    }
