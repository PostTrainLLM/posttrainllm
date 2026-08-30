#!/usr/bin/env python3
"""Focused offline tests for the chess policy benchmark."""

from __future__ import annotations

import json
import io
import sys
import tempfile
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
# scripts/ is grouped into topic subdirs; each is a flat import surface.
for _d in [ROOT / "scripts", *sorted(p for p in (ROOT / "scripts").iterdir() if p.is_dir())]:
    sys.path.insert(0, str(_d))

import chess_benchmark as bench  # noqa: E402
import aggregate_chess_candidate_matrix as candidate_matrix  # noqa: E402
import chess_cloud_pilot as cloud  # noqa: E402
import chess_cloud_matrix as matrix  # noqa: E402
import chess_llm_policy as policy  # noqa: E402
import chess_checkpoint_eval as checkpoint_eval  # noqa: E402
import chess_elo  # noqa: E402
import chess_finishing_guards as finishing_guards  # noqa: E402
import chess_move_quality as move_quality  # noqa: E402
import chess_reproduction_recipe as reproduction_recipe  # noqa: E402
import chess_sft_corpus as sft_corpus  # noqa: E402
import chess_sft_text as sft_text  # noqa: E402
import chess_sft_train as sft_train  # noqa: E402
import chess_strength_ladder as strength_ladder  # noqa: E402
import parse_chess_devin_batch as devin_batch  # noqa: E402
import verify_chess_candidate_labels as verifier  # noqa: E402

SUITE = ROOT / "evals/chess/fixtures/development-puzzles-v1.json"


class FirstLegalPolicy:
    policy_id = "first-legal"
    revision = "test/v1"

    def choose(self, state, legal_moves):
        del state
        return legal_moves[0]


class FixedPolicy:
    revision = "test/v1"

    def __init__(self, policy_id, moves):
        self.policy_id = policy_id
        self.moves = iter(moves)

    def choose(self, state, legal_moves):
        del state, legal_moves
        return next(self.moves)


class FakeRungPolicy:
    revision = "fake-rung/v1"
    engine_identity = None

    def __init__(self, rung):
        self.policy_id = rung["rung_id"]

    def choose(self, state, legal_moves):
        del state
        return legal_moves[0]

    def close(self):
        pass


class FakeScoredPolicy:
    revision = "fake-scored/v1"

    def __init__(self, scores):
        self.policy_id = "fake-scored"
        self.scores = scores
        self.last_scores = {}

    def choose(self, state, legal_moves):
        del state
        self.last_scores = {move: self.scores.get(move, -100.0) for move in legal_moves}
        return max(legal_moves, key=lambda move: (self.last_scores[move], move))


def test_starting_observation_is_canonical():
    board = chess.Board()
    state = bench.observation(board, 0)
    assert state["fen"] == chess.STARTING_FEN
    assert state["legal_moves"] == sorted(state["legal_moves"])
    assert len(state["legal_moves"]) == 20
    assert bench.serialize_observation(state).startswith(f"FEN={chess.STARTING_FEN};PLY=0;LEGAL=")


def test_strict_parser_rejects_prose_san_and_illegal_moves():
    board = chess.Board()
    assert bench.parse_strict_uci("e2e4", board).uci() == "e2e4"
    for raw in ("", "I choose e2e4", "e4", "e2e5", "```e2e4```"):
        try:
            bench.parse_strict_uci(raw, board)
        except ValueError:
            pass
        else:
            raise AssertionError(f"strict parser accepted {raw!r}")


def test_special_rules_are_delegated_to_pinned_runtime():
    castling = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert {"e1g1", "e1c1"}.issubset(bench.legal_uci(castling))
    en_passant = chess.Board("8/8/8/3pP3/8/8/8/4K2k w - d6 0 1")
    assert "e5d6" in bench.legal_uci(en_passant)
    promotion = chess.Board("8/P7/8/8/8/8/8/k6K w - - 0 1")
    assert {"a7a8q", "a7a8r", "a7a8b", "a7a8n"}.issubset(bench.legal_uci(promotion))


def test_lichess_chess960_castling_notation_is_canonicalized():
    board = chess.Board("rn1qk2r/pbppppbp/1p3np1/8/2PP4/5NP1/PP2PPBP/RNBQ1RK1 b kq - 0 1")
    assert bench.parse_strict_uci("e8h8", board).uci() == "e8g8"
    assert "e8g8" in bench.legal_uci(board)


def test_constrained_schema_and_parser_use_legal_uci():
    board = chess.Board()
    legal = list(bench.legal_uci(board))
    schema = policy.constrained_action_schema(legal)
    assert schema["properties"]["move"]["enum"] == legal
    assert policy.parse_constrained_output('{"move":"e2e4"}', board).uci() == "e2e4"


def test_constrained_parser_cannot_admit_an_illegal_move():
    board = chess.Board()
    for raw in ('{"move":"e2e5"}', '{"move":"e4"}', '{"move":"e2e4","other":1}', '{}'):
        try:
            policy.parse_constrained_output(raw, board)
        except (ValueError, json.JSONDecodeError):
            pass
        else:
            raise AssertionError(f"constrained parser accepted {raw!r}")


def test_puzzle_suite_validates_and_random_result_is_replayable():
    suite = bench.load_puzzle_suite(SUITE)
    result1 = bench.evaluate_puzzles(bench.RandomLegalPolicy(17), suite)
    result2 = bench.evaluate_puzzles(bench.RandomLegalPolicy(17), suite)
    assert result1["aggregate"]["puzzles"] == 20
    assert [row["parsed_move"] for row in result1["decisions"]] == [
        row["parsed_move"] for row in result2["decisions"]
    ]
    assert result1["aggregate"]["legal_rate"] == 1.0


def test_complete_fools_mate_trace_and_checkmate():
    white = FixedPolicy("white", ["f2f3", "g2g4"])
    black = FixedPolicy("black", ["e7e5", "d8h4"])
    result = bench.run_game(white, black, maximum_plies=8)
    assert result["outcome"] == {"winner": "black", "result": "0-1", "termination": "checkmate"}
    assert len(result["decisions"]) == 4
    assert all(row["legal"] for row in result["decisions"])


def test_illegal_move_forfeits_without_repair():
    result = bench.run_game(FixedPolicy("white", ["e2e5"]), FirstLegalPolicy(), maximum_plies=4)
    assert result["outcome"]["termination"] == "invalid-decision-forfeit"
    assert result["outcome"]["winner"] == "black"
    assert result["decisions"][0]["parsed_move"] is None
    assert result["decisions"][0]["raw_output"] == "e2e5"


def test_gate_config_was_frozen_before_screen():
    gate = json.loads((ROOT / "configs/chess/development-gate-v1.json").read_text(encoding="utf-8"))
    assert gate["status"] == "thresholds-frozen-before-model-screen"
    assert gate["required_puzzles"] == 20
    assert gate["frontier"]["accuracy_margin_over_strongest_local_general_minimum"] == 0.1
    assert gate["specialist_parameter_count_maximum"] == 50_000_000


def test_candidate_model_matrices_are_valid_and_frozen():
    verification = matrix.load_config(ROOT / "configs/chess/model-verification-matrix-v3.json")
    ceiling = matrix.load_config(ROOT / "configs/chess/frontier-ceiling-audit-v1.json")
    assert verification["suite_id"] == ceiling["suite_id"]
    assert any(row["requested_model"] == "glm-5.2" for row in verification["models"])
    assert ceiling["models"][0]["reasoning_effort"] == "high"


def test_codex_event_parser_rejects_tool_use():
    safe = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "test"}),
            json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "e2e4"}}),
        ]
    )
    assert cloud.parse_codex_events(safe)["event_count"] == 2
    unsafe = safe + "\n" + json.dumps({"type": "item.started", "item": {"type": "command_execution"}})
    try:
        cloud.parse_codex_events(unsafe)
    except ValueError as exc:
        assert "tool use" in str(exc)
    else:
        raise AssertionError("Codex tool use was accepted")


def test_cloud_matrix_claude_envelope_and_tool_guard():
    envelope = json.dumps(
        {
            "is_error": False,
            "structured_output": {"move": "e2e4"},
            "modelUsage": {"claude-sonnet-5": {"inputTokens": 10}},
            "total_cost_usd": 0.01,
            "num_turns": 1,
        }
    )
    raw, metadata = matrix.parse_claude_envelope(envelope, constrained=True)
    assert raw == '{"move": "e2e4"}'
    assert metadata["resolved_models"] == ["claude-sonnet-5"]
    assert metadata["cost_usd"] == 0.01
    unsafe = json.dumps({"type": "item.started", "item": {"type": "web_search"}})
    try:
        matrix.parse_codex_events(unsafe)
    except ValueError as exc:
        assert "tool use" in str(exc)
    else:
        raise AssertionError("matrix adapter accepted tool use")


def test_devin_batch_parser_extracts_only_complete_moves_object():
    text = 'wrapper {"other":1}\nfinal {"moves":[{"puzzle_id":"p1","move":"e2e4"}]}\nend'
    assert devin_batch.extract_moves_object(text) == {
        "moves": [{"puzzle_id": "p1", "move": "e2e4"}]
    }
    try:
        devin_batch.extract_moves_object("no structured result")
    except ValueError as exc:
        assert "no moves JSON" in str(exc)
    else:
        raise AssertionError("missing Devin result was accepted")


def test_deep_label_admission_is_fail_closed():
    stable = {
        "top_move": "e2e4",
        "gap_cp": 300,
        "equivalent_forced_mates": False,
        "variations": [{"pv_legal": True}, {"pv_legal": True}],
    }
    assert verifier.admission_reasons(stable, stable, minimum_gap_cp=150, duplicate=False) == []
    changed = {**stable, "top_move": "d2d4"}
    assert "top-move-changed" in verifier.admission_reasons(
        stable, changed, minimum_gap_cp=150, duplicate=False
    )
    ambiguous = {**stable, "gap_cp": 12, "equivalent_forced_mates": True}
    reasons = verifier.admission_reasons(stable, ambiguous, minimum_gap_cp=150, duplicate=True)
    assert reasons == ["duplicate-position", "insufficient-final-gap", "multiple-forced-mate-moves"]


def test_principal_variation_legality_and_slice_selection():
    board = chess.Board()
    assert verifier.pv_is_legal(board, [chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")])
    assert not verifier.pv_is_legal(board, [chess.Move.from_uci("e2e5")])
    puzzles = [
        {"id": f"p-{index}", "label": {"legal_move_count": index + 2}}
        for index in range(12)
    ]
    first = verifier.select_verification_slice(puzzles, 8, 17)
    second = verifier.select_verification_slice(puzzles, 8, 17)
    assert [row["id"] for row in first] == [row["id"] for row in second]
    assert len({row["id"] for row in first}) == 8


def test_candidate_matrix_separates_raw_legality_execution_and_redirect():
    document = {
        "track": "legal-constrained-diagnostic",
        "model": {"policy_id": "test-policy", "requested_model": "test-model", "backend": "test"},
        "aggregate": {"total_cost_usd": 0.25},
        "decisions": [
            {"puzzle_id": "p1", "exact": True, "legal": True, "failure": None, "latency_ms": 10},
            {"puzzle_id": "p2", "exact": False, "legal": False, "failure": "provider", "latency_ms": 20},
        ],
    }
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "run.json"
        path.write_text(json.dumps(document))
        result = candidate_matrix.aggregate_run([path])
    assert result["raw_legal_rate"] == 0.5
    assert result["execution_rate"] == 0.5
    assert result["executed_legal_rate"] == 1.0
    assert result["redirect_required"] == 1
    assert result["provider_failures"] == 1


def test_recorded_development_results_preserve_the_gradient():
    random_result = json.loads((ROOT / "evals/chess/random-legal-development-v2.json").read_text())
    qwen4 = json.loads((ROOT / "evals/chess/qwen3-4b-development-v2.json").read_text())
    qwen9 = json.loads((ROOT / "evals/chess/qwen3.5-9b-development-v1.json").read_text())
    codex = json.loads((ROOT / "evals/chess/codex-gpt-5.5-development-v1.json").read_text())
    assert random_result["calibration"]["seeds"] == 2000
    assert qwen4["aggregate"]["exact_move_accuracy"] == 0.0
    assert qwen9["aggregate"]["exact_move_accuracy"] == 0.1
    assert codex["aggregate"]["exact_move_accuracy"] == 0.65
    assert codex["aggregate"]["legal_rate"] == 1.0


def test_lichess_eval_compiler_is_deterministic_and_fail_closed():
    config = sft_corpus.load_config(ROOT / "configs/chess/lichess-eval-corpus-v1.json")
    fixture = str(ROOT / "evals/chess/fixtures/lichess-eval-tiny-v1.jsonl")
    first = io.StringIO()
    second = io.StringIO()
    manifest1 = sft_corpus.compile_corpus(config, fixture, first)
    manifest2 = sft_corpus.compile_corpus(config, fixture, second)
    assert first.getvalue() == second.getvalue()
    assert manifest1 == manifest2
    rows = [json.loads(line) for line in first.getvalue().splitlines()]
    assert len(rows) == 2
    assert rows[0]["target"] == "e2e4"
    assert rows[1]["target"] == "c7c5"  # highest-depth evaluation wins
    assert all(row["target"] in row["legal_moves"] for row in rows)
    assert all(len(row["input"].encode("utf-8")) <= 512 for row in rows)
    assert len({row["fen"] for row in rows}) == len(rows)
    assert manifest1["counts"]["accepted"] == 2
    assert manifest1["counts"]["rejected"] == 4
    assert manifest1["counts"]["rejection_reasons"]["duplicate-position"] == 1
    assert manifest1["counts"]["rejection_reasons"]["below-minimum-depth"] == 1
    assert manifest1["counts"]["rejection_reasons"]["malformed-json"] == 1


def test_compiled_rows_render_to_bounded_python_training_text():
    config = sft_corpus.load_config(ROOT / "configs/chess/lichess-eval-corpus-v1.json")
    fixture = str(ROOT / "evals/chess/fixtures/lichess-eval-tiny-v1.jsonl")
    compiled = io.StringIO()
    sft_corpus.compile_corpus(config, fixture, compiled)
    with tempfile.TemporaryDirectory() as directory:
        input_path = Path(directory) / "compiled.jsonl"
        input_path.write_text(compiled.getvalue())
        first = io.StringIO()
        second = io.StringIO()
        manifest1 = sft_text.render_training_text(
            input_path,
            first,
            split="train",
            maximum_rows=2,
            repeat=3,
            context_length=512,
        )
        manifest2 = sft_text.render_training_text(
            input_path,
            second,
            split="train",
            maximum_rows=2,
            repeat=3,
            context_length=512,
        )
    assert first.getvalue() == second.getvalue()
    assert manifest1 == manifest2
    assert manifest1["unique_rows"] == 2
    assert manifest1["rendered_sequences"] == 6
    assert ";LEGAL=" not in first.getvalue()
    assert first.getvalue().count(";MOVE=e2e4\n") == 3


def test_chess_sft_masks_every_prompt_byte_and_trains_only_the_move():
    config = sft_corpus.load_config(ROOT / "configs/chess/lichess-eval-corpus-v1.json")
    fixture = str(ROOT / "evals/chess/fixtures/lichess-eval-tiny-v1.jsonl")
    compiled = io.StringIO()
    sft_corpus.compile_corpus(config, fixture, compiled)
    row = json.loads(compiled.getvalue().splitlines()[0])
    inputs, targets = sft_train.encode_row(row)
    prompt_length = len(row["input"].encode("utf-8"))
    assert targets[: prompt_length - 1] == [-100] * (prompt_length - 1)
    assert [target for target in targets if target != -100] == list(f"{row['target']}\n".encode("ascii"))
    assert inputs[prompt_length - 1] == ord("=")


def test_checkpoint_eval_loader_rejects_row_hash_drift():
    config = sft_corpus.load_config(ROOT / "configs/chess/lichess-eval-corpus-v1.json")
    fixture = str(ROOT / "evals/chess/fixtures/lichess-eval-tiny-v1.jsonl")
    compiled = io.StringIO()
    sft_corpus.compile_corpus(config, fixture, compiled)
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "compiled.jsonl"
        path.write_text(compiled.getvalue())
        rows = checkpoint_eval.load_rows(path, "train", maximum_rows=1)
        assert len(rows) == 1
        document = json.loads(compiled.getvalue().splitlines()[0])
        document["target"] = "d2d4"
        path.write_text(json.dumps(document) + "\n")
        try:
            checkpoint_eval.load_rows(path, "train", maximum_rows=1)
        except ValueError as exc:
            assert str(exc) == "compiled chess row hash mismatch"
        else:
            raise AssertionError("checkpoint eval admitted a mutated compiled row")


def test_44m_chess_candidate_stays_inside_parameter_ceiling():
    config = json.loads((ROOT / "configs/model.chess-44m-v0.json").read_text())
    v = config["vocab_size"]
    c = config["d_model"]
    context = config["context_length"]
    layers = config["n_layers"]
    mlp = config["d_mlp"]
    estimated = v * c + context * c + 2 * c + layers * (
        4 * (c * c + c) + 4 * c + (c * mlp + mlp) + (mlp * c + c)
    )
    assert estimated == 44_527_616
    assert config["_notes"]["expected_params_canonical_estimator"] == estimated
    assert 30_000_000 <= estimated <= 50_000_000


def test_44m_tiny_overfit_evidence_passes_only_the_correctness_gate():
    result = json.loads((ROOT / "evals/chess/character-chess-44m-tiny-overfit-v1.json").read_text())
    assert result["status"] == "passed-correctness-gate-not-strength-evidence"
    assert result["model"]["parameters"] == 44_527_616
    assert result["training"]["stopped_at_step"] == 150
    assert result["training"]["maximum_authorized_steps"] == 200
    assert result["evaluation_path"][-1]["exact_target_rate"] == 1.0
    assert result["evaluation_path"][-1]["executed_legal_rate"] == 1.0
    assert result["evaluation_path"][-1]["minimum_target_log_score_margin"] > 0
    assert "held-out chess strength" in result["interpretation"]["not_claimed"]
    assert result["interpretation"]["next_gate"].startswith("owner-approved")


def test_44m_stockfish_rating_is_honestly_below_the_ladder_floor():
    result = json.loads((ROOT / "evals/chess/character-chess-44m-stockfish-rating-v1.json").read_text())
    assert result["status"] == "below-calibrated-floor-diagnostic-extrapolation"
    assert result["candidate_matches"]["games"] == 30
    assert result["candidate_matches"]["white_games"] == 15
    assert result["candidate_matches"]["black_games"] == 15
    assert result["candidate_matches"]["executed_legal_rate"] == 1.0
    assert result["rating"]["display"] == "<536"
    assert result["rating"]["range_state"] == "below-calibrated-floor"
    assert result["rating"]["diagnostic_extrapolation"] == result["rating"]["estimate"]
    assert result["rating"]["qualification_failures"] == []
    low, high = result["rating"]["paired_opening_bootstrap_interval_95"]
    assert low < result["rating"]["estimate"] < high
    assert "Not FIDE" in result["rating"]["disclaimer"]
    assert result["interpretation"]["next_gate"].startswith("Train the frozen 10000-row pilot")


def test_finishing_guards_deliver_mate_and_preserve_model_scores():
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 w - - 0 1")
    base = FakeScoredPolicy({"f7a7": 10.0, "f7f8": 1.0})
    guarded = finishing_guards.FinishingGuardPolicy(base)
    selected = guarded.choose(bench.observation(board, 0), list(bench.legal_uci(board)))
    assert selected in {"f7f8", "f7e8", "f7h7", "f7g7"}
    assert guarded.last_decision_metadata["raw_argmax"] == "f7a7"
    assert guarded.last_decision_metadata["intervened"] is True
    assert guarded.last_decision_metadata["events"][0]["guard"] == "deliver-mate-in-one"


def test_full_game_trace_records_guard_intervention_metadata():
    base = FakeScoredPolicy({"f7a7": 10.0, "f7f8": 1.0})
    guarded = finishing_guards.FinishingGuardPolicy(base)
    result = bench.run_game(
        guarded,
        FirstLegalPolicy(),
        starting_fen="7k/5Q2/6K1/8/8/8/8/8 w - - 0 1",
        maximum_plies=2,
    )
    assert result["outcome"]["termination"] == "checkmate"
    metadata = result["decisions"][0]["policy_metadata"]
    assert metadata["serving_policy"] == "always-score-finishing-guards/v1"
    assert metadata["intervened"] is True
    assert metadata["events"][0]["candidates_after"] == 4


def test_finishing_guards_avoid_opponent_mate_when_a_safe_move_exists():
    board = chess.Board()
    for move in ("f2f3", "e7e5"):
        board.push_uci(move)
    candidates, events = finishing_guards.finishing_guard_candidates(board, ["g2g4", "d2d3"])
    assert candidates == ["d2d3"]
    assert events[0]["guard"] == "avoid-opponent-mate-in-one"


def test_finishing_guards_avoid_stalemating_a_won_position():
    board = chess.Board("k7/2Q5/2K5/8/8/8/8/8 w - - 0 1")
    candidates, events = finishing_guards.finishing_guard_candidates(board, ["c7b6", "c7d8"])
    assert candidates == ["c7d8"]
    assert events[-1]["guard"] == "avoid-draw-while-winning"
    assert events[-1]["reason"] == "material-advantage"


def test_finishing_guard_steps_aside_when_every_candidate_allows_mate():
    board = chess.Board()
    for move in ("f2f3", "e7e5"):
        board.push_uci(move)
    candidates, events = finishing_guards.finishing_guard_candidates(board, ["g2g4"])
    assert candidates == ["g2g4"]
    assert events == []


def test_move_quality_uses_mover_perspective_and_frozen_thresholds():
    document = {
        "games": [
            {
                "game_id": "g1",
                "decisions": [
                    {
                        "policy_id": "candidate",
                        "legal": True,
                        "pre_fen": chess.STARTING_FEN,
                        "parsed_move": "e2e4",
                        "ply": 0,
                    },
                    {
                        "policy_id": "opponent",
                        "legal": True,
                        "pre_fen": chess.STARTING_FEN,
                        "parsed_move": "d2d4",
                        "ply": 1,
                    },
                ],
            }
        ]
    }
    aggregate, rows = move_quality.grade_trace(
        document,
        "candidate",
        {"blunder": 100, "severe_blunder": 300},
        lambda board, move: (250, 100),
    )
    assert len(rows) == 1
    assert rows[0]["centipawn_loss"] == 150
    assert aggregate["average_centipawn_loss"] == 150
    assert aggregate["blunder_rate"] == 1.0
    assert aggregate["severe_blunder_rate"] == 0.0


def test_qwen_reproduction_recipe_is_staged_and_operator_gated():
    recipe = reproduction_recipe.load_recipe(ROOT / "configs/chess/qwen-reproduction-v1.json")
    assert [stage["total_rows"] for stage in recipe["stages"]] == [10000, 100000, 1000000, 2000000]
    assert all(stage["training_authorized"] is False for stage in recipe["stages"])
    assert all(
        stage["arms"]["commentary-8pct"]["grounded_commentary"] == stage["total_rows"] * 8 // 100
        for stage in recipe["stages"]
    )
    assert recipe["evaluation"]["raw_serving_policy"] != recipe["evaluation"]["guarded_serving_policy"]


def test_strength_ladder_smoke_is_paired_and_unrated():
    config = strength_ladder.load_config(ROOT / "configs/chess/strength-ladder-smoke-v1.json")
    openings = strength_ladder.load_openings(ROOT / "configs/chess/openings-development-v1.json")
    candidate = strength_ladder.FirstLegalPolicy("candidate-smoke")
    result = strength_ladder.run_ladder(
        candidate,
        {"backend": "first-legal", "model_ref": None},
        config,
        openings,
        "/opt/homebrew/bin/stockfish",
        opponent_factory=lambda rung: FakeRungPolicy(rung),
    )
    assert result["aggregate"]["games"] == 4
    assert result["aggregate"]["colors"] == {"white": 2, "black": 2}
    assert result["aggregate"]["candidate_raw_legal_rate"] == 1.0
    assert result["aggregate"]["rating"]["status"] == "unrated"
    assert set(result["aggregate"]["rating"]["qualification_failures"]) == {
        "minimum-completed-games",
        "minimum-games-per-rung",
        "minimum-calibrated-rungs",
    }
    assert all(game["outcome"]["termination"] == "move-cap-draw" for game in result["games"])


def test_strength_ladder_marks_finite_estimate_below_floor_as_extrapolation():
    config = strength_ladder.load_config(ROOT / "configs/chess/strength-ladder-smoke-v1.json")
    config["rungs"] = [
        {
            **config["rungs"][0],
            "rung_id": "floor",
            "calibrated_rating": 536.361,
            "rating_state": "calibrated",
        }
    ]
    config["qualification"] = {
        "minimum_completed_games": 6,
        "minimum_games_per_rung": 6,
        "minimum_calibrated_rungs": 1,
        "maximum_color_imbalance": 0,
        "maximum_invalid_forfeit_rate": 0.0,
    }
    games = []
    for index in range(6):
        color = "white" if index % 2 == 0 else "black"
        winner = None if index == 0 else ("black" if color == "white" else "white")
        games.append(
            {
                "rung_id": "floor",
                "opening_id": f"opening-{index // 2}",
                "candidate_color": color,
                "white": {"policy_id": "candidate" if color == "white" else "floor"},
                "black": {"policy_id": "candidate" if color == "black" else "floor"},
                "outcome": {"winner": winner, "termination": "checkmate"},
                "decisions": [],
            }
        )
    rating = strength_ladder.summarize_games(games, "candidate", config)["rating"]
    assert rating["status"] == "below-calibrated-floor"
    assert rating["display"] == "<536"
    assert rating["diagnostic_extrapolation"] == rating["estimate"]
    assert rating["qualification_failures"] == []


def test_strength_ladder_treats_floating_point_floor_equality_as_on_ladder():
    config = strength_ladder.load_config(ROOT / "configs/chess/strength-ladder-smoke-v1.json")
    config["rungs"] = [
        {
            **config["rungs"][0],
            "rung_id": "floor",
            "calibrated_rating": 536.3611231466995,
            "rating_state": "calibrated",
        }
    ]
    config["qualification"] = {
        "minimum_completed_games": 6,
        "minimum_games_per_rung": 6,
        "minimum_calibrated_rungs": 1,
        "maximum_color_imbalance": 0,
        "maximum_invalid_forfeit_rate": 0.0,
    }
    games = []
    for index in range(6):
        color = "white" if index % 2 == 0 else "black"
        games.append(
            {
                "rung_id": "floor",
                "opening_id": f"opening-{index // 2}",
                "candidate_color": color,
                "white": {"policy_id": "candidate" if color == "white" else "floor"},
                "black": {"policy_id": "candidate" if color == "black" else "floor"},
                "outcome": {"winner": None, "termination": "threefold-repetition"},
                "decisions": [],
            }
        )

    rating = strength_ladder.summarize_games(games, "candidate", config)["rating"]

    assert rating["status"] == "qualified-internal-rating"
    assert rating["range_state"] == "on-calibrated-ladder"
    assert rating["display"] == "536"
    assert rating["diagnostic_extrapolation"] is None


def test_strength_ladder_does_not_configure_managed_uci_options():
    config = strength_ladder.load_config(ROOT / "configs/chess/strength-ladder-smoke-v1.json")
    options = strength_ladder.stockfish_options(config["rungs"][0], config["engine"])

    assert options == {
        "Threads": 1,
        "Hash": 16,
        "UCI_LimitStrength": False,
        "Skill Level": 0,
    }
    assert "Ponder" not in options


def test_internal_elo_fit_tracks_score_against_a_fixed_anchor():
    observations = [(1320.0, score) for score in (1.0, 0.5, 0.0, 1.0)]
    estimate, state = chess_elo.fit_single_rating(observations)
    assert state == "finite"
    assert estimate > 1320.0
    tied, tied_state = chess_elo.fit_single_rating([(1320.0, 1.0), (1320.0, 0.0)])
    assert tied_state == "finite"
    assert abs(tied - 1320.0) < 1e-6


def test_connected_pool_keeps_the_disclosed_anchor_fixed():
    matches = [
        ("weak", "anchor", 0.0),
        ("anchor", "weak", 1.0),
        ("middle", "anchor", 0.5),
        ("anchor", "middle", 0.5),
        ("weak", "middle", 0.0),
        ("middle", "weak", 1.0),
    ]
    ratings = chess_elo.fit_connected_pool(
        ["weak", "middle", "anchor"],
        matches,
        anchor_id="anchor",
        anchor_rating=1320.0,
    )
    assert ratings["anchor"] == 1320.0
    assert ratings["weak"] < ratings["middle"]
    assert ratings["weak"] < ratings["anchor"]
    assert abs(ratings["middle"] - ratings["anchor"]) < 100


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    for test in tests:
        test()
        print(f"  ok: {test.__name__}")
    print(f"chess benchmark tests: {len(tests)} passed")
