// Render authored rich-text fragments shared with Astro, never built HTML.
export function authoredHtmlToMarkdown(source) {
  const blocks = [];
  const text = source
    .replace(/<table\b[^>]*>([\s\S]*?)<\/table\s*>/gi, (_, table) => {
      const rows = [...table.matchAll(/<tr\b[^>]*>([\s\S]*?)<\/tr\s*>/gi)].map(
        (row) =>
          [...row[1].matchAll(/<t[hd]\b[^>]*>([\s\S]*?)<\/t[hd]\s*>/gi)].map(
            (cell) =>
              authoredHtmlToMarkdown(cell[1])
                .replaceAll("|", "\\|")
                .replace(/\s*\n\s*/g, " "),
          ),
      );
      if (!rows.length) return "";
      const width = Math.max(...rows.map((row) => row.length));
      const line = (row) =>
        `| ${Array.from({ length: width }, (_, i) => row[i] || "").join(" | ")} |`;
      const markdown = [
        line(rows[0]),
        line(Array(width).fill("---")),
        ...rows.slice(1).map(line),
      ].join("\n");
      const index = blocks.push(`\n\n${markdown}\n\n`) - 1;
      return `\nSOURCE_CODE_${index}\n`;
    })
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<(script|style|svg|button)\b[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(
      /(?:<pre\b[^>]*>|<div\b[^>]*class=["'][^"']*code-body[^"']*["'][^>]*>)([\s\S]*?)(?:<\/pre>|<\/div>)/gi,
      (_, code) => {
        const index =
          blocks.push(
            `\n\n\`\`\`\n${decode(code.replace(/<[^>]+>/g, "")).trim()}\n\`\`\`\n\n`,
          ) - 1;
        return `\nSOURCE_CODE_${index}\n`;
      },
    )
    .replace(
      /<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1\s*>/gi,
      (_, level, value) =>
        `\n\n${"#".repeat(Number(level))} ${value
          .replace(/<br\s*\/?>/gi, " ")
          .replace(/\s+/g, " ")
          .trim()}\n\n`,
    )
    .replace(
      /<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a\s*>/gi,
      (_, href, value) => `[${value.replace(/<[^>]*>/g, "").trim()}](${href})`,
    )
    .replace(/<(?:strong|b)\b[^>]*>([\s\S]*?)<\/(?:strong|b)\s*>/gi, "**$1**")
    .replace(/<code\b[^>]*>([\s\S]*?)<\/code\s*>/gi, "`$1`")
    .replace(/<li\b[^>]*>/gi, "\n- ")
    .replace(/<\/?(?:p|div|section|article|ul|ol|header)\b[^>]*>/gi, "\n\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(?:span|small|dt|dd)\s*>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .split("\n")
    .map((line) =>
      decode(line)
        .replace(/[ \t]+/g, " ")
        .trim(),
    )
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
  return text
    .replace(/SOURCE_CODE_(\d+)/g, (_, index) => blocks[Number(index)])
    .trim();
}
function decode(text) {
  return text
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&amp;/g, "&")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)));
}
