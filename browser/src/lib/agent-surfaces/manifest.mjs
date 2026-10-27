// Generated from sass-maker/saas-maker tooling/lib/agent-surfaces; use sync-agent-readability.mjs.
import { buildLlmsTxt } from './llms.mjs';
import { listMarkdownRoutes, buildMarkdownIndex } from './documents.mjs';
import { buildApiAiCatalog } from './catalog.mjs';
import { markdownPathFor } from './http.mjs';

/**
 * Single source of truth for a product's agent surfaces.
 *
 * @typedef {import('./llms.mjs').LlmsMeta} LlmsMeta
 * @typedef {import('./catalog.mjs').ApiAiCatalog} ApiAiCatalog
 * @typedef {import('./catalog.mjs').AgentSurface} AgentSurface
 *
 * @typedef {{
 *   name: string,
 *   url: string,
 *   summary: string,
 *   contact?: string,
 *   openapi?: string,
 *   updatedAt?: string,
 *   trainingAllowed?: boolean,
 *   excludedPaths?: string[],
 *   mode?: 'static' | 'collection' | 'dynamic' | 'spa',
 *   product?: import('./llms.mjs').LlmsLink[],
 *   docs?: import('./llms.mjs').LlmsLink[],
 *   feeds?: import('./llms.mjs').LlmsLink[],
 *   optional?: import('./llms.mjs').LlmsLink[],
 *   notes?: string[],
 *   surfaces?: AgentSurface[],
 *   pages?: Record<string, string>,
 *   llmsFull?: string | null,
 *   sitemap?: string | null,
 *   auth?: { public?: boolean, notes?: string },
 *   negotiation?: boolean,
 * }} AgentSurfaceConfig
 *
 * pages: map of pathname → markdown body (for static/runtime serve)
 */

/**
 * @param {AgentSurfaceConfig} config
 */
export function createAgentSurfaceManifest(config) {
  if (!config?.name || !config?.url || !config?.summary) {
    throw new TypeError('createAgentSurfaceManifest requires name, url, summary');
  }

  const origin = config.url.replace(/\/$/, '');
  const pages = { ...(config.pages || {}) };

  // Ensure homepage has an index.md key if pages has "/" content.
  if (pages['/'] && !pages['/index.md']) {
    pages['/index.md'] = pages['/'];
  }

  const surfaces =
    config.surfaces ||
    deriveSurfacesFromPages(pages, config.mode || 'static');

  const catalog = buildApiAiCatalog({
    name: config.name,
    url: origin,
    llmsFull: `${origin}/llms-full.txt`,
    sitemap: config.sitemap,
    markdown: { suffix: '.md', negotiation: config.negotiation ?? true },
    surfaces,
    auth: config.auth,
  });

  const llmsTxt = buildLlmsTxt({
    name: config.name,
    summary: config.summary,
    url: origin,
    product: config.product,
    docs: config.docs,
    feeds: config.feeds,
    optional: config.optional,
    notes: config.notes,
  });

  const manifest = {
    origin,
    name: config.name,
    summary: config.summary,
    contact: config.contact,
    openapi: config.openapi,
    notes: config.notes,
    updatedAt: config.updatedAt,
    trainingAllowed: config.trainingAllowed ?? false,
    excludedPaths: config.excludedPaths,
    mode: config.mode || 'static',
    llmsTxt,
    llmsFull: config.llmsFull ?? null,
    catalog,
    pages,
    negotiation: config.negotiation ?? true,
  };
  if (Object.keys(pages).length) manifest.llmsTxt = buildMarkdownIndex(manifest, listMarkdownRoutes(manifest));
  return manifest;
}

/**
 * @param {Record<string, string>} pages
 * @param {string} kind
 * @returns {import('./catalog.mjs').AgentSurface[]}
 */
function deriveSurfacesFromPages(pages, kind) {
  const surfaces = [];
  const seen = new Set();

  for (const key of Object.keys(pages)) {
    let htmlPath = key;
    if (key.endsWith('.md')) {
      htmlPath = key === '/index.md' ? '/' : key.slice(0, -3);
    }
    if (seen.has(htmlPath)) continue;
    seen.add(htmlPath);
    const id =
      htmlPath === '/'
        ? 'home'
        : htmlPath.replace(/^\//, '').replace(/\//g, '-') || 'page';
    surfaces.push({
      id,
      url: htmlPath,
      md: markdownPathFor(htmlPath),
      kind: /** @type {any} */ (kind === 'spa' ? 'spa' : kind === 'collection' ? 'collection' : kind === 'dynamic' ? 'dynamic' : 'static'),
    });
  }

  if (surfaces.length === 0) {
    surfaces.push({ id: 'home', url: '/', md: '/index.md', kind: 'static' });
  }
  return surfaces;
}
