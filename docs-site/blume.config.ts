import { defineConfig } from "blume";

// PRDs and OpenSpec content are public by default. Set DOCS_PUBLIC_INTERNAL=false
// to exclude internal-only trees (prds/**, openspec/**) from the build.
const publicInternal = process.env.DOCS_PUBLIC_INTERNAL !== "false";

/**
 * posttrainllm documentation — Blume (AI-ready docs).
 *
 * Static build emits llms.txt, llms-full.txt, per-page .md mirrors, sitemap,
 * robots, and agent-readability.json with zero custom Worker code.
 *
 * Source of truth: the committed Markdown under `../docs` (the repo's
 * canonical docs tree). Blume is only the presentation + search layer; it
 * never owns content. Do not edit `docs-site/docs/` — that path is a
 * build-time scratch dir and is gitignored.
 *
 * Custom domain (recommended): https://docs.posttrainllm.com
 */
export default defineConfig({
  title: "PostTrainLLM docs",
  description:
    "Mac-local LLM factory documentation — training, inference, evals, systems notes, and learning paths.",
  content: {
    // Point directly at the repo's canonical docs tree so there is exactly
    // one home for every doc. Relative to this config file (docs-site/).
    root: "../docs",
    exclude: publicInternal ? [] : ["prds/**", "openspec/**"],
  },
  navigation: {
    // Keep every page at its existing URL; show curated entrances in the
    // sidebar instead of an alphabetical dump of the research corpus.
    sidebar: [
      "/",
      {
        label: "Current learning",
        display: "group",
        collapsed: false,
        items: ["/learn", "/learn/inference-systems-13w", "/learning-progress"],
      },
      {
        label: "Foundations and labs",
        display: "group",
        items: [
          "/learn/curriculum",
          "/learn/README",
          "/learn/artifact-journey",
          "/learn/coverage-map",
          "/learning-pipeline",
        ],
      },
      {
        label: "Reference library",
        display: "group",
        items: [
          "/library",
          "/learn/llm-mechanics-fundamentals",
          "/learn/advanced-llm-inference",
          "/industry_learning_roadmap",
          "/techniques/README",
          "/recipes/README",
        ],
      },
      {
        label: "Factory handbook",
        display: "group",
        items: [
          "/quickstart",
          "/cli-reference",
          "/factory/README",
          "/factory/eval-protocol",
          "/factory/packaging",
          "/factory/reports",
        ],
      },
      {
        label: "Evidence and decisions",
        display: "group",
        items: [
          "/attempt-ledger",
          "/factory/public-artifacts",
          "/research/mac_decode_baseline_m5pro",
          "/audits/history-coverage-audit",
          "/external-products-reviewed",
        ],
      },
      {
        label: "History and parked work",
        display: "group",
        items: [
          "/doc-status",
          "/NEXT",
          "/prds/README",
          "/roadmap/index",
          "/parked/README",
          "/learn/legacy-walkthrough",
        ],
      },
    ],
  },
  github: {
    owner: "PostTrainLLM",
    repo: "posttrainllm",
    branch: "main",
    dir: "docs",
  },
  search: {
    provider: "orama",
  },
  ai: {
    llmsTxt: true,
  },
  seo: {
    agentReadability: true,
    sitemap: true,
    robots: true,
  },
  deployment: {
    // Served at the apex under /docs (posttrainllm.com/docs) — no separate
    // product/subdomain. base prefixes every asset + route.
    base: "/docs",
    site: "https://posttrainllm.com",
    output: "static",
  },
});
