// Public report cards are compiled from these checked-in JSON contracts by
// scripts/factory/fine_tune_report_card.py. Never read their rendered HTML.
const label = (key) =>
  key.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
function valueMarkdown(value, depth = 0) {
  if (value === null) return "Not recorded";
  if (typeof value !== "object") return String(value);
  if (Array.isArray(value))
    return value.length
      ? value.map((item) => `- ${valueMarkdown(item, depth + 1)}`).join("\n")
      : "None recorded";
  if ("state" in value && "value" in value) {
    return [
      value.value === null
        ? "Not recorded"
        : valueMarkdown(value.value, depth + 1),
      value.unit ? `Unit: ${value.unit}` : "",
      `Evidence state: ${value.state}`,
      value.note,
      value.derived_from
        ? `Derived from: ${valueMarkdown(value.derived_from, depth + 1)}`
        : "",
      value.sources?.length ? `Sources: ${value.sources.join(", ")}` : "",
    ]
      .filter(Boolean)
      .join(" — ");
  }
  return Object.entries(value)
    .map(
      ([key, item]) => `**${label(key)}:** ${valueMarkdown(item, depth + 1)}`,
    )
    .join(depth ? "; " : "\n\n");
}
export function reportCardMarkdown(card) {
  if (!card.title || !card.subject || !card.decision || !card.compiled_from)
    throw new Error("Invalid public report card");
  const sections = [
    ["Subject", "subject"],
    ["Decision", "decision"],
    ["Before and after", "gates"],
    ["Per-slice evidence", "slices"],
    ["Cost and performance", "performance"],
    ["Eval validity and leakage", "eval_validity"],
    ["Caveats", "caveats"],
    ["Artifact and routing boundary", "artifact"],
    ["Source evidence", "evidence"],
    ["Compiled from", "compiled_from"],
  ];
  const covered = new Set([
    "title",
    "schema_version",
    ...sections.map(([, key]) => key),
  ]);
  // Explicitly preserve any additional public contract fields so schema growth
  // cannot silently drop evidence. All input is already published JSON.
  for (const key of Object.keys(card))
    if (!covered.has(key)) sections.push([label(key), key]);
  return (
    [
      `# ${card.title}`,
      `PostTrainLLM fine-tune report card · schema v${card.schema_version}`,
      ...sections.flatMap(([title, key]) =>
        key in card ? [`## ${title}`, valueMarkdown(card[key])] : [],
      ),
    ].join("\n\n") + "\n"
  );
}
