import { defineConfig } from 'blume';

// PRDs and OpenSpec content are public by default. Set DOCS_PUBLIC_INTERNAL=false
// to exclude internal-only trees (prds/**, openspec/**) from the build.
const publicInternal = process.env.DOCS_PUBLIC_INTERNAL !== 'false';

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
  title: 'posttrainllm docs',
  description:
    'Mac-local LLM factory documentation — training, inference, evals, systems notes, and learning paths.',
  content: {
    // Point directly at the repo's canonical docs tree so there is exactly
    // one home for every doc. Relative to this config file (docs-site/).
    root: '../docs',
    exclude: publicInternal ? [] : ['prds/**', 'openspec/**'],
  },
  github: {
    owner: 'PostTrainLLM',
    repo: 'posttrainllm',
    branch: 'main',
    dir: 'docs',
  },
  search: {
    provider: 'orama',
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
    base: '/docs',
    site: 'https://posttrainllm.com',
    output: 'static',
  },
});
