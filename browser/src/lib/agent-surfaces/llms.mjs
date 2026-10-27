// Generated from sass-maker/saas-maker tooling/lib/agent-surfaces; use sync-agent-readability.mjs.
/**
 * Build llmstxt.org-style index documents.
 *
 * @typedef {{ title: string, url: string, description?: string }} LlmsLink
 * @typedef {{
 *   name: string,
 *   summary: string,
 *   url?: string,
 *   product?: LlmsLink[],
 *   docs?: LlmsLink[],
 *   feeds?: LlmsLink[],
 *   optional?: LlmsLink[],
 *   notes?: string[],
 * }} LlmsMeta
 */

/**
 * @param {LlmsMeta} meta
 * @returns {string}
 */
export function buildLlmsTxt(meta) {
  if (!meta?.name) throw new TypeError('buildLlmsTxt: meta.name required');
  if (!meta?.summary) throw new TypeError('buildLlmsTxt: meta.summary required');

  const lines = [`# ${meta.name}`, '', `> ${meta.summary.trim()}`, ''];

  if (meta.notes?.length) {
    for (const note of meta.notes) lines.push(note);
    lines.push('');
  }

  appendSection(lines, 'Product', meta.product);
  appendSection(lines, 'Docs', meta.docs);
  appendSection(lines, 'Feeds', meta.feeds);
  appendSection(lines, 'Optional', meta.optional);

  // Always point agents at the machine catalog when present.
  if (meta.url) {
    const origin = meta.url.replace(/\/$/, '');
    lines.push('## Machine surfaces');
    lines.push('');
    lines.push(`- [Agent catalog](${origin}/api/ai): JSON inventory of public surfaces`);
    lines.push(`- [This index](${origin}/llms.txt)`);
    lines.push('');
  }

  return lines.join('\n').replace(/\n{3,}/g, '\n\n');
}

/**
 * @param {string[]} lines
 * @param {string} heading
 * @param {LlmsLink[] | undefined} links
 */
function appendSection(lines, heading, links) {
  if (!links?.length) return;
  lines.push(`## ${heading}`, '');
  for (const link of links) {
    const desc = link.description ? `: ${link.description}` : '';
    lines.push(`- [${link.title}](${link.url})${desc}`);
  }
  lines.push('');
}
