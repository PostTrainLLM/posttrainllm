#!/usr/bin/env node
/**
 * export_leaderboard.mjs — generate leaderboard.json + leaderboard.csv from
 * the same gallery manifest the leaderboard page renders.
 *
 * The leaderboard page (browser/src/pages/leaderboard.astro) fetches
 * /gallery/manifest.json at runtime and groups models by benchmark id.
 * This script produces static exports from the same source so users can
 * download the data without running the page.
 *
 * Usage:
 *   node scripts/archive/export_leaderboard.mjs
 *
 * Outputs:
 *   browser/public/data/leaderboard.json
 *   browser/public/data/leaderboard.csv
 */
import { readFileSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const MANIFEST = resolve(ROOT, "browser/public/gallery/manifest.json");
const OUT_JSON = resolve(ROOT, "browser/public/data/leaderboard.json");
const OUT_CSV = resolve(ROOT, "browser/public/data/leaderboard.csv");

const BENCH_META = {
  "tinystories-ppl": {
    name: "TinyStories PPL",
    lowerIsBetter: true,
    unit: "perplexity",
    description:
      "Held-out perplexity over 50 stories from a slice of the TinyStories corpus that wasn't seen during gallery training. Score = exp(mean per-byte cross-entropy). Lower is better.",
  },
  "sort-6": {
    name: "Sort-6",
    lowerIsBetter: false,
    unit: "accuracy",
    description:
      'Karpathy minGPT algorithmic task. Prompt is "sort: 5 1 4 2 6 3 = ", model must continue "1 2 3 4 5 6". Exact-match accuracy over 200 deterministic trials. Higher is better.',
  },
  "reverse-16": {
    name: "Reverse-16",
    lowerIsBetter: false,
    unit: "accuracy",
    description:
      "Reverse a lowercase string of up to 16 characters. Exact-match over 200 deterministic trials. Higher is better.",
  },
  "fineweb-ppl-bpe": {
    name: "FineWeb PPL (BPE)",
    lowerIsBetter: true,
    unit: "perplexity",
    description:
      "Held-out perplexity over a 5MB FineWeb-style text slice, scored token-level using the model's BPE tokenizer. Lower is better.",
  },
};

function formatParams(n) {
  if (n == null) return null;
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(0) + "K";
  return String(n);
}

function formatDuration(ms) {
  if (ms == null) return null;
  const min = ms / 60000;
  if (min >= 60) return (min / 60).toFixed(1) + " hr";
  if (min >= 1) return min.toFixed(0) + " min";
  return (ms / 1000).toFixed(0) + " s";
}

function main() {
  const raw = readFileSync(MANIFEST, "utf-8");
  const manifest = JSON.parse(raw);

  const benchmarks = Object.entries(BENCH_META).map(([id, meta]) => ({
    id,
    ...meta,
    scored_entries: 0,
  }));

  const entries = (manifest.models || []).map((m) => {
    const scores = {};
    for (const [benchId, benchMeta] of Object.entries(BENCH_META)) {
      const raw = m.benchmarks?.[benchId];
      if (raw != null) {
        scores[benchId] = {
          score: raw,
          rank: null, // filled below
        };
        const b = benchmarks.find((b) => b.id === benchId);
        if (b) b.scored_entries++;
      }
    }
    return {
      id: m.id,
      name: m.name,
      icon: m.icon || null,
      params: m.params || formatParams(m.paramCount),
      param_count: m.paramCount ?? null,
      corpus: m.corpus || null,
      corpus_url: m.corpusUrl || null,
      train_loss: m.trainLoss ?? null,
      steps: m.steps ?? null,
      train_wall: formatDuration(m.trainWallMs) ?? null,
      train_wall_ms: m.trainWallMs ?? null,
      browser_trained: m.submission?.browserTrained ?? false,
      featured: m.submission?.featured ?? false,
      author: m.submission?.author ?? null,
      scores,
    };
  });

  // Compute ranks per benchmark
  for (const [benchId, meta] of Object.entries(BENCH_META)) {
    const scored = entries
      .filter((e) => e.scores[benchId] != null)
      .sort((a, b) =>
        meta.lowerIsBetter
          ? a.scores[benchId].score - b.scores[benchId].score
          : b.scores[benchId].score - a.scores[benchId].score,
      );
    scored.forEach((e, i) => {
      e.scores[benchId].rank = i + 1;
    });
  }

  const payload = {
    generated_at: new Date().toISOString(),
    source: "/gallery/manifest.json",
    note: manifest.note || "",
    benchmarks,
    entries,
  };

  writeFileSync(OUT_JSON, JSON.stringify(payload, null, 2) + "\n", "utf-8");

  // CSV: one row per (model, benchmark) with a score
  const csvLines = [
    "rank,model_id,model_name,params,param_count,corpus,browser_trained,featured,benchmark,benchmark_name,score,unit,lower_is_better,train_wall_ms",
  ];
  for (const e of entries) {
    for (const [benchId, meta] of Object.entries(BENCH_META)) {
      const s = e.scores[benchId];
      if (s == null) continue;
      const row = [
        s.rank ?? "",
        csv(e.id),
        csv(e.name),
        csv(e.params ?? ""),
        e.param_count ?? "",
        csv(e.corpus ?? ""),
        e.browser_trained,
        e.featured,
        csv(benchId),
        csv(meta.name),
        s.score,
        csv(meta.unit),
        meta.lowerIsBetter,
        e.train_wall_ms ?? "",
      ];
      csvLines.push(row.join(","));
    }
  }
  writeFileSync(OUT_CSV, csvLines.join("\n") + "\n", "utf-8");

  const totalRows = csvLines.length - 1;
  console.log(`leaderboard.json  → ${OUT_JSON}`);
  console.log(`leaderboard.csv   → ${OUT_CSV} (${totalRows} rows)`);
}

function csv(val) {
  const s = String(val ?? "");
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

main();
