/**
 * Public acknowledgments. The study registry owns dispositions and local
 * evidence; this list groups writeups by product and adds primary links.
 */
import studyRegistry from "../../../docs/studies/registry.json";

export interface Inspiration {
  slug: string;
  name: string;
  thread: string;
  opening: string;
  source: { label: string; href: string };
  studyIds: string[];
  localRead?: string;
  boundary?: string;
  evidence?: { label: string; href: string }[];
  reading?: { label: string; href: string }[];
}

export const inspirations: Inspiration[] = [
  {
    slug: "trainloop-ai",
    name: "TrainLoop AI",
    thread: "Research loops",
    opening:
      "TrainLoop made us pay attention to the attempts that failed, the slices that changed, and the traces behind a score. That discipline shaped how this small lab records its own work.",
    source: { label: "TrainLoop AI", href: "https://www.trainloop.ai/" },
    studyIds: [
      "trainloop-ai",
      "trainloop-nollamd",
      "trainloop-oapl",
      "trainloop-lora-geometry",
      "trainloop-mercor-coding-agent",
    ],
  },
  {
    slug: "baseten",
    name: "Baseten",
    thread: "Factory framing",
    opening:
      "Baseten's account of post-training helped us see the work as a full system: data, reward, performance, evaluation, and delivery. We translated that frame into a factory sized for one Mac.",
    source: {
      label: "Baseten on post-training",
      href: "https://www.baseten.co/about-us/#post-training",
    },
    studyIds: ["baseten-post-training"],
  },
  {
    slug: "hugging-face",
    name: "Hugging Face",
    thread: "Open baselines",
    opening:
      "The model hub made small public SQL specialists available as real baselines. Those models helped us ask whether a local result survives comparison on the same task and rules.",
    source: {
      label: "Hugging Face models",
      href: "https://huggingface.co/models",
    },
    studyIds: ["hugging-face-sql-specialists"],
  },
  {
    slug: "sqlcoder",
    name: "SQLCoder and Arctic Text2SQL",
    thread: "Evaluation",
    opening:
      "These SQL projects raised the standard of evidence. A query that resembles the reference text is less useful than a query that executes correctly against a serious shared benchmark.",
    source: {
      label: "Defog SQLCoder",
      href: "https://github.com/defog-ai/sqlcoder",
    },
    studyIds: ["defog-sqlcoder-arctic-text2sql"],
    reading: [
      {
        label: "Arctic Text2SQL",
        href: "https://www.snowflake.com/en/blog/engineering/arctic-text2sql-r1-sql-generation-benchmark/",
      },
    ],
  },
  {
    slug: "apple-foundation-models",
    name: "Apple Foundation Models",
    thread: "Mac capability",
    opening:
      "Apple's on-device model gave us a useful floor to measure. Its limits on our action-grounding tasks clarified why the lab keeps its own weights and evaluation gate.",
    source: {
      label: "Apple Foundation Models framework",
      href: "https://developer.apple.com/documentation/foundationmodels",
    },
    studyIds: ["apple-on-device-foundation-models"],
  },
  {
    slug: "castform",
    name: "Castform",
    thread: "Training loops",
    opening:
      "Castform's trace and reward framing helped us draw a more inspectable route from an agent failure to training data. The local translation remains scaffolding until a frozen evaluator proves a gain.",
    source: { label: "Castform", href: "https://castform.com/" },
    studyIds: ["castform-rl-finetune"],
  },
  {
    slug: "cline",
    name: "Cline",
    thread: "Agent architecture",
    opening:
      "Cline's explicit tool and context boundaries helped us reason about structured actions. We retained the lesson while leaving a new coding-agent product parked.",
    source: { label: "Cline source", href: "https://github.com/cline/cline" },
    studyIds: ["cline-context-hierarchy"],
  },
  {
    slug: "gigatoken",
    name: "Gigatoken",
    thread: "Data preparation",
    opening:
      "Gigatoken is a reminder to profile the boring first pass. Fast bulk tokenization can matter on a large corpus, though we have not found a current bottleneck that calls for adopting it.",
    source: {
      label: "Gigatoken source",
      href: "https://github.com/marcelroed/gigatoken",
    },
    studyIds: ["gigatoken"],
  },
  {
    slug: "needle-2",
    name: "Needle 2",
    thread: "Small specialists",
    opening:
      "Needle 2's tiny tool-calling package deserved a direct Mac test. The result was negative on our gate, and keeping that result visible is part of the credit we owe a useful idea.",
    source: {
      label: "Needle 2 model card",
      href: "https://huggingface.co/Cactus-Compute/needle2",
    },
    studyIds: ["needle-2"],
  },
  {
    slug: "parakeet-wgsl",
    name: "parakeet.wgsl",
    thread: "Browser runtimes",
    opening:
      "Public kernels, a package format, and a reproducible browser run made parakeet.wgsl a concrete runtime lesson. We verified execution locally without treating it as an accuracy win or integration decision.",
    source: {
      label: "parakeet.wgsl source",
      href: "https://github.com/narcotic-sh/parakeet.wgsl",
    },
    studyIds: ["parakeet-wgsl"],
  },
  {
    slug: "savante-aryabhata",
    name: "Savante and Aryabhata",
    thread: "Specialist data",
    opening:
      "Their mathematics specialist is a useful study of curated data, filtered traces, and verifiable rewards as one recipe. We have studied the published work, not reproduced its training result.",
    source: { label: "Savante", href: "https://savante.ai/" },
    studyIds: ["savante-aryabhata"],
    reading: [
      { label: "Aryabhata paper", href: "https://arxiv.org/abs/2508.08665" },
    ],
  },
  {
    slug: "bonsai-2",
    name: "Bonsai 2",
    thread: "Packaging",
    opening:
      "Bonsai sharpened our habit of separating weight-file size from peak runtime memory and capability retained. A fair same-Mac comparison remains a proposed exercise.",
    source: {
      label: "Bonsai 2 release",
      href: "https://prismml.com/news/bonsai-2-27b",
    },
    studyIds: ["bonsai-2-27b"],
    reading: [
      {
        label: "MLX model card",
        href: "https://huggingface.co/prism-ml/Ternary-Bonsai-2-27B-mlx-2bit",
      },
    ],
  },
  {
    slug: "qorl",
    name: "QORL",
    thread: "Evaluation",
    opening:
      "QORL helped us ask a harder database question: does offline search still win after a native planner baseline, held-out parameters, routing overhead, and tuning cost? The experiment remains unstarted.",
    source: { label: "QORL project", href: "https://rohanbansal.com/qorl" },
    studyIds: ["qorl"],
  },
  {
    slug: "vllm",
    name: "vLLM",
    thread: "Serving systems",
    opening:
      "vLLM makes scheduling, paged KV, and batching legible as serving problems. We study that architecture to understand which constraints carry over to one Mac and which belong to a cluster.",
    source: {
      label: "vLLM source",
      href: "https://github.com/vllm-project/vllm",
    },
    studyIds: ["inside-vllm"],
    reading: [
      { label: "Inside vLLM", href: "https://www.aleksagordic.com/blog/vllm" },
    ],
  },
  {
    slug: "splash",
    name: "Splash",
    thread: "Mac runtimes",
    opening:
      "Splash shows what a model-specific Mac engine can gain by specializing kernels, weights, cache, and startup memory. Its published numbers are the team's report, not our own benchmark.",
    source: {
      label: "Splash source",
      href: "https://github.com/incoai/splash",
    },
    studyIds: ["splash-mac-inference"],
    reading: [
      { label: "Launch article", href: "https://inco.ai/blog/splash/" },
    ],
  },
  {
    slug: "halo",
    name: "Halo",
    thread: "Scale boundary",
    opening:
      "Halo brings pre-training, SFT, preference work, and RL into one training framework that spans a GPU and clusters. For this lab it is a map of the single-Mac boundary, not a Mac runtime dependency.",
    source: {
      label: "Halo source",
      href: "https://github.com/whitecircle/halo",
    },
    studyIds: [],
    localRead:
      "Halo is a useful architecture reference for the factory loop from pre-training through RL. We are mapping where its single-GPU path ends and its expert, context, tensor, and data parallel paths begin. That gives the Mac lab a precise vocabulary for future scale without changing the current local implementation.",
    boundary:
      "Halo's published training path targets PyTorch and CUDA hardware. We have not run it on this Mac, reproduced its benchmarks, or adopted it as a dependency. Any future use would need a separate target, frozen evaluator, and resource budget.",
    evidence: [
      {
        label: "Our Mac and cluster boundary map",
        href: "/docs/learn/mac-mastery-map",
      },
    ],
  },
  {
    slug: "transformer-explainer",
    name: "Transformer Explainer",
    thread: "Learning tools",
    opening:
      "A live, inspectable GPT-2 in the browser gives learners something to manipulate after a forward-pass walkthrough. It sets a useful bar for explanations that invite investigation.",
    source: {
      label: "Transformer Explainer",
      href: "https://poloclub.github.io/transformer-explainer/",
    },
    studyIds: [],
    localRead:
      "Our ground-up sessions pair annotated source with outside interactive explanations. Transformer Explainer is a good companion because a learner can inspect a live model after reading about attention and the forward pass, rather than relying only on a static diagram.",
    boundary:
      "It is an external teaching project, not a PostTrainLLM runtime or a validation of our training results. Our reading list retains it as a learning reference; our own code and tests remain the authority for the local implementation.",
    evidence: [
      {
        label: "Our external reading list",
        href: "/docs/learn/external-references",
      },
    ],
  },
  {
    slug: "coreml-llm",
    name: "CoreML-LLM",
    thread: "Mac runtimes",
    opening:
      "CoreML-LLM is a community example of taking owned weights toward Apple's Neural Engine. It informs our research boundary; it is not a shipped PostTrainLLM engine.",
    source: {
      label: "CoreML-LLM source",
      href: "https://github.com/john-rocky/CoreML-LLM",
    },
    studyIds: [],
    localRead:
      "Our ANE dossier uses community implementations to understand conversion, layout, and execution constraints. CoreML-LLM offers one concrete way to study an ANE-oriented stack while our native work keeps model ownership and exact evaluation separate from the serving layer.",
    boundary:
      "We have not adopted CoreML-LLM as the PostTrainLLM app engine or established a same-model, same-Mac comparison. Upstream speed claims require their exact hardware, model, and settings before they can inform a local choice.",
    evidence: [
      {
        label: "Our ANE research dossier",
        href: "/docs/learn/ane-research/dossier",
      },
    ],
  },
  {
    slug: "mlx",
    name: "MLX",
    thread: "Mac foundations",
    opening:
      "MLX is a foundational Mac-local reference for training and inference. We study its implementation and use the platform where it fits while keeping our own model and evaluation contract.",
    source: { label: "Apple MLX", href: "https://github.com/ml-explore/mlx" },
    studyIds: [],
    localRead:
      "MLX gives this project a native Apple Silicon path for tensor work and model adaptation. The learning value is also architectural: its APIs and examples show what the platform handles, letting us spend effort on the data, evaluation, and packaging questions that remain ours.",
    boundary:
      "Using MLX does not make every model trainable within one Mac's memory or make a specialist good at its task. Each run still needs a bounded preset, a frozen baseline, and a task-specific gate.",
    evidence: [
      { label: "Our Mac mastery map", href: "/docs/learn/mac-mastery-map" },
    ],
  },
  {
    slug: "omlx",
    name: "oMLX",
    thread: "Mac runtimes",
    opening:
      "oMLX is a reference for the serving problems that appear on a single Mac: memory tiers, KV management, and concurrent requests. We keep it as a comparison point, not a claimed dependency.",
    source: { label: "oMLX", href: "https://omlx.ai/" },
    studyIds: [],
    localRead:
      "oMLX is a useful comparison point for continuous batching and memory-aware serving on one Mac. The project helps us distinguish model capability from serving quality and ask when a warm shared model process changes throughput or response time.",
    boundary:
      "Our map names oMLX as a reference, not a measured head-to-head or a current production dependency. Its exact behavior and performance can change, so any adoption decision would require a pinned revision and same-workload comparison.",
    evidence: [
      { label: "Our Mac mastery map", href: "/docs/learn/mac-mastery-map" },
    ],
  },
  {
    slug: "prime-intellect",
    name: "Prime Intellect",
    thread: "Scale boundary",
    opening:
      "Prime Intellect helps us map the work that distributed training can absorb and the coordination a single machine never sees. That is a learning boundary, not a local reproduction plan.",
    source: {
      label: "Prime Intellect",
      href: "https://www.primeintellect.ai/",
    },
    studyIds: [],
    localRead:
      "Prime Intellect is part of our single-machine-to-cluster map. Distributed reinforcement learning shows how a training workload can use parallel environments and tolerate coordination costs differently from a token-by-token inference request.",
    boundary:
      "This is a scale lesson, not a plan to reproduce frontier compute on one Mac. Our local factory keeps its small, inspectable target and records where memory, bandwidth, and available accelerators set hard limits.",
    evidence: [
      { label: "Our Mac mastery map", href: "/docs/learn/mac-mastery-map" },
    ],
  },
  {
    slug: "teale-petals",
    name: "teale and Petals",
    thread: "Scale boundary",
    opening:
      "These decentralized inference projects make the latency cost of sharding a model across machines tangible. The comparison helps explain why a single-Mac specialist is a different system.",
    source: { label: "teale", href: "https://teale.com/" },
    studyIds: [],
    localRead:
      "Together these projects illustrate two shapes of decentralized inference: sharding work across machines and making complete models available across a network. The distinction sharpens our understanding of per-token latency and what locality buys a small specialist.",
    boundary:
      "We have not installed or benchmarked either system for PostTrainLLM. Their networked design is a comparison at the distributed boundary, not a substitute for a verified local decode and task-completion gate.",
    evidence: [
      { label: "Our Mac mastery map", href: "/docs/learn/mac-mastery-map" },
    ],
    reading: [
      {
        label: "Petals source",
        href: "https://github.com/bigscience-workshop/petals",
      },
    ],
  },
  {
    slug: "weco",
    name: "Weco AI",
    thread: "Research loops",
    opening:
      "Weco's traceable, steerable autoresearch loop is a candidate to study when we have a concrete target, frozen evaluation, and fixed cost budget. It is on our radar, not installed in the factory.",
    source: { label: "Weco AI", href: "https://www.weco.ai/platform" },
    studyIds: [],
    localRead:
      "The appealing part of Weco is an inspectable search tree: a proposed code change, its run, the metric, and the next branch stay visible. That matches our preference for accountable attempts and a stable evaluator before a candidate is called better.",
    boundary:
      "We have not run Weco here. The owner recorded a trial as conditional on a concrete target, frozen eval, held-out gate, regression metric, and fixed cost budget. Its product claims are not local results.",
    evidence: [
      {
        label: "Our recorded factory stance",
        href: "https://github.com/PostTrainLLM/posttrainllm/blob/main/AGENTS.md#external-autoresearch-products-to-retain",
      },
    ],
  },
  {
    slug: "aster",
    name: "Aster AI Labs",
    thread: "Scale boundary",
    opening:
      "Aster's distributed research search is useful for understanding what massive parallel experimentation buys. We study the method and boundary without trying to reproduce its compute pattern locally.",
    source: { label: "Aster", href: "https://www.asterlab.ai/" },
    studyIds: [],
    localRead:
      "Aster's research search makes parallel experimentation itself an object of study. We use it to ask which parts of a search loop scale with more agents and which still depend on clear objectives, independent measurement, and human judgment.",
    boundary:
      "Aster's large compute pattern is outside this Mac lab. We have not reproduced its reported results; the retained value is a boundary map and ideas that may be useful only when an active target warrants them.",
    evidence: [
      {
        label: "Our recorded factory stance",
        href: "https://github.com/PostTrainLLM/posttrainllm/blob/main/AGENTS.md#external-autoresearch-products-to-retain",
      },
    ],
    reading: [
      {
        label: "Scaling research search",
        href: "https://www.asterlab.ai/research/scaling_autonomous_research_to_thousands_of_agents",
      },
    ],
  },
];

const studiesById = new Map(
  studyRegistry.studies.map((study) => [study.id, study]),
);

export function inspirationStudies(entry: Inspiration) {
  return entry.studyIds.map((id) => {
    const study = studiesById.get(id);
    if (!study) throw new Error(`Unknown inspiration study: ${id}`);
    return study;
  });
}

export function validateInspirationCoverage(): string[] {
  const ids = inspirations.flatMap((entry) => entry.studyIds);
  const expected = studyRegistry.studies.map((study) => study.id);
  return [
    ...expected
      .filter((id) => !ids.includes(id))
      .map((id) => `Uncovered study: ${id}`),
    ...ids
      .filter((id, index) => ids.indexOf(id) !== index)
      .map((id) => `Duplicate study: ${id}`),
  ];
}
