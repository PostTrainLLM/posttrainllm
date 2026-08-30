#!/usr/bin/env python3
"""Build SQL candidate-selection rows from prompts and candidate predictions.

This is the sparse-reward curriculum bridge: before asking a small model to
generate SQL from scratch, ask it to choose the best SQL among plausible
candidates. The output rows are JSONL and can be used for eval, SFT, or
preference-style data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalize_sql(sql: str) -> str:
    s = sql.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", s, flags=re.I | re.S)
    if fence:
        s = fence.group(1).strip()
    select = re.search(r"\bselect\b", s, flags=re.I)
    if select:
        s = s[select.start():]
    semi = s.find(";")
    if semi >= 0:
        s = s[:semi + 1]
    s = re.sub(r"\s+", " ", s).strip().rstrip(";").lower()
    return s


def infer_slices(row: dict) -> list[str]:
    gold = str(row.get("gold_sql") or "")
    text = gold.lower()
    slices = [f"domain:{row.get('domain', 'unknown')}"]
    if " join " in text:
        slices.append("join")
    else:
        slices.append("single_table")
    if any(fn in text for fn in ("count(", "sum(", "avg(", "min(", "max(")):
        slices.append("aggregate")
    if " where " in text:
        slices.append("filter")
    if " group by " in text:
        slices.append("group_by")
    if " order by " in text:
        slices.append("order_by")
    return slices


def rows_by_id(rows: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i, row in enumerate(rows):
        key = str(row.get("id") or row.get("index") or i)
        out[key] = row
    return out


def candidate_id(source: str, sql: str) -> str:
    h = hashlib.sha1(f"{source}\n{sql}".encode("utf-8")).hexdigest()[:10]
    return f"{source}:{h}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--prompts", required=True, help="SQL prompt/dev JSONL with id, prompt, gold_sql")
    p.add_argument(
        "--candidate",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="candidate predictions JSONL; may be repeated",
    )
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--max-candidates", type=int, default=6)
    args = p.parse_args()

    prompts = read_jsonl(Path(args.prompts))
    prompt_by_id = rows_by_id(prompts)

    candidate_sets: list[tuple[str, dict[str, dict]]] = []
    for spec in args.candidate:
        if "=" not in spec:
            raise SystemExit(f"--candidate must be NAME=PATH, got {spec!r}")
        name, raw_path = spec.split("=", 1)
        candidate_sets.append((name, rows_by_id(read_jsonl(Path(raw_path)))))

    rng = random.Random(args.seed)
    out_rows: list[dict] = []
    for i, prompt_row in enumerate(prompts):
        key = str(prompt_row.get("id") or prompt_row.get("index") or i)
        gold_sql = str(prompt_row.get("gold_sql") or "")
        choices: list[dict] = []
        seen: set[str] = set()

        def add_choice(source: str, sql: str, is_gold: bool = False) -> None:
            norm = normalize_sql(sql)
            if not norm or norm in seen:
                return
            seen.add(norm)
            choices.append({
                "id": candidate_id(source, norm),
                "source": source,
                "sql": sql.strip(),
                "normalized_sql": norm,
                "is_gold": is_gold,
            })

        add_choice("gold", gold_sql, is_gold=True)
        for name, by_id in candidate_sets:
            row = by_id.get(key)
            if not row:
                continue
            add_choice(name, str(row.get("predicted_sql") or row.get("scored_sql") or row.get("output") or ""))

        if not any(c["is_gold"] for c in choices):
            raise SystemExit(f"row {key} lost its gold choice after normalization")
        if len(choices) > args.max_candidates:
            gold = [c for c in choices if c["is_gold"]]
            nongold = [c for c in choices if not c["is_gold"]]
            rng.shuffle(nongold)
            choices = gold + nongold[: max(0, args.max_candidates - len(gold))]

        rng.shuffle(choices)
        answer_index = next(j for j, c in enumerate(choices) if c["is_gold"])
        out_rows.append({
            "id": key,
            "task": "sql_candidate_selection",
            "prompt": prompt_row["prompt"],
            "question": prompt_row.get("question"),
            "domain": prompt_row.get("domain"),
            "db": prompt_row.get("db"),
            "slices": infer_slices(prompt_row),
            "choices": choices,
            "answer_index": answer_index,
            "answer_id": choices[answer_index]["id"],
            "answer_sql": gold_sql,
        })

    Path(args.out).write_text(
        "\n".join(json.dumps(r, separators=(",", ":"), sort_keys=True) for r in out_rows) + "\n"
    )
    print(f"wrote {len(out_rows)} SQL candidate-selection rows -> {args.out}")


if __name__ == "__main__":
    main()
