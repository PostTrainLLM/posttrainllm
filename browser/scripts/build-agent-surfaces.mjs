// Build the public search/agent discovery surface from the site output.
//
// Route truth is deliberately assembled after Astro and Blume have both built:
// - Astro's generated sitemap owns browser routes.
// - Blume's generated sitemap owns documentation routes and Markdown.
// - deterministic report-card HTML files are explicit public pages.
//
// Machine resources are catalogued separately and never enter the page sitemap.

import { promises as fs } from "node:fs";
import { dirname, extname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ORIGIN = "https://posttrainllm.com";
const here = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(here, "..", "dist");
const CHECK_ONLY = process.argv.includes("--check");
const MAC_RELEASE_PATH = "/releases/mac.json";

const decodeEntities = (value) =>
  value
    .replace(/&#(\d+);/g, (_, code) => String.fromCodePoint(Number(code)))
    .replace(/&#x([\da-f]+);/gi, (_, code) =>
      String.fromCodePoint(Number.parseInt(code, 16)),
    )
    .replaceAll("&nbsp;", " ")
    .replaceAll("&amp;", "&")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'");

const stripTags = (value) =>
  decodeEntities(value.replace(/<[^>]+>/g, " "))
    .replace(/\s+/g, " ")
    .trim();

function htmlToMarkdown(html, canonicalUrl) {
  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const title = stripTags(titleMatch?.[1] ?? new URL(canonicalUrl).pathname);
  const mainMatch = html.match(/<main\b[^>]*>([\s\S]*?)<\/main>/i);
  let body =
    mainMatch?.[1] ??
    html.match(/<body\b[^>]*>([\s\S]*?)<\/body>/i)?.[1] ??
    html;

  body = body
    .replace(/<(script|style|svg|noscript)\b[\s\S]*?<\/\1>/gi, "")
    .replace(/<(nav|footer|form)\b[\s\S]*?<\/\1>/gi, "")
    .replace(
      /<a\b[^>]*href=(["'])(.*?)\1[^>]*>([\s\S]*?)<\/a>/gi,
      (_, _q, href, text) => {
        const label = stripTags(text);
        if (!label) return "";
        try {
          const absolute = new URL(href, canonicalUrl);
          return `[${label}](${absolute.href})`;
        } catch {
          return label;
        }
      },
    )
    .replace(/<img\b[^>]*alt=(["'])(.*?)\1[^>]*>/gi, (_, _q, alt) =>
      alt.trim() ? ` ${alt.trim()} ` : "",
    )
    .replace(
      /<h([1-6])\b[^>]*>([\s\S]*?)<\/h\1>/gi,
      (_, level, text) =>
        `\n\n${"#".repeat(Number(level))} ${stripTags(text)}\n\n`,
    )
    .replace(
      /<li\b[^>]*>([\s\S]*?)<\/li>/gi,
      (_, text) => `\n- ${stripTags(text)}`,
    )
    .replace(/<(pre|blockquote)\b[^>]*>([\s\S]*?)<\/\1>/gi, (_, tag, text) => {
      const content = decodeEntities(text.replace(/<[^>]+>/g, "")).trim();
      if (!content) return "";
      return tag.toLowerCase() === "pre"
        ? `\n\n\`\`\`\n${content}\n\`\`\`\n\n`
        : `\n\n${content
            .split("\n")
            .map((line) => `> ${line}`)
            .join("\n")}\n\n`;
    })
    .replace(/<(p|div|section|article|header|dl|table|tr)\b[^>]*>/gi, "\n\n")
    .replace(/<\/(p|div|section|article|header|dl|table|tr)>/gi, "\n\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(
      /<(dt|th)\b[^>]*>([\s\S]*?)<\/\1>/gi,
      (_, _tag, text) => `\n\n**${stripTags(text)}**\n`,
    )
    .replace(
      /<(dd|td)\b[^>]*>([\s\S]*?)<\/\1>/gi,
      (_, _tag, text) => ` ${stripTags(text)} `,
    )
    .replace(/<[^>]+>/g, " ");

  body = decodeEntities(body)
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trimEnd())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  const heading = body.match(/^#\s+/m) ? "" : `# ${title}\n\n`;
  return `${heading}> Canonical page: ${canonicalUrl}\n\n${body}\n`;
}

function canonicalize(rawUrl) {
  const url = new URL(rawUrl, ORIGIN);
  if (url.origin !== ORIGIN) {
    throw new Error(`cross-origin sitemap URL: ${rawUrl}`);
  }
  url.hash = "";
  url.search = "";
  let path = url.pathname.replace(/\/+/g, "/");
  if (
    (path === "/docs" || path.startsWith("/docs/")) &&
    !path.endsWith("/") &&
    extname(path) === ""
  ) {
    path += "/";
  }
  url.pathname = path || "/";
  return url.href;
}

function routePath(canonicalUrl) {
  const pathname = new URL(canonicalUrl).pathname;
  return pathname.length > 1 && pathname.endsWith("/")
    ? pathname.slice(0, -1)
    : pathname;
}

async function sitemapUrls(path) {
  const xml = await fs.readFile(path, "utf8");
  return [...xml.matchAll(/<loc>([\s\S]*?)<\/loc>/g)].map((match) =>
    canonicalize(decodeEntities(match[1].trim())),
  );
}

function outputPaths(canonicalUrl) {
  const pathname = routePath(canonicalUrl);
  if (pathname === "/") {
    return { html: resolve(DIST, "index.html"), md: resolve(DIST, "index.md") };
  }
  if (pathname === "/docs") {
    return {
      html: resolve(DIST, "docs", "index.html"),
      md: resolve(DIST, "docs", "index.md"),
    };
  }
  if (pathname.startsWith("/docs/")) {
    const subpath = pathname.slice("/docs/".length);
    return {
      html: resolve(DIST, "docs", subpath, "index.html"),
      md: resolve(DIST, "docs", `${subpath}.md`),
    };
  }
  if (extname(pathname).toLowerCase() === ".html") {
    return {
      html: resolve(DIST, pathname.slice(1)),
      md: resolve(DIST, pathname.slice(1).replace(/\.html$/i, ".md")),
    };
  }
  return {
    html: resolve(DIST, `${pathname.slice(1)}.html`),
    md: resolve(DIST, `${pathname.slice(1)}.md`),
  };
}

async function reportCardUrls() {
  const directory = resolve(DIST, "report-cards");
  const entries = await fs.readdir(directory, { withFileTypes: true });
  return entries
    .filter((entry) => entry.isFile() && entry.name.endsWith(".html"))
    .map((entry) =>
      canonicalize(`/report-cards/${entry.name.slice(0, -".html".length)}`),
    )
    .sort();
}

function surfaceKind(canonicalUrl) {
  const pathname = routePath(canonicalUrl);
  if (pathname === "/docs" || pathname.startsWith("/docs/"))
    return "documentation";
  if (pathname.startsWith("/report-cards/")) return "report-card";
  return "application";
}

async function buildInventory() {
  const astro = await sitemapUrls(resolve(DIST, "sitemap-0.xml"));
  const docs = await sitemapUrls(resolve(DIST, "docs", "sitemap.xml"));
  const reports = await reportCardUrls();
  const urls = [...astro, ...docs, ...reports];
  const unique = [...new Set(urls)].sort();
  if (unique.length !== urls.length - 1) {
    // /docs is intentionally advertised by both Astro and Blume; anything else
    // is an ambiguous route owner.
    const duplicates = urls.filter((url, index) => urls.indexOf(url) !== index);
    const unexpected = [...new Set(duplicates)].filter(
      (url) => routePath(url) !== "/docs",
    );
    if (unexpected.length > 0 || urls.length - unique.length !== 1) {
      throw new Error(
        `unexpected duplicate canonical routes: ${duplicates.join(", ")}`,
      );
    }
  }
  return unique;
}

function xmlEscape(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

async function buildOutputs() {
  const urls = await buildInventory();
  const surfaces = [];
  const generatedMarkdown = new Map();
  const macRelease = JSON.parse(
    await fs.readFile(resolve(DIST, MAC_RELEASE_PATH.slice(1)), "utf8"),
  );

  for (const url of urls) {
    const { html, md } = outputPaths(url);
    await fs.access(html);
    if (!new URL(url).pathname.startsWith("/docs")) {
      generatedMarkdown.set(
        md,
        htmlToMarkdown(await fs.readFile(html, "utf8"), url),
      );
    }
    const page = await fs.readFile(html, "utf8");
    const title = stripTags(
      page.match(/<title[^>]*>([\s\S]*?)<\/title>/i)?.[1] ?? url,
    );
    const description = stripTags(
      page.match(
        /<meta[^>]+name=(["'])description\1[^>]+content=(["'])(.*?)\2/i,
      )?.[3] ??
        page.match(
          /<meta[^>]+content=(["'])(.*?)\1[^>]+name=(["'])description\3/i,
        )?.[2] ??
        "",
    );
    surfaces.push({
      id: routePath(url) === "/" ? "home" : routePath(url).slice(1),
      url,
      md: `${ORIGIN}/${relative(DIST, md).split("\\").join("/")}`,
      kind: surfaceKind(url),
      title,
      description,
    });
  }

  const machineResources = [
    {
      kind: "feed",
      url: `${ORIGIN}/devlog/rss.xml`,
      description: "Devlog RSS feed",
    },
    {
      kind: "mac-release-json",
      url: `${ORIGIN}${MAC_RELEASE_PATH}`,
      description: `Native Mac release record — ${
        macRelease.downloadable
          ? "verified and downloadable"
          : "notarization pending"
      }`,
    },
    ...(await fs.readdir(resolve(DIST, "report-cards")))
      .filter((name) => name.endsWith(".json"))
      .sort()
      .map((name) => ({
        kind: "report-card-json",
        url: `${ORIGIN}/report-cards/${name}`,
        description: "Validated fine-tune report-card payload",
      })),
  ];

  const sitemap =
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    urls.map((url) => `  <url><loc>${xmlEscape(url)}</loc></url>`).join("\n") +
    "\n</urlset>\n";
  const sitemapIndex =
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    `  <sitemap><loc>${ORIGIN}/sitemap-0.xml</loc></sitemap>\n` +
    `  <sitemap><loc>${ORIGIN}/docs/sitemap.xml</loc></sitemap>\n` +
    "</sitemapindex>\n";
  const counts = { application: 0, documentation: 0, "report-card": 0 };
  for (const surface of surfaces) counts[surface.kind] += 1;
  const llms = `# posttrainllm

> A Mac-local LLM specialist factory: post-training, evidence-gated packaging,
> MLX runtime work, and a WebGPU playground.

## When to use this

Reach for PostTrainLLM when you need to train, fine-tune, evaluate, or package a specialist LLM on a single Apple Silicon Mac — without cloud compute. Best-fit jobs:

- Fine-tuning an open model with LoRA/QLoRA on a Mac (MLX)
- Evaluating a local model against frozen benchmarks (BFCL, tool-calling, perplexity)
- Packaging a trained specialist for MLX or on-device inference
- Comparing Mac-local training approaches (distillation, GRPO, SFT)
- Running the WebGPU inference playground in a browser

Do not use PostTrainLLM for: large-scale distributed training, frontier-scale pretraining, or anything that requires a GPU cluster — it is designed for one Mac.

## Public surface

- [Home](${ORIGIN}/): Product and research-lab overview
- [Documentation](${ORIGIN}/docs/): ${counts.documentation} source documents
- [Artifacts](${ORIGIN}/artifacts): Public packages, evidence, and blockers
- [Mac app](${ORIGIN}/download): ${
    macRelease.downloadable
      ? `Verified release ${macRelease.version} (${macRelease.build})`
      : `Release ${macRelease.version} (${macRelease.build}) — notarization pending, not yet downloadable`
  }
- [Devlog](${ORIGIN}/devlog): Build history
- [Agent catalog](${ORIGIN}/api/ai): Complete page-to-Markdown inventory
- [OpenAPI spec](${ORIGIN}/openapi.json): Machine-readable API description
- [Sitemap](${ORIGIN}/sitemap.xml): Canonical public HTML routes
- [Full agent index](${ORIGIN}/llms-full.txt): Every public page grouped by kind

## Boundaries

Public machine resources are catalogued separately from HTML pages. Local
factory runs, models, private artifacts, and unpublished evidence are excluded.
\`decision.json\` remains the terminal quality and product authority.

## CLI

PostTrainLLM ships a native Mac CLI for the full factory loop:

\`\`\`bash
# build the native factory CLI
git clone https://github.com/PostTrainLLM/posttrainllm && cd native-mac
swift build --product posttrainllm

# distill a specialist, gate it, serve it
posttrainllm distill --teacher qwen3 --student …
posttrainllm eval-gate --spec sql.json --candidate …
posttrainllm serve --port 8080  # OpenAI-compatible
\`\`\`

The CLI exposes 100+ subcommands covering train, eval, package, serve, and
inspect. See \`posttrainllm --help\` for the full command surface.
`;
  const llmsFull =
    `${llms}\n` +
    ["application", "report-card", "documentation"]
      .map((kind) => {
        const heading = {
          application: "Application and research pages",
          "report-card": "Fine-tune report cards",
          documentation: "Documentation",
        }[kind];
        const entries = surfaces
          .filter((surface) => surface.kind === kind)
          .map(
            (surface) =>
              `- [${surface.title}](${surface.url}) — ` +
              `[Markdown](${surface.md})` +
              (surface.description ? ` — ${surface.description}` : ""),
          )
          .join("\n");
        return `## ${heading}\n\n${entries}`;
      })
      .join("\n\n") +
    "\n";
  const catalog =
    JSON.stringify(
      {
        name: "posttrainllm",
        version: "2",
        url: ORIGIN,
        llms: `${ORIGIN}/llms.txt`,
        llmsFull: `${ORIGIN}/llms-full.txt`,
        sitemap: `${ORIGIN}/sitemap.xml`,
        robots: `${ORIGIN}/robots.txt`,
        markdown: { suffix: ".md", negotiation: true },
        openapi: `${ORIGIN}/openapi.json`,
        surfaces,
        machineResources,
        auth: {
          public: true,
          notes:
            "Only public site output is indexed. Local factory runs, models, private artifacts, and unpublished evidence are excluded; decision.json remains the terminal quality and product authority.",
        },
      },
      null,
      2,
    ) + "\n";

  return {
    urls,
    surfaces,
    generatedMarkdown,
    sitemap,
    sitemapIndex,
    llms,
    llmsFull,
    catalog,
    macRelease,
  };
}

async function verify(outputs) {
  const sitemapSet = new Set(outputs.urls);
  if (sitemapSet.size !== outputs.urls.length)
    throw new Error("duplicate sitemap URLs");
  if (outputs.surfaces.length !== outputs.urls.length)
    throw new Error("catalog/page mismatch");

  for (const surface of outputs.surfaces) {
    if (!sitemapSet.has(surface.url))
      throw new Error(`catalog orphan: ${surface.url}`);
    if (!surface.md.startsWith(`${ORIGIN}/`))
      throw new Error(`cross-origin Markdown: ${surface.md}`);
    const mdPath = resolve(DIST, new URL(surface.md).pathname.slice(1));
    const expected = outputs.generatedMarkdown.get(mdPath);
    const markdown = expected ?? (await fs.readFile(mdPath, "utf8"));
    if (!/^#\s+\S/m.test(markdown) || stripTags(markdown).length < 120) {
      throw new Error(`non-substantive Markdown: ${relative(DIST, mdPath)}`);
    }
  }

  for (const url of outputs.urls) {
    const path = new URL(url).pathname;
    if (/\.(json|xml|rss|txt|md)$/i.test(path) || path === "/api/ai") {
      throw new Error(`machine resource entered page sitemap: ${url}`);
    }
  }

  const releaseResource = `${ORIGIN}${MAC_RELEASE_PATH}`;
  if (
    !outputs.surfaces.some((surface) => surface.url === `${ORIGIN}/download`)
  ) {
    throw new Error("Mac download page missing from public page inventory");
  }
  if (outputs.surfaces.some((surface) => surface.url === releaseResource)) {
    throw new Error("Mac release JSON entered the HTML page inventory");
  }
  if (!outputs.catalog.includes(`\"url\": \"${releaseResource}\"`)) {
    throw new Error("Mac release JSON missing from machine resources");
  }
  if (outputs.macRelease.downloadable !== true) {
    if (
      outputs.macRelease.artifactURL !== null ||
      outputs.macRelease.sha256 !== null
    ) {
      throw new Error("ineligible Mac release exposed artifact metadata");
    }
    if (!outputs.llms.includes("notarization pending, not yet downloadable")) {
      throw new Error("agent index overstated pending Mac release");
    }
  }
}

const outputs = await buildOutputs();

if (CHECK_ONLY) {
  const expectedFiles = new Map([
    [resolve(DIST, "sitemap.xml"), outputs.sitemap],
    [resolve(DIST, "sitemap-index.xml"), outputs.sitemapIndex],
    [resolve(DIST, "api-ai.json"), outputs.catalog],
    [resolve(DIST, "llms.txt"), outputs.llms],
    [resolve(DIST, "llms-full.txt"), outputs.llmsFull],
    ...outputs.generatedMarkdown,
  ]);
  for (const [path, expected] of expectedFiles) {
    const actual = await fs.readFile(path, "utf8");
    if (actual !== expected)
      throw new Error(
        `generated agent surface drifted: ${relative(DIST, path)}`,
      );
  }
} else {
  for (const [path, markdown] of outputs.generatedMarkdown) {
    await fs.mkdir(dirname(path), { recursive: true });
    await fs.writeFile(path, markdown, "utf8");
  }
  await fs.writeFile(resolve(DIST, "sitemap.xml"), outputs.sitemap, "utf8");
  await fs.writeFile(
    resolve(DIST, "sitemap-index.xml"),
    outputs.sitemapIndex,
    "utf8",
  );
  await fs.writeFile(resolve(DIST, "api-ai.json"), outputs.catalog, "utf8");
  await fs.writeFile(resolve(DIST, "llms.txt"), outputs.llms, "utf8");
  await fs.writeFile(resolve(DIST, "llms-full.txt"), outputs.llmsFull, "utf8");
}

await verify(outputs);
console.log(
  `agent surfaces ${CHECK_ONLY ? "verified" : "generated"}: ` +
    `${outputs.urls.length} pages, ${outputs.surfaces.length} Markdown counterparts`,
);
