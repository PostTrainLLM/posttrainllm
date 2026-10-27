import arena from "./benchmarks/game-arena-candidate-v1.json";
export const chess = arena.games.find(
  (game) => game.competition_family === "head-to-head",
)!;
export const score = arena.games.find(
  (game) => game.competition_family === "paired-score",
)!;
export const chessResult = chess.result;
export const scoreResult = score.result;
if (
  !chessResult.ratings ||
  !chessResult.qualification ||
  chessResult.forfeit_rate == null ||
  !scoreResult.entries
) {
  throw new Error(
    "Arena evidence lacks required head-to-head or paired-score results",
  );
}

export const policyNames: Record<string, string> = {
  "qwen3-4b-instruct-2507-4bit": "Qwen3 4B",
  "qwen3.5-9b-mlx-4bit": "Qwen3.5 9B",
  "claude-sonnet-5": "Claude Sonnet 5",
  "claude-opus-4-8": "Claude Opus 4.8",
};
export const eloFloor = 1200;
export const eloCeiling = 1800;
export const eloPosition = (rating: number) =>
  `${Math.max(0, Math.min(100, ((rating - eloFloor) / (eloCeiling - eloFloor)) * 100))}%`;
export const deltaFloor = -20;
export const deltaCeiling = 30;
export const deltaPosition = (value: number) =>
  `${Math.max(0, Math.min(100, ((value - deltaFloor) / (deltaCeiling - deltaFloor)) * 100))}%`;
export const clientData = JSON.stringify(arena).replaceAll("<", "\\u003c");
