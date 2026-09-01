type PublicExperiment = {
  id: string;
  family: string;
  source: string;
};

type ExperimentFilter = {
  family?: string;
  search?: string;
  status?: string;
};

const benchmarkHrefs: Record<string, string> = {
  "character-chess-benchmark-candidate": "/benchmarks/chess",
  "character-2048-frontier-screen": "/benchmarks/game-2048",
  "character-game-arena-candidate": "/benchmarks/arena",
};

const artifactHrefs: Record<string, string> = {
  "archive-model": "/artifacts/hf-specialist-model-archive-v1",
  "browser-memory64-large-presets": "/artifacts/memory64-browser-behemoth",
  "browser-speedup-headline-curve": "/artifacts/browser-webgpu-speedup",
  "factory-run-schema": "/artifacts/factory-run-schema-v1",
  "fileops-qwen3-4b-distilled": "/artifacts/qwen3-4b-file-ops-distilled",
  "fileops-qwen3-4b-multibackend-distilled":
    "/artifacts/qwen3-4b-multibackend-distilled",
  "fileops-qwen3-4b-rest-fused": "/artifacts/qwen3-4b-rest-fused",
  "needle2-base-public-gate": "/artifacts/needle2-tool-selection",
  "needle2-task-catalog-ablation": "/artifacts/needle2-tool-selection",
  "pace-planner-v8": "/artifacts/pace-intent-router-v8",
  "parakeet-wgsl-browser-asr-smoke": "/artifacts/parakeet-wgsl-browser-asr",
  "sql-routed-v1": "/artifacts/qwen06-sql-routed-v1",
  "vibethinker-3b-agentic-distilled":
    "/artifacts/vibethinker-3b-agentic-distilled",
};

export const learningPathByFamily: Record<string, string> = {
  "apple-fm": "browser-and-mac-runtime",
  "archive-model": "quantization-and-packaging",
  architecture: "architecture-and-kernels",
  autocorrect: "post-training",
  "browser-product": "browser-and-mac-runtime",
  chess: "evaluation-and-factory",
  "factory-docs": "evaluation-and-factory",
  "file-ops": "post-training",
  "game-benchmarks": "evaluation-and-factory",
  offhours: "evaluation-and-factory",
  "pace-planner": "evaluation-and-factory",
  "runtime-perf": "runtime-and-agents",
  sql: "post-training",
  "tool-calling": "post-training",
};

const recipeHrefByFamily: Record<string, string> = {
  architecture: "/docs/techniques/moe",
  autocorrect: "/docs/factory/autocorrect-adapter-recipe",
  "file-ops": "/docs/recipes/distillation-fc",
  "pace-planner": "/docs/recipes/pace-planner",
  sql: "/docs/techniques/sql-technique-backlog",
  "tool-calling": "/docs/recipes/distillation-fc",
};

const recipeHrefByAttempt: Record<string, string> = {
  "needle2-base-public-gate": "/docs/techniques/needle2-baseline-review",
  "needle2-task-catalog-ablation": "/docs/techniques/needle2-baseline-review",
  "parakeet-wgsl-browser-asr-smoke":
    "/docs/techniques/parakeet-wgsl-browser-smoke",
};

export function experimentPublicHref(attempt: PublicExperiment): string {
  const benchmarkHref = benchmarkHrefs[attempt.id];
  if (benchmarkHref) return benchmarkHref;
  const artifactHref = artifactHrefs[attempt.id];
  if (artifactHref) return artifactHref;
  if (attempt.id.startsWith("offhours-")) {
    return "/artifacts/offhours-context-interference";
  }
  if (attempt.source.startsWith("docs/")) {
    return `/${attempt.source.replace(/\.md$/, "")}`;
  }
  return "/docs/attempt-ledger";
}

export function experimentLearningHref(attempt: PublicExperiment): string {
  const path = learningPathByFamily[attempt.family];
  return path ? `/learn#path-${path}` : "/learn";
}

export function experimentRecipeHref(attempt: PublicExperiment): string {
  return (
    recipeHrefByAttempt[attempt.id] ??
    recipeHrefByFamily[attempt.family] ??
    "/recipes#complete-registry"
  );
}

export function experimentMatches(
  candidate: ExperimentFilter,
  query: string,
  family: string,
  status: string,
): boolean {
  if (query && !candidate.search?.includes(query)) return false;
  if (family && candidate.family !== family) return false;
  if (status && candidate.status !== status) return false;
  return true;
}
