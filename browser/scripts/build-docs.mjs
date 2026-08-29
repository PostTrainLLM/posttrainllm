// Build and merge the Blume documentation into the Astro browser site.
//
// Blume renders the canonical repo-root docs/ tree. Its generated links need a
// final normalization pass because authored Markdown links resolve from the
// source document, while browsers resolve from the generated route. Keeping
// that reconciliation here makes the deployed artifact—not either framework—
// the source of truth for URLs, headings, and canonicals.

import { spawnSync } from "node:child_process";
import {
  cpSync,
  existsSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, posix, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const BROWSER_ROOT = resolve(here, "..");
const REPO_ROOT = resolve(BROWSER_ROOT, "..");
const DOCS_SOURCE = resolve(REPO_ROOT, "docs");
const DOCS_SITE_DIR = resolve(REPO_ROOT, "docs-site");
const DOCS_SITE_DIST = resolve(DOCS_SITE_DIR, "dist");
const DEST_DIR = resolve(BROWSER_ROOT, "dist", "docs");
const ORIGIN = "https://posttrainllm.com";
const REPOSITORY_URL = "https://github.com/PostTrainLLM/posttrainllm";
const DOC_URL_PATTERN =
  /(?<![A-Za-z0-9._~!$&'*+,;=:@%/-])(?:https:\/\/posttrainllm\.com)?\/docs(?:\/[A-Za-z0-9._~!$&'*+,;=:@%/-]*)?(?:\?[A-Za-z0-9._~!$&'*+,;=:@%/?-]*)?(?:#[A-Za-z0-9._~!$&'*+,;=:@%/?-]*)?/g;
const STATIC_FILE_PATTERN =
  /\.(?:html?|mdx?|json|xml|txt|png|jpe?g|webp|avif|gif|svg|ico|css|m?js|map|woff2?|ttf|otf|wasm|pdf|zip)$/i;
const TEXT_OUTPUT_PATTERN = /\.(?:html?|mdx?|json|xml|txt|css|m?js)$/i;
const RENDERED_HREF_PATTERN = /href=(["'])([^"']+)\1/gi;
const EXTERNAL_URL_REPLACEMENTS = new Map([
  [
    "https://github.com/ggerganov/llama.cpp/blob/master/docs/quantize.md",
    "https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md",
  ],
  [
    "https://github.com/ggerganov/ggml/blob/master/docs/gguf.md",
    "https://github.com/ggml-org/ggml/blob/master/docs/gguf.md",
  ],
  [
    "https://github.com/huggingface/safetensors",
    "https://github.com/safetensors/safetensors",
  ],
  [
    "https://openreview.net/forum?id=tJHDw8XfeC",
    "https://arxiv.org/abs/2410.17215",
  ],
  [
    "https://github.com/hiyouga/LLaMA-Factory",
    "https://github.com/hiyouga/LlamaFactory",
  ],
  [
    "https://github.com/pytorch/torchtune",
    "https://github.com/meta-pytorch/torchtune",
  ],
  [
    "https://developer.mozilla.org/en-US/docs/WebAssembly/Concepts",
    "https://developer.mozilla.org/en-US/docs/WebAssembly/Guides/Concepts",
  ],
  [
    "https://www.3blue1brown.com/topics/linear-algebra",
    "https://www.3blue1brown.com/?topic=linear-algebra",
  ],
  [
    "https://www.3blue1brown.com/lessons/gpt",
    "https://www.3blue1brown.com/lessons/gpt/",
  ],
  [
    "https://www.3blue1brown.com/lessons/backpropagation",
    "https://www.3blue1brown.com/lessons/backpropagation/",
  ],
  [
    "https://github.com/VsonicV/es-fine-tuning-paper",
    "https://github.com/VsonicV/es-at-scale",
  ],
  [
    "https://github.com/settings/tokens",
    "https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens",
  ],
  [
    "https://docs.mistral.ai/capabilities/agents/",
    "https://docs.mistral.ai/studio/agents/introduction",
  ],
  [
    "https://docs.mistral.ai/agents/handoffs/",
    "https://docs.mistral.ai/studio/agents/handoffs",
  ],
  [
    "https://cookbook.openai.com/examples/evaluation/getting_started_with_openai_evals",
    "https://developers.openai.com/cookbook/examples/evaluation/getting_started_with_openai_evals",
  ],
  [
    "https://cookbook.openai.com/examples/evaluation/use-cases/structured-outputs-evaluation",
    "https://developers.openai.com/cookbook/examples/evaluation/use-cases/structured-outputs-evaluation",
  ],
  ["https://laminalabs.ai/", "https://www.laminalabs.ai/"],
  [
    "https://lmsys.org/blog/2024-01-17-sglang/",
    "https://www.lmsys.org/blog/2024-01-17-sglang/",
  ],
  [
    "https://bentoml.com/llm/inference-optimization/data-tensor-pipeline-expert-hybrid-parallelism",
    "https://handbook.modular.com/inference-optimization/data-tensor-pipeline-expert-hybrid-parallelism/",
  ],
  [
    "https://www.anthropic.com/research/building-effective-agents/",
    "https://www.anthropic.com/engineering/building-effective-agents",
  ],
  [
    "https://www.anthropic.com/news/contextual-retrieval",
    "https://www.anthropic.com/engineering/contextual-retrieval",
  ],
  [
    "https://x.com/AliesTaha/status/2037272772305707405",
    "https://x.com/waterloo_intern/status/2037272772305707405",
  ],
  [
    "https://x.com/AliesTaha/status/2030074784894308770",
    "https://x.com/waterloo_intern/status/2030074784894308770",
  ],
  [
    "https://x.com/AliesTaha/status/2024493443905683859",
    "https://x.com/waterloo_intern/status/2024493443905683859",
  ],
  [
    "https://www.sbert.net/examples/applications/retrieve_rerank/README.html",
    "https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html",
  ],
  [
    "https://developers.google.com/machine-learning/guides/rules-of-ml",
    "https://developers.google.com/machine-learning/guides/rules-of-ml?hl=en",
  ],
  ["https://www.goodfire.ai/", "https://www.goodfire.com/"],
  [
    "https://www.3blue1brown.com/topics/neural-networks",
    "https://www.3blue1brown.com/?topic=neural-networks",
  ],
  [
    "https://github.com/sarthakagrawal927/clicky/pull/new/eval/fm-fixtures-v2",
    "https://github.com/HeyPace/pace/pull/new/eval/fm-fixtures-v2",
  ],
  [
    "https://predibase.com/blog/graduate-from-openai-to-open-source-12-best-practices-for-distilling-smaller",
    "https://www.rubrik.com/blog/ai/24/graduate-from-openai-to-open-source-12-best-practices-for-distilling-smaller",
  ],
  [
    "https://www.3blue1brown.com/lessons/attention",
    "https://www.3blue1brown.com/lessons/attention/",
  ],
  [
    "https://github.com/PostTrainLLM/posttrainllm/blob/main/webgpu",
    "https://github.com/PostTrainLLM/posttrainllm/tree/main/webgpu",
  ],
  [
    "https://huggingface.co/learn/audio-course",
    "https://huggingface.co/learn/audio-course/chapter0/introduction",
  ],
  [
    "https://huggingface.co/learn/nlp-course/chapter6/5",
    "https://huggingface.co/learn/llm-course/chapter6/5",
  ],
  [
    "https://huggingface.co/HuggingFaceTB/fineweb-edu-classifier",
    "https://huggingface.co/HuggingFaceFW/fineweb-edu-classifier",
  ],
  ["https://trajectory.ai/", "https://www.trajectory.ai/"],
  [
    "https://trajectory.ai/field-notes/multi-lora-training-for-continual-learning",
    "https://www.trajectory.ai/field-notes/multi-lora-training-for-continual-learning",
  ],
  [
    "https://openreview.net/forum?id=PCjK8dqrWW",
    "https://arxiv.org/abs/2407.05291",
  ],
  [
    "https://openreview.net/forum?id=IVXmV8Uxwh",
    "https://arxiv.org/abs/2403.12031",
  ],
  [
    "https://openreview.net/forum?id=u0azVc9Y0y",
    "https://arxiv.org/abs/2408.07057",
  ],
  [
    "https://openreview.net/forum?id=3XMA8RDJu2",
    "https://arxiv.org/abs/2407.00066",
  ],
  [
    "https://developer.chrome.com/blog/new-in-webgpu-125",
    "https://developer.chrome.com/blog/new-in-webgpu-125?hl=en",
  ],
  [
    "https://huggingface.co/docs/datasets-server",
    "https://huggingface.co/docs/dataset-viewer/index",
  ],
  [
    "https://github.com/PostTrainLLM/posttrainllm/issues/new",
    "https://github.com/PostTrainLLM/posttrainllm/issues",
  ],
  [
    "https://unsloth.ai/docs/get-started/beginner-start-here/unsloth-requirements",
    "https://unsloth.ai/docs/get-started/fine-tuning-for-beginners/unsloth-requirements",
  ],
  [
    "https://openai.com/index/our-approach-to-the-model-spec/",
    "https://model-spec.openai.com/",
  ],
  [
    "https://www.rubrik.com/blog/company/25/rubrik-predibase-bipul-sinha",
    "https://ir.rubrik.com/news-events/press-releases/news-details/2025/Rubrik-to-Acquire-Predibase-to-Accelerate-Agentic-AI-Adoption/default.aspx",
  ],
  ["https://arize.com/phoenix/", "https://github.com/Arize-ai/phoenix"],
  [
    "https://www.lamini.ai/pricing",
    "https://docs.lamini.ai/tuning/memory_tuning/",
  ],
  ["https://unsloth.ai/", "https://github.com/unslothai/unsloth"],
  [
    "https://philarchive.org/archive/SMIRTP-8",
    "https://philpapers.org/rec/SMIRTP-8",
  ],
  [
    "https://www.lesswrong.com/posts/AcKRB8wDpdaN6v6ru/interpreting-gpt-the-logit-lens",
    "https://arxiv.org/abs/2303.08112",
  ],
  [
    "https://huggingface.co/inclusionAI/UI-Venus-Ground-2B",
    "https://github.com/inclusionAI/UI-Venus",
  ],
  [
    "https://medium.com/@yakovbeder/llm-d-the-inference-scheduler-that-fixes-what-more-gpus-cant-03644ac55504",
    "https://github.com/llm-d/llm-d",
  ],
  [
    "https://openreview.net/pdf?id=ZU9tRffRSA",
    "https://github.com/NVIDIA/RULER",
  ],
  [
    "https://www.hpcwire.com/2025/09/10/mlperf-inference-v5-1-results-land-with-new-benchmarks-and-record-participation/",
    "https://mlcommons.org/2025/09/mlperf-inference-v5-1-results/",
  ],
  [
    "https://medium.com/engineering-draw-things/metal-flashattention-2-0-pushing-forward-on-device-inference-training-on-apple-silicon-fe8aac1ab23c",
    "https://engineering.drawthings.ai/p/metal-flashattention-2-0-pushing-forward-on-device-inference-training-on-apple-silicon-fe8aac1ab23c",
  ],
  [
    "https://huggingface.co/datasets/cerebras/SlimPajama-627B",
    "https://arxiv.org/abs/2309.10818",
  ],
  [
    "https://huggingface.co/datasets/bigscience/roots",
    "https://arxiv.org/abs/2303.03915",
  ],
  [
    "https://www.swebench.com/verified.html",
    "https://github.com/SWE-bench/SWE-bench",
  ],
]);

function splitUrlSuffix(value) {
  const suffixIndex = value.search(/[?#]/);
  return suffixIndex === -1
    ? { pathname: value, suffix: "" }
    : {
        pathname: value.slice(0, suffixIndex),
        suffix: value.slice(suffixIndex),
      };
}

let generatedSourceMaps;

function readGeneratedSourceMaps() {
  if (generatedSourceMaps) return generatedSourceMaps;
  const sourceToRoute = new Map();
  const routeToSource = new Map();
  const outputToSource = new Map();

  function visit(directory) {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const target = resolve(directory, entry.name);
      if (entry.isDirectory()) {
        visit(target);
        continue;
      }
      if (entry.name !== "index.html") continue;
      const html = readFileSync(target, "utf8");
      const editPath = html.match(
        new RegExp(`${REPOSITORY_URL}/edit/main/([^"'#?]+)`, "i"),
      )?.[1];
      if (!editPath) continue;
      const sourcePath = resolve(REPO_ROOT, decodeURIComponent(editPath));
      const relativeOutput = relative(DOCS_SITE_DIST, target)
        .split(sep)
        .join("/");
      const route =
        relativeOutput === "index.html"
          ? "/docs/"
          : `/docs/${relativeOutput.replace(/index\.html$/, "")}`;
      sourceToRoute.set(sourcePath, route);
      routeToSource.set(route, sourcePath);
      outputToSource.set(relativeOutput, sourcePath);
    }
  }

  visit(DOCS_SITE_DIST);
  generatedSourceMaps = { sourceToRoute, routeToSource, outputToSource };
  return generatedSourceMaps;
}

function sourceDirectoryForHtml(target) {
  const relativeHtml = relative(DEST_DIR, target).split(sep).join("/");
  const mappedSource =
    readGeneratedSourceMaps().outputToSource.get(relativeHtml);
  if (mappedSource) {
    return relative(DOCS_SOURCE, dirname(mappedSource)).split(sep).join("/");
  }
  const outputDirectory = posix.dirname(relativeHtml);
  // Blume renders `learn/foo.md` to `learn/foo/index.html`. Resolve links
  // from the Markdown document's directory, not the generated route. An
  // authored `training/index.md` is the exception: its source directory is
  // already the generated route directory.
  if (relativeHtml === "index.html") return "";
  if (existsSync(resolve(DOCS_SOURCE, outputDirectory, "index.md"))) {
    return outputDirectory;
  }
  return posix.dirname(outputDirectory);
}

function generatedDocsRoute(sourcePath) {
  if (!/\.md$/i.test(sourcePath)) return null;
  const mappedRoute = readGeneratedSourceMaps().sourceToRoute.get(sourcePath);
  if (mappedRoute) return mappedRoute;
  const relativeSource = relative(DOCS_SOURCE, sourcePath).split(sep).join("/");
  if (relativeSource === ".." || relativeSource.startsWith("../")) return null;

  const route = relativeSource.replace(/\.md$/i, "");
  const generatedPage =
    route.toLowerCase() === "index"
      ? resolve(DOCS_SITE_DIST, "index.html")
      : resolve(DOCS_SITE_DIST, route, "index.html");
  if (!existsSync(generatedPage)) return null;
  return route.toLowerCase() === "index" ? "/docs/" : `/docs/${route}/`;
}

function repositoryUrl(target) {
  const repositoryPath = relative(REPO_ROOT, target).split(sep).join("/");
  if (
    repositoryPath === ".." ||
    repositoryPath.startsWith("../") ||
    repositoryPath.startsWith("/")
  ) {
    return null;
  }

  const encodedPath = repositoryPath
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
  const view = statSync(target).isDirectory() ? "tree" : "blob";
  return `${REPOSITORY_URL}/${view}/main/${encodedPath}`;
}

function resolveAuthoredSourceTarget(sourceRelative) {
  const exact = resolve(DOCS_SOURCE, sourceRelative);
  const candidates = [
    exact,
    `${exact}.md`,
    resolve(exact, "README.md"),
    resolve(exact, "index.md"),
  ];
  const exactCandidate = candidates.find((candidate) => existsSync(candidate));
  if (exactCandidate) return exactCandidate;

  const route = `/docs/${sourceRelative
    .replace(/^\.\//, "")
    .replace(/\.md$/i, "")
    .replace(/\/+$/, "")}/`;
  return readGeneratedSourceMaps().routeToSource.get(route) ?? null;
}

function rewriteAuthoredSourceLinks(target, html) {
  const sourceDirectory = sourceDirectoryForHtml(target);

  return html.replace(RENDERED_HREF_PATTERN, (match, quote, rawHref) => {
    const currentExternalUrl = EXTERNAL_URL_REPLACEMENTS.get(rawHref);
    if (currentExternalUrl) {
      return `href=${quote}${currentExternalUrl}${quote}`;
    }
    const editPrefix = `${REPOSITORY_URL}/edit/main/`;
    if (rawHref.startsWith(editPrefix)) {
      return `href=${quote}${REPOSITORY_URL}/blob/main/${rawHref.slice(editPrefix.length)}${quote}`;
    }
    if (
      rawHref.startsWith("#") ||
      rawHref.startsWith("//") ||
      /^(?:[a-z]+:)/i.test(rawHref)
    ) {
      return match;
    }

    const { pathname, suffix } = splitUrlSuffix(rawHref);
    if (
      !pathname ||
      (!pathname.startsWith("/docs/") && pathname.startsWith("/"))
    ) {
      return match;
    }

    const sourceRelative = pathname.startsWith("/docs/")
      ? pathname.slice("/docs/".length)
      : posix.normalize(posix.join(sourceDirectory, pathname));
    const sourceTarget = resolveAuthoredSourceTarget(sourceRelative);
    if (!sourceTarget) return match;

    const destination =
      generatedDocsRoute(sourceTarget) ?? repositoryUrl(sourceTarget);
    return destination ? `href=${quote}${destination}${suffix}${quote}` : match;
  });
}

function enforceSinglePageTitle(html) {
  const headings = [...html.matchAll(/<h1\b([^>]*)>([\s\S]*?)<\/h1>/gi)];
  if (headings.length <= 1) return { html, removed: 0, demoted: 0 };

  const normalizeText = (value) =>
    value
      .replace(/<[^>]+>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  let after = html;
  let removed = 0;
  let demoted = 0;
  const pageTitle = normalizeText(headings[0][2]);
  for (const heading of headings.slice(1).reverse()) {
    if (normalizeText(heading[2]) === pageTitle) {
      const duplicateId = heading[1].match(/\bid=(["'])(.*?)\1/i)?.[2];
      if (duplicateId && !/\bid=/i.test(headings[0][1])) {
        after = after.replace(
          headings[0][0],
          `<h1${headings[0][1]} id="${duplicateId}">${headings[0][2]}</h1>`,
        );
      }
      after = after.replace(heading[0], "");
      removed += 1;
      continue;
    }
    after = after.replace(heading[0], `<h2${heading[1]}>${heading[2]}</h2>`);
    demoted += 1;
  }
  return { html: after, removed, demoted };
}

function canonicalDocsUrl(value) {
  const prefix = value.startsWith(ORIGIN) ? ORIGIN : "";
  const relativeUrl = prefix ? value.slice(prefix.length) : value;
  const { pathname, suffix } = splitUrlSuffix(relativeUrl);
  if (pathname === "/docs/index" || pathname === "/docs/index/") {
    return `${prefix}/docs/${suffix}`;
  }
  if (pathname.endsWith("/") || STATIC_FILE_PATTERN.test(pathname))
    return value;
  return `${prefix}${pathname}/${suffix}`;
}

function decodeHtmlText(value) {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">");
}

function encodeHtmlText(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function encodeHtmlAttribute(value, quote) {
  const encoded = encodeHtmlText(value);
  return quote === '"'
    ? encoded.replaceAll('"', "&quot;")
    : encoded.replaceAll("'", "&#39;");
}

function truncateText(value, maximum) {
  if (value.length <= maximum) return value;
  const candidate = value.slice(0, maximum - 1);
  const wordBoundary = candidate.lastIndexOf(" ");
  const shortened =
    wordBoundary >= maximum * 0.65
      ? candidate.slice(0, wordBoundary)
      : candidate;
  return `${shortened.trimEnd()}…`;
}

function normalizeDocumentMetadata(html) {
  let titleChanged = false;
  let descriptionChanged = false;
  let after = html.replace(/<title>([\s\S]*?)<\/title>/i, (match, rawTitle) => {
    let title = decodeHtmlText(rawTitle)
      .replace(/\s+-\s+posttrainllm docs\s*$/i, "")
      .replaceAll("&", "and")
      .trim();
    if (title.length < 30) {
      title = title.toLowerCase().includes("posttrainllm")
        ? `${title} technical documentation`
        : `${title} | PostTrainLLM reference`;
    }
    title = truncateText(title, 60);
    const encoded = encodeHtmlText(title);
    if (encoded === rawTitle) return match;
    titleChanged = true;
    return `<title>${encoded}</title>`;
  });

  const descriptionTag = after.match(
    /<meta\b(?=[^>]*\bname=["']description["'])[^>]*>/iu,
  )?.[0];
  const content = descriptionTag?.match(/\bcontent=(["'])(.*?)\1/iu);
  if (descriptionTag && content) {
    let description = decodeHtmlText(content[2]).trim();
    if (description.length < 70) {
      description = `${description.replace(/[.\s]+$/u, "")}. This preserved page points to the current PostTrainLLM roadmap and canonical project status.`;
    }
    description = truncateText(description, 160);
    let encoded = encodeHtmlAttribute(description, content[1]);
    if (encoded.length > 160) {
      description = truncateText(
        description,
        Math.max(70, 160 - (encoded.length - description.length)),
      );
      encoded = encodeHtmlAttribute(description, content[1]);
    }
    if (encoded !== content[2]) {
      const nextTag = descriptionTag.replace(
        content[0],
        `content=${content[1]}${encoded}${content[1]}`,
      );
      after = after.replace(descriptionTag, nextTag);
      descriptionChanged = true;
    }
  }

  return { html: after, titleChanged, descriptionChanged };
}

function normalizeDocsOutput(directory) {
  let urlReplacements = 0;
  let duplicateTitles = 0;
  let demotedTitles = 0;
  let documentTitles = 0;
  let documentDescriptions = 0;

  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      const nested = normalizeDocsOutput(target);
      urlReplacements += nested.urlReplacements;
      duplicateTitles += nested.duplicateTitles;
      demotedTitles += nested.demotedTitles;
      documentTitles += nested.documentTitles;
      documentDescriptions += nested.documentDescriptions;
      continue;
    }
    if (!TEXT_OUTPUT_PATTERN.test(entry.name)) continue;

    const before = readFileSync(target, "utf8");
    const withSourceLinks = entry.name.endsWith(".html")
      ? rewriteAuthoredSourceLinks(target, before)
      : before;
    const deduplicated = entry.name.endsWith(".html")
      ? enforceSinglePageTitle(withSourceLinks)
      : { html: withSourceLinks, removed: 0, demoted: 0 };
    duplicateTitles += deduplicated.removed;
    demotedTitles += deduplicated.demoted;
    const metadata = entry.name.endsWith(".html")
      ? normalizeDocumentMetadata(deduplicated.html)
      : {
          html: deduplicated.html,
          titleChanged: false,
          descriptionChanged: false,
        };
    if (metadata.titleChanged) documentTitles += 1;
    if (metadata.descriptionChanged) documentDescriptions += 1;
    const after = metadata.html.replace(DOC_URL_PATTERN, (value) => {
      const canonical = canonicalDocsUrl(value);
      if (canonical !== value) urlReplacements += 1;
      return canonical;
    });
    if (after !== before) writeFileSync(target, after);
  }

  return {
    urlReplacements,
    duplicateTitles,
    demotedTitles,
    documentTitles,
    documentDescriptions,
  };
}

function normalizeExternalUrls(directory) {
  let replacements = 0;
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      replacements += normalizeExternalUrls(target);
      continue;
    }
    if (!entry.name.endsWith(".html")) continue;

    const before = readFileSync(target, "utf8");
    const after = before.replace(
      RENDERED_HREF_PATTERN,
      (match, quote, rawHref) => {
        const currentUrl = EXTERNAL_URL_REPLACEMENTS.get(rawHref);
        if (!currentUrl) return match;
        replacements += 1;
        return `href=${quote}${currentUrl}${quote}`;
      },
    );
    if (after !== before) writeFileSync(target, after);
  }
  return replacements;
}

function normalizeInternalDocsUrls(directory) {
  let replacements = 0;
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      replacements += normalizeInternalDocsUrls(target);
      continue;
    }
    if (!entry.name.endsWith(".html")) continue;

    const before = readFileSync(target, "utf8");
    const after = before.replace(
      RENDERED_HREF_PATTERN,
      (match, quote, rawHref) => {
        if (
          !rawHref.startsWith("/docs") &&
          !rawHref.startsWith(`${ORIGIN}/docs`)
        ) {
          return match;
        }
        const canonical = canonicalDocsUrl(rawHref);
        if (canonical === rawHref) return match;
        replacements += 1;
        return `href=${quote}${canonical}${quote}`;
      },
    );
    if (after !== before) writeFileSync(target, after);
  }
  return replacements;
}

function assertInternalDocsLinks(directory) {
  const brokenLinks = [];

  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      brokenLinks.push(...assertInternalDocsLinks(target));
      continue;
    }
    if (!entry.name.endsWith(".html")) continue;

    const relativeHtml = relative(DEST_DIR, target).split(sep).join("/");
    const currentRoute =
      relativeHtml === "index.html"
        ? "/docs/"
        : `/docs/${relativeHtml.replace(/index\.html$/, "")}`;
    const html = readFileSync(target, "utf8");

    for (const match of html.matchAll(RENDERED_HREF_PATTERN)) {
      let rawHref = match[2];
      if (rawHref.startsWith(ORIGIN)) {
        rawHref = rawHref.slice(ORIGIN.length);
      } else if (
        rawHref.startsWith("#") ||
        rawHref.startsWith("//") ||
        /^(?:[a-z]+:)/i.test(rawHref)
      ) {
        continue;
      }

      const { pathname } = splitUrlSuffix(rawHref);
      const route = pathname.startsWith("/")
        ? pathname
        : posix.resolve(posix.dirname(currentRoute), pathname);
      if (!route.startsWith("/docs/")) continue;

      const docsPath = route.slice("/docs/".length);
      const candidate = route.endsWith("/")
        ? resolve(DEST_DIR, docsPath, "index.html")
        : resolve(DEST_DIR, docsPath);
      if (!existsSync(candidate)) {
        brokenLinks.push(`${relativeHtml}: ${match[2]}`);
      }
    }
  }

  if (directory === DEST_DIR && brokenLinks.length > 0) {
    throw new Error(
      `broken internal docs links:\n${brokenLinks
        .map((link) => `- ${link}`)
        .join("\n")}`,
    );
  }
  return brokenLinks;
}

function alignCanonicalUrls(directory = DEST_DIR) {
  let count = 0;
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const target = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      count += alignCanonicalUrls(target);
      continue;
    }
    if (entry.name !== "index.html") continue;

    const outputPath = relative(DEST_DIR, target).split(sep).join("/");
    const route =
      outputPath === "index.html" ? "" : outputPath.replace(/index\.html$/, "");
    const canonicalUrl = `${ORIGIN}/docs/${route}`;
    const html = readFileSync(target, "utf8");
    const canonicalTag = html.match(
      /<link\b(?=[^>]*\brel=["']canonical["'])[^>]*>/iu,
    )?.[0];
    const currentCanonical = canonicalTag?.match(
      /\bhref=["']([^"']+)["']/iu,
    )?.[1];
    if (!currentCanonical) {
      throw new Error(`missing canonical URL in ${outputPath}`);
    }
    if (currentCanonical !== canonicalUrl) {
      writeFileSync(target, html.replaceAll(currentCanonical, canonicalUrl));
    }
    count += 1;
  }
  return count;
}

const pnpmCommand = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
console.log("build-docs.mjs: installing docs-site dependencies …");
const install = spawnSync(pnpmCommand, ["install", "--frozen-lockfile"], {
  cwd: DOCS_SITE_DIR,
  stdio: "inherit",
});
if (install.status !== 0) process.exit(install.status ?? 1);

console.log("build-docs.mjs: building Blume docs in ../docs-site …");
const build = spawnSync(pnpmCommand, ["run", "build"], {
  cwd: DOCS_SITE_DIR,
  stdio: "inherit",
});
if (build.status !== 0) process.exit(build.status ?? 1);

if (!existsSync(resolve(BROWSER_ROOT, "dist", "index.html"))) {
  throw new Error("build the Astro site before merging docs");
}
if (!existsSync(resolve(DOCS_SITE_DIST, "index.html"))) {
  throw new Error(`expected ${DOCS_SITE_DIST} after the docs build`);
}

// Astro clears dist/ before every build. Keep any deliberate legacy redirect
// files it emitted under dist/docs and merge the canonical Blume output over
// them; a second run remains deterministic without deleting anything here.
cpSync(DOCS_SITE_DIST, DEST_DIR, { recursive: true });
const canonicalCount = alignCanonicalUrls();
const normalization = normalizeDocsOutput(DEST_DIR);
const internalUrlCount = normalizeInternalDocsUrls(
  resolve(BROWSER_ROOT, "dist"),
);
const externalUrlCount = normalizeExternalUrls(resolve(BROWSER_ROOT, "dist"));
assertInternalDocsLinks(DEST_DIR);

console.log(
  `build-docs.mjs: merged ${canonicalCount} docs; normalized ${normalization.urlReplacements + internalUrlCount} internal and ${externalUrlCount} external URLs, ${normalization.documentTitles} titles, and ${normalization.documentDescriptions} descriptions; removed ${normalization.duplicateTitles} duplicate and demoted ${normalization.demotedTitles} extra H1s; verified all internal docs links`,
);
