/** Week contracts from docs/learn/inference-systems-13w.md. Detailed lessons after Week 1 are planned. */
export interface InferenceWeek {
  week: number;
  dates: string;
  title: string;
  prerequisites: string;
  progression: string;
  artifact: string;
  passCriterion: string;
  boundary: string;
  readiness: "ready" | "planned";
}

const weekContracts: Omit<InferenceWeek, "prerequisites" | "passCriterion">[] =
  [
    {
      week: 1,
      dates: "Sep 28–Oct 4",
      title: "Decoder forward path",
      progression:
        "IDs and embeddings → bytes and position → attention → causal heads → transformer block → reference trace → closed-book debug.",
      artifact:
        "Annotated token-to-logit trace, a bounded CPU correctness smoke, and an independent explanation on changed shapes.",
      boundary:
        "Seven lessons are ready. The Day 1 toy is not the full model; the Day 6 single timing is not a benchmark.",
      readiness: "ready",
    },
    {
      week: 2,
      dates: "Oct 5–11",
      title: "Generation and KV cache",
      progression:
        "Generation loop → prefill/decode → cached state → cache shapes/bytes → cached versus uncached correctness.",
      artifact:
        "A tested local comparison with cache arithmetic and matching relevant logits under declared tolerance.",
      boundary:
        "Inspect a compatible implementation first; this repo's reference cache path is not assumed. Detailed lessons remain to be authored.",
      readiness: "planned",
    },
    {
      week: 3,
      dates: "Oct 12–18",
      title: "Measurement",
      progression:
        "Timing boundaries → TTFT/inter-token latency → throughput/concurrency → memory/dtype → warmup, variance, profiling.",
      artifact:
        "Reproducible output and a prediction-versus-observation note with pinned workload, versions, and repetitions.",
      boundary:
        "Audit an existing harness first. One forward time is insufficient. Detailed lessons remain to be authored.",
      readiness: "planned",
    },
    {
      week: 4,
      dates: "Oct 19–25",
      title: "GPU execution and CUDA/Triton",
      progression:
        "CPU/GPU roles → grid/block/thread/warp → access patterns → tiny CUDA kernel → introductory Triton fusion.",
      artifact:
        "Reference-checked vector operation and fused softmax, including edge cases and memory-traffic explanation.",
      boundary:
        "NVIDIA execution requires separately approved compatible hardware, pinned tooling, and cost cap. Mac/source practice cannot pass that gate. Detailed lessons and host verification remain.",
      readiness: "planned",
    },
    {
      week: 5,
      dates: "Oct 26–Nov 1",
      title: "Attention performance",
      progression:
        "Materialized attention → IO/tiling → numerical stability → optimized path → controlled comparison.",
      artifact:
        "Reference-versus-optimized comparison with shapes, dtypes, correctness tolerance, timing, and transfer limits.",
      boundary:
        "Mac measurements do not establish NVIDIA performance. Detailed lessons and compatible path verification remain.",
      readiness: "planned",
    },
    {
      week: 6,
      dates: "Nov 2–8",
      title: "Trace vLLM",
      progression:
        "Engine overview → request entry → scheduling → model runner → output/KV lifecycle.",
      artifact:
        "Source-linked request trace at a pinned revision and a hand-simulated request.",
      boundary:
        "Mac source review is code-understanding evidence, not a vLLM runtime result. Detailed lessons and source revision remain to be pinned.",
      readiness: "planned",
    },
    {
      week: 7,
      dates: "Nov 9–15",
      title: "Scheduling and KV ownership",
      progression:
        "Arrivals → token budgets → KV allocation/release → batching/prefill scheduling → fairness/failure.",
      artifact:
        "Three-request simulation and one investigated scheduling choice with allocation invariants.",
      boundary:
        "Simulation is not a production benchmark. Detailed lessons remain to be authored.",
      readiness: "planned",
    },
    {
      week: 8,
      dates: "Nov 16–22",
      title: "Bounded runtime change",
      progression:
        "Choose issue → reproduce → test → patch → before/after → review.",
      artifact:
        "A reviewable patch, correctness tests, controlled measurements, and a regression-risk explanation.",
      boundary:
        "Requires an executable baseline; no upstream publication is implied. Detailed lessons depend on the chosen issue.",
      readiness: "planned",
    },
    {
      week: 9,
      dates: "Nov 23–29",
      title: "Serving behavior",
      progression:
        "Request mix → service targets → concurrency/queueing → tail latency → overload tradeoffs.",
      artifact:
        "Bounded serving-load report separating queue and model time, plus changed-mix diagnosis.",
      boundary:
        "Label local simulation separately from runtime measurement. Detailed lessons and environment remain to be specified.",
      readiness: "planned",
    },
    {
      week: 10,
      dates: "Nov 30–Dec 6",
      title: "Single device to cluster",
      progression:
        "Capacity → sharding → communication volume → topology → design comparison.",
      artifact:
        "Declared model/workload memory and communication calculation with topology-aware assumptions.",
      boundary:
        "Multi-GPU reasoning is required; a multi-GPU benchmark is not. Detailed lessons remain to be authored.",
      readiness: "planned",
    },
    {
      week: 11,
      dates: "Dec 7–13",
      title: "Capstone investigation",
      progression:
        "One hypothesis → frozen workload → controls → bounded intervention → predicted failure.",
      artifact:
        "Raw evidence, code, config, stop rule, and competing explanations; a supported negative result counts.",
      boundary:
        "Use one investigation from prior work, not a new project. Detailed lessons depend on the selected hypothesis.",
      readiness: "planned",
    },
    {
      week: 12,
      dates: "Dec 14–20",
      title: "Capstone review",
      progression:
        "Reproduce → vary workload → find regressions → challenge mechanism → conclude.",
      artifact:
        "Write-up with reproduction steps, limitations, uncertainty, changed-workload evidence, and ship/reject/revise decision.",
      boundary:
        "One favorable run is not a universal speed claim. Detailed lessons remain to be authored.",
      readiness: "planned",
    },
    {
      week: 13,
      dates: "Dec 21–27",
      title: "Unfamiliar-problem assessment",
      progression:
        "Tensor/correctness → cache/memory → measurement trap → serving diagnosis → review.",
      artifact:
        "Predict, diagnose, interpret evidence, and defend the next test on unfamiliar inputs.",
      boundary:
        "Finishing the schedule does not itself establish professional seniority. Detailed assessment prompts remain to be authored.",
      readiness: "planned",
    },
  ];

const prerequisites = [
  "Day 1 arithmetic, indexing, and a small Python function",
  "Week 1 causal forward trace",
  "Week 2 generation and cache model",
  "Week 3 measurement definitions and reference comparisons",
  "Week 4 GPU execution model and correctness checks",
  "Weeks 2–5 inference, measurement, and attention concepts",
  "Week 6 request-to-output source trace",
  "Week 7 scheduling trace and an executable baseline",
  "Weeks 3 and 8 controlled measurement and bounded runtime change",
  "Week 9 serving limits and Week 2 memory arithmetic",
  "One bounded question supported by Weeks 1–10 evidence",
  "Week 11 frozen capstone workload and raw evidence",
  "Weeks 1–12 traces, measurements, and reviewed limitations",
];

const passCriteria = [
  "Explain the decoder path on changed shapes, show causal isolation, and preserve one bounded CPU correctness baseline.",
  "Show cache-size arithmetic and matching relevant cached versus uncached logits with fixed model, inputs, and settings; explain reused work.",
  "Pin workload, precision, versions, warmups, repetitions, and metric definitions; diagnose one misleading setup.",
  "Compare edge cases with a reference and explain indexing, masking, coalescing, and memory traffic; NVIDIA execution remains pending without compatible hardware.",
  "Explain correctness, measured bottleneck, speed/space tradeoff, and where the result does not transfer.",
  "Trace a request end to end at a pinned source revision; identify state ownership and where time can accumulate.",
  "Check KV allocation invariants for three requests and predict fairness and latency/throughput tradeoffs.",
  "Reproduce the issue, pass correctness tests, compare controlled before/after evidence, and name a regression risk.",
  "Report latency distribution, throughput, queue versus model time, and the cost of an intervention under a changed request mix.",
  "Defend declared memory, communication, and topology assumptions; separate calculation from execution.",
  "Preserve raw evidence, code, config, controls, stop rule, and competing explanations, including a supported negative result.",
  "Reproduce and vary workload, identify regressions and uncertainty, then defend ship/reject/revise from evidence.",
  "On unfamiliar inputs, predict, choose a diagnostic, interpret evidence, and defend the next test without claiming schedule-based mastery.",
];

export const inferenceWeeks: InferenceWeek[] = weekContracts.map(
  (week, index) => ({
    ...week,
    prerequisites: prerequisites[index],
    passCriterion: passCriteria[index],
  }),
);
