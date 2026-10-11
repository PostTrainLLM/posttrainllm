// Release visual audit for the public learning lab.
// Run after `pnpm build` while `pnpm preview` is serving the static output.

import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const baseURL = process.env.E2E_URL ?? "http://127.0.0.1:4173";
const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, "../..");
const attemptsSource = JSON.parse(
  await readFile(path.join(repoRoot, "docs/attempts.json"), "utf8"),
).attempts;
const recipeSource = JSON.parse(
  await readFile(path.join(repoRoot, "docs/recipes/registry.json"), "utf8"),
).recipes;
const pathSource = JSON.parse(
  await readFile(path.join(repoRoot, "docs/learn/path-registry.json"), "utf8"),
).paths;
const journeySource = JSON.parse(
  await readFile(
    path.join(repoRoot, "docs/learn/artifact-journey.json"),
    "utf8",
  ),
).stages;
const studySource = JSON.parse(
  await readFile(path.join(repoRoot, "docs/studies/registry.json"), "utf8"),
).studies;
const evidenceDir = process.env.EVIDENCE_DIR
  ? path.resolve(process.env.EVIDENCE_DIR)
  : path.resolve(here, "../../artifacts/design/lab");
const viewports = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 1000 },
];
const routes = [
  "/",
  "/download",
  "/playground",
  "/inference",
  "/webgpu-test",
  "/training-dashboard",
  "/experiments",
  "/recipes",
  "/learn",
  "/studies",
  "/studies/trainloop-ai",
  "/experiments/sql-toy-sft-r4",
  "/recipes/distillation",
  "/learn/paths/post-training",
  "/learn/artifacts/byte-tinygpt",
  "/docs/cli-reference",
  "/artifacts/needle2-tool-selection",
  "/artifacts/parakeet-wgsl-browser-asr",
];

await mkdir(evidenceDir, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
    : {}),
});
const failures = [];
const observations = [];
const heroObservations = [];

for (const viewport of viewports) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  const consoleErrors = [];
  const pageErrors = [];
  const requestErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      consoleErrors.push(`${page.url()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    requestErrors.push(
      `${page.url()}: ${request.url()} (${request.failure()?.errorText ?? "failed"})`,
    );
  });

  for (const route of routes) {
    const response = await page.goto(`${baseURL}${route}`, {
      waitUntil: "networkidle",
      timeout: 30_000,
    });
    const state = await page.evaluate(() => ({
      title: document.title,
      h1: document.querySelector("h1")?.textContent?.trim() ?? "",
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    }));
    const observation = {
      route,
      viewport: viewport.width,
      status: response?.status() ?? 0,
      h1: state.h1,
      horizontalOverflow: state.scrollWidth > state.innerWidth,
    };
    observations.push(observation);
    if (observation.status !== 200)
      failures.push(`${route} returned ${observation.status}`);
    if (!observation.h1)
      failures.push(`${route} has no H1 at ${viewport.width}px`);
    if (observation.horizontalOverflow) {
      failures.push(`${route} overflows horizontally at ${viewport.width}px`);
    }
  }

  await page.goto(`${baseURL}/`, { waitUntil: "networkidle" });
  const homeState = await page.evaluate(() => ({
    h1Count: document.querySelectorAll("h1").length,
    layout: document
      .querySelector("[data-hero-layout]")
      ?.getAttribute("data-hero-layout"),
    brand: getComputedStyle(document.documentElement)
      .getPropertyValue("--brand")
      .trim(),
    entryPoints: document.querySelectorAll("#entry-points nav > a").length,
    guides: document.querySelectorAll("#field-guides nav > a").length,
    quickstart: document
      .querySelector('.identity-actions [data-log="quickstart_opened"]')
      ?.getAttribute("href"),
    proof: document
      .querySelector('[data-log="specialist_proof_opened"]')
      ?.getAttribute("href"),
    fileOps: document.querySelector("#file-ops-proof")?.textContent ?? "",
    sql: document.querySelector("#sql-proof")?.textContent ?? "",
    ledger: document.querySelector("#paper-trail")?.textContent ?? "",
    footer: document
      .querySelector('footer[data-fleet-footer="studio"]')
      ?.getAttribute("data-catalog-id"),
    footerGroups: [
      ...document.querySelectorAll("studio-footer nav[aria-label=Footer] h2"),
    ].map((node) => node.textContent?.trim() ?? ""),
  }));
  heroObservations.push({ viewport: viewport.width, ...homeState });
  if (homeState.h1Count !== 1 || homeState.layout !== "masthead")
    failures.push(`home masthead contract drifted at ${viewport.width}px`);
  if (homeState.brand !== "#48e5c2")
    failures.push(`home brand drifted at ${viewport.width}px`);
  if (homeState.entryPoints !== 4 || homeState.guides !== 7)
    failures.push(`home directories drifted at ${viewport.width}px`);
  if (
    homeState.quickstart !== "/docs/quickstart" ||
    homeState.proof !== "/artifacts"
  )
    failures.push(`home logged actions missing at ${viewport.width}px`);
  for (const phrase of [
    "9/12",
    "12/12",
    "30/45",
    "25/45",
    "2.42×",
    "360.50s",
    "148.91s",
    "Breadth fell",
  ])
    if (!homeState.fileOps.includes(phrase))
      failures.push(`home file-ops proof missing ${phrase}`);
  for (const phrase of ["0.860", "0.920", "0.000", "retry-data"])
    if (!homeState.sql.includes(phrase))
      failures.push(`home SQL proof missing ${phrase}`);
  const worked = attemptsSource.filter(
    (attempt) => attempt.status === "worked",
  ).length;
  const caveated = attemptsSource.filter(
    (attempt) => attempt.status === "worked-with-caveat",
  ).length;
  const mixed = attemptsSource.length - worked - caveated;
  for (const phrase of [
    `${attemptsSource.length} resolved attempts`,
    `${worked} worked cleanly`,
    `${caveated} worked with caveat`,
    `${mixed} failed`,
  ])
    if (!homeState.ledger.includes(phrase))
      failures.push(`home ledger missing ${phrase}`);
  if (
    homeState.footer !== "posttrainllm" ||
    homeState.footerGroups.join(",") !== "build,measure,learn,agents and source"
  )
    failures.push(`home StudioFooter contract drifted at ${viewport.width}px`);
  await page.screenshot({
    path: path.join(evidenceDir, `after-${viewport.width}.png`),
    fullPage: true,
  });

  await page.goto(`${baseURL}/studies/trainloop-ai`, {
    waitUntil: "networkidle",
  });
  await page.screenshot({
    path: path.join(evidenceDir, `knowledge-dossier-${viewport.width}.png`),
    fullPage: true,
  });

  await page.goto(`${baseURL}/learn`, { waitUntil: "networkidle" });
  await page.screenshot({
    path: path.join(evidenceDir, `learn-${viewport.width}.png`),
  });
  await page.locator("#artifact-journey").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: path.join(evidenceDir, `learn-journey-${viewport.width}.png`),
  });

  await page.goto(`${baseURL}/experiments`, { waitUntil: "networkidle" });
  await page.locator("#experiment-search").fill("needle");
  await page.locator("#archive-title").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: path.join(evidenceDir, `experiments-needle-${viewport.width}.png`),
  });

  if (consoleErrors.length > 0)
    failures.push(...consoleErrors.map((error) => `console: ${error}`));
  if (pageErrors.length > 0)
    failures.push(...pageErrors.map((error) => `page: ${error}`));
  if (requestErrors.length > 0)
    failures.push(...requestErrors.map((error) => `request: ${error}`));
  await context.close();
}

const context = await browser.newContext({ viewport: viewports.at(-1) });
const page = await context.newPage();

await page.goto(`${baseURL}/experiments`, { waitUntil: "networkidle" });
const attemptCount = await page.locator(".experiment").count();
await page.locator("#experiment-search").fill("needle");
const needleCount = await page.locator(".experiment:visible").count();
await page.locator("#experiment-reset").click();
await page.locator('[data-filter-status="worked-with-caveat"]').click();
const caveatCount = await page.locator(".experiment:visible").count();

await page.goto(`${baseURL}/recipes`, { waitUntil: "networkidle" });
const recipeCount = await page.locator("#complete-registry .rec-card").count();

await page.goto(`${baseURL}/learn`, { waitUntil: "networkidle" });
const stageCount = await page.locator(".artifact-stage").count();
const artifactCount = await page.locator(".journey-artifact").count();
const pathCount = await page.locator(".path-card").count();

await page.goto(`${baseURL}/studies`, { waitUntil: "networkidle" });
const studyCount = await page.locator(".study-grid article").count();

const counts = {
  attempts: attemptCount,
  needleResults: needleCount,
  workedWithCaveat: caveatCount,
  recipes: recipeCount,
  journeyStages: stageCount,
  buildableArtifacts: artifactCount,
  learningPaths: pathCount,
  studies: studyCount,
};
const expected = {
  attempts: attemptsSource.length,
  needleResults: attemptsSource.filter((attempt) =>
    `${attempt.name} ${attempt.family}`.toLowerCase().includes("needle"),
  ).length,
  workedWithCaveat: attemptsSource.filter(
    (attempt) => attempt.status === "worked-with-caveat",
  ).length,
  recipes: recipeSource.length,
  journeyStages: journeySource.length,
  buildableArtifacts: journeySource.flatMap((stage) => stage.artifacts).length,
  learningPaths: pathSource.length,
  studies: studySource.length,
};
for (const [key, value] of Object.entries(expected)) {
  if (counts[key] !== value)
    failures.push(`${key}: expected ${value}, got ${counts[key]}`);
}

for (const resource of [
  ["/llms.txt", "text/plain"],
  ["/llms-full.txt", "text/plain"],
  ["/api-ai.json", "application/json"],
  ["/releases/mac.json", "application/json"],
]) {
  const [route, expectedType] = resource;
  const response = await page.request.get(`${baseURL}${route}`);
  if (response.status() !== 200) {
    failures.push(`${route} returned ${response.status()}`);
    continue;
  }
  const contentType = response.headers()["content-type"] ?? "";
  if (!contentType.includes(expectedType)) {
    failures.push(`${route} content type ${contentType} != ${expectedType}`);
  }
}

const agentCatalog = await (
  await page.request.get(`${baseURL}/api-ai.json`)
).json();
if (agentCatalog.version !== "3") failures.push("agent catalog is not v3");
if (agentCatalog.experimentSummary?.total !== attemptsSource.length)
  failures.push("agent catalog experiment total drifted");
const expectedNonPositive = attemptsSource.filter(
  (attempt) => !["worked", "worked-with-caveat"].includes(attempt.status),
).length;
if (agentCatalog.experimentSummary?.nonPositiveOrMixed !== expectedNonPositive)
  failures.push("agent catalog non-positive result total drifted");
if (agentCatalog.learningSummary?.paths !== pathSource.length)
  failures.push("agent catalog learning path total drifted");
if (agentCatalog.learningSummary?.studies !== studySource.length)
  failures.push("agent catalog study total drifted");
for (const group of ["build", "measure", "learn"]) {
  if (!Array.isArray(agentCatalog.capabilities?.[group]))
    failures.push(`agent catalog missing ${group} capabilities`);
}

await context.close();
await browser.close();

console.log(
  JSON.stringify(
    { baseURL, counts, heroObservations, observations, failures },
    null,
    2,
  ),
);
if (failures.length > 0) process.exitCode = 1;
