// Generated from sass-maker/saas-maker tooling/lib/agent-surfaces; use sync-agent-readability.mjs.
import { htmlPathFromMarkdown, markdownPathFor } from './http.mjs';

/** Registry entries are explicitly public. Never populate them from user state. */
export function listMarkdownRoutes(manifest) {
  const paths = new Map();
  for (const [key, body] of Object.entries(manifest.pages)) {
    const path = key.endsWith('.md') ? htmlPathFromMarkdown(key) : key;
    if (paths.has(path)) continue;
    const surface = manifest.catalog.surfaces.find((item) => new URL(item.url).pathname === path);
    paths.set(path, {
      path,
      url: new URL(path, manifest.origin).href,
      md: new URL(markdownPathFor(path), manifest.origin).href,
      title: body.match(/^#\s+(.+)$/m)?.[1] || surface?.id || path,
      description: surface?.description || body.match(/^>\s+(.+)$/m)?.[1] || '',
    });
  }
  return [...paths.values()];
}

export function buildMarkdownIndex(manifest, routes) {
  const lines = [`# ${manifest.name}`, '', `> ${manifest.summary}`, '',
    ...(manifest.notes || []), '',
    '<!-- Keep in sync with robots.txt and ai.txt. -->', '', '## Public pages', ''];
  for (const route of routes.slice(0, 50)) {
    lines.push(`- [${escapeLabel(route.title)}](${route.md}): ${route.description || route.title}`);
  }
  if (routes.length > 50) lines.push('', `Showing 50 of ${routes.length} pages; the catalog lists all public routes.`);
  lines.push('', '## Machine-readable', '',
    `- [Full content](${manifest.origin}/llms-full.txt): Bounded public page content`,
    `- [Markdown catalog](${manifest.origin}/api/md/_catalog): All registered public routes`,
    `- [Agent catalog](${manifest.origin}/api/ai): Existing discovery contract`,
    `- [AI usage policy](${manifest.origin}/ai.txt): Permissions and attribution`);
  if (manifest.catalog.sitemap) lines.push(`- [Sitemap](${manifest.catalog.sitemap}): Canonical HTML pages`);
  if (manifest.openapi) lines.push(`- [OpenAPI](${manifest.openapi}): Public API contract`);
  return `${lines.join('\n')}\n`;
}

export function buildAiTxt(manifest, routes) {
  const contact = manifest.contact;
  return [
    '# Keep in sync with robots.txt and llms.txt.',
    '[identity]', `name: ${manifest.name}`, `url: ${manifest.origin}`, `description: ${manifest.summary}`,
    ...(contact ? [`contact: ${contact}`] : []), '',
    '[permissions]', 'allowed: summarise, quote with attribution, cite, index for search/answers',
    ...(manifest.trainingAllowed ? ['training: allowed on public pages only'] : []), '',
    '[restrictions]', 'No fabricated quotes or reviews/ratings.',
    'Do not present this content as your own.', 'No training on private user data.', '',
    '[attribution]', `cite: ${manifest.name} and the canonical HTML URL`, '',
    '[scope]', `included: public routes listed at ${manifest.origin}/api/md/_catalog`,
    `public-route-count: ${routes.length}`,
    `excluded: ${(manifest.excludedPaths || ['/admin', '/api', '/dashboard', '/auth']).join(', ')}`, '',
    ...(contact ? ['[contact]', `contact: ${contact}`, ''] : []),
    ...(manifest.updatedAt ? [`Last updated: ${manifest.updatedAt}`, ''] : []),
  ].join('\n');
}

export async function buildFullMarkdown(manifest, routes, render, { maxChars = 500000, maxPages = 50 } = {}) {
  const header = `# ${manifest.name} - full content\n\n> ${manifest.summary}\n\nGenerated: ${new Date().toISOString().slice(0, 10)}\n\n`;
  const footer = `\nFull catalog: ${manifest.origin}/api/md/_catalog\n`;
  let body = header;
  let included = 0;
  for (const route of routes) {
    if (route.full === false) continue;
    if (included >= maxPages) break;
    const markdown = await render(route.path);
    if (markdown == null) continue;
    const section = `---\n<!-- source: ${route.url} -->\n${markdown}\n\n`;
    if (body.length + section.length + footer.length + 150 > maxChars) {
      console.warn(`Full Markdown export reached its ${maxChars}-character limit after ${included} pages.`);
      break;
    }
    body += section;
    included++;
  }
  return `${body}Included ${included} of ${routes.length} registered public pages (limit ${maxPages} pages / ${maxChars} characters).\n${footer}`;
}

function escapeLabel(value) {
  return value.replace(/[\\[\]]/g, '\\$&').replace(/[\r\n]/g, ' ');
}
