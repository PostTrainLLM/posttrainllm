import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import baseline from "./authored-fragment-baseline.json" with { type: "json" };
import { authoredHtmlToMarkdown } from "../src/lib/authored-markdown.mjs";
import {
  authoredExpressions,
  projectAuthoredTemplate,
} from "../src/lib/template-markdown.mjs";
import { createStaticAssetHandler } from "../src/lib/agent-surfaces/adapters/static-assets.mjs";

const root = new URL("../", import.meta.url);
const origin = "https://posttrainllm.com";
const assets = {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    try {
      const body = await readFile(new URL(`dist${path}`, root), "utf8");
      const type = path.endsWith(".md")
        ? "text/markdown"
        : path.endsWith(".html")
          ? "text/html"
          : "text/plain";
      return new Response(body, { headers: { "Content-Type": type } });
    } catch {
      return new Response("<!doctype html><title>Not found</title>", {
        status: 404,
        headers: { "Content-Type": "text/html" },
      });
    }
  },
};

test("authored expression projections preserve nested syntax and reject unmapped source", () => {
  const source =
    "<h1>{title}</h1><p>{items.map((item) => `${item.name}: {literal}`)}</p><a href={url}>Source</a>";
  const expressions = authoredExpressions(source);
  assert.equal(expressions.length, 3);
  assert.throws(
    () => projectAuthoredTemplate(source, () => undefined),
    /Unmapped authored expression/,
  );
  const markdown = projectAuthoredTemplate(source, (code) =>
    code === "title"
      ? "Evidence"
      : code === "url"
        ? "https://example.com/proof"
        : "- Recorded: 0\n- Unknown: not measured",
  );
  assert.match(markdown, /# Evidence/);
  assert.match(markdown, /Recorded: 0/);
  assert.match(markdown, /Unknown: not measured/);
  assert.match(markdown, /\[Source\]\(https:\/\/example.com\/proof\)/);
});

test("source rich text keeps table cells, code, and links", () => {
  const markdown = authoredHtmlToMarkdown(
    '<table><tr><th>Model</th><th>Result</th></tr\n><tr><td><a href="/evidence">Baseline</a></td><td>0 | not measured</td></tr></table><pre><code>x &lt; y\n  indented()</code></pre>',
  );
  assert.match(markdown, /\| Model \| Result \|/);
  assert.match(markdown, /\[Baseline\]\(\/evidence\)/);
  assert.match(markdown, /0 \\\| not measured/);
  assert.match(markdown, /```\nx < y\n  indented\(\)\n```/);
});

test("extracted authored fragments retain original content except terminal whitespace", async () => {
  for (const slug of [
    "devlog",
    "roadmap",
    "speedup",
    "webgpu-test",
    "playground",
  ]) {
    const body = await readFile(new URL(`src/content/public/${slug}.html`, root), "utf8");
    assert.equal(createHash("sha256").update(body.trimEnd() + "\n").digest("hex"), baseline.hashes[slug], slug);

  }
});

test("built registry is complete, public, and advertised in each canonical page", async () => {
  const catalog = JSON.parse(
    await readFile(new URL("dist/api/md/_catalog", root), "utf8"),
  );
  assert.ok(catalog.length > 268);
  assert.equal(
    new Set(catalog.map((route) => route.path)).size,
    catalog.length,
  );
  for (const route of catalog) {
    assert.equal(new URL(route.url).origin, origin);
    const markdown = await readFile(
      new URL(`dist${route.assetPath}`, root),
      "utf8",
    );
    assert.match(markdown, /^<!-- agent-source-envelope -->\n# /);
    assert.ok(markdown.includes(`Canonical: ${route.url}`));
    const path =
      route.path === "/"
        ? "index.html"
        : route.path.startsWith("/docs")
          ? `${route.path.slice(1)}/index.html`
          : `${route.path.slice(1)}.html`;
    const html = await readFile(new URL(`dist/${path}`, root), "utf8");
    assert.match(html, /name="ai-summary"/);
    assert.ok(html.includes(`type="text/markdown" href="${route.md}"`));
  }
});

test("real built content supports all three Markdown forms and preserves HTTP semantics", async () => {
  const handler = createStaticAssetHandler({ origin });
  for (const path of [
    "/",
    "/learn/session",
    "/benchmarks/chess",
    "/inference",
    "/studies/halo",
  ]) {
    const suffix = path === "/" ? "/index.md" : path + ".md";
    for (const url of [
      path,
      suffix,
      "/api/md/" + (path === "/" ? "" : path.slice(1)),
    ]) {
      const response = await handler(
        new Request(origin + url, {
          headers: { Accept: "text/markdown;q=1, text/html;q=0.4" },
        }),
        assets,
      );
      assert.equal(response.status, 200, url);
      assert.match(response.headers.get("Content-Type"), /text\/markdown/);
      assert.equal(response.headers.get("Content-Location"), origin + path);
      assert.match(response.headers.get("X-Robots-Tag"), /noindex/);
      assert.equal(response.headers.get("Access-Control-Allow-Origin"), "*");
      assert.ok(Number(response.headers.get("X-Markdown-Tokens")) > 0);
      assert.match(
        await response.text(),
        /Canonical: https:\/\/posttrainllm.com/,
      );
    }
  }
  assert.equal(
    await handler(
      new Request(origin + "/learn", {
        headers: { Accept: "text/html;q=1, text/markdown;q=0.5" },
      }),
      assets,
    ),
    null,
  );
  const head = await handler(
    new Request(origin + "/learn.md", { method: "HEAD" }),
    assets,
  );
  assert.equal(await head.text(), "");
  for (const path of ["/does-not-exist.md", "/api/md/auth"]) {
    const response = await handler(new Request(origin + path), assets);
    assert.equal(response?.status, 404, path);
  }
  assert.equal(
    await handler(
      new Request(origin + "/api/private", {
        headers: { Accept: "text/markdown" },
      }),
      assets,
    ),
    null,
  );
});
