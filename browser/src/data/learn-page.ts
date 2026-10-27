import pathRegistry from "../../../docs/learn/path-registry.json";
import artifactJourney from "../../../docs/learn/artifact-journey.json";
import recipeRegistry from "../../../docs/recipes/registry.json";
export const REPO = "https://github.com/PostTrainLLM/posttrainllm";
export const source = (path: string) => `${REPO}/blob/main/${path}`;

export const fieldGuides = [
  {
    href: "/articles/how-to-cook-an-llm",
    label: "How to cook an LLM — interactive field guide",
  },
  { href: "/docs/cli-reference", label: "CLI lab reference" },
  { href: "/how-to-train-your-own-llm", label: "How to train your own LLM" },
  { href: "/fine-tune-llm-on-mac", label: "Fine-tune an LLM on a Mac" },
  { href: "/mlx-lora-fine-tuning", label: "MLX LoRA fine-tuning" },
  { href: "/docs/learn/competitive-landscape", label: "Competitive landscape" },
];

export const learningPaths = pathRegistry.paths;
export const docHref = (path: string) => `/${path.replace(/\.md$/, "")}`;
export const evidenceHref = (path: string) => {
  if (/^https?:\/\//.test(path)) return path;
  return path.endsWith(".md") ? docHref(path) : source(path);
};
export const artifactHref = (path: string) =>
  path.startsWith("/") ? path : evidenceHref(path);
export const pathCards = learningPaths.map((path) => ({
  ...path,
  recipes: recipeRegistry.recipes.filter(
    (recipe) => recipe.learning_path === path.id,
  ),
}));
export const readinessLegend = artifactJourney.readiness as Record<
  string,
  string
>;
export const artifactStages = artifactJourney.stages.map((stage) => ({
  ...stage,
  artifacts: stage.artifacts.map((artifact) => ({
    ...artifact,
    actions: [
      { name: "Build", ...artifact.build },
      { name: "Modify", ...artifact.modify },
      { name: "Tune", ...artifact.tune },
      { name: "Prove", ...artifact.evaluate },
      { name: "Package", ...artifact.package },
    ],
  })),
}));

export const chapters = [
  {
    number: "01",
    id: "target",
    title: "Choose a target worth compressing.",
    question: "Can a narrow capability be specified tightly enough to measure?",
    body: "Start with the task, the incumbent, and a frozen success bar—not a model. A frontier model first proves the ruler can represent the capability at all.",
    emits: "target.json + frozen baseline",
    docs: [
      { label: "Factory contract", href: "/docs/factory/overview" },
      { label: "Method vs recipe", href: "/docs/techniques/method-vs-recipe" },
    ],
    code: [
      {
        label: "FactoryRunCommand.swift",
        href: source("native-mac/Sources/TinyGPT/FactoryRunCommand.swift"),
      },
      {
        label: "EvalGate.swift",
        href: source("native-mac/Sources/TinyGPT/EvalGate.swift"),
      },
    ],
  },
  {
    number: "02",
    id: "data",
    title: "Build data for the failure, not the benchmark name.",
    question:
      "Which decisions are missing, and where did each training row come from?",
    body: "Trace review turns misses into slices. Synthetic teachers are useful only when provenance, deduplication, contamination checks, and a held-out gate stay attached to the rows.",
    emits: "dataset + manifest + provenance",
    docs: [
      { label: "Dataset inventory", href: "/docs/dataset-inventory" },
      {
        label: "Distillation recipe",
        href: "/docs/recipes/distill-specialist",
      },
    ],
    code: [
      {
        label: "DatasetRegistry.swift",
        href: source("native-mac/Sources/TinyGPTData/DatasetRegistry.swift"),
      },
      {
        label: "SFTCorpus.swift",
        href: source("native-mac/Sources/TinyGPTModel/SFTCorpus.swift"),
      },
    ],
  },
  {
    number: "03",
    id: "post-train",
    title: "Change the smallest model that can plausibly close the gap.",
    question:
      "Does SFT, preference training, or rejection sampling improve the frozen target?",
    body: "The readable Swift + MLX path remains the local reference. Every intervention is a recipe with exact data, adapter, optimizer, steps, and composition—not just a technique name.",
    emits: "adapter + recipe + training trace",
    docs: [
      {
        label: "Post-training factory",
        href: "/docs/factory/post-training-factory",
      },
      {
        label: "Tool-calling case study",
        href: "/docs/learn/tool-calling-frontier-parity",
      },
    ],
    code: [
      {
        label: "SFT.swift",
        href: source("native-mac/Sources/TinyGPT/SFT.swift"),
      },
      {
        label: "FactoryRunLifecycle.swift",
        href: source("native-mac/Sources/TinyGPTIO/FactoryRunLifecycle.swift"),
      },
    ],
  },
  {
    number: "04",
    id: "evaluate",
    title: "Make the candidate earn the claim.",
    question:
      "Did capability rise on the frozen target without unacceptable regressions?",
    body: "The same evaluator scores baseline and candidate. Slice metrics, legality, raw outputs, latency, RAM, throughput, and uncertainty stay visible; a benchmark whose frontier ceiling fails is rejected.",
    emits: "metrics + traces + regression gate",
    docs: [
      { label: "Evaluation protocol", href: "/docs/factory/eval-protocol" },
      { label: "Benchmark archive", href: "/benchmarks" },
    ],
    code: [
      {
        label: "EvalCompare.swift",
        href: source("native-mac/Sources/TinyGPT/EvalCompare.swift"),
      },
      {
        label: "EvalBFCL.swift",
        href: source("native-mac/Sources/TinyGPT/EvalBFCL.swift"),
      },
    ],
  },
  {
    number: "05",
    id: "package",
    title: "Package the boundary, not just the weights.",
    question:
      "Where is this specialist allowed to answer, and when must it redirect?",
    body: "A specialist artifact includes identity, base model, adapter, prompt contract, eval evidence, resource measurements, and routing constraints. Narrow depth can ship only with an honest boundary.",
    emits: "validated specialist package",
    docs: [
      { label: "Packaging contract", href: "/docs/factory/packaging" },
      { label: "Public specialists", href: "/artifacts" },
    ],
    code: [
      {
        label: "FactoryRun.swift",
        href: source("native-mac/Sources/TinyGPTIO/FactoryRun.swift"),
      },
      {
        label: "FineTuneReportCard.swift",
        href: source("native-mac/Sources/TinyGPTIO/FineTuneReportCard.swift"),
      },
    ],
  },
  {
    number: "06",
    id: "report",
    title: "End every run with a decision.",
    question: "Should this candidate ship, retry, redirect, or be rejected?",
    body: "The report binds score delta to regressions, cost, latency, RAM, throughput, missing measurements, and source hashes. Failed attempts remain part of the system because they change what gets tried next.",
    emits: "report card + ship / retry / reject",
    docs: [
      { label: "Reporting contract", href: "/docs/factory/reports" },
      { label: "Attempt ledger", href: "/docs/attempt-ledger" },
    ],
    code: [
      {
        label: "build_fine_tune_report_card.py",
        href: source("scripts/factory/build_fine_tune_report_card.py"),
      },
      {
        label: "factory_run_lifecycle.py",
        href: source("scripts/factory/factory_run_lifecycle.py"),
      },
    ],
  },
];

export const cases = [
  {
    state: "improved",
    tone: "live",
    title: "Tool calling: training helps a weak base",
    metric: "56 → 76 → 78",
    text: "The 1.7B arc moved from stock to SFT to GRPO. SFT did most of the work; GRPO added two points, then the approach plateaued below the stronger 4B.",
    href: "/docs/learn/tool-calling-frontier-parity",
    link: "Read the full arc",
  },
  {
    state: "routed",
    tone: "amber",
    title: "File ops: depth won, breadth regressed",
    metric: "58 → 100 / 59.6 → 42.3",
    text: "The distilled 4B aced the narrow hard gate while losing out-of-domain breadth. That is a routed specialist result, not a general model upgrade.",
    href: "/artifacts/qwen3-4b-file-ops-distilled",
    link: "Inspect the package",
  },
  {
    state: "rejected ruler",
    tone: "fail",
    title: "Character 2048: no intelligence gradient",
    metric: "1.058× best frontier ratio",
    text: "The strongest completed frontier attempt did not clear the frozen 1.10× bar over paired random legal play. Training was stopped and the replay was retained.",
    href: "/benchmarks/game-2048",
    link: "Watch the failed attempt",
  },
  {
    state: "candidate",
    tone: "amber",
    title: "Character Chess: promising, not frozen",
    metric: "65% frontier development score",
    text: "The first suite showed a real gradient, but the frontier did not approach the required ceiling. The expanded candidate pool remains for human review—not small-model grading.",
    href: "/benchmarks/chess",
    link: "Inspect candidate evidence",
  },
];

export const structuredData = {
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  name: "How the posttrainllm specialist factory works",
  description:
    "A source-linked walkthrough from target selection to data, post-training, evaluation, packaging, and an honest ship, retry, or reject report.",
  url: "https://posttrainllm.com/learn",
  isPartOf: { "@id": "https://posttrainllm.com/#app" },
  hasPart: chapters.map((chapter) => ({
    "@type": "TechArticle",
    position: Number(chapter.number),
    headline: chapter.title,
    url: `https://posttrainllm.com/learn#${chapter.id}`,
  })),
};
