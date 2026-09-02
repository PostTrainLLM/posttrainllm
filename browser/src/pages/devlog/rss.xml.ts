/**
 * /devlog/rss.xml — RSS feed for the PostTrainLLM devlog.
 *
 * The devlog is a single long-form page (browser/src/pages/devlog.astro) with
 * dated sections. This endpoint emits a valid RSS 2.0 feed with one <item>
 * per section so feed readers can surface individual entries.
 *
 * Entries are anchored to the real section headings on the live page; each
 * item links back to /devlog with the section anchor.
 */

const ORIGIN = "https://posttrainllm.com";

interface DevlogEntry {
  title: string;
  description: string;
  guid: string;
  date: string;
}

const entries: DevlogEntry[] = [
  {
    title: "The site you're reading — a dark research-lab redesign",
    description:
      "Unified the site into one instrument: a single dark design system, the loss-curve logo as the universal mark, machine-transparent claims, and structured-data SEO.",
    guid: "devlog-redesign",
    date: "2026-07-10",
  },
  {
    title: "The factory loop closed — and the first ship-decision was 'retry'",
    description:
      "The north star became one canonical run: target → data → post-train → eval → package → report, ending in a documented ship/reject/retry decision. It executed end-to-end for the first time on 2026-07-04.",
    guid: "devlog-factory-loop",
    date: "2026-07-04",
  },
  {
    title: "The DPO saga — a policy collapse, then a base-model prior",
    description:
      "Three DPO runs to strip SQL wrapper prose: ref-free SimPO collapsed (exec 0.860 → 0.080), reference-anchored DPO cured the collapse (0.900), but clean-SQL rate stayed 0.000 — the wrapper is a base-model prior a rank-4 adapter can't override.",
    guid: "devlog-dpo-saga",
    date: "2026-07-11",
  },
  {
    title: "Frontier parity at 4B — the distillation that worked",
    description:
      "A Qwen3-4B distilled on multi-turn file-ops trajectories reached 100% on the BFCL hard gate, up from 58%. The honest cost: out-of-domain breadth dropped 59.6% → 42.3% — real catastrophic forgetting. Ships as a routed specialist.",
    guid: "devlog-frontier-parity-4b",
    date: "2026-06-16",
  },
  {
    title: "The eval that was broken",
    description:
      "A fine-tune looked like it beat its baseline — until the baseline turned out to be non-reproducible and the v1 fixture set was measuring the wrong thing. The whole factory's eval discipline came out of that miss.",
    guid: "devlog-broken-eval",
    date: "2026-06-01",
  },
  {
    title: "The Mac runtime — MLX-Swift, OpenAI-compatible, on one machine",
    description:
      "The factory is a native Swift/MLX CLI — 100+ subcommands, one binary. It serves an OpenAI- and Ollama-compatible endpoint, runs an agent loop with FSM-constrained JSON, and packages to MLX, safetensors, and CoreML.",
    guid: "devlog-mac-runtime",
    date: "2026-06-20",
  },
  {
    title: "Learning from y = mx + b up",
    description:
      "A ground-up curriculum: ten modules from 'a model is a parameterized function' to a self-improving factory, each with a toy exercise, a repo anchor, and a mastery gate. A coverage map ties every subsystem to a learning anchor.",
    guid: "devlog-curriculum",
    date: "2026-06-25",
  },
  {
    title: "Memory64 — breaking the 4 GB tab ceiling",
    description:
      "WebAssembly's -sMEMORY64=1 + -sWASM_BIGINT flags switch the module to 64-bit pointers, lifting the cap into the tens of GB. Allocated a 473M-parameter model end-to-end in a browser tab.",
    guid: "devlog-memory64",
    date: "2026-05-20",
  },
  {
    title: "Matmul kernel sweep — what worked, what didn't",
    description:
      "Workgroup-shared tiling (16×16) + thread-level register blocking (4×4) gave up to 5.18× speedup. f16-packed storage was not additive with tiling. 8×8 register block lost at every size — register spill on Apple GPUs.",
    guid: "devlog-matmul-sweep",
    date: "2026-05-15",
  },
  {
    title: "Speed evolution — the cumulative picture",
    description:
      "From naive WASM to tiled+blocked WebGPU to Flash Attention 2: verified WASM measurements, the historical unqualified WebGPU curve, and the receipt required to reproduce it.",
    guid: "devlog-speed-evolution",
    date: "2026-05-25",
  },
  {
    title: "The lever that actually shipped — Flash Attention 2",
    description:
      "FA2 on Apple GPUs: a hand-written Metal kernel with the tiled+blocked structure from the matmul sweep. Measured forward-pass speedup and the end-to-end training parity check.",
    guid: "devlog-fa2",
    date: "2026-06-05",
  },
  {
    title: "What's next — what genuinely remains",
    description:
      "The honest roadmap: what's proven, what's parked, and what the next real milestone is — not aspiration, but the next gate that produces a ship/reject decision.",
    guid: "devlog-whats-next",
    date: "2026-07-01",
  },
  {
    title: "The bug that wasn't in any kernel",
    description:
      "An end-to-end training loss diverged 30× despite every standalone kernel benchmark passing. The bug was in the integration — the end-to-end parity test became the bar.",
    guid: "devlog-integration-bug",
    date: "2026-05-18",
  },
  {
    title: "Notes on pair-programming with AI",
    description:
      "Lessons from building the entire project AI-paired: where the AI helps, where it doesn't, and the workflow patterns that produced real results vs. wasted cycles.",
    guid: "devlog-pair-programming",
    date: "2026-06-28",
  },
];

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export function GET() {
  const pubDate = new Date().toUTCString();
  const items = entries
    .map(
      (e) => `    <item>
      <title>${escapeXml(e.title)}</title>
      <link>${ORIGIN}/devlog#${e.guid}</link>
      <guid isPermaLink="true">${ORIGIN}/devlog#${e.guid}</guid>
      <description>${escapeXml(e.description)}</description>
      <pubDate>${new Date(e.date).toUTCString()}</pubDate>
    </item>`,
    )
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>PostTrainLLM — Devlog</title>
    <link>${ORIGIN}/devlog</link>
    <description>Notes from building PostTrainLLM — kernel measurements, honest negative results, decisions made while AI-pairing on a Mac-local LLM factory.</description>
    <language>en-us</language>
    <lastBuildDate>${pubDate}</lastBuildDate>
    <atom:link href="${ORIGIN}/devlog/rss.xml" rel="self" type="application/rss+xml" />
${items}
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
