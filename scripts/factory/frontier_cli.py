"""Shared subscription-CLI contract for bounded factory ceiling checks."""


def answer_schema():
    item = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"id": {"type": "string"}, "answer": {"type": "string"}},
        "required": ["id", "answer"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["answers"],
        "properties": {"answers": {"type": "array", "items": item}},
    }


def codex_command(schema, output, prompt, json_events=False):
    return [
        "codex",
        "exec",
        "--ephemeral",
        *(["--json"] if json_events else []),
        "-m",
        "gpt-6.1-sol",
        "-c",
        "model_reasoning_effort=medium",
        "-s",
        "read-only",
        "--skip-git-repo-check",
        "--output-schema",
        str(schema),
        "-o",
        str(output),
        prompt,
    ]
