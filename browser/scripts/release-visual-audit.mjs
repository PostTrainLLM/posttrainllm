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
  "/download",
  "/playground",
  "/inference",
  "/webgpu-test",
  "/training-dashboard",
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
  const homeState = await page.evaluate(() => {
    const curve = document.querySelector(".hero-curve");
    const curveDot = document.querySelector(".hc-dot");
    const curveLine = document.querySelector(".hc-line");
    const curveBand = document.querySelector(".hero-curve-band");
    const curveCaption = document.querySelector(".hero-curve-cap");
    const stats = document.querySelector(".hero-stats");
    const actions = [
      ...document.querySelectorAll(
        ".hero > .hero-inner .hero-cta a, .hero > .hero-inner .mac-release-entry",
      ),
    ];
    if (
      !(curve instanceof SVGElement) ||
      !(curveDot instanceof SVGElement) ||
      !(curveLine instanceof SVGPathElement) ||
      !(curveBand instanceof HTMLElement) ||
      !(curveCaption instanceof HTMLElement) ||
      !(stats instanceof HTMLElement) ||
      actions.some((action) => !(action instanceof HTMLElement))
    ) {
      return null;
    }
    const statsStyle = getComputedStyle(stats);
    const headline = document.querySelector(".hero-h1");
    if (!(headline instanceof HTMLElement)) return null;
    const curveBounds = curve.getBoundingClientRect();
    const viewBox = curve.viewBox.baseVal;
    const curveLength = curveLine.getTotalLength();
    const curvePoints = Array.from({ length: 201 }, (_, index) => {
      const point = curveLine.getPointAtLength((curveLength * index) / 200);
      return {
        x: curveBounds.x + (point.x / viewBox.width) * curveBounds.width,
        y: curveBounds.y + (point.y / viewBox.height) * curveBounds.height,
      };
    });
    const actionBounds = actions.map((action) =>
      action.getBoundingClientRect(),
    );
    const dotBounds = curveDot.getBoundingClientRect();
    const captionBounds = curveCaption.getBoundingClientRect();
    const statsBounds = stats.getBoundingClientRect();
    const bandBounds = curveBand.getBoundingClientRect();
    return {
      curveInsideBand:
        curveBounds.top >= bandBounds.top &&
        curveBounds.bottom <= bandBounds.bottom,
      actionOverlap: actionBounds.some((action) =>
        curvePoints.some(
          (point) =>
            point.x >= action.left &&
            point.x <= action.right &&
            point.y >= action.top &&
            point.y <= action.bottom,
        ),
      ),
      actionClearance: Math.min(
        ...actionBounds.map((action) => bandBounds.top - action.bottom),
      ),
      curveVerticalShare:
        (Math.max(...curvePoints.map((point) => point.y)) -
          Math.min(...curvePoints.map((point) => point.y))) /
        bandBounds.height,
      headlineSize: Number.parseFloat(getComputedStyle(headline).fontSize),
      heroMetrics: [...stats.querySelectorAll("li")].map((item) => ({
        value: item.querySelector("b")?.textContent?.trim() ?? "",
        label: item.querySelector("span")?.textContent?.trim() ?? "",
      })),
      terminalClearance: statsBounds.top - dotBounds.bottom,
      captionOverlapsCurveTerminal:
        captionBounds.top < dotBounds.bottom &&
        captionBounds.bottom > dotBounds.top,
      statsBackground: statsStyle.backgroundColor,
      statsBackdrop: statsStyle.backdropFilter,
      entryPoints: document.querySelectorAll(".entry-rail > a").length,
      outcomeCounts: [...document.querySelectorAll(".outcome-count b")].map(
        (node) => node.textContent?.trim() ?? "",
      ),
      footerGroups: [...document.querySelectorAll(".foot-group > p")].map(
        (node) => node.textContent?.trim() ?? "",
      ),
    };
  });
  if (!homeState) {
    failures.push(`home proof surfaces missing at ${viewport.width}px`);
  } else {
    heroObservations.push({
      viewport: viewport.width,
      headlineSize: Number(homeState.headlineSize.toFixed(2)),
      actionClearance: Number(homeState.actionClearance.toFixed(2)),
      curveVerticalShare: Number(
        (homeState.curveVerticalShare * 100).toFixed(2),
      ),
      terminalClearance: Number(homeState.terminalClearance.toFixed(2)),
    });
    if (!homeState.curveInsideBand)
      failures.push(
        `hero curve escaped its evidence band at ${viewport.width}px`,
      );
    if (homeState.actionOverlap)
      failures.push(`hero curve crosses an action at ${viewport.width}px`);
    if (homeState.actionClearance < 40)
      failures.push(
        `hero curve band has only ${homeState.actionClearance.toFixed(1)}px clearance after actions at ${viewport.width}px`,
      );
    if (homeState.curveVerticalShare < 0.55)
      failures.push(
        `hero curve uses only ${(homeState.curveVerticalShare * 100).toFixed(1)}% of its band at ${viewport.width}px`,
      );
    if (homeState.headlineSize > 52.1)
      failures.push(
        `hero headline grew to ${homeState.headlineSize.toFixed(1)}px at ${viewport.width}px`,
      );
    const expectedHeroMetrics = [
      { value: "100%", label: "file ops · 12/12 · stock 9/12" },
      { value: "55.6%", label: "breadth · 25/45 · stock 30/45" },
      { value: "0", label: "unexpected side effects · stock 8" },
      {
        value: "2.42×",
        label: "depth wall speed · 360.50s → 148.91s",
      },
    ];
    if (
      JSON.stringify(homeState.heroMetrics) !==
      JSON.stringify(expectedHeroMetrics)
    )
      failures.push(`hero proof metrics drifted at ${viewport.width}px`);
    if (homeState.terminalClearance < 56)
      failures.push(
        `hero curve terminal has only ${homeState.terminalClearance.toFixed(1)}px clearance above stats at ${viewport.width}px`,
      );
    if (homeState.captionOverlapsCurveTerminal)
      failures.push(
        `hero curve terminal overlaps its caption at ${viewport.width}px`,
      );
    if (homeState.statsBackground !== "rgba(0, 0, 0, 0)")
      failures.push(`hero stats still hide the curve at ${viewport.width}px`);
    if (homeState.statsBackdrop !== "none")
      failures.push(`hero stats still blur the curve at ${viewport.width}px`);
    if (homeState.entryPoints !== 4)
      failures.push(`home entry map has ${homeState.entryPoints} items`);
    if (homeState.outcomeCounts.join(",") !== "5,37,34")
      failures.push(
        `home outcome distribution drifted: ${homeState.outcomeCounts}`,
      );
    if (
      homeState.footerGroups.join(",") !== "Build,Measure,Learn,Agents + source"
    )
      failures.push(
        `footer capability groups drifted: ${homeState.footerGroups}`,
      );
  }
  await page.screenshot({
    path: path.join(evidenceDir, `after-${viewport.width}.png`),
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
  attempts: 76,
  needleResults: 3,
  workedWithCaveat: 37,
  recipes: 18,
  journeyStages: 9,
  buildableArtifacts: 13,
  learningPaths: 9,
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
if (agentCatalog.experimentSummary?.total !== 76)
  failures.push("agent catalog experiment total drifted");
if (agentCatalog.experimentSummary?.nonPositiveOrMixed !== 34)
  failures.push("agent catalog non-positive result total drifted");
if (agentCatalog.learningSummary?.paths !== 9)
  failures.push("agent catalog learning path total drifted");
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
