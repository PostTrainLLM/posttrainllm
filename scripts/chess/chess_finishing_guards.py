#!/usr/bin/env python3
"""Engine-free finishing guards over a model's scored legal chess moves."""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

import chess

PIECE_VALUES = {
    chess.PAWN: 1.0,
    chess.KNIGHT: 3.0,
    chess.BISHOP: 3.0,
    chess.ROOK: 5.0,
    chess.QUEEN: 9.0,
}


def board_from_state(state: dict[str, Any]) -> chess.Board:
    """Restore history when available so repetition and claim checks stay honest."""
    fen = state.get("fen")
    initial_fen = state.get("initial_fen")
    history = state.get("history_uci")
    if (
        isinstance(initial_fen, str)
        and isinstance(history, list)
        and all(isinstance(row, str) for row in history)
    ):
        board = chess.Board(initial_fen)
        for move_text in history:
            move = chess.Move.from_uci(move_text)
            if move not in board.legal_moves:
                raise ValueError("state history contains an illegal move")
            board.push(move)
        if board.fen(en_passant="fen") != chess.Board(fen).fen(en_passant="fen"):
            raise ValueError("state history does not reconstruct the current FEN")
        return board
    return chess.Board(fen)


def material_balance(board: chess.Board) -> float:
    """Material balance in pawns from the side-to-move perspective."""
    return sum(
        value
        * (
            len(board.pieces(piece_type, board.turn))
            - len(board.pieces(piece_type, not board.turn))
        )
        for piece_type, value in PIECE_VALUES.items()
    )


def move_is_mate(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        return board.is_checkmate()
    finally:
        board.pop()


def move_allows_mate_in_one(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        for reply in list(board.legal_moves):
            board.push(reply)
            try:
                if board.is_checkmate():
                    return True
            finally:
                board.pop()
        return False
    finally:
        board.pop()


def move_gives_draw(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        return (
            board.is_stalemate()
            or board.is_insufficient_material()
            or board.is_fivefold_repetition()
            or board.is_seventyfive_moves()
            or board.can_claim_draw()
        )
    finally:
        board.pop()


def opponent_reply_count(board: chess.Board) -> int | None:
    if board.is_check():
        return None
    board.push(chess.Move.null())
    try:
        return board.legal_moves.count()
    finally:
        board.pop()


def winning_for_side_to_move(
    board: chess.Board,
    *,
    mate_available: bool,
    material_threshold: float = 4.0,
    confine_replies: int = 2,
) -> tuple[bool, str | None]:
    if mate_available:
        return True, "mate-in-one"
    balance = material_balance(board)
    if balance >= material_threshold:
        return True, "material-advantage"
    if confine_replies > 0 and balance >= 0:
        replies = opponent_reply_count(board)
        if replies is not None and replies <= confine_replies:
            return True, "opponent-confined"
    return False, None


def _event(guard: str, before: int, after: int, reason: str) -> dict[str, Any]:
    return {
        "guard": guard,
        "reason": reason,
        "candidates_before": before,
        "candidates_after": after,
    }


def finishing_guard_candidates(
    board: chess.Board,
    candidates: Sequence[str],
    *,
    material_threshold: float = 4.0,
    confine_replies: int = 2,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Narrow legal candidates; step aside whenever no safer alternative exists."""
    legal = {move.uci() for move in board.legal_moves}
    ordered = list(dict.fromkeys(candidates))
    if not ordered or any(move not in legal for move in ordered):
        raise ValueError("finishing guards require non-empty legal candidates")
    moves = {text: chess.Move.from_uci(text) for text in ordered}
    events: list[dict[str, Any]] = []

    mating = [text for text in ordered if move_is_mate(board, moves[text])]
    mate_available = bool(mating)
    if mating and len(mating) < len(ordered):
        events.append(
            _event("deliver-mate-in-one", len(ordered), len(mating), "mate-available")
        )
        return mating, events

    safe = [text for text in ordered if not move_allows_mate_in_one(board, moves[text])]
    if safe and len(safe) < len(ordered):
        events.append(
            _event(
                "avoid-opponent-mate-in-one",
                len(ordered),
                len(safe),
                "safe-alternative",
            )
        )
        ordered = safe

    winning, winning_reason = winning_for_side_to_move(
        board,
        mate_available=mate_available,
        material_threshold=material_threshold,
        confine_replies=confine_replies,
    )
    if winning:
        non_drawing = [
            text for text in ordered if not move_gives_draw(board, moves[text])
        ]
        non_drawing_safe = [
            text
            for text in non_drawing
            if not move_allows_mate_in_one(board, moves[text])
        ]
        if non_drawing_safe and len(non_drawing_safe) < len(ordered):
            events.append(
                _event(
                    "avoid-draw-while-winning",
                    len(ordered),
                    len(non_drawing_safe),
                    winning_reason or "winning",
                )
            )
            ordered = non_drawing_safe
    return ordered, events


class FinishingGuardPolicy:
    """Re-rank a scored legal policy without adding search or engine advice."""

    revision = "always-score-finishing-guards/v1"

    def __init__(
        self,
        base_policy: Any,
        *,
        material_threshold: float = 4.0,
        confine_replies: int = 2,
    ):
        self.base_policy = base_policy
        self.policy_id = base_policy.policy_id
        self.material_threshold = material_threshold
        self.confine_replies = confine_replies
        self.last_decision_metadata: dict[str, Any] | None = None
        self._counts: Counter[str] = Counter()

    @property
    def guard_counts(self) -> dict[str, int]:
        return dict(sorted(self._counts.items()))

    def choose(self, state: dict[str, Any], legal_moves: Sequence[str]) -> str:
        raw_argmax = self.base_policy.choose(state, legal_moves)
        scores = getattr(self.base_policy, "last_scores", None)
        if not isinstance(scores, dict) or set(scores) != set(legal_moves):
            raise ValueError("finishing guards require scores for every legal move")
        board = board_from_state(state)
        candidates, events = finishing_guard_candidates(
            board,
            sorted(scores),
            material_threshold=self.material_threshold,
            confine_replies=self.confine_replies,
        )
        selected = max(candidates, key=lambda move: (scores[move], move))
        for event in events:
            self._counts[event["guard"]] += 1
        self.last_decision_metadata = {
            "serving_policy": self.revision,
            "raw_argmax": raw_argmax,
            "selected": selected,
            "intervened": selected != raw_argmax,
            "guard_fired": bool(events),
            "events": events,
        }
        return selected
