## Why

posttrainllm publishes 324 canonical HTML pages across the Astro browser, Blume
documentation, and deterministic fine-tune report cards, but its root sitemap
and agent catalog expose only a fraction of them. A source-derived indexing
contract is needed so search engines and AI agents can discover the same public
surface without mistaking APIs, data files, redirects, or private run artifacts
for pages.

## What Changes

- Build one canonical public-route inventory from generated Astro pages, Blume
  documentation, and committed report cards.
- Generate a merged sitemap, `/api/ai` catalog, `llms.txt` indexes, and
  substantive Markdown counterparts for every public HTML page from that shared
  inventory.
- Preserve machine-readable APIs, JSON, RSS, gallery data, local run output,
  models, and private artifacts as separate non-page resources or exclusions.
- Add canonical and social metadata to deterministic report-card pages without
  changing their evidence, outcomes, or decision semantics.
- Point robots and page metadata at the merged sitemap and validate route,
  catalog, and Markdown integrity during the normal browser build.

## Capabilities

### New Capabilities

- `public-agent-indexing`: Source-derived discovery and agent-readable coverage
  for every canonical public posttrainllm HTML route.

### Modified Capabilities

- `fine-tune-report-card`: Public report-card HTML gains discovery metadata
  while retaining the canonical `decision.json`-derived outcome and evidence.

## Impact

The change affects the browser build, public indexing files, deterministic
report-card HTML generation, and their focused checks. It adds no runtime or
production dependency, performs no training or model loading, and does not
deploy. `decision.json` remains the terminal quality and product authority.
