// Generated from sass-maker/saas-maker tooling/lib/agent-surfaces; use sync-agent-readability.mjs.
/**
 * Absolutize authored links without changing code examples or real .md routes.
 * @param {string} markdown
 * @param {string} canonical
 * @param {{htmlPathsByMarkdown?: Record<string, string>, resolveLink?: (href: string) => string | undefined}} options
 */
export function absoluteMarkdownLinks(markdown, canonical, { htmlPathsByMarkdown = {}, resolveLink } = {}) {
  const code = [];
  const protect = (text) => {
    const token = `\u0000markdown-code-${code.length}\u0000`;
    const newline = text.endsWith('\n') ? '\n' : '';
    code.push(newline ? text.slice(0, -1) : text);
    return token + newline;
  };
  const source = markdown
    .replace(/^( {0,3})(`{3,}|~{3,})[^\n]*\n[\s\S]*?^\1\2[^\n]*(?:\n|$)/gm, protect)
    .replace(/(`+)([^`]|(?!\1)`)*?\1/g, protect);
  function destination(raw) {
    const angle = raw.startsWith('<') && raw.endsWith('>');
    const href = angle ? raw.slice(1, -1) : raw;
    const resolved = resolveLink?.(href);
    if (resolved !== undefined) return angle ? `<${resolved}>` : resolved;
    const url = new URL(href, canonical);
    if (url.origin === new URL(canonical).origin && Object.hasOwn(htmlPathsByMarkdown, url.pathname)) {
      url.pathname = htmlPathsByMarkdown[url.pathname];
    } else if (/^[a-z][a-z0-9+.-]*:/i.test(href)) return raw;
    return angle ? `<${url.href}>` : url.href;
  }
  return source
    .replace(/(!?\[[^\]\n]*\]\()(\s*)(<[^>\n]+>|[^\s)]+)(?=[\s)])/g, (_match, lead, space, href) => `${lead}${space}${destination(href)}`)
    .replace(/^( {0,3}\[[^\]\n]+\]:\s*)(<[^>\n]+>|\S+)/gm, (_match, lead, href) => `${lead}${destination(href)}`)
    .replace(/\u0000markdown-code-(\d+)\u0000/g, (_match, index) => code[Number(index)]);
}
