// Release visual audit for the public learning lab.
// Run after `pnpm build` while `pnpm preview` is serving the static output.

import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const baseURL = process.env.E2E_URL ?? "http://127.0.0.1:4173";
const here = path.dirname(fileURLToPath(import.meta.url));
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
  "/experiments",
  "/recipes",
  "/learn",
  "/docs/cli-reference",
  "/artifacts/needle2-tool-selection",
  "/artifacts/parakeet-wgsl-browser-asr",
];

await mkdir(evidenceDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const failures = [];
const observations = [];

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

const counts = {
  attempts: attemptCount,
  needleResults: needleCount,
  workedWithCaveat: caveatCount,
  recipes: recipeCount,
  journeyStages: stageCount,
  buildableArtifacts: artifactCount,
  learningPaths: pathCount,
};
const expected = {
  attempts: 75,
  needleResults: 2,
  workedWithCaveat: 38,
  recipes: 18,
  journeyStages: 9,
  buildableArtifacts: 13,
  learningPaths: 9,
};
for (const [key, value] of Object.entries(expected)) {
  if (counts[key] !== value)
    failures.push(`${key}: expected ${value}, got ${counts[key]}`);
}

await context.close();
await browser.close();

console.log(
  JSON.stringify({ baseURL, counts, observations, failures }, null, 2),
);
if (failures.length > 0) process.exitCode = 1;
