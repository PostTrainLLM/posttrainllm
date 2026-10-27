import { authoredHtmlToMarkdown } from "./authored-markdown.mjs";
import type { KnowledgeRecord } from "../data/knowledgeGraph";
import type { EditorialContent } from "../data/education-content";
import readingContract from "../content/public/dossier-reading.json";

const publicOrigin = "https://posttrainllm.com";
export function markdownLink(label: string, href: string): string {
  return `[${label.replaceAll("[", "\\[").replaceAll("]", "\\]")}](${new URL(href, publicOrigin).href})`;
}
export function knowledgeMarkdown(record: KnowledgeRecord): string {
  return (
    [
      `# ${record.title}`,
      record.kindLabel,
      record.description,
      ...record.facts.map((fact) => `**${fact.label}:** ${fact.value}`),
      ...record.sections.flatMap((section) => [
        `## ${section.title}`,
        ...(section.paragraphs ?? []),
        ...(section.items ?? []).map((item) => `- ${item}`),
      ]),
      "## How to read this dossier",
      ...readingContract,
      "## Source provenance",
      `The normalized record comes from \`${record.sourceRecord}\`. The links below are the tracked evidence and explanatory sources preserved with the record.`,
      ...record.sources.map(
        (source) => `- ${markdownLink(source.label, source.href)}`,
      ),
      "## Related evidence",
      ...record.relations.map(
        (relation) => `- ${markdownLink(relation.label, relation.href)}`,
      ),
      `Canonical record: \`${record.kind}:${record.id}\``,
    ].join("\n\n") + "\n"
  );
}
export function editorialMarkdown(content: EditorialContent): string {
  return (
    [
      `# ${content.title}`,
      content.description,
      authoredHtmlToMarkdown(content.html),
      "## Continue through the factory",
      ...content.internalLinks.map(
        (href) =>
          `- ${markdownLink(href.replace(/^\//, "").replaceAll("-", " "), href)}`,
      ),
    ].join("\n\n") + "\n"
  );
}

export function markdownTable(columns: string[], rows: string[][]): string {
  const line = (row: string[]) =>
    `| ${row.map((cell) => cell.replaceAll("|", "\\|").replaceAll("\n", " ")).join(" | ")} |`;
  return [
    line(columns),
    line(columns.map(() => "---")),
    ...rows.map(line),
  ].join("\n");
}
