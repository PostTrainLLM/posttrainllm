export type ArtifactState =
  | "release-ready-metadata"
  | "release-ready-weights"
  | "candidate-current-best"
  | "report-ready-candidate"
  | "report-only"
  | "blocked"
  | "parked";

export type ArtifactMetric = {
  label: string;
  value: string;
  context: string;
};

export type ArtifactTable = {
  title: string;
  columns: string[];
  rows: string[][];
};

export type ArtifactComparison = {
  name: string;
  metric: string;
  score: string;
  size: string;
  comparability: "Direct" | "Directional" | "Not comparable";
  note: string;
  sourceHref?: string;
};

/// Outcome labels emitted by the report-card compiler. Only the two ship
/// labels may appear on a `ship` decision, so a report-only or rejected
/// artifact can never read as shipped. Mirrors
/// `fine_tune_report_card.OUTCOME_LABELS`.
export type ReportCardOutcome =
  | "shipped-specialist"
  | "routed-ship"
  | "report-only"
  | "rejected";

/// A published Fine-Tune Report Card for this artifact. Compiled offline from
/// recorded factory evidence by `scripts/build_fine_tune_report_card.py` and
/// served as a static page from `browser/public/report-cards/`.
///
/// This is a *link plus label* only: the report card itself is the source of
/// truth for its numbers, and duplicating them here would let the two surfaces
/// drift. It does not change weight-release policy — `state` still governs
/// what may be released.
export type ArtifactReportCard = {
  outcome: ReportCardOutcome;
  /// False whenever the ship decision cannot be traced end to end (historical
  /// values, unvalidated benchmark, unchecked leakage, open blockers).
  verified: boolean;
  href: string;
  jsonHref: string;
};

export type ArtifactEntry = {
  slug: string;
  title: string;
  eyebrow: string;
  state: ArtifactState;
  date: string;
  summary: string;
  lede: string;
  kind: string;
  tags: string[];
  metrics: ArtifactMetric[];
  comparisons: ArtifactComparison[];
  tables: ArtifactTable[];
  evidence: { label: string; href: string }[];
  blockers: { blocker: string; why: string; unblock: string }[];
  nextAction: string;
  reportCard?: ArtifactReportCard;
};

export const stateLabel: Record<ArtifactState, string> = {
  "release-ready-metadata": "Release-ready metadata",
  "release-ready-weights": "Release-ready weights",
  "candidate-current-best": "Current-best candidate",
  "report-ready-candidate": "Report-ready candidate",
  "report-only": "Report artifact",
  blocked: "Blocked",
  parked: "Parked",
};

export const outcomeLabel: Record<ReportCardOutcome, string> = {
  "shipped-specialist": "Shipped specialist",
  "routed-ship": "Shipped — routed only",
  "report-only": "Report only — no model to use",
  rejected: "Rejected candidate",
};

function reportCard(
  slug: string,
  outcome: ReportCardOutcome,
  verified: boolean,
): ArtifactReportCard {
  return {
    outcome,
    verified,
    href: `/report-cards/${slug}.html`,
    jsonHref: `/report-cards/${slug}.json`,
  };
}

export const artifacts: ArtifactEntry[] = [
  {
    slug: "qwen06-sql-routed-v1",
    title: "Qwen3-0.6B Routed SQL Specialist",
    eyebrow: "SQL factory POC",
    state: "report-ready-candidate",
    date: "2026-07-02",
    kind: "Routed adapter artifact",
    tags: ["SQL", "routing", "LoRA", "evals"],
    summary:
      "A two-adapter routed SQL artifact: public schema-only SQL routes to a b-mc2 adapter; local SQLite execution routes to a synthetic execution adapter.",
    lede:
      "This is the cleanest current proof of the factory thesis: a tiny 0.6B model can beat a small public SQL baseline on a frozen exact-match slice, but only the routed artifact survives both public and execution-style gates.",
    metrics: [
      { label: "Public exact", value: "0.531", context: "64-row b-mc2/sql-create-context slice" },
      { label: "T5-small baseline", value: "0.484", context: "same 64 public rows" },
      { label: "Synthetic execution", value: "0.860", context: "50 heldout SQLite rows" },
      { label: "Synthetic exact", value: "0.840", context: "same 50 heldout rows" },
    ],
    comparisons: [
      {
        name: "posttrainllm routed SQL v1",
        metric: "b-mc2 exact / synthetic exec",
        score: "0.531 / 0.860",
        size: "0.6B base + 2 routed LoRAs",
        comparability: "Direct",
        note: "Current local candidate; public exact and synthetic execution gates are both frozen.",
      },
      {
        name: "T5-small local baseline",
        metric: "b-mc2 exact",
        score: "0.484",
        size: "~60M",
        comparability: "Direct",
        note: "Same 64-row public slice; posttrainllm is +4.7 points exact on this narrow gate.",
        sourceHref: "https://huggingface.co/cssupport/t5-small-awesome-text-to-sql",
      },
      {
        name: "Defog SQLCoder-7B-2",
        metric: "Defog SQL-Eval category scores",
        score: "77.1-96%",
        size: "7B",
        comparability: "Directional",
        note: "Strong public SQL specialist, but reported as category-level Defog SQL-Eval scores rather than this b-mc2 slice.",
        sourceHref: "https://huggingface.co/defog/sqlcoder-7b-2",
      },
      {
        name: "Snowflake Arctic-Text2SQL-R1-7B",
        metric: "BIRD execution accuracy",
        score: "68.47%",
        size: "7B",
        comparability: "Not comparable",
        note: "Useful target class for public SQL execution; posttrainllm must add a BIRD/Spider execution gate before claiming this lane.",
        sourceHref: "https://www.snowflake.com/en/blog/engineering/arctic-text2sql-r1-sql-generation-benchmark/",
      },
      {
        name: "Snowflake Arctic-Text2SQL-R1-14B / 32B",
        metric: "BIRD execution accuracy",
        score: "70.04% / 71.83%",
        size: "14B / 32B",
        comparability: "Not comparable",
        note: "Shows the current public high bar: execution accuracy, not exact string match.",
        sourceHref: "https://www.snowflake.com/en/blog/engineering/arctic-text2sql-r1-sql-generation-benchmark/",
      },
    ],
    tables: [
      {
        title: "Adapter comparison",
        columns: ["Setup", "Public exact", "Synthetic exec", "Decision"],
        rows: [
          ["Public v4 only", "0.531", "0.240", "Route required"],
          ["Blend v1", "0.297", "0.560", "Reject"],
          ["Best static composition", "0.516", "0.460", "Reject"],
          ["BIRD + b-mc2 v5", "0.438", "0.280", "Reject"],
          ["Classifier-routed v1", "0.531", "0.860", "Current best"],
        ],
      },
      {
        title: "Router verification",
        columns: ["Check", "Result", "Evidence"],
        rows: [
          ["Unlabeled mixed rows", "114", "64 public / 50 synthetic"],
          ["Public route reason", "64", "known_public_source"],
          ["Synthetic route reason", "50", "sqlite_db_field"],
          ["Route confidence", ">= 0.99", "all smoke rows"],
        ],
      },
      {
        title: "Output-hygiene DPO retries (composed, 50 heldout rows)",
        columns: ["Run", "Execution", "Clean-SQL", "Decision"],
        rows: [
          ["Frozen baseline (SFT)", "0.860", "0.000", "reference"],
          ["2026-07-04 ref-free SimPO", "0.080", "0.000", "retry-training (collapse)"],
          ["2026-07-11 ref-anchored DPO", "0.900", "0.000", "retry-training"],
          ["2026-07-11 higher-pressure DPO", "0.920", "0.000", "retry-data"],
        ],
      },
    ],
    evidence: [
      { label: "SQL POC report", href: "/docs/specialists/b1-sql-poc" },
      { label: "Public artifact registry", href: "/docs/factory/public-artifacts" },
      { label: "Router smoke", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/evals/sql-routed-router-smoke.sh" },
      { label: "Router implementation", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/scripts/run_sql_routed_generate.py" },
    ],
    blockers: [
      {
        blocker: "Public execution benchmark missing",
        why: "b-mc2 exact match is useful, but serious SQL claims need execution accuracy on public DBs.",
        unblock: "Add BIRD Mini-Dev SQLite or Spider SQLite execution fixtures once the DB bundle is local.",
      },
      {
        blocker: "Output hygiene (raw completions carry an Answer:/Explanation: wrapper)",
        why: "Two reference-anchored DPO retries (2026-07-04 SimPO collapse → fixed; 2026-07-11 gentle + higher-pressure) improved execution 0.860 → 0.900 → 0.920 but left the clean-SQL raw rate at 0.000. The wrapper is a base-model prose prior a rank-4 preference adapter can't strip — the 108 SFT targets are already bare SELECT. Composed DPO is ruled out for hygiene.",
        unblock: "Generation-strength fix, not more DPO: stronger SFT (higher rank / more examples) or inference-time steering (constrained SELECT-prefix decoding / stop sequence). Execution is not the problem; only the wrapper is.",
      },
      {
        blocker: "Not a specialist package yet",
        why: "The adapters currently live under gitignored run folders, not package metadata.",
        unblock: "Package under specialists/ only after a ship decision on a public execution gate.",
      },
    ],
    nextAction:
      "Publish as a report artifact. Two hygiene DPO retries proved reference anchoring cures the SimPO collapse and even lifts execution to 0.920, but output hygiene needs a generation-strength fix (stronger SFT or constrained SELECT-prefix decoding), not more preference tuning. Do not present as a shipped SQL model until a public execution gate and clean-output gate pass.",
    reportCard: reportCard("qwen06-sql-routed-v1", "report-only", false),
  },
  {
    slug: "qwen3-4b-file-ops-distilled",
    title: "Qwen3-4B File-Ops Distilled",
    eyebrow: "First specialist package",
    state: "release-ready-weights",
    date: "2026-06-19",
    kind: "Specialist package",
    tags: ["agentic", "distillation", "file ops", "BFCL"],
    summary:
      "A routed 4B file-operation specialist distilled from frontier/gold trajectories, with the breadth regression disclosed in the package.",
    lede:
      "This is the strongest model win in the repo: a Mac-built specialist reaches 100% on the file-ops hard gate. It is also the clearest example of why routing is mandatory, because breadth drops outside the trained domain.",
    metrics: [
      { label: "File-ops hard gate", value: "100%", context: "up from 58% stock 4B" },
      { label: "Heldout file-ops", value: "95%", context: "hardgen heldout suite" },
      { label: "Breadth after tuning", value: "42.3%", context: "down from 59.6% stock" },
      { label: "Artifact size", value: "7.5GB", context: "local HF/MLX safetensors directory" },
    ],
    comparisons: [
      {
        name: "posttrainllm Qwen3-4B file-ops specialist",
        metric: "local file-ops hard gate",
        score: "100%",
        size: "4B, 7.5GB package",
        comparability: "Direct",
        note: "Domain specialist result; not a general BFCL leaderboard submission.",
      },
      {
        name: "Stock Qwen3-4B",
        metric: "same local file-ops hard gate",
        score: "58%",
        size: "4B",
        comparability: "Direct",
        note: "Before/after delta is +42 points on the frozen domain gate.",
      },
      {
        name: "Frontier calibration",
        metric: "same local file-ops hard gate",
        score: "~99-100%",
        size: "frontier API/teacher",
        comparability: "Direct",
        note: "Used as the ceiling check for whether the eval is a usable ruler.",
      },
      {
        name: "BFCL V4 public leader",
        metric: "overall BFCL V4 accuracy",
        score: "75.0%",
        size: "large public model",
        comparability: "Directional",
        note: "LLM Stats snapshot for Qwen3.7 Max; it marks BFCL-V4 rows as self-reported/unverified, so this is market context only.",
        sourceHref: "https://llm-stats.com/benchmarks/bfcl-v4",
      },
      {
        name: "BFCL V4 public average",
        metric: "overall BFCL V4 accuracy",
        score: "61.1%",
        size: "13 tracked models",
        comparability: "Directional",
        note: "LLM Stats reports 13 self-reported rows and 0 verified rows; posttrainllm still needs a full BFCL submission for direct comparison.",
        sourceHref: "https://llm-stats.com/benchmarks/bfcl-v4",
      },
      {
        name: "Qwen3.5-4B public BFCL-V4 row",
        metric: "overall BFCL V4 accuracy",
        score: "50.3%",
        size: "4B",
        comparability: "Directional",
        note: "Closest public 4B-class tool-calling row in the same LLM Stats snapshot, but still not the local file-ops gate.",
        sourceHref: "https://llm-stats.com/benchmarks/bfcl-v4",
      },
    ],
    tables: [
      {
        title: "Measured result",
        columns: ["Gate", "Stock", "Specialist", "Readout"],
        rows: [
          ["File-ops hard gate", "0.58", "1.00", "Domain win"],
          ["File-ops hardgen heldout", "-", "0.95", "Generalizes within file ops"],
          ["Out-of-domain breadth", "0.596", "0.423", "Regression; route only"],
        ],
      },
    ],
    evidence: [
      { label: "Model card", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/specialists/qwen3-4b-file-ops-distilled/model_card.md" },
      { label: "Hugging Face model", href: "https://huggingface.co/posttrainllm/qwen3-4b-file-ops-distilled" },
      { label: "Eval report", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/specialists/qwen3-4b-file-ops-distilled/eval_report.json" },
      { label: "Frontier parity writeup", href: "/docs/learn/tool-calling-frontier-parity" },
      { label: "Specialist registry", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/specialists/registry.json" },
    ],
    blockers: [
      {
        blocker: "Breadth regression",
        why: "The tuned model is wrong to use as a general planner.",
        unblock: "Keep all public copy routed-only and include the negative-transfer table.",
      },
    ],
    nextAction:
      "Keep routed-only warnings attached and add a consumer pull/load smoke before wiring this into any app.",
    reportCard: reportCard("qwen3-4b-file-ops-distilled", "routed-ship", false),
  },
  {
    slug: "qwen3-4b-rest-fused",
    title: "Qwen3-4B ReST Fused",
    eyebrow: "Teacher-free breadth recovery",
    state: "release-ready-weights",
    date: "2026-07-13",
    kind: "Research specialist package",
    tags: ["agentic", "ReST", "tool calling", "BFCL"],
    summary:
      "A teacher-free ReST candidate that preserves the 100% file-ops gate while recovering out-of-domain breadth above the stock 4B baseline.",
    lede:
      "This is the factory's first narrow ship decision from an existing measured candidate: the public weights, frozen fixtures, package, and routing boundary are preserved, while missing historical performance and trace evidence stays visible.",
    metrics: [
      { label: "File-ops hard gate", value: "100%", context: "held from the distilled depth anchor" },
      { label: "Breadth after ReST", value: "65%", context: "up from 59.6% stock 4B" },
      { label: "Breadth delta", value: "+5.4pp", context: "52 held-out non-file-ops tasks" },
      { label: "Paid API cost", value: "$0", context: "teacher-free local ReST iteration" },
    ],
    comparisons: [
      {
        name: "posttrainllm Qwen3-4B ReST",
        metric: "out-of-domain breadth",
        score: "65%",
        size: "4B, 8.06GB stored",
        comparability: "Direct",
        note: "Recorded on the same 52-task breadth fixture and prompt family as stock.",
      },
      {
        name: "Stock Qwen3-4B",
        metric: "same out-of-domain breadth fixture",
        score: "59.6%",
        size: "4B",
        comparability: "Direct",
        note: "The ReST iteration recovers breadth without giving up the file-ops depth gate.",
      },
      {
        name: "File-ops-only distilled 4B",
        metric: "same out-of-domain breadth fixture",
        score: "42.3%",
        size: "4B",
        comparability: "Direct",
        note: "Shows the negative transfer that the ReST iteration was designed to recover.",
      },
    ],
    tables: [
      {
        title: "Recorded result",
        columns: ["Gate", "Stock", "ReST candidate", "Readout"],
        rows: [
          ["File-ops hard gate", "0.58", "1.00", "Depth preserved"],
          ["Out-of-domain breadth", "0.596", "0.65", "+5.4 points over stock"],
          ["Latency / RAM / tok-s", "not preserved", "not preserved", "No estimated values"],
        ],
      },
    ],
    evidence: [
      { label: "Model card", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/specialists/qwen3-4b-rest-fused/model_card.md" },
      { label: "Hugging Face model", href: "https://huggingface.co/posttrainllm/qwen3-4b-rest-fused" },
      { label: "Eval report", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/specialists/qwen3-4b-rest-fused/eval_report.json" },
      { label: "ReST inventory", href: "/docs/sessions/2026-06-17-stepback-inventory-roi" },
      { label: "Specialist registry", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/specialists/registry.json" },
    ],
    blockers: [
      {
        blocker: "Historical performance evidence missing",
        why: "The original run did not preserve latency, RAM, tok-s, elapsed time, or raw predictions.",
        unblock: "Run a fresh product-specific gate only when a downstream integration justifies the heavy model work.",
      },
      {
        blocker: "Not a Pace planner",
        why: "Pace uses a different intent envelope and its own six-dimension ship gate.",
        unblock: "Re-distill on Pace's action surface and clear the Pace gate before runtime wiring.",
      },
    ],
    nextAction:
      "Keep this package research-only. Freeze a product-specific target before spending compute on another eval or training run.",
    reportCard: reportCard("qwen3-4b-rest-fused", "routed-ship", false),
  },
  {
    slug: "hf-specialist-model-archive-v1",
    title: "Hugging Face Specialist Model Archive v1",
    eyebrow: "Artifact storage cleanup",
    state: "report-only",
    date: "2026-07-03",
    kind: "Model archive index",
    tags: ["Hugging Face", "artifacts", "specialists", "cleanup"],
    summary:
      "The local specialist model cache was promoted to Hugging Face or deleted when safely re-downloadable from upstream repos.",
    lede:
      "This archive makes artifact storage explicit: unique posttrainllm model outputs live on Hugging Face, while plain upstream base-model caches are removed locally instead of being mirrored under posttrainllm.",
    metrics: [
      { label: "posttrainllm HF repos", value: "5", context: "unique specialist or converted model artifacts" },
      { label: "Local model cache", value: "cleared", context: "after upload/remote-size verification" },
      { label: "Storage policy", value: "HF first", context: "R2 remains optional private cache or legacy mirror" },
    ],
    comparisons: [
      {
        name: "Hugging Face artifact storage",
        metric: "public model distribution",
        score: "active",
        size: "model repos",
        comparability: "Direct",
        note: "Current target for public weights, adapters, and large specialist artifacts.",
        sourceHref: "https://huggingface.co/sarthakagrawal927",
      },
      {
        name: "Local Mac cache",
        metric: "durable artifact storage",
        score: "rejected",
        size: "~30GB cleaned",
        comparability: "Direct",
        note: "Useful during training, but not the system of record after a model is uploaded or known re-downloadable.",
      },
      {
        name: "Cloudflare R2",
        metric: "artifact storage role",
        score: "optional",
        size: "private cache / legacy mirror",
        comparability: "Directional",
        note: "No longer the default public artifact store for model weights.",
      },
    ],
    tables: [
      {
        title: "Uploaded posttrainllm artifacts",
        columns: ["Artifact", "HF repo", "Status", "Readout"],
        rows: [
          [
            "mt4b_fused",
            "qwen3-4b-file-ops-distilled",
            "release-ready",
            "File-ops hard gate 58% -> 100%; breadth regression disclosed",
          ],
          [
            "mt4b_rest_fused",
            "qwen3-4b-rest-fused",
            "archive",
            "ReST breadth recovery variant: depth 100%, breadth 65%",
          ],
          [
            "mt4b_mb_fused",
            "qwen3-4b-multibackend-distilled",
            "archive / failed attempt",
            "Negative-transfer comparison artifact: depth 100%, breadth 31%",
          ],
          [
            "vibethinker-3b-mlx",
            "vibethinker-3b-mlx",
            "archive",
            "Local MLX conversion of the VibeThinker 3B reasoning specialist",
          ],
          [
            "vibe_distill_fused",
            "vibethinker-3b-agentic-distilled",
            "archive",
            "posttrainllm distilled VibeThinker variant; needs eval promotion before product use",
          ],
        ],
      },
      {
        title: "Deleted upstream caches",
        columns: ["Local cache", "Upstream repo", "Reason"],
        rows: [
          ["mxbai-embed-large-v1", "mixedbread-ai/mxbai-embed-large-v1", "Public upstream cache; no posttrainllm delta"],
          ["qwen3-embedding-0.6b", "Qwen/Qwen3-Embedding-0.6B", "Public upstream cache; no posttrainllm delta"],
          ["qwen3-vl-2b-instruct", "Qwen/Qwen3-VL-2B-Instruct", "Public upstream cache; no posttrainllm delta"],
        ],
      },
    ],
    evidence: [
      { label: "File-ops HF model", href: "https://huggingface.co/posttrainllm/qwen3-4b-file-ops-distilled" },
      { label: "ReST HF model", href: "https://huggingface.co/posttrainllm/qwen3-4b-rest-fused" },
      { label: "Multibackend HF model", href: "https://huggingface.co/posttrainllm/qwen3-4b-multibackend-distilled" },
      { label: "VibeThinker MLX HF model", href: "https://huggingface.co/posttrainllm/vibethinker-3b-mlx" },
      { label: "VibeThinker distilled HF model", href: "https://huggingface.co/posttrainllm/vibethinker-3b-agentic-distilled" },
      { label: "HF storage policy", href: "/docs/factory/huggingface-artifact-storage" },
      { label: "Public artifacts policy", href: "/docs/factory/public-artifacts" },
    ],
    blockers: [
      {
        blocker: "Archive entries are not ship decisions",
        why: "Public weights can be useful as evidence without being the selected model for Pace or any product lane.",
        unblock: "Promote only candidates with a current factory run, eval report, package metadata, and routed-use decision.",
      },
      {
        blocker: "VibeThinker distilled eval needs promotion",
        why: "The weights are preserved, but the public artifact should not imply a measured win until the eval evidence is attached.",
        unblock: "Run the factory eval gate and publish a before/after report before using it as a specialist package.",
      },
    ],
    nextAction:
      "Use this as the public storage index. Future specialist pages should link to specific HF repos and keep failed variants visible as comparison evidence.",
  },
  {
    slug: "factory-run-schema-v1",
    title: "Factory Run Schema v1",
    eyebrow: "Process artifact",
    state: "report-only",
    date: "2026-07-02",
    kind: "Factory contract",
    tags: ["factory", "evals", "reports"],
    summary:
      "The canonical target -> data -> post-training -> eval -> package -> report shape for posttrainllm runs.",
    lede:
      "A specialist factory needs proof folders, not vibes. This schema defines the local run directory, required metrics, and decision vocabulary that every public artifact should eventually satisfy.",
    metrics: [
      { label: "Required files", value: "8", context: "config, dataset, train log, evals, report, artifact, decision" },
      { label: "Decisions", value: "6", context: "ship, reject, retry-data, retry-training, retry-eval, park" },
      { label: "First-class outputs", value: "5", context: "data, training, eval, package, report" },
    ],
    comparisons: [
      {
        name: "posttrainllm factory schema",
        metric: "required public run files",
        score: "8",
        size: "repo-local contract",
        comparability: "Direct",
        note: "Defines the minimum evidence bundle each future public model artifact must carry.",
      },
      {
        name: "Ad hoc model card only",
        metric: "before/after reproducibility",
        score: "weak",
        size: "single document",
        comparability: "Directional",
        note: "Useful for release notes, but insufficient for a factory claim without eval JSON, decision, and blockers.",
      },
    ],
    tables: [
      {
        title: "Run folder contract",
        columns: ["File", "Purpose", "Public relevance"],
        rows: [
          ["config.json", "Target, base, method, thresholds", "Explains what was attempted"],
          ["dataset.json", "Sources, rows, filtering, heldout", "Provenance"],
          ["eval-baseline.json", "Frozen baseline result", "Before number"],
          ["eval-candidate.json", "Candidate result", "After number"],
          ["decision.json", "Ship/reject/retry call", "Honest release status"],
        ],
      },
    ],
    evidence: [
      { label: "Run schema", href: "/docs/factory/run-schema" },
      { label: "Report template", href: "/docs/factory/reports" },
      { label: "Packaging rules", href: "/docs/factory/packaging" },
    ],
    blockers: [
      {
        blocker: "Needs a canonical rendered example",
        why: "The schema is real, but the website should show one complete run folder as the public example.",
        unblock: "Promote the SQL routed result into a small report-only rendered artifact.",
      },
    ],
    nextAction:
      "Turn the SQL routed result into the first website-native factory report that follows this schema.",
  },
  {
    slug: "browser-webgpu-speedup",
    title: "Browser WebGPU Training Speedup",
    eyebrow: "Browser performance artifact",
    state: "report-only",
    date: "2026-05-31",
    kind: "Benchmark report",
    tags: ["WebGPU", "WASM", "browser", "performance"],
    summary:
      "The original browser posttrainllm track: hand-written WebGPU kernels beat WASM SIMD more as model width grows.",
    lede:
      "This is the public proof that the browser playground was not just a demo. The same GPT-2-shaped training path runs through a benchmark harness and reports measured end-to-end speedups.",
    metrics: [
      { label: "WebGPU speedup", value: "12.1x", context: "vs WASM SIMD at d_model=256" },
      { label: "Small-width speedup", value: "2.6x", context: "d_model=96" },
      { label: "Browser track", value: "shipped", context: "WASM, SIMD, OPFS, WebGPU fast path" },
    ],
    comparisons: [
      {
        name: "posttrainllm WebGPU",
        metric: "training step speedup",
        score: "12.1x",
        size: "d_model=256 browser run",
        comparability: "Direct",
        note: "Directly measured against the repo's WASM SIMD path.",
      },
      {
        name: "posttrainllm WASM SIMD",
        metric: "training step speedup",
        score: "1.0x",
        size: "same browser model/config",
        comparability: "Direct",
        note: "Portable CPU baseline and fallback path.",
      },
      {
        name: "Native Mac runtimes",
        metric: "browser training benchmark",
        score: "not measured",
        size: "MLX/Metal class",
        comparability: "Not comparable",
        note: "Native runtimes are the right competition for production throughput, but not for the browser-learning artifact.",
      },
    ],
    tables: [
      {
        title: "Performance readout",
        columns: ["Variant", "Result", "Interpretation"],
        rows: [
          ["WASM SIMD", "baseline", "Portable CPU path"],
          ["WebGPU d_model=96", "2.6x", "GPU overhead still visible"],
          ["WebGPU d_model=256", "12.1x", "GPU dominates as width grows"],
        ],
      },
    ],
    evidence: [
      { label: "Performance journey", href: "/roadmap" },
      { label: "Performance docs", href: "/docs/performance" },
      { label: "Playground", href: "/playground" },
    ],
    blockers: [
      {
        blocker: "Not active factory center",
        why: "The browser track is valuable, but current active work is the Mac-local specialist factory.",
        unblock: "Use browser pages to present factory reports instead of expanding playground scope.",
      },
    ],
    nextAction:
      "Keep as a public performance artifact and cross-link it from factory reports when browser-local training matters.",
  },
  {
    slug: "memory64-browser-behemoth",
    title: "Memory64 Browser Behemoth Allocation",
    eyebrow: "Browser memory artifact",
    state: "report-only",
    date: "2026-05-31",
    kind: "Capability report",
    tags: ["Memory64", "browser", "WASM"],
    summary:
      "A WebAssembly Memory64 build lifted the browser model allocation ceiling past the old 4GB tab limit.",
    lede:
      "The Memory64 work is a useful public artifact because it has a crisp blocker, a measurable unlock, and a compatibility lesson: browsers can train larger local models, but feature detection matters.",
    metrics: [
      { label: "Allocated params", value: "473M", context: "browser tab, Memory64 build" },
      { label: "Allocation time", value: "3.7s", context: "measured Behemoth allocation" },
      { label: "Train step", value: "82.2s", context: "single sanity step after allocation" },
    ],
    comparisons: [
      {
        name: "posttrainllm Memory64 build",
        metric: "browser allocation ceiling",
        score: "473M params",
        size: ">4GB heap path",
        comparability: "Direct",
        note: "Shows the browser can allocate beyond the old wasm32 limit on supported runtimes.",
      },
      {
        name: "posttrainllm wasm32 build",
        metric: "browser allocation ceiling",
        score: "OOM around 4GB",
        size: "32-bit heap path",
        comparability: "Direct",
        note: "Baseline failure mode that Memory64 fixes.",
      },
    ],
    tables: [
      {
        title: "Memory ceiling",
        columns: ["Build", "Outcome", "Why"],
        rows: [
          ["WASM32", "OOM around 4GB heap", "32-bit pointer ceiling"],
          ["WASM Memory64", "473M params allocated", "64-bit memory address path"],
        ],
      },
    ],
    evidence: [
      { label: "Devlog writeup", href: "/devlog" },
      { label: "Browser playground", href: "/playground" },
    ],
    blockers: [
      {
        blocker: "Browser support variability",
        why: "Memory64 descriptor spelling and support differ across browser versions.",
        unblock: "Keep runtime feature detection and clear fallback copy.",
      },
    ],
    nextAction:
      "Keep this as a public technical artifact; do not make it active factory work unless a browser-run specialist needs it.",
  },
  {
    slug: "ane-m8-coreml-chain",
    title: "ANE M8 Core ML Chain",
    eyebrow: "Mac runtime artifact",
    state: "parked",
    date: "2026-06-17",
    kind: "Runtime experiment",
    tags: ["ANE", "Core ML", "Qwen3", "Mac"],
    summary:
      "A layer-chunked Core ML chain ran a Qwen3 28-block path on the Apple Neural Engine at about 17 tok/s.",
    lede:
      "This artifact maps the boundary between owning the model and using Apple’s acceleration stack. It is parked because capability comes from our model/eval loop; Core ML is a deployment target, not the product center.",
    metrics: [
      { label: "ANE decode", value: "17 tok/s", context: "Qwen3 28-block layer-chunked chain" },
      { label: "FoundationModels context", value: "4096", context: "too small for real tool catalogs" },
      { label: "Action grounding", value: "25%", context: "FoundationModels BFCL agentic full catalog" },
    ],
    comparisons: [
      {
        name: "posttrainllm Qwen3 Core ML chain",
        metric: "ANE decode",
        score: "17 tok/s",
        size: "28-block Qwen3 path",
        comparability: "Direct",
        note: "Runtime experiment only; capability still comes from posttrainllm weights and evals.",
      },
      {
        name: "Apple FoundationModels",
        metric: "action grounding / context",
        score: "25% / 4096 tokens",
        size: "Apple on-device model",
        comparability: "Directional",
        note: "Useful as a free local floor, but too weak to be the specialist capability dependency.",
      },
      {
        name: "posttrainllm active MLX path",
        metric: "specialist eval readiness",
        score: "active",
        size: "owned weights",
        comparability: "Directional",
        note: "Preferred competition lane: model quality first, runtime optimization second.",
      },
    ],
    tables: [
      {
        title: "Platform stance",
        columns: ["Path", "Decision", "Reason"],
        rows: [
          ["Apple FoundationModels", "Routing floor only", "Weak action grounding and short context"],
          ["Our weights -> Core ML", "Optional future", "Battery/perf optimization if capability is already solved"],
          ["MLX/posttrainllm runtime", "Active", "Own the model and eval gate"],
        ],
      },
    ],
    evidence: [
      { label: "ANE/CoreML parked lane", href: "/docs/parked/ane-coreml" },
      { label: "Apple on-device model notes", href: "/docs/learn/apple-on-device-foundation-models" },
      { label: "Project status", href: "https://github.com/PostTrainLLM/tinygpt/blob/main/PROJECT_STATUS.md" },
    ],
    blockers: [
      {
        blocker: "Capability dependency rejected",
        why: "Apple's model cannot be the differentiator; it is a free local floor at best.",
        unblock: "Only revive Core ML when a shipped posttrainllm specialist needs a battery/runtime optimization.",
      },
    ],
    nextAction:
      "Leave parked. Keep the numbers public as boundary-mapping evidence.",
  },
  {
    slug: "huge-decode-throughput",
    title: "Huge Preset Decode Throughput",
    eyebrow: "Mac runtime benchmark",
    state: "report-only",
    date: "2026-06-06",
    kind: "Benchmark report",
    tags: ["MLX", "decode", "Mac", "throughput"],
    summary:
      "The native Mac runtime reached high local decode throughput on the Huge preset, showing the serving path is viable for local eval loops.",
    lede:
      "This is a runtime artifact, not a model-quality claim. Its value is operational: local eval loops need throughput, stable serving, and cheap repeated generation.",
    metrics: [
      { label: "Huge decode", value: "696 tok/s", context: "96M/Huge preset, ctx 1024" },
      { label: "Mega pilot", value: "293 tok/s", context: "960M pilot" },
      { label: "Warm TTFT p99", value: "5.8ms", context: "reported runtime metric" },
    ],
    comparisons: [
      {
        name: "posttrainllm Huge preset",
        metric: "decode throughput",
        score: "696 tok/s",
        size: "96M",
        comparability: "Direct",
        note: "Local runtime baseline for cheap repeated eval/smoke loops.",
      },
      {
        name: "posttrainllm Mega pilot",
        metric: "decode throughput",
        score: "293 tok/s",
        size: "960M",
        comparability: "Direct",
        note: "Shows the throughput drop as local model size approaches specialist scale.",
      },
      {
        name: "External serving stacks",
        metric: "same benchmark",
        score: "not measured",
        size: "MLX/llama.cpp/Ollama class",
        comparability: "Not comparable",
        note: "Needs a shared prompt/config/device table before public competitive serving claims.",
      },
    ],
    tables: [
      {
        title: "Runtime numbers",
        columns: ["Metric", "Value", "Use"],
        rows: [
          ["Decode throughput", "696 tok/s", "Fast local eval/smoke loops"],
          ["Mega pilot throughput", "293 tok/s", "Boundary mapping for larger local models"],
          ["Warm TTFT p99", "5.8ms", "Interactive serving viability"],
        ],
      },
    ],
    evidence: [
      { label: "README headline metrics", href: "https://github.com/PostTrainLLM/tinygpt#headline-results" },
      { label: "Performance docs", href: "/docs/performance" },
    ],
    blockers: [
      {
        blocker: "Preset-specific",
        why: "The headline number is not a blanket claim for all HF models or specialists.",
        unblock: "Attach latency/RAM/tok-s numbers to each future specialist artifact.",
      },
    ],
    nextAction:
      "Use this as the baseline expectation for future artifact performance tables.",
  },
  {
    slug: "gallery-int4-browser-models",
    title: "4-bit Browser Gallery Models",
    eyebrow: "Distribution artifact",
    state: "parked",
    date: "2026-05-31",
    kind: "Browser gallery artifact",
    tags: ["gallery", "quantization", "browser"],
    summary:
      "The browser gallery ships fp16 and int4 variants so model downloads are smaller and cold-start is cheaper.",
    lede:
      "This artifact is less glamorous than the model work, but it is exactly the kind of public detail users care about: what ships, how big it is, and what tradeoff it makes.",
    metrics: [
      { label: "Gallery download", value: "~75MB -> ~20MB", context: "4-bit storage-side variants" },
      { label: "Compression", value: "~4x", context: "int4 gallery files vs fp16" },
      { label: "Browser-loadable", value: "yes", context: "unlike Mac-side multi-GB specialists" },
    ],
    comparisons: [
      {
        name: "posttrainllm int4 gallery file",
        metric: "download size",
        score: "~20MB",
        size: "4-bit storage",
        comparability: "Direct",
        note: "Smaller cold-load distribution artifact for browser demos.",
      },
      {
        name: "posttrainllm fp16 gallery file",
        metric: "download size",
        score: "~75MB",
        size: "fp16 storage",
        comparability: "Direct",
        note: "Simpler baseline with larger download size.",
      },
      {
        name: "Mac specialist packages",
        metric: "artifact size",
        score: "multi-GB",
        size: "HF/MLX safetensors",
        comparability: "Directional",
        note: "Different distribution lane; browser gallery compression should not be mixed with Mac specialist packaging.",
      },
    ],
    tables: [
      {
        title: "Distribution tradeoff",
        columns: ["Format", "Benefit", "Limit"],
        rows: [
          ["fp16", "Simple and accurate", "Larger download"],
          ["int4 storage", "Smaller cold load", "Not a training-speed win"],
        ],
      },
    ],
    evidence: [
      { label: "Roadmap gallery section", href: "/roadmap#gallery" },
      { label: "Gallery manifest", href: "/gallery/manifest.json" },
    ],
    blockers: [
      {
        blocker: "Not the active artifact channel",
        why: "Browser gallery models are not the same as Mac-side specialist packages.",
        unblock: "Keep separate from specialist registry; only connect through public reports.",
      },
    ],
    nextAction:
      "Keep as a public distribution artifact and avoid mixing it with Mac specialist packaging claims.",
  },
];

export function getArtifact(slug: string): ArtifactEntry | undefined {
  return artifacts.find((entry) => entry.slug === slug);
}
