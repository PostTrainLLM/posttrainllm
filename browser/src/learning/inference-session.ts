import type { InferenceSession } from "./inference-content";

type SessionInput = Omit<
  InferenceSession,
  | "id"
  | "routeId"
  | "week"
  | "day"
  | "number"
  | "readiness"
  | "lesson"
  | "nextSessionId"
>;

export function makeSession(day: number, data: SessionInput): InferenceSession {
  return {
    ...data,
    id: `inference-w01-d${String(day).padStart(2, "0")}`,
    routeId: "inference-systems-13w",
    week: 1,
    day,
    number: `W1 · D${day}`,
    readiness: "ready",
    lesson: data.sections.flatMap((section) => section.paragraphs ?? []),
    nextSessionId:
      day < 7 ? `inference-w01-d${String(day + 1).padStart(2, "0")}` : null,
  };
}
