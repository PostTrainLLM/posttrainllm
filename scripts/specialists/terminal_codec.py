"""333-token monochrome terminal state/delta oracle; no shell execution.

Independent WorldTUI-inspired byte/row protocol. COPY always reads the old
frame. Contract: docs/factory/specialist-labs.md; not WorldTUI-compatible weights.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

ROW = 256
(
    BOS,
    SCREEN,
    SCREEN_END,
    CURSOR,
    INPUT,
    INPUT_END,
    OUTPUT,
    OUTPUT_END,
    COPY,
    WAIT,
    TEXT,
    ROW_END,
    PAD,
) = range(320, 333)
VOCAB_SIZE = 333


@dataclass(frozen=True)
class Screen:
    lines: tuple[str, ...]
    cursor_row: int = 0
    cursor_col: int = 0
    visible: bool = True

    def __post_init__(self):
        if not 1 <= len(self.lines) <= 64 or not 1 <= len(self.lines[0]) <= 255:
            raise ValueError("screen must be 1–64 rows by 1–255 columns")
        if any(
            len(line) != self.cols or any(not 32 <= ord(char) <= 126 for char in line)
            for line in self.lines
        ):
            raise ValueError(
                "screen lines must have equal width and printable ASCII cells"
            )
        if (
            not 0 <= self.cursor_row < self.rows
            or not 0 <= self.cursor_col < self.cols
            or not isinstance(self.visible, bool)
        ):
            raise ValueError("invalid cursor")

    @property
    def rows(self):
        return len(self.lines)

    @property
    def cols(self):
        return len(self.lines[0])

    def as_dict(self):
        return {
            "lines": list(self.lines),
            "cursor_row": self.cursor_row,
            "cursor_col": self.cursor_col,
            "visible": self.visible,
        }

    @classmethod
    def from_dict(cls, value):
        return cls(
            tuple(value["lines"]),
            value["cursor_row"],
            value["cursor_col"],
            value["visible"],
        )

    @classmethod
    def custom(cls, text="lab@mac:~$ ", rows=8, cols=48):
        if not 1 <= rows <= 64 or not 1 <= cols <= 255:
            raise ValueError("invalid screen size")
        content = text.split("\n")
        if len(content) > rows or any(len(line) > cols for line in content):
            raise ValueError("custom screen exceeds dimensions")
        padded = tuple(line.ljust(cols) for line in content) + (" " * cols,) * (
            rows - len(content)
        )
        return cls(padded, len(content) - 1, min(len(content[-1]), cols - 1))


def snapshot(screen):
    tokens = [BOS, SCREEN, screen.rows, screen.cols]
    for index, line in enumerate(screen.lines):
        tokens.extend([ROW + index, TEXT, *line.encode("ascii"), ROW_END])
    return tokens + [
        CURSOR,
        screen.cursor_row,
        screen.cursor_col,
        int(screen.visible),
        SCREEN_END,
    ]


def event_tokens(event):
    if set(event) == {"keys"}:
        keys = bytes(event["keys"])
        if not 1 <= len(keys) <= 256:
            raise ValueError("a key event must contain 1–256 raw bytes")
        return [INPUT, *keys, INPUT_END]
    if (
        set(event) == {"wait_ms"}
        and isinstance(event["wait_ms"], int)
        and 0 <= event["wait_ms"] <= 65535
    ):
        value = event["wait_ms"]
        return [WAIT, value // 256, value % 256, INPUT_END]
    raise ValueError("event must contain raw keys or wait_ms")


def allowed(prefix, screen):
    """Return exact next-token grammar, rejecting malformed/incomplete deltas.

    Each row is emitted at most once in increasing order. Text occupies one
    contiguous span; COPY may precede it. Cursor is emitted after all rows.
    """
    state, last_row, col, count = "start", -1, 0, 0
    for token in prefix:
        valid = _allowed(state, last_row, col, count, screen)
        if token not in valid:
            raise ValueError(f"invalid terminal token {token} in state {state}")
        if state == "rows":
            if token == CURSOR:
                state = "cursor_row"
            else:
                last_row, state = token - ROW, "operation"
        elif state == "after_copy":
            state = "rows" if token == ROW_END else "text_col"
        elif state == "text_col":
            col, count, state = token, 0, "text"
        elif state == "text":
            if token == ROW_END:
                state = "rows"
            else:
                count += 1
        else:
            state = next_state(state, token)
    return _allowed(state, last_row, col, count, screen)


def next_state(state, token):
    if state == "operation":
        return "copy_source" if token == COPY else "text_col"
    return {
        "start": "rows",
        "copy_source": "after_copy",
        "cursor_row": "cursor_col",
        "cursor_col": "visible",
        "visible": "end",
        "end": "done",
    }[state]


def _allowed(state, last_row, col, count, screen):
    if state == "start":
        return [OUTPUT]
    if state == "rows":
        return [*range(ROW + last_row + 1, ROW + screen.rows), CURSOR]
    if state == "operation":
        return [COPY, TEXT]
    if state == "copy_source" or state == "cursor_row":
        return list(range(screen.rows))
    if state == "after_copy":
        return [TEXT, ROW_END]
    if state == "text_col" or state == "cursor_col":
        return list(range(screen.cols))
    if state == "text":
        return ([ROW_END] if count else []) + (
            list(range(32, 127)) if col + count < screen.cols else []
        )
    return {"visible": [0, 1], "end": [OUTPUT_END], "done": []}[state]


def apply_delta(screen, tokens):
    if allowed(tokens, screen) or not tokens or tokens[-1] != OUTPUT_END:
        raise ValueError("terminal delta is incomplete")
    lines = list(screen.lines)
    index = 1
    while tokens[index] != CURSOR:
        row = tokens[index] - ROW
        index += 1
        if tokens[index] == COPY:
            lines[row] = screen.lines[tokens[index + 1]]
            index += 2
        if tokens[index] == TEXT:
            col = tokens[index + 1]
            index += 2
            end = tokens.index(ROW_END, index)
            text = bytes(tokens[index:end]).decode("ascii")
            lines[row] = lines[row][:col] + text + lines[row][col + len(text) :]
            index = end
        index += 1  # ROW_END
    return Screen(
        tuple(lines), tokens[index + 1], tokens[index + 2], bool(tokens[index + 3])
    )


def delta(before, after):
    if (before.rows, before.cols) != (after.rows, after.cols):
        raise ValueError("resize requires a fresh snapshot")
    tokens = [OUTPUT]
    for index, line in enumerate(after.lines):
        if line == before.lines[index]:
            continue
        tokens.append(ROW + index)
        if line in before.lines:
            tokens.extend([COPY, before.lines.index(line), ROW_END])
            continue
        changed = [
            i for i, (a, b) in enumerate(zip(before.lines[index], line)) if a != b
        ]
        start, end = changed[0], changed[-1] + 1
        tokens.extend([TEXT, start, *line[start:end].encode("ascii"), ROW_END])
    return tokens + [
        CURSOR,
        after.cursor_row,
        after.cursor_col,
        int(after.visible),
        OUTPUT_END,
    ]


def corrupted(screen, row, col, character):
    """One visible-cell perturbation for bounded correction tests/data."""
    lines = list(screen.lines)
    line = lines[row]
    lines[row] = line[:col] + character + line[col + 1 :]
    return replace(screen, lines=tuple(lines))
