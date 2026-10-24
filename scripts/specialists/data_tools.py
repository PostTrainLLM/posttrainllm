"""Guided local imports and leakage-safe payloads; contract: specialist-labs.md."""

from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime

from common import digest


def csv_rows(content):
    reader = csv.reader(io.StringIO(content), strict=True)
    try:
        table = list(reader)
    except csv.Error as error:
        raise ValueError(f"invalid CSV: {error}") from None
    if len(table) < 2:
        raise ValueError("CSV needs a header and data rows")
    columns = [c.strip() for c in table[0]]
    if any(not c for c in columns) or len(set(columns)) != len(columns):
        raise ValueError("CSV column names must be nonempty and unique")
    values = [r for r in table[1:] if r and any(v.strip() for v in r)]
    if any(len(r) != len(columns) for r in values):
        raise ValueError("CSV rows must have the same number of columns as the header")
    rows = [dict(zip(columns, r)) for r in values]
    return rows


def parse(content, format):
    if not isinstance(content, str) or len(content.encode()) > 800_000:
        raise ValueError("import at most 800 KB of UTF-8 data")
    content = content.lstrip("\ufeff")
    if format == "csv":
        rows = csv_rows(content)
    elif format == "jsonl":
        rows = [json.loads(line) for line in content.splitlines() if line.strip()]
    elif format == "json":
        rows = json.loads(content)
        if isinstance(rows, dict):
            rows = rows.get("rows", rows.get("episodes"))
    else:
        raise ValueError("choose CSV, JSON or JSONL")
    return row_columns(rows)


def row_columns(rows):
    if not isinstance(rows, list) or not 1 <= len(rows) <= 10000:
        raise ValueError("import 1–10000 records")
    if any(not isinstance(r, dict) for r in rows):
        raise ValueError("each record must be an object")
    columns = list(dict.fromkeys(k for r in rows for k in r))
    if len(columns) > 64:
        raise ValueError("import at most 64 columns")
    return rows, columns


def inspect(payload):
    rows, columns = parse(payload["content"], payload["format"])
    result = {"columns": columns, "count": len(rows), "preview": rows[:5]}
    mapping = payload.get("mapping")
    if mapping is not None:
        mode = payload["mode"]
        if mode == "decision":
            dataset = decision_data(rows, mapping)
        elif mode == "forecast":
            dataset = forecast_data(rows, mapping, payload.get("horizon", 8))
        elif mode == "terminal":
            from terminal_model import examples

            examples(rows, 2048)
            dataset = {
                "train": {"episodes": rows},
                "summary": f"{len(rows)} terminal episodes; experimental",
            }
        else:
            raise ValueError("unknown data mode")
        result.update({"dataset": dataset, "sha256": digest(rows)})
    return result


def decision_row(row, index, mapping):
    from decision import validate_item

    if isinstance(row.get("options"), dict):
        item = dict(row)
    else:
        fields = mapping.get("options", [])
        if not 2 <= len(fields) <= 26 or len(set(fields)) != len(fields):
            raise ValueError("choose 2–26 different option columns")
        options = {
            chr(65 + i): str(row.get(c, "")).strip() for i, c in enumerate(fields)
        }
        answer = str(row.get(mapping.get("answer"), "")).strip()
        # Accept an assigned label, column name, or a unique option value.
        if answer in fields:
            answer = chr(65 + fields.index(answer))
        elif answer not in options:
            matches = [k for k, v in options.items() if v == answer]
            if len(matches) != 1:
                raise ValueError(
                    f"row {index + 1}: answer must identify exactly one option"
                )
            answer = matches[0]
        item = {
            "question": str(row.get(mapping.get("question"), "")).strip(),
            "options": options,
            "answer": answer,
        }
    item["id"] = str(item.get("id", f"row-{index + 1}"))
    validate_item(item)
    return item


def decision_data(rows, mapping):
    from decision_eval import split_rows

    items = [decision_row(row, index, mapping) for index, row in enumerate(rows)]
    if len({r["id"] for r in items}) != len(items):
        raise ValueError("record ids must be unique")
    groups = split_rows(items)
    heldout = groups["test"] + groups["regression"]
    return {
        "train": {"rows": groups["train"]},
        "prepare": {"rows": items},
        "score": {"rows": heldout},
        "predict": {"item": {k: v for k, v in heldout[0].items() if k != "answer"}},
        "compare": {"splits": groups},
        "ceiling": {"rows": heldout},
        "summary": " · ".join(f"{len(value)} {name}" for name, value in groups.items()),
    }


def check_timestamps(rows, timestamp):
    if timestamp:
        stamps = []
        for row in rows:
            value = str(row.get(timestamp, ""))
            try:
                stamp = float(value)
            except ValueError:
                stamp = datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            if not math.isfinite(stamp):
                raise ValueError("timestamps must be finite")
            stamps.append(stamp)
        if any(b <= a for a, b in zip(stamps, stamps[1:])):
            raise ValueError(
                "timestamps must be strictly increasing; sort and deduplicate first"
            )


def numeric_columns(rows, columns):
    values = []
    for column in columns:
        numbers = []
        for row in rows:
            value = row.get(column)
            number = None if value is None or str(value).strip() == "" else float(value)
            if number is not None and not math.isfinite(number):
                raise ValueError(
                    "use empty cells for missing observations, not NaN/Infinity"
                )
            numbers.append(number)
        values.append(numbers)
    return values


def forecast_data(rows, mapping, horizon):
    if (
        isinstance(horizon, bool)
        or not isinstance(horizon, int)
        or not 1 <= horizon <= 32
    ):
        raise ValueError("forecast horizon must be 1–32")
    columns = mapping.get("values", [])
    if not 1 <= len(columns) <= 32 or len(set(columns)) != len(columns):
        raise ValueError("choose 1–32 distinct numeric target columns")
    check_timestamps(rows, mapping.get("timestamp"))
    if len(rows) < 3 * horizon + 8:
        raise ValueError(
            f"need at least {3 * horizon + 8} chronological rows for train, test and regression"
        )
    values = numeric_columns(rows, columns)
    n = len(rows)
    train_origin = n - 3 * horizon
    train_row = {
        "id": "import-train",
        "context": [r[:train_origin] for r in values],
        "target": [r[train_origin : train_origin + horizon] for r in values],
    }
    series = {"id": "import-" + digest(values)[:12], "values": values}
    from forecast import inputs, matrix

    inputs(train_row, horizon)
    matrix(train_row["target"], "target")
    return {
        "train": {"rows": [train_row]},
        "predict": {"item": {"context": values}, "horizon": horizon},
        "backtest": {
            "series": series,
            "horizon": horizon,
            "origins": [n - 2 * horizon, n - horizon],
            "season": min(24, train_origin),
        },
        "compare": {
            "series": series,
            "horizon": horizon,
            "origins": [n - 2 * horizon, n - horizon],
            "season": min(24, train_origin),
            "train_rows": [train_row],
        },
        "summary": f"{len(columns)} targets · train through row {n - 2 * horizon} · {horizon} test + {horizon} regression time steps",
    }
