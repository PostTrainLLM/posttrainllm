#!/usr/bin/env node

/**
 * Build gate for canonical learning evidence.
 *
 * Every tracked source object must resolve to one HTML page, one generated
 * Markdown counterpart, one self-canonical URL, one JSON-LD record, and one
 * sitemap entry with an explicit freshness date.
 */
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const browserRoot = path.resolve(here, "..");
const repoRoot = path.resolve(browserRoot, "..");
const dist = path.join(browserRoot, "dist");
const origin = "https://posttrainllm.com";

const readJson = (relative) =>
  JSON.parse(readFileSync(path.join(repoRoot, relative), "utf8"));

const attempts = readJson("docs/attempts.json").attempts;
const recipes = readJson("docs/recipes/registry.json").recipes;
const learningPaths = readJson("docs/learn/path-registry.json").paths;
const learningArtifacts = readJson(
  "docs/learn/artifact-journey.json",
).stages.flatMap((stage) => stage.artifacts);
const studies = readJson("docs/studies/registry.json").studies;

const records = [
  ...studies.map((record) => ({ ...record, route: `/studies/${record.id}` })),
  ...attempts.map((record) => ({
    ...record,
    route: `/experiments/${record.id}`,
  })),
  ...recipes.map((record) => ({ ...record, route: `/recipes/${record.id}` })),
  ...learningPaths.map((record) => ({
    ...record,
    route: `/learn/paths/${record.id}`,
  })),
  ...learningArtifacts.map((record) => ({
    ...record,
    route: `/learn/artifacts/${record.id}`,
  })),
];

const sitemap = readFileSync(path.join(dist, "sitemap.xml"), "utf8");
const failures = [];
const titles = new Map();
const descriptions = new Map();
const seenRoutes = new Set();

const decode = (value) =>
  value
    .replaceAll("&amp;", "&")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">");

const strip = (html) =>
  decode(
    html
      .replace(/<(script|style|svg|noscript)\b[\s\S]*?<\/\1>/giu, " ")
      .replace(/<[^>]+>/gu, " "),
  )
    .replace(/\s+/gu, " ")
    .trim();

function capture(html, pattern) {
  return decode(html.match(pattern)?.[1]?.trim() ?? "");
}

for (const record of records) {
  if (seenRoutes.has(record.route)) {
    failures.push(`${record.route}: duplicate canonical route`);
    continue;
  }
  seenRoutes.add(record.route);

  const relative = record.route.slice(1);
  const htmlPath = path.join(dist, `${relative}.html`);
  const markdownPath = path.join(dist, `${relative}.md`);
  if (!existsSync(htmlPath)) {
    failures.push(`${record.route}: HTML route missing`);
    continue;
  }
  if (!existsSync(markdownPath)) {
    failures.push(`${record.route}: Markdown route missing`);
  }

  const html = readFileSync(htmlPath, "utf8");
  const canonical = capture(html, /<link\s+rel="canonical"\s+href="([^"]+)"/iu);
  if (canonical !== `${origin}${record.route}`) {
    failures.push(`${record.route}: canonical is ${canonical || "missing"}`);
  }
  if (
    !html.includes(
      `rel="alternate" type="text/markdown" href="${record.route}.md"`,
    )
  ) {
    failures.push(`${record.route}: Markdown alternate link missing`);
  }
  if (!/<script[^>]+type="application\/ld\+json"/iu.test(html)) {
    failures.push(`${record.route}: JSON-LD missing`);
  }
  const h1Count = [...html.matchAll(/<h1(?:\s|>)/gu)].length;
  const h2Count = [...html.matchAll(/<h2(?:\s|>)/gu)].length;
  if (h1Count !== 1)
    failures.push(`${record.route}: expected one h1, found ${h1Count}`);
  if (h2Count < 2)
    failures.push(`${record.route}: expected substantive h2 sections`);

  const title = capture(html, /<title>([\s\S]*?)<\/title>/iu);
  const description = capture(
    html,
    /<meta\s+name="description"\s+content="([^"]+)"/iu,
  );
  for (const [kind, value, index] of [
    ["title", title, titles],
    ["description", description, descriptions],
  ]) {
    if (!value) {
      failures.push(`${record.route}: ${kind} missing`);
    } else if (index.has(value)) {
      failures.push(
        `${record.route}: duplicate ${kind} shared with ${index.get(value)}`,
      );
    } else {
      index.set(value, record.route);
    }
  }

  const main = html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/iu)?.[1] ?? "";
  const words = strip(main).split(/\s+/u).filter(Boolean).length;
  if (words < 300) {
    failures.push(`${record.route}: thin dossier (${words} words)`);
  }

  const sitemapPattern = new RegExp(
    `<loc>${origin.replaceAll(".", "\\.")}${record.route.replaceAll("/", "\\/")}</loc><lastmod>\\d{4}-\\d{2}-\\d{2}</lastmod>`,
    "u",
  );
  if (!sitemapPattern.test(sitemap)) {
    failures.push(`${record.route}: sitemap lastmod missing`);
  }
}

if (failures.length) {
  for (const failure of failures) console.error(`KNOWLEDGE INDEX: ${failure}`);
  console.error(`knowledge-index check failed: ${failures.length} findings`);
  process.exit(1);
}

console.log(
  `knowledge-index check ok: ${records.length} source objects, ${seenRoutes.size} canonical HTML routes, Markdown parity and sitemap freshness`,
);
