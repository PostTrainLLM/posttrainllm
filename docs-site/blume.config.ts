import { defineConfig } from 'blume';

/**
 * posttrainllm documentation — Blume (AI-ready docs).
 *
 * Static build emits llms.txt, llms-full.txt, per-page .md mirrors, sitemap,
 * robots, and agent-readability.json with zero custom Worker code.
 *
 * Custom domain (recommended): https://docs.posttrainllm.com
 */
export default defineConfig({
  title: 'posttrainllm docs',
  description:
    'Mac-local LLM factory documentation — training, inference, evals, systems notes, and learning paths.',
  content: {
    root: 'docs',
  },
  github: {
    owner: 'PostTrainLLM',
    repo: 'posttrainllm',
    branch: 'main',
    dir: 'docs-site/docs',
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
    site: 'https://docs.posttrainllm.com',
    output: 'static',
  },
});
