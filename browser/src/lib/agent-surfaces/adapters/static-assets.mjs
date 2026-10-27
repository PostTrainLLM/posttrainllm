// Generated from sass-maker/saas-maker tooling/lib/agent-surfaces; use sync-agent-readability.mjs.
import { createAgentSurfaceManifest } from '../manifest.mjs';
import { createAgentSurfaceHandler, discoveryLinkHeader } from '../handler.mjs';
import { wantsMarkdown } from '../http.mjs';

// Workers Assets can omit MIME for extensionless JSON. Parsing and the
// manifest/registry shape checks remain mandatory; HTML never qualifies.
function metadataType(response) {
  const type = response.headers.get('content-type');
  return !type || /^(?:application\/(?:json|octet-stream)|text\/plain)(?:;|$)/i.test(type);
}

/**
 * Serve only build-registered public Markdown assets, never the HTML fallback.
 * @param {{ origin?: string, catalogPath?: string, identity?: object, preserveMarkdownPaths?: string[], publicReservedPaths?: string[], loadMarkdown?: (path: string, request: Request, route: any) => Promise<string | null | undefined> | string | null | undefined }} options
 */
export function createStaticAssetHandler({ origin, catalogPath = '/api/md/_catalog', identity, preserveMarkdownPaths = [], publicReservedPaths = [], loadMarkdown }) {
  const handlers = new WeakMap();
  return async function handle(request, assets) {
    if (!assets?.fetch) return null;
    const pathname = new URL(request.url).pathname;
    if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method)) return null;
    const direct = pathname === '/api/md' || pathname.startsWith('/api/md/');
    const discovery = ['/llms.txt', '/llms-full.txt', '/ai.txt'].includes(pathname);
    if (!direct && !discovery) {
      if (preserveMarkdownPaths.includes(pathname) || ['/auth.md', '/skill.md', '/SKILL.md', '/agents.md', '/AGENTS.md'].includes(pathname)) return null;
      if (/^\/(?:api|admin|auth|dashboard|_next|_astro|\.well-known)(?:\/|$)/.test(pathname) && !publicReservedPaths.includes(pathname)) return null;
      // Public entity slugs can contain dots (for example /launchdesk/example.io).
      if (/\.(?:css|m?js|map|json|xml|txt|png|jpe?g|gif|svg|webp|avif|ico|woff2?|ttf|otf|mp[34]|webm|pdf|zip|wasm)$/i.test(pathname)) return null;
    }
    if (!pathname.endsWith('.md') && !pathname.startsWith('/api/md') && !['/llms.txt', '/llms-full.txt', '/ai.txt'].includes(pathname) && !wantsMarkdown(request)) return null;
    let handler = handlers.get(assets);
    if (!handler) {
      handler = (async () => {
        const assetOrigin = origin || new URL(request.url).origin;
        let config = identity;
        if (!config) {
          const response = await assets.fetch(new Request(new URL('/api/md/_identity', assetOrigin)));
          if (!response.ok || !metadataType(response)) throw new Error('Public identity unavailable');
          config = await response.json();
        }
        const canonicalOrigin = config.url || origin;
        return createAgentSurfaceHandler({
        preserveMarkdownPaths,
        publicReservedPaths,
        manifest: createAgentSurfaceManifest({ ...config, url: canonicalOrigin, pages: {} }),
        async listMarkdownRoutes() {
          const response = await assets.fetch(new Request(new URL(catalogPath, assetOrigin)));
          if (!response.ok || !metadataType(response)) throw new Error('Public Markdown catalog unavailable');
          const catalog = await response.json();
          if (!Array.isArray(catalog)) throw new TypeError('Invalid public Markdown catalog');
          return catalog;
        },
        async loadMarkdown(path, publicRequest, route) {
          const rendered = await loadMarkdown?.(path, publicRequest, route);
          if (rendered !== undefined) {
            if (rendered !== null && typeof rendered !== 'string') throw new TypeError('Public renderer must return Markdown text or null');
            return rendered;
          }
          const md = route?.assetPath || (path === '/' ? '/index.md' : `${path.replace(/\/$/, '')}.md`);
          if (!md.startsWith('/') || md.startsWith('//') || new URL(md, assetOrigin).origin !== new URL(assetOrigin).origin) throw new Error('Invalid public asset path');
          const response = await assets.fetch(new Request(new URL(md, assetOrigin)));
          if (response.status === 404) return null;
          if (!response.ok || !response.headers.get('content-type')?.includes('text/markdown')) throw new Error('Public Markdown asset unavailable');
          const body = await response.text();
          if (/^\s*<(?:!doctype|html)/i.test(body)) throw new Error('HTML fallback is not Markdown');
          return body;
        },
      });
      })().catch((error) => { handlers.delete(assets); throw error; });
      handlers.set(assets, handler);
    }
    try {
      return await (await handler)(request);
    } catch {
      return new Response(request.method === 'HEAD' ? null : '# Markdown temporarily unavailable\n', {
        status: 503, headers: {
          'Content-Type': 'text/markdown; charset=utf-8', 'Cache-Control': 'no-store',
          'CDN-Cache-Control': 'no-store', 'Cloudflare-CDN-Cache-Control': 'no-store',
          'Vary': 'Accept', 'X-Robots-Tag': 'noindex, follow',
          'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET, HEAD, OPTIONS',
        },
      });
    }
  };
}

export function advertiseMarkdown(response, origin, mdPath) {
  const headers = new Headers(response.headers);
  headers.append('Link', discoveryLinkHeader(origin));
  if (mdPath) headers.append('Link', `<${new URL(mdPath, origin).href}>; rel="alternate"; type="text/markdown"`);
  const vary = new Set((headers.get('Vary') || '').split(',').map((value) => value.trim()).filter(Boolean));
  if (!vary.has('*') && ![...vary].some((value) => value.toLowerCase() === 'accept')) vary.add('Accept');
  headers.set('Vary', [...vary].join(', '));
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}
