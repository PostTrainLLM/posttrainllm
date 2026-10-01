import { mkdir } from "node:fs/promises";
await mkdir(
  process.env.KITCHEN_EVIDENCE_DIR || "../artifacts/design/llm-kitchen",
  { recursive: true },
);
// First-screen composition check: primary interaction and scene navigation are visible.
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
const browser = await chromium.launch({ headless: true });
const results = [];
const targets = {
  ingredients: "#harvest-status",
  chopping: "#chop-preview",
  cleaning: "#prepare-batch",
  "base-recipe": "#cook-step",
  refine: "[data-checkpoint=sft]",
  chat: "#return-stove",
};
try {
  for (const [width, height] of [
    [1440, 900],
    [1366, 768],
    [768, 1024],
    [390, 844],
  ]) {
    const page = await browser.newPage({
      viewport: { width, height },
      reducedMotion: "reduce",
    });
    for (const [stage, target] of Object.entries(targets)) {
      await page.goto(
        `${process.env.KITCHEN_URL || "http://127.0.0.1:4173"}/articles/how-to-cook-an-llm#${stage}`,
      );
      await page.locator(`#${stage}[data-open=true]`).waitFor();
      await page.evaluate(() => document.fonts.ready);
      await page.locator(target).waitFor({ state: "visible" });
      const action = await page.locator(target).boundingBox();
      const next = await page
        .locator(stage === "chat" ? "#scene-back" : "#scene-forward")
        .boundingBox();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      );
      results.push({
        width,
        height,
        stage,
        primaryBottom: Math.round(action.y + action.height),
        navigationBottom: Math.round(next.y + next.height),
        primaryInViewport: action.y >= 0 && action.y + action.height <= height,
        navigationInViewport: next.y + next.height <= height,
        overflow,
      });
      if (width === 1440 || width === 390)
        await page.screenshot({
          path: `${process.env.KITCHEN_EVIDENCE_DIR || "../artifacts/design/llm-kitchen"}/compact-${stage}-${width}.png`,
        });
    }
    for (const [panel, target] of [
      ["1", "#simulate-feedback"],
      ["2", "#add-garnish"],
    ]) {
      await page.goto(
        "http://127.0.0.1:4173/articles/how-to-cook-an-llm#refine",
      );
      await page.locator(`[data-refine-panel="${panel}"]`).click();
      await page.locator(target).waitFor({ state: "visible" });
      const action = await page.locator(target).boundingBox();
      const next = await page.locator("#scene-forward").boundingBox();
      results.push({
        width,
        height,
        stage: `refine-${panel}`,
        primaryBottom: Math.round(action.y + action.height),
        navigationBottom: Math.round(next.y + next.height),
        primaryInViewport: action.y >= 0 && action.y + action.height <= height,
        navigationInViewport: next.y + next.height <= height,
        overflow: false,
      });
    }
    await page.goto(
      `${process.env.KITCHEN_URL || "http://127.0.0.1:4173"}/articles/how-to-cook-an-llm`,
    );
    const start = await page.locator(".start-journey").boundingBox();
    const route = await page.locator(".journey-map").boundingBox();
    results.push({
      width,
      height,
      stage: "welcome",
      primaryBottom: Math.round(start.y + start.height),
      navigationBottom: Math.round(route.y + route.height),
      primaryInViewport: start.y + start.height <= height,
      navigationInViewport: route.y + route.height <= height,
      overflow: false,
    });
    await page.screenshot({
      path: `${process.env.KITCHEN_EVIDENCE_DIR || "../artifacts/design/llm-kitchen"}/compact-welcome-${width}.png`,
    });
    await page.close();
  }
  await writeFile(
    `${process.env.KITCHEN_EVIDENCE_DIR || "../artifacts/design/llm-kitchen"}/viewport-review.json`,
    JSON.stringify(results, null, 2),
  );
  console.log(JSON.stringify(results));
  if (
    results.some(
      (r) => r.overflow || !r.primaryInViewport || !r.navigationInViewport,
    )
  )
    process.exitCode = 1;
} finally {
  await browser.close();
}
