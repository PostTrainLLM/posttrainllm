#!/usr/bin/env python3
"""SQLite persistence, execution, resumption, and export for OffHours."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

import offhours_core as core

SCHEMA_VERSION = "offhours/sqlite/v1"


class CompletionClient(Protocol):
    def complete(self, messages: list[dict[str, str]], seed: int) -> dict[str, Any]: ...


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    days: int
    tasks_per_day: int
    seed: int
    conditions: list[str]
    provenance: dict[str, Any]


@dataclass(frozen=True)
class ModelTurnRecord:
    run_id: str
    day: sqlite3.Row
    plan_index: int
    turn: dict[str, Any]
    input_text: str
    transcript: list[dict[str, str]]
    response: dict[str, Any]
    graded: dict[str, Any]
    upper_bound: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA foreign_keys = ON")
    database.execute("PRAGMA journal_mode = WAL")
    database.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
          run_id TEXT PRIMARY KEY,
          schema_version TEXT NOT NULL,
          created_at TEXT NOT NULL,
          status TEXT NOT NULL,
          config_sha256 TEXT NOT NULL,
          seed INTEGER NOT NULL,
          days INTEGER NOT NULL,
          tasks_per_day INTEGER NOT NULL,
          conditions_json TEXT NOT NULL,
          plan_json TEXT NOT NULL,
          provenance_json TEXT NOT NULL,
          last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS days (
          run_id TEXT NOT NULL,
          day_id TEXT NOT NULL,
          day_index INTEGER NOT NULL,
          condition TEXT NOT NULL,
          severity INTEGER,
          execution_order INTEGER NOT NULL,
          status TEXT NOT NULL,
          context_verified INTEGER NOT NULL DEFAULT 1,
          next_turn_index INTEGER NOT NULL DEFAULT 0,
          turn_plan_json TEXT NOT NULL,
          transcript_json TEXT NOT NULL,
          last_error TEXT,
          completed_at TEXT,
          PRIMARY KEY (run_id, day_id, condition),
          FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS turns (
          run_id TEXT NOT NULL,
          day_id TEXT NOT NULL,
          condition TEXT NOT NULL,
          plan_index INTEGER NOT NULL,
          kind TEXT NOT NULL,
          task_id TEXT,
          task_index INTEGER,
          event_id TEXT,
          severity INTEGER,
          distance_from_last_event INTEGER,
          input_text TEXT NOT NULL,
          input_words INTEGER NOT NULL,
          request_sha256 TEXT,
          raw_output TEXT,
          parsed_output_json TEXT,
          format_valid INTEGER,
          correct INTEGER,
          decision_correct INTEGER,
          reason_code_valid INTEGER,
          skipped INTEGER NOT NULL DEFAULT 0,
          expected_decision TEXT,
          expected_reason_code TEXT,
          actual_decision TEXT,
          actual_reason_code TEXT,
          employee_action TEXT,
          reply_length INTEGER,
          context_tokens INTEGER,
          output_tokens INTEGER,
          context_upper_bound INTEGER,
          latency_ms REAL,
          endpoint_model TEXT,
          system_fingerprint TEXT,
          error_code TEXT,
          created_at TEXT NOT NULL,
          PRIMARY KEY (run_id, day_id, condition, plan_index),
          FOREIGN KEY (run_id, day_id, condition) REFERENCES days(run_id, day_id, condition)
        );
        """
    )
    return database


def build_provenance(
    bundle: dict[str, Any],
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validation = core.validate_bundle(bundle)
    model = json.loads(json.dumps(bundle["config"]["model"]))
    overrides = overrides or {}
    if overrides.get("base_url"):
        model["base_url"] = overrides["base_url"]
    if overrides.get("api_key_env"):
        model["api_key_env"] = overrides["api_key_env"]
    model_file = overrides.get("model_file")
    if model_file:
        path = Path(model_file).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f"model file does not exist: {path}")
        model["model_file"] = {
            "path": str(path),
            "sha256": core.file_sha256(path),
            "unavailable_reason": None,
        }
    if overrides.get("quantization"):
        model["quantization"] = overrides["quantization"]
        model["quantization_unavailable_reason"] = None
    if overrides.get("server_name"):
        model["inference_server"]["name"] = overrides["server_name"]
    if overrides.get("server_version"):
        model["inference_server"]["version"] = overrides["server_version"]
        model["inference_server"]["version_unavailable_reason"] = None
    return {
        "schema_version": "offhours/provenance/v1",
        "model": model,
        "system_prompt_sha256": validation["system_prompt_sha256"],
        "policy_version": bundle["claims"]["policy_revision"],
        "task_bank_version": bundle["claims"]["revision"],
        "scenario_version": bundle["scenarios"]["revision"],
        "config_sha256": validation["config_sha256"],
        "claims_sha256": validation["claims_sha256"],
        "scenarios_sha256": validation["scenarios_sha256"],
        "hidden_chain_of_thought_stored": False,
    }


def prepare_run(
    database: sqlite3.Connection,
    bundle: dict[str, Any],
    spec: RunSpec,
) -> None:
    run_id = spec.run_id
    plan = core.build_plan(bundle, spec.days, spec.tasks_per_day, spec.seed)
    valid_conditions = {item["id"] for item in bundle["config"]["conditions"]}
    if (
        not spec.conditions
        or len(spec.conditions) != len(set(spec.conditions))
        or not set(spec.conditions) <= valid_conditions
    ):
        raise ValueError(
            "conditions must be a non-empty unique subset of the pilot conditions"
        )
    config_hash = spec.provenance["config_sha256"]
    existing = database.execute(
        "SELECT * FROM runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    if existing:
        expected = (
            config_hash,
            spec.seed,
            spec.days,
            spec.tasks_per_day,
            core.canonical_json(spec.conditions),
            core.canonical_json(spec.provenance),
        )
        actual = (
            existing["config_sha256"],
            existing["seed"],
            existing["days"],
            existing["tasks_per_day"],
            existing["conditions_json"],
            existing["provenance_json"],
        )
        if actual != expected:
            raise ValueError("resume arguments do not match the stored run identity")
        return

    created_at = utc_now()
    with database:
        database.execute(
            """
            INSERT INTO runs (
              run_id, schema_version, created_at, status, config_sha256, seed,
              days, tasks_per_day, conditions_json, plan_json, provenance_json
            ) VALUES (?, ?, ?, 'planned', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                SCHEMA_VERSION,
                created_at,
                config_hash,
                spec.seed,
                spec.days,
                spec.tasks_per_day,
                core.canonical_json(spec.conditions),
                core.canonical_json(plan),
                core.canonical_json(spec.provenance),
            ),
        )
        condition_meta = {item["id"]: item for item in bundle["config"]["conditions"]}
        system_transcript = [
            {"role": "system", "content": bundle["config"]["system_prompt"]}
        ]
        for day in plan:
            selected_order = [
                name for name in day["condition_order"] if name in spec.conditions
            ]
            for execution_order, condition in enumerate(selected_order, 1):
                turn_plan = core.build_turn_plan(bundle, day, condition)
                database.execute(
                    """
                    INSERT INTO days (
                      run_id, day_id, day_index, condition, severity, execution_order,
                      status, turn_plan_json, transcript_json
                    ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                    """,
                    (
                        run_id,
                        day["day_id"],
                        day["day_index"],
                        condition,
                        condition_meta[condition]["severity"],
                        execution_order,
                        core.canonical_json(turn_plan),
                        core.canonical_json(system_transcript),
                    ),
                )


def _set_interrupted(
    database: sqlite3.Connection, run_id: str, day: sqlite3.Row, message: str
) -> None:
    safe_message = message.replace("\n", " ")[:240]
    with database:
        database.execute(
            "UPDATE days SET status = 'interrupted', last_error = ? WHERE run_id = ? AND day_id = ? AND condition = ?",
            (safe_message, run_id, day["day_id"], day["condition"]),
        )
        database.execute(
            "UPDATE runs SET status = 'interrupted', last_error = ? WHERE run_id = ?",
            (safe_message, run_id),
        )


def _turn_identity_values(
    run_id: str,
    day: sqlite3.Row,
    plan_index: int,
    turn: dict[str, Any],
    input_text: str,
) -> tuple[Any, ...]:
    return (
        run_id,
        day["day_id"],
        day["condition"],
        plan_index,
        turn["kind"],
        turn.get("task_id"),
        turn.get("task_index"),
        turn.get("last_event_id") or turn.get("event_id"),
        turn.get("severity"),
        turn.get("distance_from_last_event"),
        input_text,
        len(input_text.split()),
    )


def _record_context_failure(
    database: sqlite3.Connection,
    run_id: str,
    day: sqlite3.Row,
    plan_index: int,
    turn: dict[str, Any],
    input_text: str,
    upper_bound: int,
) -> None:
    with database:
        database.execute(
            """
            INSERT INTO turns (
              run_id, day_id, condition, plan_index, kind, task_id, task_index,
              event_id, severity, distance_from_last_event, input_text, input_words,
              skipped, expected_decision, expected_reason_code, context_upper_bound,
              error_code, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'context-limit', ?)
            """,
            (
                *_turn_identity_values(run_id, day, plan_index, turn, input_text),
                turn.get("claim", {}).get("expected", {}).get("decision"),
                turn.get("claim", {}).get("expected", {}).get("reason_code"),
                upper_bound,
                utc_now(),
            ),
        )
        database.execute(
            """
            UPDATE days SET status = 'failed_context', context_verified = 0,
              last_error = 'context safety bound exceeded'
            WHERE run_id = ? AND day_id = ? AND condition = ?
            """,
            (run_id, day["day_id"], day["condition"]),
        )
        database.execute(
            "UPDATE runs SET status = 'failed_context', last_error = 'context safety bound exceeded' WHERE run_id = ?",
            (run_id,),
        )


def _record_filler(
    database: sqlite3.Connection,
    run_id: str,
    day: sqlite3.Row,
    plan_index: int,
    turn: dict[str, Any],
    transcript: list[dict[str, str]],
) -> None:
    input_text = core.filler_prompt(turn["message"])
    transcript.append({"role": "user", "content": input_text})
    with database:
        database.execute(
            """
            INSERT INTO turns (
              run_id, day_id, condition, plan_index, kind, event_id, severity,
              input_text, input_words, created_at
            ) VALUES (?, ?, ?, ?, 'event', ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                day["day_id"],
                day["condition"],
                plan_index,
                turn["event_id"],
                turn["severity"],
                input_text,
                len(input_text.split()),
                utc_now(),
            ),
        )
        database.execute(
            """
            UPDATE days SET next_turn_index = ?, transcript_json = ?, status = 'running', last_error = NULL
            WHERE run_id = ? AND day_id = ? AND condition = ?
            """,
            (
                plan_index + 1,
                core.canonical_json(transcript),
                run_id,
                day["day_id"],
                day["condition"],
            ),
        )


def _model_turn_data(
    bundle: dict[str, Any],
    turn: dict[str, Any],
    raw_output: str,
) -> dict[str, Any]:
    contracts = bundle["config"]["response_contracts"]
    if turn["kind"] == "task":
        expected = turn["claim"]["expected"]
        graded = core.parse_claim_response(raw_output, expected, contracts["claim"])
        return {
            **graded,
            "expected_decision": expected["decision"],
            "expected_reason_code": expected["reason_code"],
            "employee_action": None,
            "reply_length": None,
        }
    graded = core.parse_event_response(raw_output, contracts["event"])
    return {
        "format_valid": graded["format_valid"],
        "correct": None,
        "decision_correct": None,
        "reason_code_valid": None,
        "actual_decision": None,
        "actual_reason_code": None,
        "parsed": graded["parsed"],
        "expected_decision": None,
        "expected_reason_code": None,
        "employee_action": graded["employee_action"],
        "reply_length": len(graded["reply"]) if graded["reply"] is not None else None,
    }


def _record_model_turn(
    database: sqlite3.Connection,
    record: ModelTurnRecord,
) -> None:
    run_id = record.run_id
    day = record.day
    plan_index = record.plan_index
    turn = record.turn
    input_text = record.input_text
    transcript = record.transcript
    response = record.response
    graded = record.graded
    upper_bound = record.upper_bound
    transcript.append({"role": "assistant", "content": response["content"]})
    context_tokens = response.get("context_tokens")
    context_verified = int(
        isinstance(context_tokens, int) and not isinstance(context_tokens, bool)
    )
    with database:
        database.execute(
            """
            INSERT INTO turns (
              run_id, day_id, condition, plan_index, kind, task_id, task_index,
              event_id, severity, distance_from_last_event, input_text, input_words,
              request_sha256, raw_output, parsed_output_json, format_valid, correct,
              decision_correct, reason_code_valid, expected_decision, expected_reason_code,
              actual_decision, actual_reason_code, employee_action, reply_length,
              context_tokens, output_tokens, context_upper_bound, latency_ms, endpoint_model,
              system_fingerprint, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                *_turn_identity_values(run_id, day, plan_index, turn, input_text),
                core.canonical_hash(transcript[:-1]),
                response["content"],
                core.canonical_json(graded["parsed"])
                if graded["parsed"] is not None
                else None,
                graded["format_valid"],
                graded["correct"],
                graded["decision_correct"],
                graded["reason_code_valid"],
                graded["expected_decision"],
                graded["expected_reason_code"],
                graded["actual_decision"],
                graded["actual_reason_code"],
                graded["employee_action"],
                graded["reply_length"],
                context_tokens,
                response.get("output_tokens"),
                upper_bound,
                response.get("latency_ms"),
                response.get("endpoint_model"),
                response.get("system_fingerprint"),
                utc_now(),
            ),
        )
        database.execute(
            """
            UPDATE days SET next_turn_index = ?, transcript_json = ?, status = 'running',
              context_verified = context_verified * ?, last_error = NULL
            WHERE run_id = ? AND day_id = ? AND condition = ?
            """,
            (
                plan_index + 1,
                core.canonical_json(transcript),
                context_verified,
                run_id,
                day["day_id"],
                day["condition"],
            ),
        )


def execute_day(
    database: sqlite3.Connection,
    bundle: dict[str, Any],
    run_id: str,
    day: sqlite3.Row,
    client: CompletionClient,
    master_seed: int,
) -> None:
    turn_plan = json.loads(day["turn_plan_json"])
    transcript = json.loads(day["transcript_json"])
    config = bundle["config"]
    model = config["model"]
    safe_limit = model["context_limit"] - model["context_safety_margin_tokens"]
    for plan_index in range(day["next_turn_index"], len(turn_plan)):
        turn = turn_plan[plan_index]
        if turn["kind"] == "event" and not turn["response_required"]:
            _record_filler(database, run_id, day, plan_index, turn, transcript)
            continue
        input_text = (
            core.claim_prompt(turn["claim"]["input"])
            if turn["kind"] == "task"
            else core.event_prompt(turn["message"])
        )
        request_messages = [*transcript, {"role": "user", "content": input_text}]
        upper_bound = core.context_token_upper_bound(
            request_messages, model["max_output_tokens"]
        )
        if upper_bound >= safe_limit:
            _record_context_failure(
                database, run_id, day, plan_index, turn, input_text, upper_bound
            )
            return
        request_seed = core.derive_seed(
            master_seed,
            day["day_id"],
            turn.get("task_index") or turn.get("event_index"),
            turn["kind"],
        )
        try:
            response = client.complete(request_messages, request_seed)
        except Exception as exc:
            _set_interrupted(database, run_id, day, str(exc))
            raise
        transcript.append({"role": "user", "content": input_text})
        graded = _model_turn_data(bundle, turn, response["content"])
        _record_model_turn(
            database,
            ModelTurnRecord(
                run_id=run_id,
                day=day,
                plan_index=plan_index,
                turn=turn,
                input_text=input_text,
                transcript=transcript,
                response=response,
                graded=graded,
                upper_bound=upper_bound,
            ),
        )
        context_tokens = response.get("context_tokens")
        if isinstance(context_tokens, int) and context_tokens >= safe_limit:
            with database:
                database.execute(
                    """
                    UPDATE days SET status = 'failed_context', context_verified = 0,
                      last_error = 'server token usage reached context safety limit'
                    WHERE run_id = ? AND day_id = ? AND condition = ?
                    """,
                    (run_id, day["day_id"], day["condition"]),
                )
                database.execute(
                    "UPDATE runs SET status = 'failed_context', last_error = 'server token usage reached context safety limit' WHERE run_id = ?",
                    (run_id,),
                )
            return
    with database:
        database.execute(
            """
            UPDATE days SET status = 'completed', completed_at = ?, last_error = NULL
            WHERE run_id = ? AND day_id = ? AND condition = ?
            """,
            (utc_now(), run_id, day["day_id"], day["condition"]),
        )


def execute_run(
    database: sqlite3.Connection,
    bundle: dict[str, Any],
    run_id: str,
    client: CompletionClient,
) -> dict[str, Any]:
    run = database.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if run is None:
        raise ValueError(f"unknown run_id: {run_id}")
    if run["status"] == "completed":
        return run_summary(database, run_id)
    with database:
        database.execute(
            "UPDATE runs SET status = 'running', last_error = NULL WHERE run_id = ?",
            (run_id,),
        )
    days = database.execute(
        "SELECT * FROM days WHERE run_id = ? ORDER BY day_index, execution_order",
        (run_id,),
    ).fetchall()
    for original in days:
        day = database.execute(
            "SELECT * FROM days WHERE run_id = ? AND day_id = ? AND condition = ?",
            (run_id, original["day_id"], original["condition"]),
        ).fetchone()
        if day["status"] == "completed":
            continue
        if day["status"] == "failed_context":
            break
        execute_day(database, bundle, run_id, day, client, run["seed"])
        current = database.execute(
            "SELECT status FROM days WHERE run_id = ? AND day_id = ? AND condition = ?",
            (run_id, day["day_id"], day["condition"]),
        ).fetchone()
        if current["status"] != "completed":
            break
    remaining = database.execute(
        "SELECT COUNT(*) FROM days WHERE run_id = ? AND status != 'completed'",
        (run_id,),
    ).fetchone()[0]
    if remaining == 0:
        with database:
            database.execute(
                "UPDATE runs SET status = 'completed', last_error = NULL WHERE run_id = ?",
                (run_id,),
            )
    return run_summary(database, run_id)


def run_summary(database: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    run = database.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if run is None:
        raise ValueError(f"unknown run_id: {run_id}")
    status_counts = {
        row["status"]: row["count"]
        for row in database.execute(
            "SELECT status, COUNT(*) AS count FROM days WHERE run_id = ? GROUP BY status ORDER BY status",
            (run_id,),
        )
    }
    turns = database.execute(
        "SELECT COUNT(*) FROM turns WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    return {
        "run_id": run_id,
        "status": run["status"],
        "day_statuses": status_counts,
        "recorded_turns": turns,
        "last_error": run["last_error"],
    }


def export_jsonl(
    database: sqlite3.Connection, run_id: str, output: Path, *, force: bool = False
) -> int:
    if output.exists() and not force:
        raise FileExistsError(f"refusing to overwrite: {output}")
    run = database.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if run is None:
        raise ValueError(f"unknown run_id: {run_id}")
    rows = database.execute(
        """
        SELECT t.*, d.day_index, d.status AS day_status, d.context_verified
        FROM turns AS t
        JOIN days AS d USING (run_id, day_id, condition)
        WHERE t.run_id = ?
        ORDER BY d.day_index, d.execution_order, t.plan_index
        """,
        (run_id,),
    ).fetchall()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            payload = {
                "run_id": row["run_id"],
                "day_id": row["day_id"],
                "condition": row["condition"],
                "severity": row["severity"],
                "turn_kind": row["kind"],
                "task_id": row["task_id"],
                "task_index": row["task_index"],
                "correct": _optional_bool(row["correct"]),
                "expected_decision": row["expected_decision"],
                "actual_decision": row["actual_decision"],
                "format_valid": _optional_bool(row["format_valid"]),
                "reason_code_valid": _optional_bool(row["reason_code_valid"]),
                "skipped": bool(row["skipped"]),
                "distance_from_last_event": row["distance_from_last_event"],
                "context_tokens": row["context_tokens"],
                "input_tokens": None,
                "input_words": row["input_words"],
                "output_tokens": row["output_tokens"],
                "latency_ms": row["latency_ms"],
                "event_id": row["event_id"],
                "employee_action": row["employee_action"],
                "input": row["input_text"],
                "output": row["raw_output"],
                "day_status": row["day_status"],
                "context_verified": bool(row["context_verified"]),
                "error_code": row["error_code"],
            }
            handle.write(core.canonical_json(payload) + "\n")
    return len(rows)


def _optional_bool(value: Any) -> bool | None:
    return None if value is None else bool(value)
