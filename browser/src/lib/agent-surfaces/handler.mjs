// Generated from sass-maker/saas-maker tooling/lib/agent-surfaces; use sync-agent-readability.mjs.
import { wantsMarkdown, markdownPathFor, htmlPathFromMarkdown, markdownResponse } from './http.mjs';
import { listMarkdownRoutes, buildMarkdownIndex, buildAiTxt, buildFullMarkdown } from './documents.mjs';

const reserved = /^\/(?:api|admin|auth|dashboard|_next|_astro|\.well-known)(?:\/|$)/;
const nativeMarkdown = new Set(['/auth.md', '/skill.md', '/SKILL.md', '/agents.md', '/AGENTS.md']);
const documents = new Set(['/llms.txt', '/llms-full.txt', '/ai.txt', '/api/ai', '/api/md/_catalog']);

/** A loader is reachable only through the explicitly enumerated public registry. */
export function createAgentSurfaceHandler(options) {
  const { manifest, loadMarkdown } = options;
  if (!manifest) throw new TypeError('createAgentSurfaceHandler: manifest required');
  // Some public documentation sites use names such as /dashboard. Exceptions
  // are exact, source-reviewed HTML routes, never API or infrastructure paths.
  const publicReservedPaths = new Set(options.publicReservedPaths || []);
  for (const path of publicReservedPaths) {
    if (!/^\/(?:admin|auth|dashboard)(?:\/[^*?#\\]*)?$/.test(path)) throw new TypeError(`Invalid public route exception: ${path}`);
  }
  let snapshot;
  let expires = 0;
  let full;

  async function registry() {
    if (!snapshot || Date.now() >= expires) {
      full = undefined;
      expires = Date.now() + 86400000;
      snapshot = Promise.resolve(options.listMarkdownRoutes?.() ?? listMarkdownRoutes(manifest)).then((routes) => {
        const seen = new Set();
        return routes.map((route) => {
          const path = route.path;
          if (!path?.startsWith('/') || path.startsWith('//') || (reserved.test(path) && !publicReservedPaths.has(path)) || /[?#\\]/.test(path) || new URL(path, manifest.origin).pathname !== path) {
            throw new TypeError(`Invalid public Markdown route: ${path}`);
          }
          if (seen.has(path)) throw new TypeError(`Duplicate Markdown route: ${path}`);
          seen.add(path);
          return { ...route, url: new URL(path, manifest.origin).href, md: new URL(markdownPathFor(path), manifest.origin).href };
        });
      }).catch((error) => { snapshot = undefined; throw error; });
    }
    return snapshot;
  }

  async function render(path) {
    const pages = manifest.pages;
    if (Object.hasOwn(pages, path)) return pages[path];
    const mdPath = markdownPathFor(path);
    if (Object.hasOwn(pages, mdPath)) return pages[mdPath];
    // Public, cacheable renderers never inherit cookies, authorization or query state.
    return loadMarkdown ? loadMarkdown(path, new Request(new URL(path, manifest.origin)), (await registry()).find((route) => route.path === path)) : null;
  }

  return async function handleAgentSurface(request) {
    const path = new URL(request.url).pathname;
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method)) return null;
    if (nativeMarkdown.has(path) || options.preserveMarkdownPaths?.includes(path)) return null;
    const direct = path === '/api/md' || path.startsWith('/api/md/');
    const suffix = path.endsWith('.md') && !reserved.test(path);
    if (!direct && !suffix && !documents.has(path) && (!manifest.negotiation || !wantsMarkdown(request))) return null;
    const routes = await registry();
    const htmlPath = direct ? '/' + path.replace(/^\/api\/md\/?/, '') : suffix ? htmlPathFromMarkdown(path) : path;
    const route = routes.find((entry) => entry.path.replace(/\/$/, '') === htmlPath.replace(/\/$/, '') || entry.aliases?.includes(path));
    if (!documents.has(path) && !direct && !suffix && !route) return null;
    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: {
        'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
        'Access-Control-Allow-Headers': 'Accept', 'Access-Control-Max-Age': '86400',
      } });
    }
    let response;
    if (path === '/llms.txt') response = text(buildMarkdownIndex(manifest, routes));
    else if (path === '/ai.txt') response = text(buildAiTxt(manifest, routes));
    else if (path === '/api/ai') response = text(JSON.stringify(manifest.catalog), 'application/json; charset=utf-8');
    else if (path === '/api/md/_catalog') response = text(JSON.stringify(routes), 'application/json; charset=utf-8');
    else if (path === '/llms-full.txt') {
      full ??= buildFullMarkdown(manifest, routes, render, options.fullLimits).catch((error) => { full = undefined; throw error; });
      response = text(await full);
    } else {
      const body = route ? await render(route.path) : null;
      const canonical = route?.url || new URL(htmlPath, manifest.origin).href;
      response = markdownResponse(body ?? '# Not found\n\nNo public Markdown page exists at this path.\n', request, {
        'Content-Location': canonical,
        Link: `<${canonical}>; rel="canonical"`,
        ...(body == null ? { 'Cache-Control': 'no-store' } : {}),
        ...(route?.lastModified ? { 'Last-Modified': new Date(route.lastModified).toUTCString() } : {}),
      });
      if (body == null) response = new Response(response.body, { status: 404, headers: response.headers });
    }
    response.headers.append('Link', discoveryLinkHeader(manifest.origin));
    if (!suffix && !direct && !documents.has(path)) {
      // Cloudflare's URL cache does not partition on Vary: Accept.
      response.headers.set('CDN-Cache-Control', 'no-store');
      response.headers.set('Cloudflare-CDN-Cache-Control', 'no-store');
    }
    return request.method === 'HEAD' ? new Response(null, { status: response.status, headers: response.headers }) : response;
  };
}

export function discoveryLinkHeader(origin) {
  return ['/llms.txt', '/llms-full.txt', '/ai.txt'].map((path) => `<${new URL(path, origin).href}>; rel="describedby"`).join(', ');
}

function text(body, type = 'text/plain; charset=utf-8') {
  return new Response(body, { headers: {
    'Content-Type': type, 'Cache-Control': 'public, s-maxage=86400, stale-while-revalidate=604800',
    'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
    'X-Content-Type-Options': 'nosniff',
  } });
}
