import type { LearningUnit } from "./content";
import { makeSession } from "./inference-session";

export interface LessonSection {
  heading: string;
  paragraphs?: string[];
  bullets?: string[];
  code?: string;
}

export interface InferenceSession extends LearningUnit {
  routeId: "inference-systems-13w";
  week: number;
  day: number;
  minutes: number;
  prerequisites: string[];
  hardware: string;
  readiness: "ready";
  objective: string;
  diagnosticPrompt?: string;
  diagnosticRepair?: string;
  sections: LessonSection[];
  workedExample: LessonSection[];
  predictionPrompt: string;
  starterCode?: string;
  answerGuide: LessonSection[];
  checks: string[];
  evidence: string[];
  nextSessionId: string | null;
}

export const inferenceSessions: InferenceSession[] = [
  makeSession(1, {
    title: "From token IDs to next-token scores",
    summary:
      "Look up vectors, project them to scores, and find the missing context path.",
    minutes: 120,
    prerequisites: [
      "Read a small Python function",
      "Index an array",
      "Multiply and add numbers",
    ],
    hardware: "CPU and small PyTorch tensors; no model download or training",
    objective:
      "Predict four tensor shapes and explain why this toy's last-position output ignores earlier tokens.",
    diagnosticPrompt:
      "Before reading: for y=w·x+b with x=[2,3], w=[4,-1], b=2, calculate the dot product and y; label input and parameters. In a [2,4] array, locate row 1, position 2 and name the axes. Guess the output shape of Linear(3,5) applied to [2,4,3]. An uncertain answer is useful evidence, not a rejection.",
    diagnosticRepair:
      "Worked repair: w·x=4×2+(-1)×3=5, then y=5+2=7. x is the input; w and b are stored parameters. [2,4] means two batch rows with four positions each, so [1,2] is the third position of the second row (zero-based indexing). Linear(3,5) changes only the final feature axis: [2,4,3] → [2,4,5]. Retry with x=[1,4], w=[3,2], b=-1 and Linear(4,6) on [1,3,4] before moving on.",
    sections: [
      {
        heading: "What the program receives",
        paragraphs: [
          "A token ID is an integer index. It is not the token's meaning or its vector. These IDs are invented and do not encode a sentence.",
          "A parameter belongs to the model and stays fixed in this exercise. An input changes between calls. An activation is an intermediate value computed from the input. Training would update parameters from a loss; this program has no loss, backward pass, or optimizer.",
          "B counts sequences in a batch, T positions in each sequence, V vocabulary entries, and D features per vector. Shape [B,T] names two axes, not the scalar B×T. ids[b,t] selects one integer.",
        ],
      },
      {
        heading: "Lookup, projection, and selection",
        paragraphs: [
          "The embedding table has V rows and D columns. [B,T] IDs select one row per position and produce x [B,T,D]. The same ID selects the same row before position or context processing.",
          "nn.Linear(D,V,bias=False) stores a [V,D] weight. Each D-vector multiplies the transposed weight to make V logits, yielding [B,T,V]. This projection does not combine positions.",
          "Logits are scores. logits[:, -1, :] means every batch item, its final position, and all vocabulary scores: [B,V]. Softmax across V makes each row sum to one. Argmax selects one ID per batch row: [B]. It is deterministic, unlike sampling.",
          "This toy has no attention, position input, or contextual mixing. Appending the selected ID and repeating would form a generation loop; today we make one forward calculation. Random weights are not meaningful learned language.",
        ],
      },
    ],
    workedExample: [
      {
        heading: "Smaller worked example",
        paragraphs: [
          "E=[[1,0],[0,1],[1,1],[2,-1]] has four rows and width two. IDs [[0,2]] select [[1,0],[1,1]], so x is [1,2,2].",
          "For a three-output projection W=[[1,0],[0,1],[1,1]], [1,0] @ W.T = [1,0,1] and [1,1] @ W.T = [1,1,2]. The three illustrative output classes are separate from the exercise's vocabulary.",
        ],
      },
    ],
    predictionPrompt:
      "Before code: with B=2,T=4,V=32,D=8, predict shapes and axes of x, logits, probabilities, next_ids. Can replacing only ids[0,0] from 2 to 7 affect probabilities[0] at the last position when weights and final ID stay fixed? Which objects are parameters?",
    exercise:
      "Create scripts/learning/inference_w01_d01.py from the starter. Complete evaluate: lookup → projection → last-position softmax → argmax. From the repo root run .venv/bin/python scripts/learning/inference_w01_d01.py (or isolated Python with python_ref/requirements.txt). Clone ids, set changed[0,0]=7, call evaluate again using the SAME layer objects, and compare the last probabilities with torch.testing.assert_close(rtol=1e-6, atol=1e-7). Save the actual shapes and comparison. Predict whether changing the last ID guarantees a new argmax.",
    starterCode: [
      '"""Day 1 learner starter: CPU, random weights, no attention."""',
      "import torch",
      "from torch import nn",
      "",
      "torch.manual_seed(0)",
      "B, T, V, D = 2, 4, 32, 8",
      "ids = torch.tensor([[2, 5, 2, 9], [3, 5, 3, 8]], dtype=torch.long)",
      "embedding = nn.Embedding(V, D, dtype=torch.float32)",
      "output_head = nn.Linear(D, V, bias=False, dtype=torch.float32)",
      "",
      "@torch.inference_mode()",
      "def evaluate(inputs: torch.Tensor):",
      "    # TODO: lookup -> logits -> last-position softmax -> argmax.",
      "    # Return x, logits, probabilities, next_ids in that order.",
      '    raise NotImplementedError("Complete the four-step forward calculation")',
      "",
      'if __name__ == "__main__":',
      "    results = evaluate(ids)",
      '    for name, tensor in zip(["x", "logits", "probabilities", "next_ids"], results):',
      "        print(name, tuple(tensor.shape))",
    ].join("\n"),
    workPlaceholder:
      "Initial prediction, completed code, actual checks, and correction…",
    explanationPrompt:
      "Why can this toy not use an earlier token to change its last-position distribution? Distinguish it from a causal transformer. Why might a changed final token leave argmax unchanged?",
    masteryGate:
      "Self-review: correct four shapes and axes, fixed-weight experiment, and your own dependency explanation. Preserve an incorrect initial prediction alongside its correction.",
    answerGuide: [
      {
        heading: "Shapes and dependency",
        paragraphs: [
          "x [2,4,8]; logits [2,4,32]; probabilities [2,32]; next_ids [2]. Each batch item gets its own distribution over 32 IDs. Embedding and output-head weights are parameters; x and logits are intermediates.",
          "A prefix-only change leaves the final distribution equal because no operation reads another position. Changing the last ID can alter scores without changing the largest-score ID.",
        ],
      },
      {
        heading: "Instructor function",
        code: [
          "@torch.inference_mode()",
          "def evaluate(inputs: torch.Tensor):",
          "    x = embedding(inputs)",
          "    logits = output_head(x)",
          "    probabilities = torch.softmax(logits[:, -1, :], dim=-1)",
          "    next_ids = probabilities.argmax(dim=-1)",
          "    return x, logits, probabilities, next_ids",
        ].join("\n"),
      },
    ],
    checks: [
      "probabilities.sum(-1) is close to [1,1]",
      "next_ids lie in [0,31]",
      "Prefix-only change passes assert_close at rtol=1e-6, atol=1e-7",
      "Changed dimensions B=1,T=3,V=16,D=4 give [1,3,4], [1,3,16], [1,16], [1]",
    ],
    evidence: [
      "Initial prediction and correction",
      "Completed code and observed shapes",
      "Fixed-weight comparison, source revision, CPU/PyTorch version",
      "Your explanation and remaining question",
    ],
    recallPrompts: [
      "For B=1,T=3,V=16,D=4, trace the four shapes. Can a prefix-only change affect the final distribution in this toy? Why?",
      "If a prefix-only change unexpectedly alters final probabilities, name two experimental assumptions to check. Why can a changed final ID leave argmax unchanged?",
    ],
    sourceHref: "/docs/learn/session-06-tokenization-embeddings/",
    sourceLabel: "Optional embedding reference",
  }),
  makeSession(2, {
    title: "Token bytes, tensor axes, and position",
    summary:
      "Trace byte IDs and separate position information from cross-token context.",
    minutes: 120,
    prerequisites: ["Day 1 lookup and projection shapes"],
    hardware: "CPU/source review; no training",
    objective:
      "Trace byte IDs through lookup, learned position addition, and a batched projection.",
    sections: [
      {
        heading: "Actual bytes and axes",
        paragraphs: [
          "python_ref/dataset.py uses byte-v1: UTF-8 text becomes one token ID per byte in 0..255. ASCII A is byte 65. A non-ASCII character may occupy multiple bytes. Read the reference config for its current vocabulary size.",
          "[B,T,D] means batch row, token position, feature. A Linear(D,O) changes only the final axis and stores weight [O,D]. It applies the same map at every batch row and position.",
        ],
      },
      {
        heading: "Position is not context",
        paragraphs: [
          "The reference adds a learned position vector to each token vector. That gives a position a distinct representation, but the addition alone does not read another token.",
          "The reference output head may tie its weight to the token table, according to its config. Trace its actual branch. Attention is the later operation that combines positions; do not call position addition attention.",
        ],
      },
    ],
    workedExample: [
      {
        heading: "Two sequences",
        paragraphs: [
          "For IDs [[65,66],[66,65]], let E[65]=[1,0,1], E[66]=[0,1,1], P[0]=[0,0,0], P[1]=[1,0,0]. Token-plus-position vectors are [[[1,0,1],[1,1,1]],[[0,1,1],[2,0,1]]], shape [2,2,3].",
          "A Linear(3,2) maps each of these four vectors to width 2, producing [2,2,2]. No output at position 1 reads the token at position 0 through that linear map.",
        ],
      },
    ],
    predictionPrompt:
      "For B=2,T=3,D=4 and Linear(4,6), predict ID, lookup, position-added, stored weight, and output shapes. Predict whether 'Aé' is two or three byte IDs before checking encode().",
    exercise:
      "Read python_ref/dataset.py encode and python_ref/model.py forward/_head. Predict then check list(encode('Aé')) using the repo's isolated Python. In the worked table change P[1] to [0,1,0] and recompute both sequences manually. Inspect configs/model.byte-tinygpt-v0.json and record vocab_size, d_model, context_length, and tie_embeddings at this revision. Identify the first operation in model.py that can mix positions.",
    workPlaceholder:
      "Byte prediction/check, labeled axes, changed position vectors, current source anchors…",
    explanationPrompt:
      "Explain how a position vector tells the model location while a position-wise map still cannot use another token. Point to the source's first cross-position operation.",
    masteryGate:
      "Self-review: correct axes and Linear weight orientation; distinguish UTF-8 bytes, learned position, and attention. Retry shape reasoning for B=1,T=4,D=5, Linear(5,7).",
    answerGuide: [
      {
        heading: "Check after tracing",
        paragraphs: [
          "'Aé' is UTF-8 bytes [65,195,169], hence three IDs. For B=2,T=3,D=4, IDs [2,3], lookup and position-added vectors [2,3,4], Linear(4,6) weight [6,4], and output [2,3,6].",
          "With P[1]=[0,1,0], the first sequence becomes [[1,0,1],[0,2,1]] and the second [[0,1,1],[1,1,1]]. For the changed shape case, the output is [1,4,7].",
        ],
      },
    ],
    checks: [
      "Predict bytes before executing encode()",
      "Name one element such as x[1,2,:] and its axes",
      "Record current config values from JSON",
      "Locate the attention block where positions can exchange information",
    ],
    evidence: [
      "Initial byte/shape predictions",
      "Manual changed-position trace",
      "Current source revision and config",
      "Independent explanation",
    ],
    recallPrompts: [
      "Why does byte-v1 make more than one ID for 'é'? Trace [B=1,T=2,D=3] through position addition and Linear(3,5).",
      "If token 0 changes position 1 before attention, what implementation or assumption would you inspect? Explain position versus context.",
    ],
    sourceHref: "/docs/learn/session-06-tokenization-embeddings/",
    sourceLabel: "Optional tokenizer detail",
  }),
  makeSession(3, {
    title: "Single-head attention from three tokens",
    summary: "Turn query-key scores into a weighted sum of values.",
    minutes: 120,
    prerequisites: ["Day 2 tensor axes and position distinction"],
    hardware: "CPU or hand calculation; no GPU",
    objective:
      "Compute one attention row and explain why its key weights sum to one.",
    sections: [
      {
        heading: "Scores, scale, and values",
        paragraphs: [
          "A query q scores each key k by a dot product. Divide by sqrt(key width) to control score scale, then softmax across keys, not query rows or batches.",
          "For three tokens of width two, Q,K,V are each [3,2]. Q @ K.T is [3,3]: a row is one query's scores over three keys. Softmax makes each row nonnegative and sum to one. Weights [3,3] @ V [3,2] gives contextual vectors [3,2]. Today there is no causal mask; Day 4 adds it.",
        ],
      },
    ],
    workedExample: [
      {
        heading: "Two keys first",
        paragraphs: [
          "For q=[1,0], keys [1,0] and [0,1], values [2,0] and [0,2], scaled scores are approximately [0.707,0]. Softmax weights are about [0.670,0.330], and the output is about [1.340,0.660]. The rounded values guide intuition; code uses full precision.",
        ],
      },
    ],
    predictionPrompt:
      "For q0=[1,0], K=[[1,0],[0,1],[1,1]], V=[[2,0],[0,2],[2,2]], predict the scaled scores, which two keys tie, and whether the output's first coordinate exceeds its second.",
    exercise:
      "Set Q=[[1,0],[0,1],[1,1]], K=Q, and V=[[2,0],[0,2],[2,2]]. Hand-work query row 0, then use the starter snippet on CPU to compute all rows. Compare the first output within 0.01 and check row sums. Change V[2] to [4,0] while keeping Q,K fixed; predict which outputs can change, then rerun.",
    starterCode: [
      "import math",
      "import torch",
      "Q = torch.tensor([[1.,0.],[0.,1.],[1.,1.]])",
      "K = Q.clone()",
      "V = torch.tensor([[2.,0.],[0.,2.],[2.,2.]])",
      "# TODO: scores [3,3], weights [3,3], output [3,2]",
      "# Check weights.sum(-1) against torch.ones(3).",
    ].join("\n"),
    workPlaceholder:
      "First-row hand scores, weights, output, CPU check, changed-value result…",
    explanationPrompt:
      "Why does each query row sum to one over keys? What does V contribute that score weights alone do not?",
    masteryGate:
      "Self-review: hand and code output agree within 0.01; name the softmax axis and explain the changed-value result.",
    answerGuide: [
      {
        heading: "First-row answer",
        paragraphs: [
          "Scaled scores are approximately [0.707,0,0.707]. Weights are [0.401,0.198,0.401]. Output is about [1.604,1.198]. Keys 0 and 2 tie.",
          "Changing V[2] can change every output row with nonzero weight on key 2. Q,K and the weights stay fixed.",
        ],
        code: [
          "scores = Q @ K.T / math.sqrt(Q.shape[-1])",
          "weights = torch.softmax(scores, dim=-1)",
          "out = weights @ V",
          "assert torch.allclose(weights.sum(-1), torch.ones(3))",
        ].join("\n"),
      },
    ],
    checks: [
      "scores [3,3], weights [3,3], output [3,2]",
      "Rows sum to one within 1e-6",
      "First output near [1.604,1.198] within 0.01",
      "A wrong softmax axis shows up in row sums",
    ],
    evidence: [
      "Prediction",
      "Hand-worked first row and code result",
      "Changed V experiment",
      "Own explanation",
    ],
    recallPrompts: [
      "For q=[0,1] and two orthogonal keys, explain score, weight, and output shapes and the key axis.",
      "Weights sum to one down columns instead of across each query row. Identify the likely axis error and its effect.",
    ],
    sourceHref: "/docs/learn/session-10-attention/",
    sourceLabel: "Optional attention detail",
  }),
  makeSession(4, {
    title: "Causal masks and multiple heads",
    summary: "Prevent future-token leakage and label every head axis.",
    minutes: 120,
    prerequisites: ["Day 3 attention row and key-axis softmax"],
    hardware: "CPU or hand calculation; no GPU",
    objective:
      "Mask future keys, verify causal isolation, and trace multi-head shapes.",
    sections: [
      {
        heading: "Causal direction",
        paragraphs: [
          "At query position i, a causal decoder may read keys at positions 0..i. It must hide later keys. Fill forbidden score cells with negative infinity before softmax; those cells receive zero weight.",
          "For three positions, the allowed-key matrix is [[1,0,0],[1,1,0],[1,1,1]]. Masking after softmax is wrong because remaining weights no longer sum to one unless renormalized. The reference model constructs a lower-triangular mask.",
        ],
      },
      {
        heading: "Head axes",
        paragraphs: [
          "With batch B, sequence T, model width D, and H heads, each head width is d=D/H. Q,K,V reshape from [B,T,D] to [B,H,T,d]. Scores are [B,H,T,T]; softmax is on the final key axis. Each head output [B,H,T,d] is combined back to [B,T,D].",
          "A future-token edit must leave earlier causal outputs unchanged when parameters and earlier tokens are fixed. An earlier-token edit may affect later output; it need not always change the final argmax.",
        ],
      },
    ],
    workedExample: [
      {
        heading: "Three-token mask",
        paragraphs: [
          "Using Day 3's Q,K,V, row 0 may read only key 0. Its weights become [1,0,0] and output V[0]=[2,0]. Row 1 may read keys 0 and 1; row 2 may read all three. The forbidden upper-right cells are zero after softmax.",
        ],
      },
    ],
    predictionPrompt:
      "For B=2,T=3,D=8,H=2, predict d and the Q, score, head-output, and recombined shapes. Before code, predict whether replacing V[2] can change outputs at queries 0 or 1 under a causal mask.",
    exercise:
      "Take the Day 3 arrays. Build allowed=torch.tril(torch.ones(3,3,dtype=torch.bool)); fill scores where allowed is false with -inf before softmax. Record weights and output. Replace only V[2] and assert earlier outputs match within 1e-6. Then diagnose this planted bug: allowed=torch.triu(torch.ones(3,3,dtype=torch.bool)); scores.masked_fill(~allowed,-inf). Identify the future leak and fix it. Separately write the B=2,T=3,D=8,H=2 shape trace.",
    starterCode: [
      "allowed = torch.tril(torch.ones(3, 3, dtype=torch.bool))",
      "scores = Q @ K.T / math.sqrt(2)",
      "# TODO: mask forbidden future cells BEFORE softmax",
      "# TODO: weights = softmax(..., dim=-1); out = weights @ V",
      "# TODO: change V[2], recompute, compare out[:2]",
    ].join("\n"),
    workPlaceholder:
      "Shape prediction, mask matrix, output comparison, planted-bug diagnosis…",
    explanationPrompt:
      "Why must the mask be applied before key-axis softmax? Explain the direction of the causal guarantee and the difference between heads and sequence positions.",
    masteryGate:
      "Self-review: correct [B,H,T,d] and [B,H,T,T] axes; future-value change leaves earlier outputs equal; fix the transposed-mask failure.",
    answerGuide: [
      {
        heading: "Mask and shape check",
        paragraphs: [
          "d=4; Q [2,2,3,4], scores [2,2,3,3], head outputs [2,2,3,4], recombined [2,3,8].",
          "The allowed mask is lower-triangular. With changed V[2], rows 0 and 1 are unchanged; row 2 can change. The planted upper-triangular mask reverses the allowed direction and lets earlier queries see future keys.",
        ],
        code: [
          "masked = scores.masked_fill(~allowed, float('-inf'))",
          "weights = torch.softmax(masked, dim=-1)",
          "out = weights @ V",
          "changed_V = V.clone()",
          "changed_V[2] = torch.tensor([9.0, -9.0])",
          "changed_out = weights @ changed_V",
          "torch.testing.assert_close(out[:2], changed_out[:2], rtol=1e-6, atol=1e-7)",
        ].join("\n"),
      },
    ],
    checks: [
      "No fully masked query row",
      "Forbidden weights are zero",
      "Each allowed row sums to one",
      "Future-only edit preserves earlier outputs within 1e-6",
    ],
    evidence: [
      "Initial shape and dependency prediction",
      "Mask and outputs",
      "Bug diagnosis and corrected test",
      "Independent causal explanation",
    ],
    recallPrompts: [
      "For T=4, write allowed keys for each query row and explain why row 1 cannot read key 3.",
      "A causal test fails only after transposing a mask. Name the likely axis/direction error and a minimal changed-token test.",
    ],
    sourceHref: "/docs/learn/session-10-attention/",
    sourceLabel: "Optional causal-attention detail",
  }),
  makeSession(5, {
    title: "A transformer block and output head",
    summary:
      "Trace residuals, normalization, MLP, and the distinction between inference and training.",
    minutes: 120,
    prerequisites: ["Day 4 causal attention and head shapes"],
    hardware: "CPU/source review; no training run",
    objective:
      "Annotate one reference block from token vectors to logits and locate where loss would enter.",
    sections: [
      {
        heading: "One reference block",
        paragraphs: [
          "Read python_ref/model.py TransformerBlock rather than assuming every transformer has one universal ordering. This reference uses layer normalization around causal attention and an MLP, with residual additions that preserve [B,T,D].",
          "The attention path mixes allowed positions. The MLP acts independently at each position: Linear(D,hidden), nonlinearity, Linear(hidden,D). A nonlinearity lets the two-layer path express more than one collapsed linear map. Add each path back to a same-shaped residual.",
          "After all blocks, final normalization retains [B,T,D]. The reference can use its token embedding matrix as a tied output head; [B,T,D] maps to logits [B,T,V]. Check tie_embeddings in the current config.",
        ],
      },
      {
        heading: "Forward versus learning",
        paragraphs: [
          "Inference computes activations and logits with fixed parameters. Training additionally compares logits with targets to form a loss, backpropagates derivatives, and applies an optimizer update. No gradient or weight update is needed for today's forward trace.",
          "A residual is a sum, so both paths must have the same shape. LayerNorm rescales features within each token representation; it is not a cross-position attention operator.",
        ],
      },
    ],
    workedExample: [
      {
        heading: "Small block shape trace",
        paragraphs: [
          "Let B=1,T=2,D=4,H=2,MLP hidden=8,V=16. Head width is 2. Attention scores [1,2,2,2] and recombined attention [1,2,4]. After residual and normalization the MLP expands [1,2,4] to [1,2,8], then contracts to [1,2,4]. Final logits are [1,2,16].",
        ],
      },
    ],
    predictionPrompt:
      "Before reading the source details, for B=2,T=3,D=8,H=2,MLP hidden=16,V=32, predict shapes at attention scores, attention output, first residual, MLP hidden, second residual, final norm, and logits. Where would a loss enter if targets were supplied?",
    exercise:
      "Inspect TransformerBlock.forward, MLP.forward, posttrainllm.forward, and _head in python_ref/model.py at a recorded revision. Draw the actual call order and label all shapes using the prediction dimensions; compare the order with your first guess. Name the source's GELU nonlinearity. Construct a deliberate shape bug: imagine MLP's second projection returned width 15 while residual width is 8. Predict the failing addition and repair the width on paper. No training run.",
    workPlaceholder:
      "Predicted and source-checked block trace, nonlinearity, residual bug repair…",
    explanationPrompt:
      "Explain what attention can mix that the position-wise MLP cannot, why residual widths must match, and where loss/backprop would enter a training call.",
    masteryGate:
      "Self-review: source-correct ordering, every axis annotated, a repaired residual mismatch, and clear forward-versus-training distinction.",
    answerGuide: [
      {
        heading: "Shape and failure check",
        paragraphs: [
          "For B=2,T=3,D=8,H=2, score [2,2,3,3]; attention and both residual outputs [2,3,8]; MLP hidden [2,3,16]; final norm [2,3,8]; logits [2,3,32].",
          "An MLP output width 15 cannot be added to a width-8 residual. Restore the final MLP projection to width 8. In this reference, a forward call with targets computes cross-entropy loss from logits; backward and optimizer update are separate from the pure inference call. The current block is pre-LayerNorm: x + attn(ln1(x)), then x + mlp(ln2(x)).",
        ],
      },
    ],
    checks: [
      "Residual additions have identical shapes",
      "MLP hidden width returns to D",
      "Reference source order is cited at the current revision",
      "Loss/backprop are identified without claiming a training run",
    ],
    evidence: [
      "Predicted trace",
      "Source-corrected trace and revision",
      "Residual bug diagnosis",
      "Own explanation",
    ],
    recallPrompts: [
      "Trace B=1,T=4,D=6,H=3,hidden=12,V=20 through one block and the output head.",
      "A residual add fails after an MLP refactor. Which widths must match? Why does a nonlinear activation matter?",
    ],
    sourceHref: "/docs/learn/llm-mechanics-fundamentals/",
    sourceLabel: "Optional full-model walkthrough",
  }),
  makeSession(6, {
    title: "Trace the reference decoder on CPU",
    summary:
      "Connect the tiny exercises to the repository's complete causal model.",
    minutes: 300,
    prerequisites: ["Days 1–5 shapes, causal attention, and block trace"],
    hardware:
      "Apple-silicon Mac CPU; local PyTorch environment; one bounded smoke run",
    objective:
      "Trace token IDs to logits in python_ref/model.py and retain one reproducible correctness baseline.",
    sections: [
      {
        heading: "The integration path",
        paragraphs: [
          "The Day 1 toy had no context path. The reference decoder adds learned position vectors, causal self-attention, residual blocks, a position-wise MLP, final normalization, and a tied or untied output head according to config.",
          "The CPU smoke in scripts/learning/inference_week1.py uses random initialization. It checks shapes, future-token isolation, and one earlier-token fixture; its one measured forward time is unstable and is not a throughput benchmark or learner-mastery grader.",
          "Read config and code at one git revision before running. Record the actual Python/PyTorch versions and CPU device. The script's output is machine evidence; your annotated trace and explanation are separate evidence.",
        ],
      },
    ],
    workedExample: [
      {
        heading: "How to annotate one operation",
        paragraphs: [
          "For hypothetical B=1,T=3,D=4,V=16, token IDs [1,3] select embeddings [1,3,4]. Adding position vectors preserves [1,3,4]. A causal attention block also returns [1,3,4]; the tied output projection produces [1,3,16]. This example supplies shapes, not measured results or the current config numbers.",
        ],
      },
    ],
    predictionPrompt:
      "Before execution, read configs/model.byte-tinygpt-v0.json and predict input, token/position embedding, Q/K/V, per-head score, block output, and logits shapes for the script's [1,4] input. Predict which logits a final-token edit may change and which last-position logits an earlier edit may change.",
    exercise:
      "From repo root, record git rev-parse HEAD and .venv/bin/python -c 'import torch; print(torch.__version__)' (or your audited isolated Python). Read python_ref/model.py and the config; annotate the actual path and head count. Run exactly one .venv/bin/python scripts/learning/inference_week1.py. Save raw JSON, revision, config, CPU/PyTorch environment, and your trace. If an assertion fails, investigate; do not rewrite the result as a pass. Explain why the fixture's earlier-token delta is an observation, while future-token isolation is the causal property.",
    starterCode: [
      "git rev-parse HEAD",
      ".venv/bin/python -c 'import torch; print(torch.__version__)'",
      ".venv/bin/python scripts/learning/inference_week1.py",
    ].join("\n"),
    workPlaceholder:
      "Pre-run predictions, annotated source trace, exact command/environment, raw JSON and discrepancies…",
    explanationPrompt:
      "In your own words trace IDs → token+position vectors → causal attention → MLP/residuals → final norm → output head. Explain changed-token results and why one timing is only a smoke observation.",
    masteryGate:
      "Self-review: current-config shapes, passing bounded smoke or an honestly diagnosed failure, saved raw output, and an independent causal explanation. No claim of stable performance.",
    answerGuide: [
      {
        heading: "Interpret the smoke",
        paragraphs: [
          "The expected fields include input_shape, embedding_shape, logits_shape, future_token_prefix_max_delta, earlier_token_last_max_delta, and checks. Exact dimensions come from the config, not this guide. The script asserts future-token isolation to 1e-6 and a positive earlier-token delta on its nondegenerate fixture.",
          "An earlier change may influence a later position through causal attention; it is not a theorem that every changed earlier token must change every later output. Do not interpret the single one_forward_ms_unstable value as a serving benchmark.",
        ],
      },
    ],
    checks: [
      "Exact revision/config/environment retained",
      "Predicted shapes compared with raw JSON",
      "Causal isolation assertion passed or failure investigated",
      "Single timing labeled unstable",
    ],
    evidence: [
      "Prediction before run",
      "Annotated code/source trace",
      "Raw JSON and environment",
      "Own explanation plus unresolved discrepancy",
    ],
    recallPrompts: [
      "On new B,T values, predict embedding and logits shapes and trace why a final-token edit cannot change earlier causal logits.",
      "A one-pass timing improved after a code edit. Why is that insufficient for a speed claim? Name controls needed in Week 3.",
    ],
    sourceHref: "/docs/learn/llm-mechanics-fundamentals/",
    sourceLabel: "Optional reference trace",
  }),
  makeSession(7, {
    title: "Reconstruct, debug, and defend the baseline",
    summary:
      "Prove the forward path on changed shapes and diagnose a mask failure.",
    minutes: 300,
    prerequisites: ["Day 6 trace and raw CPU smoke evidence"],
    hardware: "CPU/manual debugging; no training or cache implementation",
    objective:
      "Reconstruct the forward path closed-book, fix one causal bug, and state what the Week 1 evidence does and does not show.",
    sections: [
      {
        heading: "A closed-book check",
        paragraphs: [
          "Set aside the Day 6 diagram. Rebuild the path from token IDs to logits with axis names and the causal dependency direction. Then inspect the source to correct omissions, preserving the first attempt.",
          "A failing test is useful evidence. Change one assumption at a time, identify the earliest divergent intermediate, and keep the failed trace beside the fix. A mask orientation or softmax-axis bug can produce plausible shapes and wrong semantics.",
          "The week establishes a CPU correctness baseline on a random small model. It does not establish trained language ability, stable speed, CUDA execution, or KV-cache correctness. Week 2 introduces generation and cache behavior only after this gate.",
        ],
      },
    ],
    workedExample: [
      {
        heading: "A smaller failure diagnosis",
        paragraphs: [
          "With T=2, the causal allowed matrix is [[1,0],[1,1]]. If an implementation uses [[1,1],[0,1]], query 0 sees future key 1. Changing only token 1 can then change output 0. The shape [2,2] still looks valid, so a changed-token test is necessary.",
        ],
      },
    ],
    predictionPrompt:
      "Closed-book: for B=2,T=5,D=12,H=3,V=40, predict IDs, token-plus-position, per-head Q/K/V, score, recombined block, and logits shapes. Predict the effect of changing only the last token on earlier logits.",
    exercise:
      "Write the closed-book path and compare it with python_ref/model.py. Debug this planted failure: allowed=torch.triu(torch.ones(T,T,dtype=torch.bool)); scores=scores.masked_fill(~allowed,float('-inf')). For T=3, write the allowed matrix, predict which output leaks future information, then replace triu with the correct direction. Construct a minimal changed-final-token test and state its tolerance. Review Day 6's raw JSON and write a short result/limitations note. Do not implement KV caching yet.",
    starterCode: [
      "# Planted bug: inspect before changing",
      "allowed = torch.triu(torch.ones(T, T, dtype=torch.bool))",
      "scores = scores.masked_fill(~allowed, float('-inf'))",
      "# TODO: write the allowed matrix for T=3 and a future-token isolation test.",
    ].join("\n"),
    workPlaceholder:
      "Closed-book shape trace, planted-bug prediction/fix, changed-token check, result/limits…",
    explanationPrompt:
      "Defend the causal dependency direction, the corrected mask, and the limits of your Week 1 CPU evidence. Which exact Week 2 question is still open?",
    masteryGate:
      "Self-review: changed-shape trace is correct, bug is fixed with a future-token test, raw evidence is cited, and limitations are explicit. A missed concept gets a targeted retry, not automatic completion.",
    answerGuide: [
      {
        heading: "Reconstruction and bug check",
        paragraphs: [
          "IDs [2,5]; token-plus-position [2,5,12]; per-head Q/K/V [2,3,5,4]; scores [2,3,5,5]; recombined block [2,5,12]; logits [2,5,40].",
          "For T=3, triu allows [[1,1,1],[0,1,1],[0,0,1]], leaking future keys into early queries. tril gives [[1,0,0],[1,1,0],[1,1,1]]. With fixed model parameters, changing only the final ID must leave logits at positions before it equal within the declared tolerance.",
        ],
        code: [
          "allowed = torch.tril(torch.ones(T, T, dtype=torch.bool))",
          "assert torch.allclose(original_logits[:, :-1], changed_logits[:, :-1], atol=1e-6)",
        ].join("\n"),
      },
    ],
    checks: [
      "All changed shapes and axes correct",
      "Lower-triangular allowed matrix",
      "Future-only change preserves earlier logits within 1e-6",
      "Report separates run, source reading, hand simulation, and unknowns",
    ],
    evidence: [
      "Unedited closed-book attempt and corrected trace",
      "Bug diagnosis and test",
      "Day 6 raw output reference",
      "Result/limitations note and Week 2 readiness",
    ],
    recallPrompts: [
      "For B=1,T=6,D=16,H=4,V=64, reconstruct the shape path and causal mask without notes.",
      "A model passes shape checks but earlier logits change after a future-token edit. Give two likely bug locations and one discriminating test.",
    ],
    sourceHref: "/docs/learn/inference-systems-13w/",
    sourceLabel: "Open the 13-week route",
  }),
];
