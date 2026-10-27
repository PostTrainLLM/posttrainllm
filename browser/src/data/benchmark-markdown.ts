import { projectAuthoredTemplate } from "../lib/template-markdown.mjs";
import { markdownTable } from "../lib/public-markdown";
import indexSource from "../pages/benchmarks/index.astro?raw";
import gameSource from "../pages/benchmarks/game-2048.astro?raw";
import chessSource from "../pages/benchmarks/chess.astro?raw";
import arenaSource from "../pages/benchmarks/arena.astro?raw";
import game from "./benchmarks/game-2048-pilot-v1.json";
import chess from "./benchmarks/chess-development-v1.json";
import arena from "./benchmarks/game-arena-candidate-v1.json";
import candidateMatrix from "./benchmarks/chess-candidate-model-matrix-v1.json";
import { strongest } from "./benchmark-index";
import { measuredModels, specialist } from "./benchmark-game-2048";
import {
  frontier,
  local,
  candidateRuns,
  candidateNames,
  candidateRandom,
  formatPercent,
} from "./benchmark-chess";
import {
  chessResult,
  scoreResult,
  policyNames,
  deltaPosition,
  chess as arenaChess,
  score as arenaScore,
} from "./benchmark-arena";

function main(source: string) {
  const match = source.match(/<main\b[\s\S]*?<\/main>/);
  if (!match) throw new Error("Missing authored main content");
  return match[0];
}
function tableSlot(source: string, expression: string, slot: string) {
  let found = false;
  const result = source.replace(/<table\b[\s\S]*?<\/table>/g, (table) => {
    if (!table.includes(expression)) return table;
    found = true;
    return `{${slot}}`;
  });
  if (!found) throw new Error(`Missing source table ${expression}`);
  return result;
}
const codeKey = (code: string) => code.replace(/\s+/g, " ");
const indexValues: Record<string, string | number> = {
  "chess.benchmark.name": chess.benchmark.name,
  "chess.benchmark.claim": chess.benchmark.claim,
  "replay.benchmark.name": game.benchmark.name,
  "replay.benchmark.claim": game.benchmark.claim,
  "strongest.name": strongest.name,
  "Math.round(strongest.aggregate.mean_score)": Math.round(
    strongest.aggregate.mean_score,
  ),
};
const gameResults = markdownTable(
  [
    "Policy",
    "Role",
    "Mean score",
    "Mean max tile",
    "Moves",
    "Invalid",
    "Median decision",
  ],
  [
    ...measuredModels.map((model) => [
      model.name + " · " + model.size,
      model.role === "small-base" ? "small base" : "general LLM",
      String(Math.round(model.aggregate.mean_score)),
      String(Math.round(model.aggregate.mean_maximum_tile)),
      model.aggregate.mean_moves.toFixed(1),
      String(model.aggregate.invalid_decisions),
      `${Math.round(model.aggregate.median_decision_latency_ms)} ms`,
    ]),
    [
      specialist?.name ?? "",
      "specialist",
      "Not trained — benchmark rejected at Gate 0",
      "",
      "",
      "",
      "",
    ],
  ],
);
const gameValues: Record<string, string> = {
  "replay.benchmark.claim": game.benchmark.claim,
  resultsTable: gameResults,
  "replay.reproduce.protocol": game.reproduce.protocol,
  "replay.reproduce.command_template": game.reproduce.command_template,
  "replay.reproduce.runtime": game.reproduce.runtime,
};
function gameResolve(code: string): string | undefined {
  if (code in gameValues) return gameValues[code];
  if (code.startsWith("Array.from({ length: 16 }")) return "";
  if (code.startsWith("replay.diagnostics.map("))
    return game.diagnostics
      .map(
        (item) =>
          `### ${item.name}\n\n${item.policy_id}\n\n${Math.round(item.mean_score)} mean score\n\n${item.explanation}\n\n**Built-in advantage:** ${item.structural_advantage}`,
      )
      .join("\n\n");
  if (code.startsWith("replay.benchmark.limitations.map("))
    return game.benchmark.limitations.map((item) => `- ${item}`).join("\n");
}
export const benchmarkMarkdown: Record<string, string> = {
  "/benchmarks": projectAuthoredTemplate(
    main(indexSource),
    (code) => indexValues[code],
  ),
  "/benchmarks/game-2048": projectAuthoredTemplate(
    tableSlot(main(gameSource), "measuredModels.map", "resultsTable"),
    gameResolve,
  ),
};
const candidateTable = markdownTable(
  [
    "Policy",
    "Coverage",
    "Exact",
    "Raw legal",
    "Executed legal",
    "Redirect",
    "Mean decision",
  ],
  candidateRuns.map((run) => [
    `${candidateNames[run.requested_model] ?? run.requested_model} · ${run.policy_id.includes("high-ceiling") ? "high reasoning" : run.backend}`,
    `${run.puzzles} / 40`,
    `${run.exact} / ${run.puzzles} · ${formatPercent(run.exact_move_accuracy)}`,
    formatPercent(run.raw_legal_rate),
    formatPercent(run.executed_legal_rate ?? 0),
    formatPercent(run.redirect_rate),
    run.mean_latency_ms === null
      ? "not exposed"
      : `${(run.mean_latency_ms / 1000).toFixed(2)} s`,
  ]),
);
function chessResolve(code: string): string | number | undefined {
  const key = codeKey(code);
  const values: Record<string, string | number> = {
    "replay.benchmark.claim": chess.benchmark.claim,
    candidateTable: candidateTable,
    "Math.round((frontier?.aggregate?.exact_move_accuracy ?? 0) * 100)":
      Math.round((frontier?.aggregate?.exact_move_accuracy ?? 0) * 100),
    'Math.round( (local.find((model) => model.size === "9B")?.aggregate ?.exact_move_accuracy ?? 0) * 100, )':
      Math.round(
        (local.find((model) => model.size === "9B")?.aggregate
          ?.exact_move_accuracy ?? 0) * 100,
      ),
    'Math.round( (local.find((model) => model.size === "4B")?.aggregate ?.exact_move_accuracy ?? 0) * 100, )':
      Math.round(
        (local.find((model) => model.size === "4B")?.aggregate
          ?.exact_move_accuracy ?? 0) * 100,
      ),
    "( replay.random.calibration.mean_exact_move_accuracy * 100 ).toFixed(2)": (
      chess.random.calibration.mean_exact_move_accuracy * 100
    ).toFixed(2),
    "candidateMatrix.label_authority.deep_verification.candidates":
      candidateMatrix.label_authority.deep_verification.candidates,
    'candidateRandom?.calibration ? formatPercent( candidateRandom.calibration.mean_exact_move_accuracy, ) : "not available"':
      candidateRandom?.calibration
        ? formatPercent(candidateRandom.calibration.mean_exact_move_accuracy)
        : "not available",
    "replay.reproduce.protocol": chess.reproduce.protocol,
    "replay.reproduce.puzzle_command": chess.reproduce.puzzle_command,
  };
  if (key in values) return values[key];
  if (code.startsWith("Array.from({ length: 64 }")) return "";
  if (code.startsWith("replay.benchmark.limitations.map("))
    return chess.benchmark.limitations.map((item) => `- ${item}`).join("\n");
}
benchmarkMarkdown["/benchmarks/chess"] = projectAuthoredTemplate(
  tableSlot(main(chessSource), "candidateRuns.map", "candidateTable"),
  chessResolve,
);
function arenaResolve(code: string): string | number | boolean | undefined {
  const key = codeKey(code);
  const checks = chessResult.qualification!.checks;
  const values: Record<string, string | number | boolean> = {
    "chessResult.rating_name": chessResult.rating_name,
    "chessResult.matches": chessResult.matches!,
    "chessResult.forfeits": chessResult.forfeits!,
    "chessResult.qualification.checks.minimum_total_matches":
      checks.minimum_total_matches!,
    "arena.config.qualification.head_to_head.minimum_total_matches":
      arena.config.qualification.head_to_head.minimum_total_matches,
    "chessResult.qualification.checks .minimum_matches_per_policy":
      checks.minimum_matches_per_policy!,
    "arena.config.qualification.head_to_head .minimum_matches_per_policy":
      arena.config.qualification.head_to_head.minimum_matches_per_policy,
    "chessResult.qualification.checks.maximum_forfeit_rate":
      checks.maximum_forfeit_rate!,
    "Math.round(chessResult.forfeit_rate * 100)": Math.round(
      chessResult.forfeit_rate! * 100,
    ),
    "chessResult.qualification.checks.color_balance": checks.color_balance!,
    "chessResult.qualification.checks.connected_pool": checks.connected_pool!,
    "chess.replay_path": arenaChess.replay_path,
    "score.replay_path": arenaScore.replay_path,
    "scoreResult.rating_name": scoreResult.rating_name,
    "`--zero:${deltaPosition(0)}`": `--zero:${deltaPosition(0)}`,
    "arena.status": arena.status,
  };
  if (key in values) return values[key];
  if (code.startsWith("chessResult.ratings.map("))
    return chessResult
      .ratings!.map(
        (row) =>
          `- **${policyNames[row.policy_id] ?? row.policy_id}:** ${row.rating.toFixed(0)} Arena Elo; ${row.status}. 95% interval: ${row.rating_interval_95.lower}–${row.rating_interval_95.upper}.`,
      )
      .join("\n");
  if (code.startsWith("scoreResult.entries.map((row, index)"))
    return scoreResult
      .entries!.map(
        (row) =>
          `- **${policyNames[row.policy_id] ?? row.policy_id}:** ${row.paired_mean_delta > 0 ? "+" : ""}${row.paired_mean_delta.toFixed(1)} paired delta; ${row.status}. 95% interval: ${row.paired_delta_interval_95.lower}–${row.paired_delta_interval_95.upper}.`,
      )
      .join("\n");
  if (code.startsWith("scoreResult.entries.map((row)"))
    return scoreResult
      .entries!.map(
        (row) =>
          `- ${policyNames[row.policy_id] ?? row.policy_id}: ${row.pairs} / ${arena.config.qualification.paired_score.minimum_complete_pairs_per_policy} pairs`,
      )
      .join("\n");
}
benchmarkMarkdown["/benchmarks/arena"] = projectAuthoredTemplate(
  main(arenaSource),
  arenaResolve,
);
