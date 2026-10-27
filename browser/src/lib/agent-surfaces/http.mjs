// Generated from sass-maker/saas-maker tooling/lib/agent-surfaces; use sync-agent-readability.mjs.
/** Paths that must never fall through to an SPA HTML shell. */
const AGENT_PATHS = new Set([
  '/llms.txt',
  '/llms-full.txt',
  '/ai.txt',
  '/api/ai',
  '/skill.md',
  '/agents.md',
  '/humans.txt',
  '/.well-known/skills/index.json',
  '/.well-known/agent.json',
  '/.well-known/mcp.json',
]);

/**
 * @param {string} pathname
 * @returns {boolean}
 */
export function isAgentPath(pathname) {
  if (!pathname) return false;
  const path = normalizePath(pathname);
  if (AGENT_PATHS.has(path)) return true;
  if (path.endsWith('.md')) return true;
  if (path.startsWith('/.well-known/skills/')) return true;
  return false;
}

/**
 * @param {string} htmlPath e.g. "/" or "/pricing"
 * @returns {string} e.g. "/index.md" or "/pricing.md"
 */
export function markdownPathFor(htmlPath) {
  const path = normalizePath(htmlPath);
  if (path === '/') return '/index.md';
  if (path.endsWith('.md')) return path;
  return `${path.replace(/\/$/, '')}.md`;
}

/**
 * @param {string} mdPath e.g. "/index.md" or "/pricing.md"
 * @returns {string}
 */
export function htmlPathFromMarkdown(mdPath) {
  const path = normalizePath(mdPath);
  if (path === '/index.md') return '/';
  if (path.endsWith('.md')) return path.slice(0, -3);
  return path;
}

/**
 * Prefer markdown when Accept ranks text/markdown over text/html
 * (or when only markdown/plain is offered).
 *
 * @param {Request | { headers?: Headers | Record<string, string> }} request
 * @returns {boolean}
 */
export function wantsMarkdown(request) {
  const headers = request?.headers;
  const accept =
    typeof headers?.get === 'function'
      ? headers.get('accept') || ''
      : headers?.accept || headers?.Accept || '';
  if (!accept) return false;
  const ranges = accept.toLowerCase().split(',').map((part) => {
    const [type, ...parameters] = part.trim().split(';');
    const weights = parameters.map((value) => value.trim()).filter((value) => /^q\s*=/.test(value));
    const raw = weights[0]?.split('=')[1]?.trim();
    const q = weights.length > 1 || (raw !== undefined && !/^(?:0(?:\.\d{0,3})?|1(?:\.0{0,3})?)$/.test(raw))
      ? 0 : raw === undefined ? 1 : Number(raw);
    return { type: type.trim(), q };
  });
  // Wildcards never opt into Markdown. Specific media ranges override them.
  const markdown = ranges.filter(({ type }) => type === 'text/markdown');
  if (!markdown.length) return false;
  const quality = (types) => {
    for (const type of types) {
      const matches = ranges.filter((range) => range.type === type);
      if (matches.length) return Math.min(...matches.map((range) => range.q));
    }
    return 0;
  };
  return quality(['text/markdown']) > quality(['text/html', 'text/*', '*/*']);
}

/**
 * Detect SPA / HTML shell responses that fake agent endpoints.
 * @param {string | ArrayBuffer | Uint8Array} body
 * @param {string} [contentType]
 */
export function isHtmlShell(body, contentType = '') {
  const ct = (contentType || '').toLowerCase();
  if (ct.includes('text/html') || ct.includes('application/xhtml')) return true;
  const text = bodyToPreview(body);
  if (!text) return false;
  const head = text.slice(0, 200).toLowerCase();
  return (
    head.includes('<!doctype') ||
    head.includes('<html') ||
    head.includes('<div id="root"') ||
    head.includes('<div id="app"')
  );
}

/**
 * @param {string} body
 * @param {string} contentType
 * @param {Record<string, string>} [extraHeaders]
 */
export function textResponse(body, contentType = 'text/plain; charset=utf-8', extraHeaders = {}) {
  return new Response(body, {
    status: 200,
    headers: {
      'Content-Type': contentType,
      'Cache-Control': 'public, max-age=300',
      ...extraHeaders,
    },
  });
}

/**
 * @param {unknown} data
 * @param {Record<string, string>} [extraHeaders]
 */
export function jsonResponse(data, extraHeaders = {}) {
  return new Response(JSON.stringify(data, null, 2) + '\n', {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'public, max-age=300',
      ...extraHeaders,
    },
  });
}

/**
 * @param {string} body
 * @param {Request | { headers?: Headers }} [request] for Accept negotiation
 * @param {Record<string, string>} [extraHeaders]
 */
export function markdownResponse(body, request, extraHeaders = {}) {
  return new Response(request?.method === 'HEAD' ? null : body, {
    headers: {
      'Content-Type': 'text/markdown; charset=utf-8',
      'X-Markdown-Tokens': String(Math.ceil(body.length / 4)),
      'X-Robots-Tag': 'noindex, follow',
      'Cache-Control': 'public, s-maxage=3600, stale-while-revalidate=86400',
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
      'X-Content-Type-Options': 'nosniff',
      Vary: 'Accept',
      ...extraHeaders,
    },
  });
}

/**
 * @param {string} mdPath absolute path starting with /
 */
export function alternateLinkHeader(mdPath) {
  const path = normalizePath(mdPath);
  return `<${path}>; rel="alternate"; type="text/markdown"`;
}

function normalizePath(pathname) {
  if (!pathname) return '/';
  try {
    if (pathname.startsWith('http://') || pathname.startsWith('https://')) {
      pathname = new URL(pathname).pathname;
    }
  } catch {
    /* keep raw */
  }
  let path = pathname.split('?')[0].split('#')[0];
  if (!path.startsWith('/')) path = `/${path}`;
  if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1);
  return path || '/';
}

function bodyToPreview(body) {
  if (body == null) return '';
  if (typeof body === 'string') return body;
  if (body instanceof Uint8Array) {
    return new TextDecoder().decode(body.slice(0, 256));
  }
  return '';
}
