import recipeRegistry from "../../../docs/recipes/registry.json";
type Recipe = { title: string; blurb: string; href: string; tag?: string };

export const recipes: Recipe[] = [
  {
    title: "Method vs recipe — the standard",
    href: "/docs/techniques/method-vs-recipe",
    tag: "start here",
    blurb:
      'Why "try DPO" isn\'t a plan. A recipe names the failure mode, the data, the eval gate, the slice gate, and the stop rule.',
  },
  {
    title: "Distill a specialist from a bigger model",
    href: "/docs/recipes/distill-specialist",
    blurb:
      "Teacher → student on a local machine. KL + NLL mix, temperature, α, rejection sampling on a checker.",
  },
  {
    title: "Distill function-calling: Phi-3-mini → tiny",
    href: "/docs/recipes/distillation-fc",
    blurb:
      "The full function-calling distillation arc — the recipe behind the frontier-parity result.",
  },
  {
    title: "From .atraj rollouts to a trained specialist",
    href: "/docs/recipes/from-traces",
    blurb:
      "Turn agent trajectories into SFT data: filter, dedupe (MinHash), emit ChatML, train. The self-improving loop.",
  },
  {
    title: "eval-gate as a CI / pre-commit gate",
    href: "/docs/recipes/eval-gate",
    blurb:
      "Wire a frozen eval into CI so a regression exits non-zero. The discipline that keeps main honest.",
  },
  {
    title: "Balanced training mix",
    href: "/docs/recipes/balanced-training-mix",
    blurb:
      "Mixing corpora without one domain drowning the others — ratio search with a micro-AutoMixer.",
  },
  {
    title: "Micro-AutoMixer for data-mix ratios",
    href: "/docs/recipes/automix",
    blurb:
      "Search data-mix ratios cheaply before committing compute to a full run.",
  },
  {
    title: "ScaleDown — extractive context compression",
    href: "/docs/recipes/b25-scaledown",
    blurb:
      "A specialist that compresses context extractively — smaller prompts, same answer.",
  },
  {
    title: "MLX export",
    href: "/docs/recipes/mlx-export",
    tag: "packaging",
    blurb:
      "Package a trained adapter/model for the MLX runtime — the last mile before it serves.",
  },
];

export const cookbooks: Recipe[] = [
  {
    title: "Character specialist",
    href: "/docs/recipes/cookbook-character-specialist",
    blurb: "Train a small model with a consistent voice/persona, end to end.",
  },
  {
    title: "Personal code specialist",
    href: "/docs/recipes/cookbook-personal-code-specialist",
    blurb: "A code model tuned on your own repos and conventions.",
  },
  {
    title: "posttrainllm + Pydantic AI",
    href: "/docs/recipes/cookbook-pydantic-ai",
    blurb:
      "Drive a local posttrainllm model from Pydantic AI via the OpenAI-compatible endpoint.",
  },
  {
    title: "posttrainllm + smolagents",
    href: "/docs/recipes/cookbook-smolagents",
    blurb:
      "Run smolagents against a local specialist — agents on one machine, no cloud.",
  },
];

export const registry: Recipe[] = [
  {
    title: "SQL technique lineage",
    href: "/docs/techniques/sql-technique-backlog",
    blurb:
      "The closed ledger of SQL recipes and their final dispositions — each tied to its reward surface.",
  },
  {
    title: "TrainLoop teardown",
    href: "/docs/techniques/trainloop-teardown",
    blurb:
      "What was learned (and stolen) from an external post-training platform.",
  },
  {
    title: "Audit 2026 technique inventory",
    href: "/docs/techniques/audit-inventory",
    blurb:
      "Row-level treatment of every technique in the 2026 audit: keep, experimental, flagged, delete.",
  },
];

export const completeRecipes = recipeRegistry.recipes;
