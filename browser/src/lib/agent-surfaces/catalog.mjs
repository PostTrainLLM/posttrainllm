// Generated from sass-maker/saas-maker tooling/lib/agent-surfaces; use sync-agent-readability.mjs.
/**
 * @typedef {{
 *   id: string,
 *   url: string,
 *   md?: string | null,
 *   kind: 'static' | 'collection' | 'dynamic' | 'api' | 'feed' | 'spa',
 *   description?: string,
 * }} AgentSurface
 *
 * @typedef {{
 *   name: string,
 *   version?: string,
 *   url: string,
 *   llms?: string,
 *   llmsFull?: string | null,
 *   sitemap?: string | null,
 *   markdown?: { suffix?: string, negotiation?: boolean },
 *   surfaces: AgentSurface[],
 *   auth?: { public?: boolean, notes?: string },
 * }} ApiAiCatalog
 */

function mapSurface(origin, s) {
  return {
    id: s.id,
    url: absolutize(origin, s.url),
    md: s.md == null ? null : absolutize(origin, s.md),
    kind: s.kind,
    ...(s.description ? { description: s.description } : {}),
  };
}

/**
 * @param {ApiAiCatalog} input
 * @returns {ApiAiCatalog}
 */
export function buildApiAiCatalog(input) {
  if (!input?.name) throw new TypeError('buildApiAiCatalog: name required');
  if (!input?.url) throw new TypeError('buildApiAiCatalog: url required');
  if (!Array.isArray(input.surfaces)) {
    throw new TypeError('buildApiAiCatalog: surfaces[] required');
  }

  const origin = input.url.replace(/\/$/, '');
  const catalog = {
    name: input.name,
    version: input.version || '1',
    url: origin,
    llms: input.llms || `${origin}/llms.txt`,
    llmsFull: input.llmsFull === undefined ? null : input.llmsFull,
    sitemap: input.sitemap === undefined ? `${origin}/sitemap.xml` : input.sitemap,
    markdown: {
      suffix: input.markdown?.suffix ?? '.md',
      negotiation: input.markdown?.negotiation ?? true,
    },
    surfaces: input.surfaces.map((s) => mapSurface(origin, s)),
    auth: {
      public: input.auth?.public ?? true,
      notes: input.auth?.notes ?? '',
    },
  };

  assertApiAiCatalog(catalog);
  return catalog;
}

/**
 * Lightweight runtime validation for audits and tests.
 * @param {unknown} catalog
 */
function assertApiAiCatalog(catalog) {
  if (!catalog || typeof catalog !== 'object') {
    throw new TypeError('catalog must be an object');
  }
  const c = /** @type {Record<string, unknown>} */ (catalog);
  for (const key of ['name', 'version', 'url', 'llms', 'markdown', 'surfaces']) {
    if (c[key] == null) throw new TypeError(`catalog missing ${key}`);
  }
  if (!Array.isArray(c.surfaces)) throw new TypeError('surfaces must be an array');
  const md = /** @type {Record<string, unknown>} */ (c.markdown);
  if (typeof md.suffix !== 'string' || typeof md.negotiation !== 'boolean') {
    throw new TypeError('markdown.suffix and markdown.negotiation required');
  }
  return true;
}

/**
 * @param {string} origin
 * @param {string} pathOrUrl
 */
function absolutize(origin, pathOrUrl) {
  if (!pathOrUrl) return pathOrUrl;
  if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) return pathOrUrl;
  const path = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`;
  return `${origin}${path}`;
}
