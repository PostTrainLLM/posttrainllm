export interface LearningUnit {
  id: string;
  number: string;
  title: string;
  summary: string;
  lesson: string[];
  exercise: string;
  workPlaceholder: string;
  explanationPrompt: string;
  masteryGate: string;
  recallPrompts: [string, string];
  sourceHref: string;
  sourceLabel: string;
}

export interface LearningCaseStudy {
  id: string;
  title: string;
  lesson: string;
  exercise: string;
  sourceHref: string;
  sourceLabel: string;
}

export const learningUnits: LearningUnit[] = [
  {
    id: "functions-data-parameters",
    number: "01",
    title: "Functions, data, and parameters",
    summary:
      "A model is a function whose adjustable parameters are learned from examples.",
    lesson: [
      "A function maps an input to an output. In y = mx + b, x is the input and the predicted y is the output.",
      "The examples stay fixed while fitting. The parameters m and b change because they control the function's behavior.",
      "Learning means choosing parameter values that make predictions agree with the observed targets. The same distinction scales from a two-parameter line to a transformer with billions of parameters.",
    ],
    exercise:
      "For (x, y) = (0,1), (1,3), (2,5), (3,7), (4,9), choose m and b for y = mx + b. Show all five predictions and label inputs, targets, parameters, and predictions.",
    workPlaceholder: "Show m, b, and all five predictions…",
    explanationPrompt:
      "Explain which quantities stay fixed during fitting, which change, and how parameters differ from inputs. Then connect one quantity to the repository.",
    masteryGate:
      "Explain a parameter without LLM jargon and predict the effect of changing m versus b on a new input.",
    recallPrompts: [
      "Without notes, explain inputs, targets, parameters, and predictions. Then solve y = mx + b for (0,2), (1,5), (2,8).",
      "Without notes, explain how changing m differs from changing b. Predict y at x = 6 for a line through (0,-1), (1,1), (2,3).",
    ],
    sourceHref: "/docs/learn/session-01-neural-net-basics",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "loss-gradient-descent",
    number: "02",
    title: "Loss and gradient descent",
    summary:
      "Loss measures error; gradients indicate how parameter changes affect it.",
    lesson: [
      "A loss function compresses many prediction errors into one number that can guide training.",
      "A gradient is a local slope. Gradient descent moves parameters against that slope, scaled by the learning rate.",
    ],
    exercise:
      "Compute MSE for two line fits, then take one gradient-descent step by hand.",
    workPlaceholder:
      "Show both losses, the gradient direction, and one update…",
    explanationPrompt:
      "Explain how loss turns prediction error into a training signal, what the gradient says, and how the learning rate changes the update.",
    masteryGate:
      "Predict the symptoms of a learning rate that is too high or too low.",
    recallPrompts: [
      "Without notes, compute MSE for predictions [1, 3] and targets [2, 5], then state what a positive gradient means for the next update.",
      "Diagnose two loss curves: one oscillates wildly and one falls almost flat. Explain the likely learning-rate problem and the next bounded test.",
    ],
    sourceHref: "/docs/learn/session-02-gradient-descent",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "vectors-matrices-tensors",
    number: "03",
    title: "Vectors, matrices, and tensors",
    summary:
      "Neural networks organize multiply-and-add operations over arrays with explicit shapes.",
    lesson: [
      "Vectors hold features, matrices transform them, and tensors generalize these arrays to more axes.",
      "Shape annotations expose which dimensions represent batch, sequence, embedding, heads, and vocabulary.",
    ],
    exercise:
      "Trace the shapes through one linear layer and diagnose one deliberately mismatched axis.",
    workPlaceholder: "Write each input, weight, and output shape in order…",
    explanationPrompt:
      "Explain what every axis represents, which dimensions the matrix multiply contracts, and why the mismatched shape fails.",
    masteryGate: "Read a shape error and identify which axis is wrong.",
    recallPrompts: [
      "Without notes, trace [batch=2, features=3] through a weight matrix [3, 4]. Name the output shape and contracted axis.",
      "A tensor shaped [batch, sequence, heads, head_dim] is transposed incorrectly before attention. Explain which axes must align and how you would detect the error.",
    ],
    sourceHref: "/docs/learn/session-09-tensors",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "nonlinear-networks-backprop",
    number: "04",
    title: "Non-linear networks and backpropagation",
    summary:
      "Activations make depth expressive; backpropagation assigns credit through the computation graph.",
    lesson: [
      "Stacking only linear transformations still produces one linear transformation. Non-linear activations let networks fit curved decision boundaries.",
      "Backpropagation applies the chain rule from the loss back to every parameter that influenced it.",
    ],
    exercise:
      "Inspect or train a two-layer MLP on a non-linear toy dataset and explain the gradient path.",
    workPlaceholder: "Trace the forward values and backward gradient path…",
    explanationPrompt:
      "Explain why the activation changes what the network can represent and how the chain rule carries credit back through both layers.",
    masteryGate:
      "Explain why an activation enables behavior that stacked linear layers cannot.",
    recallPrompts: [
      "Without notes, explain why two linear layers without an activation collapse into one linear map, then describe what an activation adds.",
      "Trace the dependency path from loss to the first layer of a two-layer MLP and explain where each local derivative enters.",
    ],
    sourceHref: "/docs/learn/session-03-non-linearities",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "paradigms-scaling",
    number: "05",
    title: "ML paradigms and scaling",
    summary:
      "Pretraining, supervision, preferences, reinforcement, and scaling solve different problems.",
    lesson: [
      "Self-supervision builds broad predictive capability; supervised and preference methods shape behavior for particular tasks.",
      "More scale can add capacity and knowledge, but cannot repair invalid data or an unreliable evaluation ruler.",
    ],
    exercise:
      "Classify retained posttrainllm attempts by learning paradigm and name the signal each used.",
    workPlaceholder:
      "Classify each attempt and name its data or reward signal…",
    explanationPrompt:
      "Explain what capability each learning paradigm can add, what it cannot repair, and when more scale would or would not help.",
    masteryGate:
      "Explain why scale cannot rescue a broken evaluation or contaminated dataset.",
    recallPrompts: [
      "Without notes, distinguish self-supervision, supervised fine-tuning, preference tuning, and reinforcement learning by the signal each consumes.",
      "Given a larger model with contaminated data and a noisy evaluator, explain why scale cannot establish a trustworthy improvement and what must be fixed first.",
    ],
    sourceHref: "/docs/learn/session-04-ml-paradigms",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "tokens-embeddings-language",
    number: "06",
    title: "Tokenization, embeddings, and language modeling",
    summary:
      "Text becomes token IDs, embeddings, contextual states, and next-token probabilities.",
    lesson: [
      "A tokenizer chooses the discrete units a model sees. Embeddings map each token ID into a learned vector.",
      "A causal language model learns to predict the next token from the tokens before it.",
    ],
    exercise:
      "Tokenize three prompts and inspect how punctuation and identifiers split.",
    workPlaceholder:
      "Record the token splits and the behavior they may affect…",
    explanationPrompt:
      "Explain how token boundaries become embeddings and why awkward splits can change reliability on structured text such as SQL or tool calls.",
    masteryGate:
      "Explain how tokenization can affect SQL and tool-call reliability.",
    recallPrompts: [
      "Without notes, trace text through token IDs, embeddings, contextual states, and next-token probabilities.",
      "Compare a clean identifier tokenization with one split across many tokens. Predict two effects on structured-output reliability and how you would measure them.",
    ],
    sourceHref: "/docs/learn/session-06-tokenization-embeddings",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "attention-transformers",
    number: "07",
    title: "Attention and transformer blocks",
    summary:
      "Attention routes information between positions; repeated blocks refine contextual representations.",
    lesson: [
      "Queries express what a position seeks, keys describe what positions offer, and values carry the information to combine.",
      "A transformer block combines attention, an MLP, normalization, residual paths, and positional information.",
    ],
    exercise:
      "Work one tiny query/key/value attention calculation with explicit shapes.",
    workPlaceholder: "Show Q, K, V shapes, scores, weights, and the output…",
    explanationPrompt:
      "Explain what the query seeks, what keys advertise, what values carry, and how attention changes the representation at one position.",
    masteryGate:
      "Describe what attention can copy or route that a position-wise MLP cannot.",
    recallPrompts: [
      "Without notes, describe Q, K, and V in one sentence each and trace the shapes through a single-head attention calculation.",
      "Explain why a position-wise MLP cannot directly copy information from another token, and how attention plus a residual path can do so.",
    ],
    sourceHref: "/docs/learn/session-10-attention",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "training-mechanics",
    number: "08",
    title: "Training mechanics",
    summary:
      "Batches, optimizers, schedules, precision, and correctness gates determine whether training works.",
    lesson: [
      "A loss curve only becomes useful when paired with data checks, held-out behavior, gradient health, and reproducible settings.",
      "Tiny-overfit is the first gate: if a model cannot memorize a tiny repeated set, scaling the run hides the bug rather than fixing it.",
    ],
    exercise:
      "Inspect a tiny-overfit run and diagnose data, learning-rate, capacity, and precision failures separately.",
    workPlaceholder:
      "Record the observed symptom, competing causes, and smallest test…",
    explanationPrompt:
      "Explain which evidence separates a data bug, optimization problem, capacity limit, and precision failure before a larger run begins.",
    masteryGate:
      "Distinguish a data bug, optimization bug, and capacity limit from their symptoms.",
    recallPrompts: [
      "Without notes, explain why tiny-overfit is the first correctness gate and list three failures it can expose.",
      "A larger run has a flat loss curve. Propose the smallest ordered tests that distinguish data, optimization, capacity, and precision causes.",
    ],
    sourceHref: "/docs/learn/session-08-training-mechanics",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "post-training",
    number: "09",
    title: "SFT, LoRA, and preference tuning",
    summary:
      "Post-training changes behavior using labeled demonstrations, compact updates, or preferences.",
    lesson: [
      "SFT imitates desired outputs. LoRA learns a low-rank update while keeping the base weights frozen.",
      "Preference methods compare better and worse responses; weak pair construction or missing reference control can collapse useful behavior.",
    ],
    exercise:
      "Compare the successful SQL SFT run with the failed hygiene preference run and isolate the changed variables.",
    workPlaceholder:
      "Compare target, data, update method, eval, regressions, and cost…",
    explanationPrompt:
      "Explain what SFT, LoRA, and preference tuning change, then identify which evidence supports success or failure in the two retained runs.",
    masteryGate:
      "Design a bounded recipe with data, target, regression slices, budget, and stop rule.",
    recallPrompts: [
      "Without notes, distinguish SFT, LoRA, and preference tuning by trainable parameters, supervision, and the behavior each targets.",
      "Draft a bounded post-training recipe from memory: target, data, frozen baseline, held-out gate, regressions, budget, and stop rule.",
    ],
    sourceHref: "/docs/learn/session-07-behavior-learning",
    sourceLabel: "Read the complete lesson",
  },
  {
    id: "evals-rewards-factory",
    number: "10",
    title: "Evals, rewards, and self-improvement",
    summary:
      "A frozen ruler, verifiable feedback, and retained failures make improvement measurable.",
    lesson: [
      "An evaluation must first pass a frontier-ceiling check: if a capable model cannot satisfy the ruler, the ruler is measuring noise.",
      "Held-out data, regression slices, provenance, and cost measurements turn a score into a decision.",
    ],
    exercise:
      "Draft a target, frozen baseline, held-out gate, regressions, resource budget, and ship/retry/reject rule.",
    workPlaceholder:
      "Write the ruler, holdout, regressions, budget, and decision rule…",
    explanationPrompt:
      "Explain why the evaluator must pass a frontier-ceiling check and how held-out evidence, provenance, cost, and regressions support a decision.",
    masteryGate:
      "Reject an attractive score when its ruler, holdout, provenance, or regression gate is invalid.",
    recallPrompts: [
      "Without notes, define a frontier-ceiling check and explain why an attractive score is meaningless when the ruler fails it.",
      "Given a candidate with a higher headline score but worse regressions, unclear provenance, and no held-out gate, make and justify a ship, retry, or reject decision.",
    ],
    sourceHref: "/docs/learn/session-11-evals-rewards",
    sourceLabel: "Read the complete lesson",
  },
];

export const learningCaseStudies: LearningCaseStudy[] = [
  {
    id: "savante-aryabhata",
    title: "Savante / Aryabhata: specialist data and evaluation",
    lesson:
      "Study how curated domain data, filtered reasoning traces, SFT, and verifiable-reward RL combine in a JEE mathematics specialist. The published result does not isolate the contribution of each stage.",
    exercise:
      "Write a recipe teardown separating initialization, data, filtering, SFT, reward, evaluation, missing ablations, and leakage boundaries.",
    sourceHref:
      "/docs/industry_learning_roadmap#case-study---savante--aryabhata-specialist-data-and-evaluation",
    sourceLabel: "Open the case study and sources",
  },
  {
    id: "bonsai-2",
    title: "Bonsai 2 27B: capability retained per deployment cost",
    lesson:
      "Distinguish ternary representation, packed artifact size, peak runtime memory, kernel support, latency, and capability retention relative to the source model.",
    exercise:
      "Draft a same-Mac comparison sheet covering exact revisions, task gates, peak RAM, TTFT, prefill, decode throughput, and total task latency.",
    sourceHref:
      "/docs/industry_learning_roadmap#case-study---bonsai-2-27b-capability-retained-per-deployment-cost",
    sourceLabel: "Open the case study and sources",
  },
  {
    id: "qorl",
    title: "QORL: parameter-aware query optimization",
    lesson:
      "Compare native PostgreSQL planning, structured hint search, and LLM proposals under equal budgets, then evaluate a parameter-to-plan dispatcher on fresh held-out measurements.",
    exercise:
      "Freeze parameter splits, cache policy, timeouts, SQL-equivalence checks, unfamiliar-case fallback, routing overhead, and tuning-cost break-even.",
    sourceHref:
      "/docs/industry_learning_roadmap#case-study---qorl-parameter-aware-query-optimization",
    sourceLabel: "Open the retained PRD and sources",
  },
  {
    id: "inside-vllm",
    title: "Inside vLLM: inference systems and scaling boundaries",
    lesson:
      "Trace admission, scheduling, paged KV allocation, prefill, decode, batching, caching, and the boundary from one device to distributed serving.",
    exercise:
      "Hand-simulate three requests under fixed token and KV-block budgets, then predict effects on TTFT, inter-token latency, throughput, and memory.",
    sourceHref:
      "/docs/industry_learning_roadmap#case-study---inside-vllm-inference-systems-and-scaling-boundaries",
    sourceLabel: "Open the article study guide",
  },
];
