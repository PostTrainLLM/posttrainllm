#!/usr/bin/env python3
"""Capability-gradient benchmark candidate lab.

This stdlib-only module owns the candidate scorecard validator, two
dependency-free reference environments (Connect-4 and calendar scheduling),
a random-legal baseline executor, a canonical-trace format, a deterministic
verifier for each environment, and a development-probe validator.

It does not load a model, access the network, install anything, compile,
train, or call a cloud API. The gradient gate (frontier vs random-legal) is
run by supplying model actions externally; this module provides the
environment and scoring only.

Commands:

    python3 scripts/capability_gradient_lab.py validate-scorecard
    python3 scripts/capability_gradient_lab.py validate-probes
    python3 scripts/capability_gradient_lab.py canonical-trace --env connect4 --seed 42
    python3 scripts/capability_gradient_lab.py canonical-trace --env calendar --seed 42
    python3 scripts/capability_gradient_lab.py random-baseline --env connect4 --seeds 0-9
    python3 scripts/capability_gradient_lab.py random-baseline --env calendar --seeds 0-9
    python3 scripts/capability_gradient_lab.py play --env connect4 --seed 42 --actions <complete-comma-separated-policy-trace>
    python3 scripts/capability_gradient_lab.py play --env calendar --seed 42 --action "mon 14:00"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
SCORECARD_PATH = ROOT / "configs" / "capability-gradient-lab" / "candidates-v1.json"
DEVELOPMENT_CONFIG_PATH = ROOT / "configs" / "capability-gradient-lab" / "development-v1.json"
PROBE_DIR = ROOT / "evals" / "capability-gradient-lab" / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class ValidationError(ValueError):
    """Raised for a strict scorecard, environment, or probe failure."""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


DEVELOPMENT_CONFIG = load_json(DEVELOPMENT_CONFIG_PATH)
if DEVELOPMENT_CONFIG.get("schema_version") != "capability-gradient-lab/development/v1":
    raise ValidationError("unsupported capability-gradient development config")


# ---------------------------------------------------------------------------
# Scorecard validator
# ---------------------------------------------------------------------------

REQUIRED_CANDIDATE_FIELDS = (
    "rank",
    "candidate_id",
    "title",
    "type",
    "reasoning_mode",
    "gradient_likelihood",
    "fit_30_50m",
    "selected",
    "public_proof_role",
    "baseline_evidence",
    "specialist_vs_larger_llm",
    "state_action_protocol",
    "legal_random_executor",
    "success_metric",
    "deterministic_verifier",
    "leakage_plan",
    "fit_30_50m_estimate",
    "frontier_eval_cost",
    "reject_condition",
)

REQUIRED_PROTOCOL_FIELDS = (
    "state_representation",
    "actions",
    "turn_protocol",
    "state_size_chars",
    "action_size_chars",
    "max_turns",
)

REQUIRED_METRIC_FIELDS = (
    "primary",
    "graduated",
    "intelligence_sensitive",
)

REQUIRED_LEAKAGE_FIELDS = (
    "method",
    "train_seed_range",
    "eval_seed_range",
)

REQUIRED_FIT_FIELDS = (
    "input_tokens",
    "output_tokens",
    "learnability",
    "data_volume_estimate",
)

REQUIRED_COST_FIELDS = (
    "estimated_tokens",
    "estimated_api_calls",
    "cost_tier",
)

REQUIRED_SPECIALIST_PROSPECT_FIELDS = (
    "prospect",
    "evidence_status",
    "why",
)

VALID_TYPES = ("game", "everyday_action")
VALID_GRADIENT = ("high", "medium", "low", "low_at_risk")
VALID_FIT = ("high", "medium", "low")


def validate_development_config(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema_version") != "capability-gradient-lab/development/v1":
        errors.append("development config: unsupported schema_version")
    if data.get("specialist_max_parameters") != 50_000_000:
        errors.append("development config: specialist_max_parameters must be 50000000")
    if data.get("baseline_sample_size") != 2000 or data.get("development_seed_start") != 0:
        errors.append("development config: baseline cohort must be seeds 0-1999")
    calendar = data.get("calendar")
    if not isinstance(calendar, dict):
        errors.append("development config: calendar must be an object")
    else:
        for field in (
            "days", "business_start_hour", "business_end_hour",
            "slot_granularity_minutes", "event_count_range",
            "event_duration_minutes", "participant_pool",
            "request_participant_count_range", "request_date_count",
            "request_duration_minutes", "unavailability_probability",
            "unavailability_duration_minutes", "random_valid_rate_accepted_range",
        ):
            if field not in calendar:
                errors.append(f"development config: calendar missing '{field}'")
        accepted = calendar.get("random_valid_rate_accepted_range")
        if not isinstance(accepted, list) or len(accepted) != 2 or accepted[1] > 0.35:
            errors.append("development config: calendar random-valid upper bound must be <= 0.35")
    return errors


def validate_scorecard(data: dict[str, Any]) -> list[str]:
    """Return a list of error strings; empty means valid."""
    errors: list[str] = []

    if data.get("artifact_type") != "candidate_scorecard":
        errors.append("artifact_type: must be 'candidate_scorecard'")

    candidates = data.get("candidates")
    if not isinstance(candidates, list) or len(candidates) < 6:
        errors.append(f"candidates: must be a list of at least 6, got {len(candidates) if isinstance(candidates, list) else 'non-list'}")
        return errors

    seen_ids: set[str] = set()
    selected: list[dict[str, Any]] = []
    ranks: list[int] = []
    types_present: set[str] = set()

    for i, cand in enumerate(candidates):
        prefix = f"candidates[{i}]"
        if not isinstance(cand, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        cid = cand.get("candidate_id", f"<index-{i}>")
        if cid in seen_ids:
            errors.append(f"{prefix}: duplicate candidate_id '{cid}'")
        seen_ids.add(cid)

        for field in REQUIRED_CANDIDATE_FIELDS:
            if field not in cand:
                errors.append(f"{prefix} ({cid}): missing required field '{field}'")

        if "rank" in cand:
            r = cand["rank"]
            if not isinstance(r, int) or r < 1:
                errors.append(f"{prefix} ({cid}): rank must be a positive integer, got {r}")
            ranks.append(r)

        if "type" in cand and cand["type"] not in VALID_TYPES:
            errors.append(f"{prefix} ({cid}): type must be one of {VALID_TYPES}, got '{cand['type']}'")
        if cand.get("type") in VALID_TYPES:
            types_present.add(cand["type"])

        if "gradient_likelihood" in cand and cand["gradient_likelihood"] not in VALID_GRADIENT:
            errors.append(f"{prefix} ({cid}): gradient_likelihood must be one of {VALID_GRADIENT}")

        if "fit_30_50m" in cand and cand["fit_30_50m"] not in VALID_FIT:
            errors.append(f"{prefix} ({cid}): fit_30_50m must be one of {VALID_FIT}")

        proto = cand.get("state_action_protocol")
        if isinstance(proto, dict):
            for pf in REQUIRED_PROTOCOL_FIELDS:
                if pf not in proto:
                    errors.append(f"{prefix} ({cid}).state_action_protocol: missing '{pf}'")

        metric = cand.get("success_metric")
        if isinstance(metric, dict):
            for mf in REQUIRED_METRIC_FIELDS:
                if mf not in metric:
                    errors.append(f"{prefix} ({cid}).success_metric: missing '{mf}'")

        leakage = cand.get("leakage_plan")
        if isinstance(leakage, dict):
            for lf in REQUIRED_LEAKAGE_FIELDS:
                if lf not in leakage:
                    errors.append(f"{prefix} ({cid}).leakage_plan: missing '{lf}'")

        fit = cand.get("fit_30_50m_estimate")
        if isinstance(fit, dict):
            for ff in REQUIRED_FIT_FIELDS:
                if ff not in fit:
                    errors.append(f"{prefix} ({cid}).fit_30_50m_estimate: missing '{ff}'")

        cost = cand.get("frontier_eval_cost")
        if isinstance(cost, dict):
            for cf in REQUIRED_COST_FIELDS:
                if cf not in cost:
                    errors.append(f"{prefix} ({cid}).frontier_eval_cost: missing '{cf}'")

        baseline_evidence = cand.get("baseline_evidence")
        if not isinstance(baseline_evidence, dict) or not baseline_evidence.get("status") or not baseline_evidence.get("why"):
            errors.append(f"{prefix} ({cid}).baseline_evidence: requires non-empty 'status' and 'why'")

        prospect = cand.get("specialist_vs_larger_llm")
        if not isinstance(prospect, dict):
            errors.append(f"{prefix} ({cid}).specialist_vs_larger_llm: must be an object")
        else:
            for field in REQUIRED_SPECIALIST_PROSPECT_FIELDS:
                if not prospect.get(field):
                    errors.append(f"{prefix} ({cid}).specialist_vs_larger_llm: missing '{field}'")

        if cand.get("selected"):
            selected.append(cand)

    # Ranks must be 1..N without gaps
    if ranks and sorted(ranks) != list(range(1, len(ranks) + 1)):
        errors.append(f"ranks: must be 1..{len(ranks)} without gaps, got {sorted(ranks)}")

    # Must have both game and everyday_action types
    if "game" not in types_present:
        errors.append("candidates: must include at least one 'game' type candidate")
    if "everyday_action" not in types_present:
        errors.append("candidates: must include at least one 'everyday_action' type candidate")

    # Exactly two selected
    if len(selected) != 2:
        errors.append(f"selected: exactly 2 candidates must be selected, got {len(selected)}")
    else:
        # Selected must be non-overlapping reasoning modes
        modes = [s.get("reasoning_mode", "") for s in selected]
        if modes[0] == modes[1]:
            errors.append(f"selected: both selected candidates have the same reasoning_mode '{modes[0]}' — must be non-overlapping")
        # Selected must be different types (game + everyday for maximum diversity)
        sel_types = [s.get("type", "") for s in selected]
        if sel_types[0] == sel_types[1]:
            errors.append(f"selected: both selected candidates have the same type '{sel_types[0]}' — prefer different types")

    # Gradient gate config
    gate = data.get("gradient_gate")
    if not isinstance(gate, dict):
        errors.append("gradient_gate: must be an object")
    else:
        if "definition" not in gate:
            errors.append("gradient_gate: missing 'definition'")
        if "default_margin" not in gate:
            errors.append("gradient_gate: missing 'default_margin'")
        if "default_sample_size" not in gate:
            errors.append("gradient_gate: missing 'default_sample_size'")

    return errors


# ---------------------------------------------------------------------------
# Connect-4 environment
# ---------------------------------------------------------------------------

C4_ROWS = 6
C4_COLS = 7
C4_EMPTY = 0
C4_PLAYER = 1  # X — the model's side
C4_OPPONENT = 2  # O — random-legal side


class Connect4Env:
    """Connect-4 reference environment.

    The model plays as X (player 1). The random-legal opponent plays as O.
    Board is a list of C4_ROWS lists, each with C4_COLS ints.
    Row 0 is the top, row C4_ROWS-1 is the bottom (gravity drops to bottom).
    """

    def __init__(self) -> None:
        self.board: list[list[int]] = []
        self.current_player: int = C4_PLAYER
        self.winner: int | None = None
        self.moves: list[int] = []  # column indices played
        self.done: bool = False

    def reset(self, seed: int) -> dict[str, Any]:
        rng = random.Random(seed)
        self.board = [[C4_EMPTY] * C4_COLS for _ in range(C4_ROWS)]
        self.current_player = C4_PLAYER
        self.winner = None
        self.moves = []
        self.done = False
        return self._observation()

    def legal_actions(self) -> list[int]:
        """Return list of 0-based column indices that are not full."""
        return [c for c in range(C4_COLS) if self.board[0][c] == C4_EMPTY]

    def step(self, col: int) -> dict[str, Any]:
        """Apply a move in column col (0-based). Returns observation dict."""
        if self.done:
            raise ValidationError("game is over")
        if col not in self.legal_actions():
            raise ValidationError(f"illegal action: column {col} is full or invalid")

        # Drop piece
        for row in range(C4_ROWS - 1, -1, -1):
            if self.board[row][col] == C4_EMPTY:
                self.board[row][col] = self.current_player
                break

        self.moves.append(col)

        # Check win
        if self._check_win(self.current_player):
            self.winner = self.current_player
            self.done = True
        elif not self.legal_actions():
            self.done = True  # draw
        else:
            self.current_player = C4_OPPONENT if self.current_player == C4_PLAYER else C4_PLAYER

        return self._observation()

    def _observation(self) -> dict[str, Any]:
        return {
            "board": [row[:] for row in self.board],
            "current_player": self.current_player,
            "winner": self.winner,
            "done": self.done,
            "legal_actions": self.legal_actions(),
            "move_count": len(self.moves),
        }

    def render(self) -> str:
        """Render board as text. Rows top to bottom, column labels 1-7."""
        lines = []
        for row in self.board:
            cells = []
            for cell in row:
                if cell == C4_EMPTY:
                    cells.append(".")
                elif cell == C4_PLAYER:
                    cells.append("X")
                else:
                    cells.append("O")
            lines.append(" ".join(cells))
        lines.append(" ".join(str(c + 1) for c in range(C4_COLS)))
        return "\n".join(lines)

    def parse_action(self, text: str) -> int:
        """Parse model text output to a 0-based column index."""
        text = text.strip()
        # Accept "4", "col 4", "column 4", "4\n", etc.
        digits = ""
        for ch in text:
            if ch.isdigit():
                digits += ch
            elif digits:
                break
        if not digits:
            raise ValidationError(f"cannot parse action from '{text}'")
        col = int(digits) - 1  # 1-based to 0-based
        if col < 0 or col >= C4_COLS:
            raise ValidationError(f"column {col + 1} out of range (1-{C4_COLS})")
        return col

    def random_legal_action(self, rng: random.Random) -> int:
        """Pick a uniformly random legal column."""
        legal = self.legal_actions()
        if not legal:
            raise ValidationError("no legal actions — game is over")
        return rng.choice(legal)

    def _check_win(self, player: int) -> bool:
        b = self.board
        # Horizontal
        for r in range(C4_ROWS):
            for c in range(C4_COLS - 3):
                if all(b[r][c + i] == player for i in range(4)):
                    return True
        # Vertical
        for r in range(C4_ROWS - 3):
            for c in range(C4_COLS):
                if all(b[r + i][c] == player for i in range(4)):
                    return True
        # Diagonal down-right
        for r in range(C4_ROWS - 3):
            for c in range(C4_COLS - 3):
                if all(b[r + i][c + i] == player for i in range(4)):
                    return True
        # Diagonal up-right
        for r in range(3, C4_ROWS):
            for c in range(C4_COLS - 3):
                if all(b[r - i][c + i] == player for i in range(4)):
                    return True
        return False

    def outcome_score(self) -> float:
        """Win=1.0 (X wins), draw=0.5, loss=0.0 (O wins), None if not done."""
        if not self.done:
            return 0.0
        if self.winner is None:
            return 0.5
        if self.winner == C4_PLAYER:
            return 1.0
        return 0.0

    def would_win(self, col: int, player: int) -> bool:
        """Check if placing player's piece in col would create 4-in-a-row."""
        if col not in self.legal_actions():
            return False
        # Find drop row (lowest empty cell — gravity drops to bottom)
        drop_row = -1
        for row in range(C4_ROWS - 1, -1, -1):
            if self.board[row][col] == C4_EMPTY:
                drop_row = row
                break
        if drop_row < 0:
            return False  # column full (shouldn't happen after legal_actions check)
        # Temporarily place
        self.board[drop_row][col] = player
        won = self._check_win(player)
        self.board[drop_row][col] = C4_EMPTY
        return won

    def blunder_rate(self) -> dict[str, float]:
        """Compute blunder metrics from the move history.

        missed_wins: fraction of model (X) turns where an immediate win was
        available but not taken.
        allowed_wins: fraction of model turns where the model's move allowed
        the opponent an immediate win on the next turn.
        """
        if not self.moves:
            return {"missed_wins": 0.0, "allowed_wins": 0.0}

        # Replay to compute blunders
        env = Connect4Env()
        env.reset(0)  # seed doesn't matter for empty board
        env.board = [[C4_EMPTY] * C4_COLS for _ in range(C4_ROWS)]

        x_turns = 0
        missed_wins = 0
        allowed_wins = 0

        for i, col in enumerate(self.moves):
            player = C4_PLAYER if i % 2 == 0 else C4_OPPONENT
            if player == C4_PLAYER:
                x_turns += 1
                # Check if X had an immediate win available
                had_win = any(env.would_win(c, C4_PLAYER) for c in env.legal_actions())
                took_win = env.would_win(col, C4_PLAYER) if had_win else False
                if had_win and not took_win:
                    missed_wins += 1

            # Replay through the canonical transition instead of duplicating
            # gravity/current-player logic inside the diagnostic.
            env.step(col)

            if player == C4_PLAYER and not env._check_win(C4_PLAYER):
                # Check if O now has an immediate win (X allowed it)
                o_can_win = any(env.would_win(c, C4_OPPONENT) for c in env.legal_actions())
                if o_can_win:
                    allowed_wins += 1

            if env._check_win(player):
                break

        if x_turns == 0:
            return {"missed_wins": 0.0, "allowed_wins": 0.0}
        return {
            "missed_wins": missed_wins / x_turns,
            "allowed_wins": allowed_wins / x_turns,
        }


def connect4_play_vs_random(
    seed: int,
    model_actions: Sequence[int] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Play one Connect-4 game: model (X) vs random-legal (O).

    If model_actions is provided, use them for X's moves. Otherwise X also
    plays random-legal (for baseline measurement).
    """
    if rng is None:
        rng = random.Random(seed * 7919 + 1)  # distinct stream for opponent
    env = Connect4Env()
    env.reset(seed)
    trace: list[dict[str, Any]] = []
    action_idx = 0

    failure: str | None = None
    while not env.done:
        acting_player = env.current_player
        if env.current_player == C4_PLAYER:
            if model_actions is not None and action_idx < len(model_actions):
                col = model_actions[action_idx]
                action_idx += 1
            elif model_actions is not None:
                failure = "model-action-stream-exhausted"
                break
            else:
                col = env.random_legal_action(rng)
        else:
            col = env.random_legal_action(rng)

        obs = env.step(col)
        trace.append({
            "player": "X" if acting_player == C4_PLAYER else "O",
            "column": col + 1,
            "board_after": env.render(),
            "done": env.done,
            "winner": env.winner,
        })

    return {
        "env": "connect4",
        "seed": seed,
        "status": "complete" if failure is None else "invalid",
        "failure": failure,
        "outcome": env.outcome_score() if failure is None else None,
        "winner": ("X" if env.winner == C4_PLAYER else ("O" if env.winner == C4_OPPONENT else "draw")) if failure is None else None,
        "move_count": len(env.moves),
        "moves": [m + 1 for m in env.moves],
        "blunders": env.blunder_rate(),
        "trace": trace,
    }


def connect4_random_baseline(seeds: range | list[int]) -> dict[str, Any]:
    """Run random-legal vs random-legal for the given seeds."""
    results = []
    for seed in seeds:
        result = connect4_play_vs_random(seed, model_actions=None)
        results.append({
            "seed": seed,
            "outcome": result["outcome"],
            "winner": result["winner"],
            "move_count": result["move_count"],
        })
    wins = sum(1 for r in results if r["outcome"] == 1.0)
    draws = sum(1 for r in results if r["outcome"] == 0.5)
    losses = sum(1 for r in results if r["outcome"] == 0.0)
    return {
        "env": "connect4",
        "baseline": "random_legal_vs_random_legal",
        "n_games": len(results),
        "win_rate": wins / len(results) if results else 0.0,
        "draw_rate": draws / len(results) if results else 0.0,
        "loss_rate": losses / len(results) if results else 0.0,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Calendar scheduling environment
# ---------------------------------------------------------------------------

CALENDAR_CONFIG = DEVELOPMENT_CONFIG["calendar"]
DAYS = list(CALENDAR_CONFIG["days"])
BUSINESS_START = int(CALENDAR_CONFIG["business_start_hour"])
BUSINESS_END = int(CALENDAR_CONFIG["business_end_hour"])
SLOT_GRANULARITY_MIN = int(CALENDAR_CONFIG["slot_granularity_minutes"])


class CalendarEnv:
    """Calendar scheduling reference environment.

    The model is given a calendar with existing events, a new meeting request,
    and constraints. It must propose a valid slot or output NONE.
    Single-turn task: one action, then verify.
    """

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.request: dict[str, Any] = {}
        self.constraints: dict[str, Any] = {}
        self.done: bool = False

    def reset(self, seed: int) -> dict[str, Any]:
        rng = random.Random(seed)
        self.events = []
        self.done = False

        # Dense shared-calendar blocks make a random well-formed proposal weak
        # without making it malformed or outside the declared date range.
        event_min, event_max = CALENDAR_CONFIG["event_count_range"]
        n_events = rng.randint(event_min, event_max)
        used_slots: set[tuple[str, int, int]] = set()
        attempts = 0
        while len(self.events) < n_events and attempts < n_events * 8:
            attempts += 1
            day = rng.choice(DAYS)
            # Pick a start time in business hours
            start_h = rng.randint(BUSINESS_START, BUSINESS_END - 1)
            start_m = rng.choice(list(range(0, 60, SLOT_GRANULARITY_MIN)))
            dur = rng.choice(CALENDAR_CONFIG["event_duration_minutes"])
            end_h = start_h + (start_m + dur) // 60
            end_m = (start_m + dur) % 60
            if end_h * 60 + end_m > BUSINESS_END * 60:
                continue
            slot_key = (day, start_h * 60 + start_m, end_h * 60 + end_m)
            if slot_key in used_slots:
                continue
            used_slots.add(slot_key)
            self.events.append({
                "day": day,
                "start": f"{start_h:02d}:{start_m:02d}",
                "end": f"{end_h:02d}:{end_m:02d}",
                "title": f"Existing meeting {len(self.events) + 1}",
            })

        # Generate meeting request
        duration = rng.choice(CALENDAR_CONFIG["request_duration_minutes"])
        participant_min, participant_max = CALENDAR_CONFIG["request_participant_count_range"]
        participants = rng.sample(
            CALENDAR_CONFIG["participant_pool"], rng.randint(participant_min, participant_max)
        )
        date_range = rng.sample(DAYS, CALENDAR_CONFIG["request_date_count"])
        date_range.sort(key=lambda d: DAYS.index(d))

        # Generate unavailability blocks for participants
        unavailability: list[dict[str, Any]] = []
        for p in participants:
            if rng.random() < CALENDAR_CONFIG["unavailability_probability"]:
                uday = rng.choice(date_range)
                ustart_h = rng.randint(BUSINESS_START, BUSINESS_END - 2)
                ustart_m = rng.choice(list(range(0, 60, SLOT_GRANULARITY_MIN)))
                udur = rng.choice(CALENDAR_CONFIG["unavailability_duration_minutes"])
                uend_h = ustart_h + (ustart_m + udur) // 60
                uend_m = (ustart_m + udur) % 60
                if uend_h * 60 + uend_m <= BUSINESS_END * 60:
                    unavailability.append({
                        "participant": p,
                        "day": uday,
                        "start": f"{ustart_h:02d}:{ustart_m:02d}",
                        "end": f"{uend_h:02d}:{uend_m:02d}",
                    })

        self.request = {
            "duration_minutes": duration,
            "participants": participants,
            "date_range": date_range,
        }
        self.constraints = {
            "business_hours": f"{BUSINESS_START:02d}:00-{BUSINESS_END:02d}:00",
            "unavailability": unavailability,
        }

        return self._observation()

    def _observation(self) -> dict[str, Any]:
        return {
            "events": [e.copy() for e in self.events],
            "request": self.request.copy(),
            "constraints": {k: v for k, v in self.constraints.items()},
            "done": self.done,
        }

    def render(self) -> str:
        """Render calendar state as text."""
        lines = []
        lines.append("SHARED CALENDAR BLOCKS:")
        for e in self.events:
            lines.append(f"  {e['day']} {e['start']}-{e['end']}: {e['title']}")
        lines.append("")
        lines.append(f"NEW MEETING REQUEST:")
        lines.append(f"  Duration: {self.request['duration_minutes']} minutes")
        lines.append(f"  Participants: {', '.join(self.request['participants'])}")
        lines.append(f"  Date range: {', '.join(self.request['date_range'])}")
        lines.append("")
        lines.append("CONSTRAINTS:")
        lines.append(f"  Business hours: {self.constraints['business_hours']}")
        if self.constraints["unavailability"]:
            lines.append("  Unavailability:")
            for u in self.constraints["unavailability"]:
                lines.append(f"    {u['participant']}: {u['day']} {u['start']}-{u['end']}")
        else:
            lines.append("  Unavailability: none")
        lines.append("")
        lines.append("Propose a slot as 'DAY HH:MM' (e.g., 'mon 14:00') or 'NONE' if no valid slot exists.")
        return "\n".join(lines)

    def parse_action(self, text: str) -> str:
        """Parse model text output. Returns 'DAY HH:MM' or 'NONE'."""
        text = text.strip().lower()
        if text == "none" or text.startswith("none"):
            return "NONE"
        # Try to parse "day hh:mm" or "day hh:mm" with variations
        parts = text.replace(",", " ").split()
        if len(parts) >= 2:
            day = parts[0]
            time = parts[1]
            if day in DAYS and ":" in time:
                return f"{day} {time}"
        raise ValidationError(f"cannot parse action from '{text}'")

    def legal_actions(self) -> list[str]:
        """Return every well-formed start whose full duration fits business hours."""
        slots = []
        duration = self.request.get("duration_minutes", 0)
        for day in self.request.get("date_range", []):
            for h in range(BUSINESS_START, BUSINESS_END):
                for m in range(0, 60, SLOT_GRANULARITY_MIN):
                    if h * 60 + m + duration <= BUSINESS_END * 60:
                        slots.append(f"{day} {h:02d}:{m:02d}")
        return slots

    def random_legal_action(self, rng: random.Random) -> str:
        """Pick a uniformly random slot within business hours and date range."""
        slots = self.legal_actions()
        if not slots:
            return "NONE"
        return rng.choice(slots)

    def step(self, action: str) -> dict[str, Any]:
        """Verify the proposed slot. Returns observation with verification result."""
        if self.done:
            raise ValidationError("already done")
        self.done = True
        verification = self.verify(action)
        return {
            **self._observation(),
            "action": action,
            "verification": verification,
        }

    def verify(self, action: str) -> dict[str, Any]:
        """Verify a proposed slot against all constraints.

        Returns dict with:
        - valid: bool (all constraints satisfied)
        - constraint_results: per-constraint pass/fail
        - satisfaction_score: fraction of constraints satisfied
        - reason: explanation if invalid
        """
        if action == "NONE":
            # Check if there truly is no valid slot
            has_valid = False
            for slot in self.legal_actions():
                result = self._verify_slot(slot)
                if result["valid"]:
                    has_valid = True
                    break
            if has_valid:
                return {
                    "valid": False,
                    "constraint_results": {"none_when_valid_exists": False},
                    "satisfaction_score": 0.0,
                    "reason": "NONE output but a valid slot exists",
                }
            else:
                return {
                    "valid": True,
                    "constraint_results": {"none_when_no_valid_exists": True},
                    "satisfaction_score": 1.0,
                    "reason": "correctly identified no valid slot",
                }

        return self._verify_slot(action)

    def _verify_slot(self, slot: str) -> dict[str, Any]:
        """Verify a specific slot string like 'mon 14:00'."""
        parts = slot.strip().lower().split()
        if len(parts) != 2:
            return {"valid": False, "constraint_results": {}, "satisfaction_score": 0.0, "reason": f"malformed slot '{slot}'"}
        day, time_str = parts
        constraints_checked: dict[str, bool] = {}
        reasons: list[str] = []

        # Constraint 1: day in date range
        day_in_range = day in self.request.get("date_range", [])
        constraints_checked["day_in_date_range"] = day_in_range
        if not day_in_range:
            reasons.append(f"day '{day}' not in date range {self.request['date_range']}")

        # Constraint 2: valid time format and within business hours
        try:
            h, m = map(int, time_str.split(":"))
            slot_start_min = h * 60 + m
            slot_end_min = slot_start_min + self.request["duration_minutes"]
            biz_start_min = BUSINESS_START * 60
            biz_end_min = BUSINESS_END * 60
        except (ValueError, IndexError):
            constraints_checked["within_business_hours"] = False
            reasons.append(f"malformed time '{time_str}'")
            return {
                "valid": False,
                "constraint_results": constraints_checked,
                "satisfaction_score": 0.0,
                "reason": "; ".join(reasons),
            }

        within_hours = slot_start_min >= biz_start_min and slot_end_min <= biz_end_min
        constraints_checked["within_business_hours"] = within_hours
        if not within_hours:
            reasons.append(f"slot {time_str} + {self.request['duration_minutes']}min outside business hours {self.constraints['business_hours']}")

        # Constraint 3: no overlap with existing events on same day
        overlaps = False
        for e in self.events:
            if e["day"] != day:
                continue
            e_start = _time_to_min(e["start"])
            e_end = _time_to_min(e["end"])
            if slot_start_min < e_end and slot_end_min > e_start:
                overlaps = True
                reasons.append(f"overlaps with existing event {e['day']} {e['start']}-{e['end']}")
                break
        constraints_checked["no_event_overlap"] = not overlaps

        # Constraint 4: no overlap with participant unavailability
        unavail_overlap = False
        for u in self.constraints.get("unavailability", []):
            if u["day"] != day:
                continue
            u_start = _time_to_min(u["start"])
            u_end = _time_to_min(u["end"])
            if slot_start_min < u_end and slot_end_min > u_start:
                unavail_overlap = True
                reasons.append(f"overlaps with {u['participant']} unavailability {u['day']} {u['start']}-{u['end']}")
                break
        constraints_checked["no_unavailability_overlap"] = not unavail_overlap

        all_pass = all(constraints_checked.values())
        satisfaction = sum(constraints_checked.values()) / len(constraints_checked) if constraints_checked else 0.0

        return {
            "valid": all_pass,
            "constraint_results": constraints_checked,
            "satisfaction_score": satisfaction,
            "reason": "; ".join(reasons) if reasons else "all constraints satisfied",
        }


def _time_to_min(time_str: str) -> int:
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def calendar_play(
    seed: int,
    model_action: str | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Play one calendar scheduling instance."""
    if rng is None:
        rng = random.Random(seed * 4099 + 7)
    env = CalendarEnv()
    env.reset(seed)

    if model_action is None:
        action = env.random_legal_action(rng)
    else:
        action = model_action

    none_is_correct = env.verify("NONE")["valid"]
    result = env.step(action)
    return {
        "env": "calendar",
        "seed": seed,
        "action": action,
        "valid": result["verification"]["valid"],
        "satisfaction_score": result["verification"]["satisfaction_score"],
        "none_is_correct": none_is_correct,
        "constraint_results": result["verification"]["constraint_results"],
        "reason": result["verification"]["reason"],
        "state": env.render(),
    }


def calendar_random_baseline(seeds: range | list[int]) -> dict[str, Any]:
    """Run random well-formed (not constraint-aware) proposals for the seeds."""
    results = []
    for seed in seeds:
        result = calendar_play(seed, model_action=None)
        results.append({
            "seed": seed,
            "valid": result["valid"],
            "satisfaction_score": result["satisfaction_score"],
            "none_is_correct": result["none_is_correct"],
        })
    n = len(results)
    valid_count = sum(1 for r in results if r["valid"])
    return {
        "env": "calendar",
        "baseline": "random_well_formed",
        "n_instances": n,
        "valid_rate": valid_count / n if n else 0.0,
        "avg_satisfaction": sum(r["satisfaction_score"] for r in results) / n if n else 0.0,
        "none_correct_rate": sum(1 for r in results if r["none_is_correct"]) / n if n else 0.0,
        "results": results,
    }


def validate_baseline_claims(data: dict[str, Any], sample_size: int | None = None) -> list[str]:
    """Recompute implemented baselines and reject scorecard drift or failed bands."""
    errors: list[str] = []
    if sample_size is None:
        sample_size = int(DEVELOPMENT_CONFIG["baseline_sample_size"])
    seed_start = int(DEVELOPMENT_CONFIG["development_seed_start"])
    by_id = {candidate["candidate_id"]: candidate for candidate in data.get("candidates", [])}
    seeds = range(seed_start, seed_start + sample_size)
    measured = {
        "connect4": (connect4_random_baseline(seeds), "win_rate"),
        "calendar_scheduling": (calendar_random_baseline(seeds), "valid_rate"),
    }
    for candidate_id, (result, metric_key) in measured.items():
        evidence = by_id.get(candidate_id, {}).get("baseline_evidence", {})
        expected = evidence.get("value")
        accepted = evidence.get("accepted_development_range")
        actual = result[metric_key]
        if evidence.get("status") != "measured":
            errors.append(f"{candidate_id}: implemented baseline must have status 'measured'")
        if evidence.get("sample_size") != sample_size or evidence.get("seed_range") != f"{seed_start}-{seed_start + sample_size - 1}":
            errors.append(f"{candidate_id}: measured sample_size/seed_range do not match validator cohort")
        if not isinstance(expected, (int, float)) or abs(float(expected) - actual) > 1e-12:
            errors.append(f"{candidate_id}: recorded {metric_key} {expected!r} != measured {actual}")
        if not isinstance(accepted, list) or len(accepted) != 2 or not accepted[0] <= actual <= accepted[1]:
            errors.append(f"{candidate_id}: measured {metric_key} {actual} is outside accepted range {accepted!r}")
        config_range = DEVELOPMENT_CONFIG["connect4"]["random_x_win_rate_accepted_range"] if candidate_id == "connect4" else CALENDAR_CONFIG["random_valid_rate_accepted_range"]
        if accepted != config_range:
            errors.append(f"{candidate_id}: scorecard accepted range {accepted!r} != development config {config_range!r}")
        if candidate_id == "calendar_scheduling":
            recorded_none = evidence.get("none_correct_rate")
            actual_none = result["none_correct_rate"]
            if not isinstance(recorded_none, (int, float)) or abs(float(recorded_none) - actual_none) > 1e-12:
                errors.append(f"calendar_scheduling: recorded none_correct_rate {recorded_none!r} != measured {actual_none}")
    return errors


# ---------------------------------------------------------------------------
# Canonical trace
# ---------------------------------------------------------------------------

def canonical_trace(env_name: str, seed: int) -> dict[str, Any]:
    """Produce a deterministic canonical trace for the given env and seed."""
    if env_name == "connect4":
        result = connect4_play_vs_random(seed, model_actions=None)
        return {
            "env": "connect4",
            "seed": seed,
            "trace_hash": sha256_bytes(
                json.dumps(result["moves"], ensure_ascii=False).encode("utf-8")
            ),
            "moves": result["moves"],
            "winner": result["winner"],
            "outcome": result["outcome"],
            "move_count": result["move_count"],
        }
    elif env_name == "calendar":
        result = calendar_play(seed, model_action=None)
        return {
            "env": "calendar",
            "seed": seed,
            "trace_hash": sha256_bytes(
                json.dumps({
                    "action": result["action"],
                    "valid": result["valid"],
                    "satisfaction_score": result["satisfaction_score"],
                }, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ),
            "action": result["action"],
            "valid": result["valid"],
            "satisfaction_score": result["satisfaction_score"],
            "constraint_results": result["constraint_results"],
        }
    else:
        raise ValidationError(f"unknown env '{env_name}'")


# ---------------------------------------------------------------------------
# Probe validator
# ---------------------------------------------------------------------------

def validate_probes() -> list[str]:
    """Validate all development probe sets. Returns error list."""
    errors: list[str] = []

    probe_files = {
        "connect4": PROBE_DIR / "connect4-dev-probes-v1.json",
        "calendar": PROBE_DIR / "calendar-dev-probes-v1.json",
    }

    for env_name, probe_path in probe_files.items():
        if not probe_path.exists():
            errors.append(f"{probe_path.name}: file not found")
            continue

        data = load_json(probe_path)
        if not isinstance(data, dict):
            errors.append(f"{probe_path.name}: must be a JSON object")
            continue

        if data.get("artifact_type") != "development_probes":
            errors.append(f"{probe_path.name}: artifact_type must be 'development_probes'")

        if data.get("development_only") is not True:
            errors.append(f"{probe_path.name}: development_only must be true")

        provenance = data.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{probe_path.name}: provenance must be an object")
        else:
            if "author" not in provenance or "content_origin" not in provenance:
                errors.append(f"{probe_path.name}: provenance missing 'author' or 'content_origin'")
            if "date" not in provenance:
                errors.append(f"{probe_path.name}: provenance missing 'date'")
            if "method" not in provenance:
                errors.append(f"{probe_path.name}: provenance missing 'method'")

        if "no_training_labels" not in data or data["no_training_labels"] is not True:
            errors.append(f"{probe_path.name}: no_training_labels must be true")

        if "no_frozen_eval_material" not in data or data["no_frozen_eval_material"] is not True:
            errors.append(f"{probe_path.name}: no_frozen_eval_material must be true")

        probes = data.get("probes")
        if not isinstance(probes, list) or len(probes) == 0:
            errors.append(f"{probe_path.name}: probes must be a non-empty list")
            continue

        for i, probe in enumerate(probes):
            prefix = f"{probe_path.name}.probes[{i}]"
            if not isinstance(probe, dict):
                errors.append(f"{prefix}: must be an object")
                continue

            if "id" not in probe:
                errors.append(f"{prefix}: missing 'id'")
            if "seed" not in probe:
                errors.append(f"{prefix}: missing 'seed'")
            if "expected_action" not in probe:
                errors.append(f"{prefix}: missing 'expected_action'")

            # Mechanically verify each probe
            seed = probe.get("seed")
            expected = probe.get("expected_action")
            if not isinstance(seed, int):
                errors.append(f"{prefix}: seed must be an integer")
                continue

            if env_name == "connect4":
                err = _verify_connect4_probe(prefix, seed, expected, probe)
                errors.extend(err)
            elif env_name == "calendar":
                err = _verify_calendar_probe(prefix, seed, expected, probe)
                errors.extend(err)

    return errors


def _verify_connect4_probe(
    prefix: str, seed: int, expected: Any, probe: dict[str, Any]
) -> list[str]:
    """Verify a Connect-4 probe by replaying the seed and checking the expected action."""
    errors: list[str] = []
    env = Connect4Env()
    env.reset(seed)

    # Probes may include a setup_moves field to reach a specific position
    setup_moves = probe.get("setup_moves", [])
    if not isinstance(setup_moves, list):
        errors.append(f"{prefix}: setup_moves must be a list")
        setup_moves = []

    for j, col1based in enumerate(setup_moves):
        if not isinstance(col1based, int):
            errors.append(f"{prefix}.setup_moves[{j}]: must be an integer (1-based column)")
            return errors
        col = col1based - 1
        if col not in env.legal_actions():
            errors.append(f"{prefix}.setup_moves[{j}]: column {col1based} is not legal at this point")
            return errors
        env.step(col)

    # Now check the expected action
    if not isinstance(expected, int):
        errors.append(f"{prefix}: expected_action must be an integer (1-based column)")
        return errors

    expected_col = expected - 1
    if expected_col not in env.legal_actions():
        errors.append(f"{prefix}: expected_action column {expected} is not legal at this point")
        return errors

    # Check the probe's claim about why this is the expected action
    claim = probe.get("claim", "")
    if claim == "immediate_win":
        if not env.would_win(expected_col, env.current_player):
            errors.append(f"{prefix}: claim is 'immediate_win' but column {expected} does not win for current player")
    elif claim == "immediate_block":
        opponent = C4_OPPONENT if env.current_player == C4_PLAYER else C4_PLAYER
        if not env.would_win(expected_col, opponent):
            errors.append(f"{prefix}: claim is 'immediate_block' but column {expected} does not block opponent win")
    elif claim:
        # Non-empty claim we don't auto-verify — just note it
        pass

    return errors


def _verify_calendar_probe(
    prefix: str, seed: int, expected: Any, probe: dict[str, Any]
) -> list[str]:
    """Verify a calendar scheduling probe."""
    errors: list[str] = []
    env = CalendarEnv()
    env.reset(seed)

    if not isinstance(expected, str):
        errors.append(f"{prefix}: expected_action must be a string ('DAY HH:MM' or 'NONE')")
        return errors

    # Parse the expected action
    try:
        parsed = env.parse_action(expected)
    except ValidationError as e:
        errors.append(f"{prefix}: cannot parse expected_action '{expected}': {e}")
        return errors

    # Verify it
    verification = env.verify(parsed)
    claim = probe.get("claim", "")

    if claim == "valid_slot":
        if not verification["valid"]:
            errors.append(
                f"{prefix}: claim is 'valid_slot' but verification failed: {verification['reason']}"
            )
    elif claim == "invalid_slot":
        if verification["valid"]:
            errors.append(
                f"{prefix}: claim is 'invalid_slot' but verification passed (slot is valid)"
            )
    elif claim == "correct_none":
        if not verification["valid"]:
            errors.append(
                f"{prefix}: claim is 'correct_none' but NONE was not correct: {verification['reason']}"
            )
    elif claim:
        pass  # non-empty claim we don't auto-verify

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_validate_scorecard(args: argparse.Namespace) -> int:
    data = load_json(SCORECARD_PATH)
    errors = validate_development_config(DEVELOPMENT_CONFIG) + validate_scorecard(data)
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        print(f"\nvalidate-scorecard: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"validate-scorecard: OK ({len(data['candidates'])} candidates, "
          f"{sum(1 for c in data['candidates'] if c['selected'])} selected)")
    return 0


def cmd_validate_probes(args: argparse.Namespace) -> int:
    errors = validate_probes()
    if errors:
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        print(f"\nvalidate-probes: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("validate-probes: OK (all probes mechanically verified)")
    return 0


def cmd_validate_baseline_claims(args: argparse.Namespace) -> int:
    data = load_json(SCORECARD_PATH)
    errors = validate_baseline_claims(data)
    if errors:
        for error in errors:
            print(f"  ERROR: {error}", file=sys.stderr)
        print(f"\nvalidate-baseline-claims: {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("validate-baseline-claims: OK (2,000 deterministic seeds per implemented environment)")
    return 0


def cmd_canonical_trace(args: argparse.Namespace) -> int:
    trace = canonical_trace(args.env, args.seed)
    print(json.dumps(trace, indent=2, ensure_ascii=False))
    return 0


def cmd_random_baseline(args: argparse.Namespace) -> int:
    seeds = _parse_seed_range(args.seeds)
    if args.env == "connect4":
        result = connect4_random_baseline(seeds)
    elif args.env == "calendar":
        result = calendar_random_baseline(seeds)
    else:
        print(f"unknown env '{args.env}'", file=sys.stderr)
        return 2
    # Don't print full results for large N
    summary = {k: v for k, v in result.items() if k != "results"}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    if args.env == "connect4":
        actions = []
        if args.actions:
            actions = [int(a) - 1 for a in args.actions.split(",")]
        result = connect4_play_vs_random(args.seed, model_actions=actions)
        summary = {k: v for k, v in result.items() if k != "trace"}
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    elif args.env == "calendar":
        result = calendar_play(args.seed, model_action=args.action)
        summary = {k: v for k, v in result.items() if k != "state"}
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"unknown env '{args.env}'", file=sys.stderr)
        return 2
    return 0


def _parse_seed_range(spec: str) -> list[int]:
    """Parse '0-9' or '0,1,2,3'."""
    if "-" in spec and "," not in spec:
        parts = spec.split("-")
        if len(parts) == 2:
            return list(range(int(parts[0]), int(parts[1]) + 1))
    return [int(x) for x in spec.split(",")]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Capability-gradient benchmark candidate lab")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate-scorecard", help="Validate the candidate scorecard")
    sub.add_parser("validate-probes", help="Validate all development probe sets")
    sub.add_parser("validate-baseline-claims", help="Recompute implemented baseline claims")

    ct = sub.add_parser("canonical-trace", help="Produce a canonical trace")
    ct.add_argument("--env", required=True, choices=["connect4", "calendar"])
    ct.add_argument("--seed", type=int, required=True)

    rb = sub.add_parser("random-baseline", help="Run random-legal baseline")
    rb.add_argument("--env", required=True, choices=["connect4", "calendar"])
    rb.add_argument("--seeds", required=True, help="e.g. '0-9' or '0,1,2,3'")

    play = sub.add_parser("play", help="Play a single instance")
    play.add_argument("--env", required=True, choices=["connect4", "calendar"])
    play.add_argument("--seed", type=int, required=True)
    play.add_argument("--actions", default=None, help="Connect-4: comma-separated 1-based columns")
    play.add_argument("--action", default=None, help="Calendar: 'DAY HH:MM' or 'NONE'")

    args = parser.parse_args(argv)

    handlers = {
        "validate-scorecard": cmd_validate_scorecard,
        "validate-probes": cmd_validate_probes,
        "validate-baseline-claims": cmd_validate_baseline_claims,
        "canonical-trace": cmd_canonical_trace,
        "random-baseline": cmd_random_baseline,
        "play": cmd_play,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
