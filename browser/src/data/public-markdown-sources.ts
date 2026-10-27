import { allKnowledgeRecords } from "./knowledgeGraph";
import { educationContent } from "./education-content";
import { articleContent } from "./articles-content";
import { inspirations, inspirationStudies } from "./inspirations";
import {
  knowledgeMarkdown,
  editorialMarkdown,
  markdownLink,
} from "../lib/public-markdown";
import { authoredHtmlToMarkdown } from "../lib/authored-markdown.mjs";
import devlog from "../content/public/devlog.html?raw";
import roadmap from "../content/public/roadmap.html?raw";
import speedup from "../content/public/speedup.html?raw";
import webgpu from "../content/public/webgpu-test.html?raw";
import playground from "../content/public/playground.html?raw";
import specialistSource from "../components/SpecialistLabs.astro?raw";

/** Only authored static markup is accepted here. Expressions require a data renderer. */
export function staticAstroMarkup(source: string): string {
  const body = source
    .replace(/^---[\s\S]*?---\s*/, "")
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "");
  if (/[{}]/.test(body))
    throw new Error("Dynamic Astro content requires its shared data renderer");
  return body;
}

export const publicMarkdownSources: Record<string, string> = Object.fromEntries(
  [
    ...allKnowledgeRecords.map((record) => [
      record.canonicalPath,
      knowledgeMarkdown(record),
    ]),
    ...Object.values(educationContent).map((content) => [
      content.path,
      editorialMarkdown(content),
    ]),
    ...Object.values(articleContent).map((content) => [
      content.path,
      editorialMarkdown(content),
    ]),
    ...Object.entries({
      devlog,
      roadmap,
      speedup,
      "webgpu-test": webgpu.replace(
        "running…",
        "Results are produced locally by this page in a WebGPU browser. This public document does not execute the kernel tests or claim a passing result.",
      ),
      playground: playground + staticAstroMarkup(specialistSource),
    }).map(([slug, source]) => [`/${slug}`, authoredHtmlToMarkdown(source)]),
    ...inspirations.map((entry) => {
      const studies = inspirationStudies(entry);
      return [
        `/inspiration/${entry.slug}`,
        [
          `# ${entry.name}`,
          `A note of thanks · ${entry.thread}`,
          entry.opening,
          "## What stayed with us",
          ...(studies.length
            ? studies.map((study) => study.what_mattered)
            : [entry.opening]),
          "## What we did with it",
          ...(studies.length
            ? studies.map((study) => study.local_translation)
            : [entry.localRead]),
          "## Where the comparison stops",
          ...(studies.length
            ? studies.map((study) => study.boundary)
            : [entry.boundary]),
          "## Follow the work",
          `- Original project: ${markdownLink(entry.source.label, entry.source.href)}`,
          ...(entry.reading ?? []).map(
            (link) =>
              `- Further reading: ${markdownLink(link.label, link.href)}`,
          ),
          ...studies.map(
            (study) =>
              `- Our evidence (${study.status}): ${markdownLink(study.title, `/studies/${study.id}`)}`,
          ),
          ...(entry.evidence ?? []).map(
            (link) => `- Our context: ${markdownLink(link.label, link.href)}`,
          ),
          "Independent appreciation. The named projects have not endorsed or affiliated with PostTrainLLM.",
        ].join("\n\n") + "\n",
      ];
    }),
  ],
);

import { content as home } from "./home-content";
const homeParts = [
  `# ${home.hero.title.replaceAll("\n", " ")}`,
  home.hero.issue,
  home.hero.lede,
  home.hero.primary &&
    markdownLink(home.hero.primary.label, home.hero.primary.href),
  home.hero.secondary &&
    markdownLink(home.hero.secondary.label, home.hero.secondary.href),
  home.hero.status &&
    (home.hero.status.href
      ? markdownLink(home.hero.status.label, home.hero.status.href)
      : home.hero.status.label),
];
for (const section of home.sections) {
  for (const block of section.blocks) {
    if (block.type === "statement") {
      homeParts.push(`## ${block.title}`, block.eyebrow, block.lede);
      for (const point of block.points ?? [])
        homeParts.push(`### ${point.title}`, point.body);
    } else if (block.type === "spread") {
      for (const item of block.items) {
        homeParts.push(`## ${item.title}`, item.kicker, item.body);
        if (item.code)
          homeParts.push(item.code.label, `\`\`\`\n${item.code.code}\n\`\`\``);
        if (item.diff) {
          homeParts.push(
            item.diff.file,
            `\`\`\`diff\n${item.diff.lines.map((line) => `${line.kind === "add" ? "+" : line.kind === "del" ? "-" : " "} ${line.text}`).join("\n")}\n\`\`\``,
          );
          for (const line of item.diff.lines)
            if (line.note) homeParts.push(line.note.text);
        }
      }
    } else
      throw new Error(
        `Missing homepage Markdown block renderer: ${block.type}`,
      );
  }
  for (const source of home.sources.filter(
    (source) => source.section === section.id,
  ))
    homeParts.push(markdownLink(source.label, source.href));
}
for (const directory of home.directories)
  homeParts.push(
    `## ${directory.title}`,
    directory.lede,
    ...directory.links.map(
      (link) => `- ${markdownLink(link.label, link.href)}`,
    ),
  );
publicMarkdownSources["/"] = homeParts.filter(Boolean).join("\n\n") + "\n";

import { artifacts, outcomeLabel, stateLabel } from "../artifacts";
import { markdownTable } from "../lib/public-markdown";
import artifactTemplate from "../pages/artifacts/[slug].astro?raw";
// Literal authored paragraphs stay in their existing template. Reading these
// source fragments is distinct from extracting rendered HTML output.
function paragraphWithClass(source: string, className: string): string {
  const match = source.match(
    new RegExp(`<p class="${className}">([\\s\\S]*?)<\\/p>`),
  );
  if (!match || /[{}]/.test(match[1]))
    throw new Error(`Missing static authored paragraph: ${className}`);
  return authoredHtmlToMarkdown(match[1]);
}
for (const artifact of artifacts) {
  const parts = [
    `# ${artifact.title}`,
    artifact.eyebrow,
    stateLabel[artifact.state],
    artifact.date,
    artifact.lede,
    artifact.tags.join(", "),
    "## Headline Numbers",
    paragraphWithClass(artifactTemplate, "metric-key"),
    ...artifact.metrics.map(
      (metric) =>
        `**${metric.label}:** ${metric.value}\n\n${metric.context}\n\nEvidence: ${metric.evidence}`,
    ),
    "## Competitive Context",
    markdownTable(
      ["System", "Metric", "Score", "Size / Class", "Comparable?", "Readout"],
      artifact.comparisons.map((item) => [
        item.sourceHref ? markdownLink(item.name, item.sourceHref) : item.name,
        item.metric,
        item.score,
        item.size,
        item.comparability,
        item.note,
      ]),
    ),
    paragraphWithClass(artifactTemplate, "comparison-note"),
    ...artifact.tables.flatMap((table) => [
      `## ${table.title}`,
      markdownTable(table.columns, table.rows),
    ]),
    "## Release Blockers",
    ...artifact.blockers.flatMap((item) => [
      `### ${item.blocker}`,
      item.why,
      `**Unblock:** ${item.unblock}`,
    ]),
  ];
  if (artifact.reportCard)
    parts.push(
      "## Fine-Tune Report Card",
      outcomeLabel[artifact.reportCard.outcome],
      artifact.reportCard.verified
        ? "Fully verified"
        : "Not fully verified — see the report card for why",
      markdownLink("Read the report card", artifact.reportCard.href),
      markdownLink("Machine-readable JSON", artifact.reportCard.jsonHref),
    );
  parts.push(
    "## Evidence",
    ...artifact.evidence.map(
      (link) => `- ${markdownLink(link.label, link.href)}`,
    ),
    "## Next Release Action",
    artifact.nextAction,
  );
  publicMarkdownSources[`/artifacts/${artifact.slug}`] =
    parts.join("\n\n") + "\n";
}

import articleIndexSource from "../pages/articles/index.astro?raw";
import artifactIndexSource from "../pages/artifacts/index.astro?raw";
import inspirationIndexSource from "../pages/inspiration/index.astro?raw";
import studiesIndexSource from "../pages/studies/index.astro?raw";
import { articleList } from "./articles-content";
import { studyRecords } from "./knowledgeGraph";
function literalFragment(source: string, pattern: RegExp): string {
  const match = source.match(pattern);
  if (!match || /[{}]/.test(match[1]))
    throw new Error(`Missing static content fragment: ${pattern}`);
  return authoredHtmlToMarkdown(match[1]);
}
publicMarkdownSources["/articles"] = [
  literalFragment(
    articleIndexSource,
    /<header class="hero">([\s\S]*?)<\/header>/,
  ),
  ...articleList.flatMap((article) => [
    `## ${markdownLink(article.title, article.path)}`,
    article.description,
  ]),
].join("\n\n");
publicMarkdownSources["/inspiration"] = [
  literalFragment(
    inspirationIndexSource,
    /<header class="inspiration-hero">([\s\S]*?)<\/header>/,
  ),
  "## With thanks to",
  `${inspirations.length} named tools and projects`,
  ...inspirations.flatMap((entry) => [
    `### ${markdownLink(entry.name, `/inspiration/${entry.slug}`)}`,
    entry.thread,
  ]),
  literalFragment(inspirationIndexSource, /<aside\b[^>]*>([\s\S]*?)<\/aside>/),
].join("\n\n");
publicMarkdownSources["/studies"] = [
  literalFragment(studiesIndexSource, /<header class="hero">([\s\S]*?)<dl/),
  `Canonical studies: ${studyRecords.length}`,
  `Distinct dispositions: ${new Set(studyRecords.map((record) => record.status)).size}`,
  "Unresolved ownership: 0",
  "## All retained studies",
  "Indexed from the tracked review ledger and industry learning map.",
  ...studyRecords.flatMap((study) => [
    `### ${markdownLink(study.title, study.canonicalPath)}`,
    study.kindLabel,
    study.status,
    study.sections[0]?.paragraphs?.[0] ?? study.description,
  ]),
].join("\n\n");
publicMarkdownSources["/artifacts"] = [
  literalFragment(
    artifactIndexSource,
    /<header class="hero">([\s\S]*?)<div class="summary-grid"/,
  ),
  `${artifacts.filter((entry) => entry.modelRepoId).length} published model case studies`,
  `${artifacts.length} tracked public artifacts`,
  `${artifacts.filter((entry) => entry.state === "parked").length} parked but public`,
  "## Current Release Surface",
  ...artifacts
    .filter((entry) => entry.state !== "parked")
    .flatMap((entry) => [
      `### ${markdownLink(entry.title, `/artifacts/${entry.slug}`)}`,
      entry.eyebrow,
      stateLabel[entry.state],
      entry.summary,
      ...(entry.modelRepoId
        ? [
            markdownLink(
              "Hugging Face model",
              `https://huggingface.co/${entry.modelRepoId}`,
            ),
          ]
        : []),
      ...entry.metrics
        .slice(0, 3)
        .map((metric) => `**${metric.label}:** ${metric.value}`),
      `**Competition:** ${entry.comparisons[0]?.name ?? "None"}${entry.comparisons[1] ? ` vs ${entry.comparisons[1].name}` : ""}`,
      `**Next:** ${entry.nextAction}`,
      ...(entry.reportCard
        ? [
            outcomeLabel[entry.reportCard.outcome],
            entry.reportCard.verified ? "fully verified" : "not fully verified",
            markdownLink("Report card", entry.reportCard.href),
          ]
        : []),
    ]),
  "## Parked Public Evidence",
  ...artifacts
    .filter((entry) => entry.state === "parked")
    .flatMap((entry) => [
      `### ${markdownLink(entry.title, `/artifacts/${entry.slug}`)}`,
      entry.eyebrow,
      stateLabel[entry.state],
      entry.summary,
    ]),
  literalFragment(
    artifactIndexSource,
    /<aside class="guide-link">([\s\S]*?)<\/aside>/,
  ),
].join("\n\n");

import { entries as changelog } from "./changelog";
import changelogSource from "../pages/changelog.astro?raw";
publicMarkdownSources["/changelog"] = [
  literalFragment(
    changelogSource,
    /<header class="changelog-hero">([\s\S]*?)<\/header>/,
  ),
  ...changelog.flatMap((entry) => [
    `## ${entry.date}: ${entry.title}`,
    ...entry.outcomes.map((outcome) => `- ${outcome}`),
  ]),
].join("\n\n");

import * as recipePage from "./recipes-page";
import recipeSource from "../pages/recipes.astro?raw";
const recipeLinks = (items: typeof recipePage.recipes) =>
  items.flatMap((item) => [
    `### ${markdownLink(item.title, item.href)}`,
    item.tag ?? "",
    item.blurb,
  ]);
publicMarkdownSources["/recipes"] = [
  literalFragment(
    recipeSource,
    /<header class="rec-hero">([\s\S]*?)<\/header>/,
  ),
  "## Post-training recipes",
  ...recipeLinks(recipePage.recipes),
  "## Cookbooks — real integrations",
  ...recipeLinks(recipePage.cookbooks),
  "## Complete technique → recipe registry",
  paragraphWithClass(recipeSource, "rec-intro"),
  ...recipePage.completeRecipes.flatMap((recipe) => [
    `### ${markdownLink(recipe.title, `/recipes/${recipe.id}`)}`,
    recipe.status.replaceAll("-", " "),
    recipe.failure_mode,
    `**Lab:** ${recipe.exercise}`,
    `**Mastery:** ${recipe.mastery_gate}`,
  ]),
  "## Technique registry",
  ...recipeLinks(recipePage.registry),
  literalFragment(
    recipeSource,
    /<aside class="guide-link">([\s\S]*?)<\/aside>/,
  ),
]
  .filter(Boolean)
  .join("\n\n");

import * as experiments from "./experiments-page";
import experimentTemplate from "../pages/experiments.astro?raw";
import {
  experimentPublicHref,
  experimentRecipeHref,
  experimentLearningHref,
} from "./experimentArchive";
publicMarkdownSources["/experiments"] = [
  literalFragment(experimentTemplate, /(<h1>[\s\S]*?)<div class="summary"/),
  `${experiments.attempts.length} accounted attempts`,
  "0 unresolved attempts",
  `${experiments.exact} exact-evidence records`,
  `${experiments.families.length} experiment families`,
  literalFragment(
    experimentTemplate,
    /<nav class="hero-links"[^>]*>([\s\S]*?)<\/nav>/,
  ),
  "## The shape of the work",
  "Negative results remain first-class evidence.",
  ...experiments.statusOrder.map(
    (status) =>
      `- ${experiments.labels[status]}: ${experiments.counts[status]}`,
  ),
  "## All recorded attempts",
  ...experiments.attempts.flatMap((attempt) => [
    `### ${markdownLink(attempt.name, `/experiments/${attempt.id}`)}`,
    attempt.family.replaceAll("-", " "),
    experiments.labels[attempt.status] ?? attempt.status,
    ...("methods" in attempt
      ? (attempt.methods ?? []).map((method) => `- ${method}`)
      : []),
    `**Evidence:** ${attempt.evidence}`,
    ...("failure_reason" in attempt && attempt.failure_reason
      ? [`**Why it stopped:** ${attempt.failure_reason}`]
      : []),
    `**Learning:** ${attempt.lesson}`,
    `**Disposition:** ${attempt.next_action}`,
    experiments.confidenceLabels[attempt.failure_reason_confidence],
    markdownLink("Proof", experimentPublicHref(attempt)),
    markdownLink("Recipes", experimentRecipeHref(attempt)),
    markdownLink("Learn", experimentLearningHref(attempt)),
  ]),
  literalFragment(
    experimentTemplate,
    /<aside class="closure">([\s\S]*?)<\/aside>/,
  ),
].join("\n\n");

import * as learning from "./learn-page";
import learnTemplate from "../pages/learn.astro?raw";
const learnParts = [
  literalFragment(
    learnTemplate,
    /<div class="hero-copy">([\s\S]*?)<ol class="loop"/,
  ),
  "## Field guides",
  ...learning.fieldGuides.map(
    (link) => `- ${markdownLink(link.label, link.href)}`,
  ),
  literalFragment(
    learnTemplate,
    /<header class="section-heading">([\s\S]*?)<\/header>/,
  ),
  ...Object.entries(learning.readinessLegend).map(
    ([status, meaning]) => `**${status.replaceAll("-", " ")}:** ${meaning}`,
  ),
];
for (const stage of learning.artifactStages) {
  learnParts.push(
    `### ${stage.title}`,
    stage.question,
    stage.outcome,
    markdownLink("Open the learning path", `/learn#path-${stage.path_id}`),
  );
  for (const artifact of stage.artifacts)
    learnParts.push(
      `#### ${markdownLink(artifact.title, `/learn/artifacts/${artifact.id}`)}`,
      artifact.kind,
      artifact.readiness.replaceAll("-", " "),
      artifact.summary,
      `**Workload:** ${artifact.workload}`,
      ...artifact.actions.map(
        (action) =>
          `- ${action.name}: ${markdownLink(action.label, learning.artifactHref(action.href))}`,
      ),
      ...artifact.anchors.map(
        (anchor) =>
          `- Inspect: ${markdownLink(anchor.split("/").at(-1) ?? anchor, learning.evidenceHref(anchor))}`,
      ),
      ...artifact.cli_commands.map(
        (command) =>
          `- Run: ${markdownLink(`\`${command}\``, "/docs/cli-reference")}`,
      ),
    );
}
learnParts.push(
  literalFragment(
    learnTemplate,
    /<section class="learning-lab"[^>]*>\s*<header class="section-heading">([\s\S]*?)<\/header>/,
  ),
);
for (const path of learning.pathCards)
  learnParts.push(
    `### ${markdownLink(path.title, `/learn/paths/${path.id}`)}`,
    path.prerequisites.length
      ? `after ${path.prerequisites.join(" + ")}`
      : "start here",
    ...path.sequence.map((step, index) => `${index + 1}. ${step}`),
    `**Lab:** ${path.lab}`,
    `**Mastery gate:** ${path.mastery_gate}`,
    ...path.cli_commands.map(
      (command) =>
        `- CLI entry point: ${markdownLink(`\`${command}\``, "/docs/cli-reference")}`,
    ),
    ...path.recipes.map(
      (recipe) =>
        `- ${markdownLink(`Recipe: ${recipe.title}`, `/recipes/${recipe.id}`)}`,
    ),
    ...(path.recipes.length
      ? []
      : ["Foundation prerequisite; applied recipes begin in later paths."]),
    ...path.anchors.map(
      (anchor) =>
        `- ${markdownLink(anchor.replace(/^docs\//, "").replace(/\.md$/, ""), learning.evidenceHref(anchor))}`,
    ),
  );
learnParts.push(
  literalFragment(
    learnTemplate,
    /<section class="principle"[^>]*>([\s\S]*?)<\/section>/,
  ),
  literalFragment(
    learnTemplate,
    /<section class="chapters"[^>]*>\s*<header class="section-heading">([\s\S]*?)<\/header>/,
  ),
);
for (const chapter of learning.chapters)
  learnParts.push(
    `### ${chapter.title}`,
    chapter.question,
    chapter.body,
    `**Emits:** ${chapter.emits}`,
    ...chapter.docs.map(
      (link) => `- Read: ${markdownLink(link.label, link.href)}`,
    ),
    ...chapter.code.map(
      (link) => `- Source: ${markdownLink(link.label, link.href)}`,
    ),
  );
learnParts.push(
  literalFragment(
    learnTemplate,
    /<section class="case-files"[^>]*>\s*<header class="section-heading">([\s\S]*?)<\/header>/,
  ),
);
for (const item of learning.cases)
  learnParts.push(
    `### ${item.title}`,
    item.state,
    item.text,
    markdownLink(item.link, item.href),
    item.metric,
  );
const learnSourceLinks = learnTemplate.replace(
  /href=\{source\(\s*"([^"]+)"\s*,?\s*\)\}/g,
  (_, path) => `href="${learning.source(path)}"`,
);
learnParts.push(
  literalFragment(
    learnSourceLinks,
    /<section class="source-index"[^>]*>([\s\S]*?)<\/section>/,
  ),
  literalFragment(
    learnTemplate,
    /<footer class="next-step">([\s\S]*?)<\/footer>/,
  ),
);
publicMarkdownSources["/learn"] = learnParts.join("\n\n");

import {
  release,
  releaseSummary,
  statusLabel,
  recordUpdated,
  completedChecks,
  checks,
} from "./download-page";
import downloadTemplate from "../pages/download.astro?raw";
publicMarkdownSources["/download"] = [
  `# Signed for Mac. ${release.downloadable ? "Notarized by Apple." : "Awaiting Apple notarization."}`,
  statusLabel,
  release.downloadable ? "Available to download" : "Next: Apple notarization",
  `Record updated ${recordUpdated}`,
  releaseSummary,
  `**Version:** ${release.version} (${release.build})`,
  `**System:** macOS ${release.minimumMacOS}+`,
  `**Architecture:** ${release.architecture}`,
  ...(release.downloadable && release.artifactURL
    ? [
        markdownLink("Download verified DMG", release.artifactURL),
        "Verified for direct distribution. Compare the SHA-256 below after download.",
      ]
    : [
        "Download after verification",
        "No hidden or provisional artifact URL is present on this page.",
        markdownLink(
          "Follow GitHub Releases",
          "https://github.com/PostTrainLLM/posttrainllm/releases",
        ),
      ]),
  "## Trust ledger",
  `${completedChecks} / 6`,
  ...checks.map(
    (check) =>
      `- **${check.label}:** ${check.complete ? "verified" : "pending"}. ${check.detail}`,
  ),
  markdownLink("Release record JSON", "/releases/mac.json"),
  release.downloadable
    ? "How the gate was cleared"
    : "Why the gate stays closed",
  literalFragment(
    downloadTemplate,
    /(<h2 id="method-title">[\s\S]*?)<\/section>/,
  ),
  ...(release.downloadable && release.sha256
    ? [`## SHA-256\n\n\`${release.sha256}\``]
    : []),
].join("\n\n");

import trainingDashboardSource from "../pages/training-dashboard.astro?raw";
import evalLeaderboardSource from "../pages/eval-leaderboard.astro?raw";
import saeTimelineSource from "../pages/sae-timeline.astro?raw";
import inferenceSource from "../pages/inference.astro?raw";
import { CURATED } from "./inference-models";
for (const [path, source] of Object.entries({
  "/training-dashboard": trainingDashboardSource,
  "/eval-leaderboard": evalLeaderboardSource,
  "/sae-timeline": saeTimelineSource,
})) {
  publicMarkdownSources[path] = literalFragment(
    source,
    /<main\b[^>]*>([\s\S]*?)<\/main>/,
  );
}
const inferenceMarkup = inferenceSource.replace(
  /\{\s*CURATED\.map\([\s\S]*?\)\)\s*\}/,
  "PUBLIC_CURATED_MODELS",
);
publicMarkdownSources["/inference"] = literalFragment(
  inferenceMarkup,
  /<main\b[^>]*>([\s\S]*?)<\/main>/,
).replace(
  "PUBLIC_CURATED_MODELS",
  CURATED.map(
    (model) =>
      `- ${markdownLink(model.label, `https://huggingface.co/${model.id}`)}`,
  ).join("\n"),
);

import leaderboardSource from "../pages/leaderboard.astro?raw";
import gallery from "../../public/gallery/manifest.json";
import { BENCHES } from "./leaderboard-content.mjs";
const benchId = "tinystories-ppl";
const scored = gallery.models
  .filter((model) => model.benchmarks[benchId] != null)
  .sort((a, b) => a.benchmarks[benchId] - b.benchmarks[benchId]);
const formatParams = (n: number | null) =>
  n == null
    ? "—"
    : n >= 1e9
      ? `${(n / 1e9).toFixed(2)}B`
      : n >= 1e6
        ? `${(n / 1e6).toFixed(1)}M`
        : n >= 1e3
          ? `${(n / 1e3).toFixed(0)}K`
          : String(n);
const formatDuration = (ms: number | null | undefined) =>
  ms == null
    ? "—"
    : ms >= 3600000
      ? `${(ms / 3600000).toFixed(1)} hr`
      : ms >= 60000
        ? `${(ms / 60000).toFixed(0)} min`
        : `${(ms / 1000).toFixed(0)} s`;
const leaderboardTable = markdownTable(
  ["#", "Model", "Params", "Score", "Train", "Try"],
  scored.map((model, index) => [
    String(index + 1),
    `${model.icon || "•"} ${model.name}${model.submission?.featured ? " · curated" : ""}${model.submission?.browserTrained ? " · browser" : ""}${model.corpus ? ` · trained on ${model.corpus}` : ""}`,
    formatParams(model.paramCount),
    model.benchmarks[benchId].toFixed(model.benchmarks[benchId] < 10 ? 3 : 1),
    formatDuration(model.trainWallMs),
    markdownLink("try", `/playground?gallery=${encodeURIComponent(model.id)}`),
  ]),
);
const leaderboardMarkup = leaderboardSource
  .replace(/<table class="board"[\s\S]*?<\/table>/, "PUBLIC_LEADERBOARD")
  .replace(
    /<div id="benchInfo"[^>]*>[\s\S]*?<\/div>/,
    BENCHES[benchId].explainer,
  );
publicMarkdownSources["/leaderboard"] = literalFragment(
  leaderboardMarkup,
  /<main\b[^>]*>([\s\S]*?)<\/main>/,
).replace("PUBLIC_LEADERBOARD", leaderboardTable);

import { benchmarkMarkdown } from "./benchmark-markdown";
Object.assign(publicMarkdownSources, benchmarkMarkdown);

import { learningMarkdown } from "./learning-markdown";
Object.assign(publicMarkdownSources, learningMarkdown);
