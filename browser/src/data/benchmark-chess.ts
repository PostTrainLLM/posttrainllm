import replay from "./benchmarks/chess-development-v1.json";
import candidateMatrix from "./benchmarks/chess-candidate-model-matrix-v1.json";
export const clientData = JSON.stringify(replay).replaceAll("<", "\\u003c");
export const measured = replay.models.filter((model) => model.aggregate);
export const frontier = measured.find(
  (model) => model.role === "frontier-calibration-anchor",
);
export const local = measured.filter((model) => model.role.includes("local"));
export const candidateNames: Record<string, string> = {
  "random-legal": "Random legal",
  "gpt-5.5": "GPT-5.5",
  "gpt-5.4": "GPT-5.4",
  "gpt-5.4-mini": "GPT-5.4-mini",
  "claude-sonnet-5": "Claude Sonnet 5",
  "claude-opus-4-8": "Claude Opus 4.8",
  "glm-5.2": "Devin GLM-5.2",
};
export const formatPercent = (value: number) =>
  `${(value * 100).toFixed((value * 100) % 1 ? 1 : 0)}%`;
export const candidateRuns = candidateMatrix.runs.filter(
  (run) => run.requested_model !== "random-legal",
);
export const candidateRandom = candidateMatrix.runs.find(
  (run) => run.requested_model === "random-legal",
);
