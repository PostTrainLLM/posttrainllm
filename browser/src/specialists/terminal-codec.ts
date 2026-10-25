/** Exact port of terminal_codec.py; COPY always reads the previous screen. */
export interface Screen {
  lines: string[];
  cursor_row: number;
  cursor_col: number;
  visible: boolean;
}
export const T = {
  ROW: 256,
  BOS: 320,
  SCREEN: 321,
  SCREEN_END: 322,
  CURSOR: 323,
  INPUT: 324,
  INPUT_END: 325,
  OUTPUT: 326,
  OUTPUT_END: 327,
  COPY: 328,
  WAIT: 329,
  TEXT: 330,
  ROW_END: 331,
};
const range = (start: number, end: number) =>
  Array.from({ length: Math.max(0, end - start) }, (_, i) => start + i);

function validLines(lines: unknown): lines is string[] {
  if (
    !Array.isArray(lines) ||
    lines.length < 1 ||
    lines.length > 64 ||
    typeof lines[0] !== "string"
  )
    return false;
  const width = lines[0].length;
  return (
    width >= 1 &&
    width <= 255 &&
    lines.every(
      (line) =>
        typeof line === "string" &&
        line.length === width &&
        !/[^\x20-\x7e]/.test(line),
    )
  );
}

function validIndex(value: number, length: number): boolean {
  return Number.isInteger(value) && value >= 0 && value < length;
}

export function screen(value: unknown): Screen {
  const s = value as Screen;
  if (
    !s ||
    !validLines(s.lines) ||
    !validIndex(s.cursor_row, s.lines.length) ||
    !validIndex(s.cursor_col, s.lines[0].length) ||
    typeof s.visible !== "boolean"
  )
    throw new Error("Invalid terminal screen.");
  return { ...s, lines: [...s.lines] };
}

export function snapshot(s: Screen): number[] {
  return [
    T.BOS,
    T.SCREEN,
    s.lines.length,
    s.lines[0].length,
    ...s.lines.flatMap((line, i) => [
      T.ROW + i,
      T.TEXT,
      ...[...line].map((c) => c.charCodeAt(0)),
      T.ROW_END,
    ]),
    T.CURSOR,
    s.cursor_row,
    s.cursor_col,
    Number(s.visible),
    T.SCREEN_END,
  ];
}

export function eventTokens(event: Record<string, unknown>): number[] {
  if (
    Object.keys(event).length === 1 &&
    Array.isArray(event.keys) &&
    event.keys.length >= 1 &&
    event.keys.length <= 256 &&
    event.keys.every((n) => Number.isInteger(n) && n >= 0 && n <= 255)
  )
    return [T.INPUT, ...(event.keys as number[]), T.INPUT_END];
  if (
    Object.keys(event).length === 1 &&
    Number.isInteger(event.wait_ms) &&
    Number(event.wait_ms) >= 0 &&
    Number(event.wait_ms) <= 65535
  )
    return [
      T.WAIT,
      Math.floor(Number(event.wait_ms) / 256),
      Number(event.wait_ms) % 256,
      T.INPUT_END,
    ];
  throw new Error("Use 1–256 raw key bytes or a wait_ms from 0 to 65535.");
}

export function allowed(prefix: number[], s: Screen): number[] {
  let state = "start",
    lastRow = -1,
    col = 0,
    count = 0;
  function next(): number[] {
    switch (state) {
      case "start":
        return [T.OUTPUT];
      case "rows":
        return [
          ...range(T.ROW + lastRow + 1, T.ROW + s.lines.length),
          T.CURSOR,
        ];
      case "operation":
        return [T.COPY, T.TEXT];
      case "copy_source":
      case "cursor_row":
        return range(0, s.lines.length);
      case "after_copy":
        return [T.TEXT, T.ROW_END];
      case "text_col":
      case "cursor_col":
        return range(0, s.lines[0].length);
      case "text":
        return [
          ...(count ? [T.ROW_END] : []),
          ...(col + count < s.lines[0].length ? range(32, 127) : []),
        ];
      case "visible":
        return [0, 1];
      case "end":
        return [T.OUTPUT_END];
      case "done":
        return [];
      default:
        throw new Error("Invalid terminal grammar state.");
    }
  }
  const transitions: Record<string, string> = {
    start: "rows",
    copy_source: "after_copy",
    cursor_row: "cursor_col",
    cursor_col: "visible",
    visible: "end",
    end: "done",
  };
  for (const token of prefix) {
    if (!next().includes(token))
      throw new Error(`Invalid terminal token ${token}.`);
    if (state === "rows") {
      if (token === T.CURSOR) state = "cursor_row";
      else {
        lastRow = token - T.ROW;
        state = "operation";
      }
    } else if (state === "operation")
      state = token === T.COPY ? "copy_source" : "text_col";
    else if (state === "after_copy")
      state = token === T.ROW_END ? "rows" : "text_col";
    else if (state === "text_col") {
      col = token;
      count = 0;
      state = "text";
    } else if (state === "text") {
      if (token === T.ROW_END) state = "rows";
      else count++;
    } else state = transitions[state];
  }
  return next();
}

export function applyDelta(s: Screen, tokens: number[]): Screen {
  if (allowed(tokens, s).length || tokens.at(-1) !== T.OUTPUT_END)
    throw new Error("Incomplete terminal delta.");
  const lines = [...s.lines];
  let i = 1;
  while (tokens[i] !== T.CURSOR) {
    const row = tokens[i++] - T.ROW;
    if (tokens[i] === T.COPY) {
      lines[row] = s.lines[tokens[i + 1]];
      i += 2;
    }
    if (tokens[i] === T.TEXT) {
      const col = tokens[i + 1];
      i += 2;
      const end = tokens.indexOf(T.ROW_END, i);
      const text = String.fromCharCode(...tokens.slice(i, end));
      lines[row] =
        lines[row].slice(0, col) + text + lines[row].slice(col + text.length);
      i = end;
    }
    i++;
  }
  return screen({
    lines,
    cursor_row: tokens[i + 1],
    cursor_col: tokens[i + 2],
    visible: Boolean(tokens[i + 3]),
  });
}
