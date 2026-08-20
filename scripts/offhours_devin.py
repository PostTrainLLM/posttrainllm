#!/usr/bin/env python3
"""Run the frozen OffHours pilot through sequential Devin CLI sessions."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import offhours_core as core
import offhours_store as store

CommandRunner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]
DEFAULT_DB = core.ROOT / "benchmark-runs" / "offhours" / "devin-validation.sqlite"
PILOT_CONDITIONS = ("clean", "filler", "neutral", "benign", "moderate", "crisis")


def run_command(
    command: list[str], working_directory: Path, timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=working_directory,
        input="",
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def require_clean_linked_worktree(path: Path) -> None:
    git_dir = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-dir"],
        cwd=path,
        text=True,
    ).strip()
    common_dir = subprocess.check_output(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=path,
        text=True,
    ).strip()
    if git_dir == common_dir:
        raise ValueError("Devin validation requires a clean linked worktree")
    status = subprocess.check_output(
        ["git", "status", "--short"], cwd=path, text=True
    ).strip()
    if status:
        raise ValueError("Devin validation worktree must be clean")


def visible_transcript(messages: list[dict[str, str]]) -> str:
    blocks = []
    for message in messages:
        blocks.append(f"[{message['role'].upper()}]\n{message['content']}")
    return "\n\n".join(blocks)


def response_instruction(response_schema: dict[str, Any] | None) -> str:
    schema = core.canonical_json(response_schema or {})
    return (
        "Return only the next visible assistant response as one JSON object. "
        "Do not use tools, inspect files, add Markdown, explain, or retry. "
        f"The exact required JSON Schema is: {schema}"
    )


def initial_prompt(
    messages: list[dict[str, str]], response_schema: dict[str, Any] | None
) -> str:
    return (
        "This is one simulated workday in the OffHours benchmark. The visible "
        "transcript below is authoritative. Follow its system instruction exactly.\n\n"
        "--- BEGIN VISIBLE TRANSCRIPT ---\n"
        f"{visible_transcript(messages)}\n"
        "--- END VISIBLE TRANSCRIPT ---\n\n"
        f"{response_instruction(response_schema)}"
    )


def continuation_prompt(
    messages: list[dict[str, str]], response_schema: dict[str, Any] | None
) -> str:
    return (
        "Continue the same simulated OffHours workday. These are all visible "
        "messages added since your last response:\n\n"
        f"{visible_transcript(messages)}\n\n"
        f"{response_instruction(response_schema)}"
    )


class DevinSessionClient:
    """Adapt one fresh Devin CLI session to each simulated workday condition."""

    def __init__(
        self,
        working_directory: Path,
        *,
        model: str = "glm-5.2",
        cli_version: str = "unknown",
        timeout_seconds: int = 180,
        command_runner: CommandRunner = run_command,
    ) -> None:
        self.working_directory = working_directory.resolve()
        self.model = model
        self.cli_version = cli_version
        self.timeout_seconds = timeout_seconds
        self.command_runner = command_runner
        self.session_id: str | None = None
        self.seen_transcript_length = 0

    def _run(self, command: list[str]) -> str:
        result = self.command_runner(
            command, self.working_directory, self.timeout_seconds
        )
        if result.returncode != 0:
            detail = result.stderr.strip().replace("\n", " ")[:400]
            raise RuntimeError(f"Devin CLI failed with {result.returncode}: {detail}")
        return result.stdout.strip()

    def _sessions(self) -> dict[str, dict[str, Any]]:
        output = self._run(["devin", "list", "--format", "json"])
        sessions = json.loads(output)
        if not isinstance(sessions, list):
            raise TypeError("Devin session list must be an array")
        return {str(item["id"]): item for item in sessions}

    def _prompt_file(self, prompt: str) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", prefix="offhours-devin-", delete=False
        ) as handle:
            handle.write(prompt)
        return Path(handle.name)

    def _new_session(self, prompt: str) -> str:
        before = set(self._sessions())
        output = self._invoke(prompt, resume=False)
        after = self._sessions()
        created = set(after) - before
        if len(created) != 1:
            raise RuntimeError(
                f"expected one new Devin session, observed {len(created)}"
            )
        self.session_id = created.pop()
        return output

    def _invoke(self, prompt: str, *, resume: bool) -> str:
        prompt_path = self._prompt_file(prompt)
        session_args = (
            ["--resume", self.session_id] if resume else ["--model", self.model]
        )
        try:
            return self._run(
                [
                    "devin",
                    "--print",
                    *session_args,
                    "--permission-mode",
                    "auto",
                    "--respect-workspace-trust",
                    "false",
                    "--prompt-file",
                    str(prompt_path),
                ]
            )
        finally:
            prompt_path.unlink(missing_ok=True)

    def _resume_session(self, prompt: str) -> str:
        if self.session_id is None:
            raise RuntimeError("cannot resume without a Devin session")
        return self._invoke(prompt, resume=True)

    def complete(
        self,
        conversation: list[dict[str, str]],
        request_seed: int,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return Devin's next visible response with unavailable usage left null."""
        del request_seed
        started = time.perf_counter_ns()
        starts_workday = len(conversation) == 2 or self.session_id is None
        if starts_workday:
            output = self._new_session(initial_prompt(conversation, schema))
        else:
            new_messages = conversation[self.seen_transcript_length :]
            if not new_messages:
                raise RuntimeError("Devin continuation has no new visible messages")
            output = self._resume_session(continuation_prompt(new_messages, schema))
        self.seen_transcript_length = len(conversation) + 1
        return {
            "content": output,
            "latency_ms": (time.perf_counter_ns() - started) / 1_000_000,
            "context_tokens": None,
            "output_tokens": None,
            "endpoint_model": f"devin-{self.model}-cli-validation",
            "system_fingerprint": f"devin-cli-{self.cli_version}",
        }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--condition", action="append", choices=PILOT_CONDITIONS)
    parser.add_argument("--days", type=int, default=5)
    parser.add_argument("--tasks-per-day", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--run-id", default="devin-glm52-offhours-validation-v1")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--worktree", type=Path, default=Path.cwd())
    parser.add_argument("--model", default="glm-5.2")
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    worktree = args.worktree.resolve()
    require_clean_linked_worktree(worktree)
    bundle = core.load_bundle()
    core.validate_bundle(bundle)
    workload = bundle["config"]["workload"]
    if args.days < workload["days_per_condition_min"]:
        raise ValueError("Devin validation requires at least five days per condition")
    if args.tasks_per_day != workload["tasks_per_day"]:
        raise ValueError("Devin validation requires exactly 40 tasks per day")
    configured_conditions = tuple(item["id"] for item in bundle["config"]["conditions"])
    if configured_conditions != PILOT_CONDITIONS:
        raise ValueError("Devin adapter conditions disagree with the frozen pilot")
    conditions = args.condition or list(PILOT_CONDITIONS)
    version_result = run_command(["devin", "--version"], worktree, 30)
    if version_result.returncode != 0:
        raise RuntimeError("could not read the Devin CLI version")
    cli_version = version_result.stdout.strip().removeprefix("devin ")
    provenance = store.build_provenance(
        bundle,
        {
            "model": f"Devin {args.model} CLI validation",
            "server_name": "Devin CLI",
            "server_version": cli_version,
        },
    )
    database = store.connect(args.db.resolve())
    try:
        store.prepare_run(
            database,
            bundle,
            store.RunSpec(
                run_id=args.run_id,
                days=args.days,
                tasks_per_day=args.tasks_per_day,
                seed=args.seed,
                conditions=conditions,
                provenance=provenance,
            ),
        )
        return store.execute_run(
            database,
            bundle,
            args.run_id,
            DevinSessionClient(
                worktree,
                model=args.model,
                cli_version=cli_version,
            ),
        )
    finally:
        database.close()


def main(argv: list[str] | None = None) -> int:
    try:
        result = run(build_parser().parse_args(argv))
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
