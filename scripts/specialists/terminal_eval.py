"""Frozen terminal ceiling and closed-loop screen/memory evaluation.

Real oracle screens are labels, never model inputs after the initial frame.
Contract: docs/factory/specialist-labs.md.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from common import digest, file_hash, frontier_answers, write_json
from terminal_codec import Screen
from terminal_data import heldout_identities, public_conditions

MAX_CEILING_SCREEN_CELLS = 50_000
MAX_CEILING_TOTAL_SCREEN_CELLS = 100_000
TERMINAL_CEILING_SCHEMA = "terminal-ceiling-v2"


def ceiling_request(episodes):
    """Return only public inputs; oracle frames remain local labels."""
    if not episodes:
        raise ValueError("terminal ceiling requires at least one episode")
    ids = [episode.get("id") for episode in episodes]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids):
        raise ValueError("terminal ceiling episodes need non-empty IDs")
    if len(set(ids)) != len(ids):
        raise ValueError("terminal ceiling episode IDs must be unique")
    request = []
    screen_cells = 0
    for episode in episodes:
        initial = Screen.from_dict(episode["initial_screen"])
        events = [frame["event"] for frame in episode["frames"]]
        if not events:
            raise ValueError("terminal ceiling requires at least one event per episode")
        conditions = public_conditions(episode)
        source = episode.get("source", {})
        sampling_policy = source.get("timing") if isinstance(source, dict) else None
        if not isinstance(sampling_policy, str) or not sampling_policy:
            raise ValueError("terminal ceiling needs an explicit sampling policy")
        item = {
            "id": episode["id"],
            "initial_screen": initial.as_dict(),
            "events": events,
            "world_conditions": conditions,
            "screen_contract": {
                "rows": initial.rows,
                "cols": initial.cols,
                "screens_after_events": len(events),
            },
        }
        item["sampling_policy"] = sampling_policy
        screen_cells += len(events) * initial.rows * initial.cols
        request.append(item)
    return request


def ceiling_request_chunks(request):
    """Group whole episodes into bounded requests without splitting stateful worlds."""
    chunks = []
    current = []
    current_cells = 0
    for item in request:
        contract = item["screen_contract"]
        cells = contract["rows"] * contract["cols"] * contract["screens_after_events"]
        if cells > MAX_CEILING_SCREEN_CELLS:
            raise ValueError(
                "one terminal episode exceeds the 50000 screen-cell request budget"
            )
        if current and current_cells + cells > MAX_CEILING_SCREEN_CELLS:
            chunks.append(current)
            current, current_cells = [], 0
        current.append(item)
        current_cells += cells
    if current:
        chunks.append(current)
    return chunks


def terminal_answer_schema(episodes):
    """Structured final screens; never put a JSON payload inside a string."""
    screen = {
        "type": "object",
        "properties": {
            "lines": {"type": "array", "items": {"type": "string"}},
            "cursor_row": {"type": "integer"},
            "cursor_col": {"type": "integer"},
            "visible": {"type": "boolean"},
        },
        "required": ["lines", "cursor_row", "cursor_col", "visible"],
        "additionalProperties": False,
    }
    answer = {
        "type": "object",
        "properties": {
            "id": {"type": "string", "enum": [episode["id"] for episode in episodes]},
            "screens": {"type": "array", "items": screen},
        },
        "required": ["id", "screens"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"answers": {"type": "array", "items": answer}},
        "required": ["answers"],
        "additionalProperties": False,
    }


def _answers_have_unique_episode_ids(episodes, answers):
    if not isinstance(answers, list) or len(answers) != len(episodes):
        return False
    if any(not isinstance(answer, dict) for answer in answers):
        return False
    ids = [answer.get("id") for answer in answers]
    expected_ids = [episode["id"] for episode in episodes]
    if (
        any(not isinstance(identifier, str) for identifier in ids)
        or len(set(ids)) != len(ids)
        or set(ids) != set(expected_ids)
        or any(set(answer) != {"id", "screens"} for answer in answers)
    ):
        return False
    return True


def _screen_matches(initial, predicted, frame):
    if not isinstance(predicted, dict) or set(predicted) != {
        "lines",
        "cursor_row",
        "cursor_col",
        "visible",
    }:
        return False
    try:
        predicted_screen = Screen.from_dict(predicted)
        oracle_screen = Screen.from_dict(frame["screen"])
    except (IndexError, KeyError, TypeError, ValueError):
        return False
    return (predicted_screen.rows, predicted_screen.cols) == (
        initial.rows,
        initial.cols,
    ) and predicted_screen == oracle_screen


def _episode_screens_match(episode, screens):
    frames = episode["frames"]
    if not isinstance(screens, list) or len(screens) != len(frames):
        return False
    initial = Screen.from_dict(episode["initial_screen"])
    for predicted, frame in zip(screens, frames):
        if not _screen_matches(initial, predicted, frame):
            return False
    return True


def terminal_answers_match(episodes, answers):
    """Require exact IDs, frame counts, dimensions and screen states."""
    if not _answers_have_unique_episode_ids(episodes, answers):
        return False
    by_id = {answer["id"]: answer for answer in answers}
    return all(
        _episode_screens_match(episode, by_id[episode["id"]]["screens"])
        for episode in episodes
    )


def ceiling(episodes, out):
    request = ceiling_request(episodes)
    chunks = ceiling_request_chunks(request)
    screen_cells = sum(
        len(episode["frames"])
        * len(episode["initial_screen"]["lines"])
        * len(episode["initial_screen"]["lines"][0])
        for episode in episodes
    )
    if screen_cells > MAX_CEILING_TOTAL_SCREEN_CELLS:
        raise ValueError("terminal ceiling run exceeds the 100000 screen-cell budget")
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    write_json(out / "request.json", request)
    schema = out / "schema.json"
    write_json(schema, terminal_answer_schema(episodes))
    episodes_by_id = {episode["id"]: episode for episode in episodes}
    frame_count = sum(len(episode["frames"]) for episode in episodes)
    started = time.monotonic()
    answers = []
    observed_kinds = set()
    request_bytes = 0
    deadline = started + 180
    for index, chunk in enumerate(chunks):
        chunk_episodes = [episodes_by_id[item["id"]] for item in chunk]
        prompt_request = json.dumps(chunk, separators=(",", ":"))
        prompt = (
            "Simulate each episode using only its public initial screen, raw key/wait events, "
            "world conditions, and sampling policy. Return one structured screen object after "
            "every event, in order, with exactly the declared rows and columns; cursor coordinates "
            "are zero-based. A wait_ms event advances time and may change the screen. Do not use "
            "tools or execute input commands. Do not assume hidden files or state.\n"
            + prompt_request
        )
        chunk_out = out / f"chunk-{index:02d}"
        chunk_out.mkdir()
        chunk_schema = chunk_out / "schema.json"
        write_json(chunk_schema, terminal_answer_schema(chunk_episodes))
        timeout = max(1, int(deadline - time.monotonic()))
        chunk_answers, kinds = frontier_answers(
            chunk_schema, chunk_out, prompt, timeout=timeout
        )
        answers.extend(chunk_answers)
        observed_kinds.update(kinds)
        request_bytes += len(prompt_request.encode("utf-8"))
    write_json(out / "answers.json", {"answers": answers})
    valid = terminal_answers_match(episodes, answers)
    write_json(
        out / "ceiling.json",
        {
            "schema": TERMINAL_CEILING_SCHEMA,
            "valid": bool(valid),
            "data_sha256": digest(episodes),
            "request_sha256": digest(request),
            "validator_sha256": file_hash(__file__),
            "answers_sha256": file_hash(out / "answers.json"),
            "model": "gpt-6.1-sol",
            "observed_item_types": sorted(observed_kinds),
            "episode_count": len(episodes),
            "frame_count": frame_count,
            "screen_cell_count": screen_cells,
            "request_bytes": request_bytes,
            "chunk_count": len(chunks),
            "timeout_seconds": 180,
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
        not isinstance(receipt, dict)
        or receipt.get("schema") != TERMINAL_CEILING_SCHEMA
        or not receipt.get("valid")
    ):
        raise ValueError("missing, failed, stale or mismatched terminal ceiling")
    request = ceiling_request(episodes)
    if (
        receipt.get("data_sha256") != digest(episodes)
        or receipt.get("request_sha256") != digest(request)
        or receipt.get("validator_sha256") != file_hash(__file__)
    ):
        raise ValueError("missing, failed, stale or mismatched terminal ceiling")


def evaluate(model, episodes, receipt, budget, parallel=False):
    validate_ceiling(episodes, receipt)
    from terminal_model import Session

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
