export const BENCHES = {
  "tinystories-ppl": {
    name: "TinyStories PPL",
    lowerIsBetter: true,
    explainer:
      "<strong>TinyStories PPL.</strong> Held-out perplexity over 50 stories from a slice of the TinyStories corpus that wasn't seen during gallery training. Score = exp(mean per-byte cross-entropy). Lower is better. The cleanest universal benchmark — every byte-level LM gets a real number, with clear differentiation between in-distribution and out-of-distribution models.",
  },
  "sort-6": {
    name: "Sort-6",
    lowerIsBetter: false,
    explainer:
      '<strong>Sort-6.</strong> Karpathy minGPT algorithmic task. Prompt is "sort: 5 1 4 2 6 3 = ", model must continue "1 2 3 4 5 6". Exact-match accuracy over 200 deterministic trials, higher is better. The existing gallery cards score near 0% because they were never trained on this task — this benchmark exists for SUBMISSIONS that target it directly. The pareto view "score per params" rewards getting to 90%+ with the fewest params.',
  },
  "reverse-16": {
    name: "Reverse-16",
    lowerIsBetter: false,
    explainer:
      "<strong>Reverse-16.</strong> Reverse a lowercase string of up to 16 characters. Slightly harder than sort-6 because the last input character must become the first of the output (longer dependency tail across the equals sign). Same Karpathy task family. Exact-match over 200 deterministic trials, higher is better.",
  },
  "fineweb-ppl-bpe": {
    name: "FineWeb PPL (BPE)",
    lowerIsBetter: true,
    explainer:
      "<strong>FineWeb PPL (BPE).</strong> Held-out perplexity over a 5MB FineWeb-style text slice, scored token-level using the model's BPE tokenizer. Lower is better. Byte-level browser-trained models score `null` (incompatible vocab); BPE models scored natively via `posttrainllm score-bench` (see docs/bpe_browser_scoring.md).",
  },
};
