// Focused, no-training browser check for the garden-to-table article.
// Run after browser build with the repo's Astro preview serving dist.
import { chromium } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
const base =
  process.env.E2E_URL ?? (process.env.KITCHEN_URL || "http://127.0.0.1:4173");
const evidence = path.resolve(
  process.env.EVIDENCE_DIR ?? "../artifacts/design/llm-kitchen",
);
await mkdir(evidence, { recursive: true });
const report = { viewports: [], interactions: [], errors: [] };
const assert = (condition, message) => {
  if (!condition) throw new Error(message);
};
const browser = await chromium.launch({
  headless: true,
  args: ["--disable-webgpu"],
});
try {
  for (const width of [390, 768, 1440]) {
    const context = await browser.newContext({
      viewport: { width, height: width === 1440 ? 1100 : 844 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    page.on("pageerror", (error) => report.errors.push(error.message));
    await page.goto(`${base}/articles/how-to-cook-an-llm`);
    await page.evaluate(() => document.fonts.ready);
    assert(
      (await page.locator("[data-journey-stage]").count()) === 6,
      "Six journey stops missing",
    );
    assert(
      (await page.locator(".journey-stop .scene-pair").count()) === 6,
      "Kitchen/model pairing missing",
    );
    assert(
      !(await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth,
      )),
      `Page overflow at ${width}`,
    );
    const duplicates = await page.evaluate(() => {
      const ids = [...document.querySelectorAll("[id]")].map((node) => node.id);
      return ids.filter((id, index) => ids.indexOf(id) !== index);
    });
    assert(!duplicates.length, `Duplicate IDs: ${duplicates}`);
    await page.screenshot({
      path: path.join(evidence, `after-${width}.png`),
      fullPage: true,
    });
    await page.screenshot({
      path: path.join(evidence, `first-viewport-${width}.png`),
    });
    for (const id of [
      "ingredients",
      "chopping",
      "cleaning",
      "base-recipe",
      "refine",
    ]) {
      await page.evaluate((id) => {
        location.hash = id;
      }, id);
      await page.locator(`#${id}`).waitFor({ state: "visible" });
      assert(
        (await page.locator("[data-journey-stage]:visible").count()) === 1,
        "Multiple scenes visible",
      );
      await page.locator(`#${id}`).scrollIntoViewIfNeeded();
      const activeAnimations = await page
        .locator(`#${id} .scene-art`)
        .evaluate((el) =>
          [...el.querySelectorAll("*")].some(
            (node) => getComputedStyle(node).animationName !== "none",
          ),
        );
      assert(!activeAnimations, "Reduced-motion scene animated");
      // Keep the sticky site and journey navigation out of illustration crops.
      await page.addStyleTag({
        content: ".site-header,.journey-nav { visibility:hidden!important }",
      });
      await page
        .locator(`#${id} .scene-pair`)
        .screenshot({ path: path.join(evidence, `${id}-${width}.png`) });
    }
    report.viewports.push({
      width,
      overflow: false,
      stops: 6,
      duplicateIds: 0,
    });
    await context.close();
  }
  const motionContext = await browser.newContext({
    reducedMotion: "no-preference",
  });
  const motionPage = await motionContext.newPage();
  await motionPage.goto(`${base}/articles/how-to-cook-an-llm#chopping`);
  await motionPage.waitForFunction(() =>
    document.querySelector("#chopping").classList.contains("scene-running"),
  );
  assert(
    (await motionPage
      .locator("#chopping .scene-art .scene-knife")
      .evaluate((node) => getComputedStyle(node).animationName)) ===
      "knife-chop",
    "Knife animation missing",
  );
  await motionContext.close();
  report.interactions.push(
    "Motion-enabled scene animates; reduced-motion scenes suppress animation",
  );
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
  });
  await context.addInitScript(() => {
    window.__kitchenMessages = [];
    const original = Worker.prototype.postMessage;
    Worker.prototype.postMessage = function (message, ...args) {
      window.__kitchenMessages.push(message.type);
      return original.call(this, message, ...args);
    };
  });
  const page = await context.newPage();
  page.on("pageerror", (error) => report.errors.push(error.message));
  await page.goto(`${base}/articles/how-to-cook-an-llm`);
  await page.locator(".opening-inspect").click();
  for (const id of ["explanation", "conversation", "code"])
    await page.locator(`[data-ingredient][value=${id}]`).check();
  await page.locator("[data-ingredient][value=duplicate]").check();
  await page.locator("[data-ingredient][value=broken]").check();
  assert(
    (await page.locator("#harvest-status").textContent()).includes(
      "5 text sample",
    ),
    "Harvest count stale",
  );
  await page.locator("#scene-forward").click();
  assert(
    await page
      .locator("#chopping h2")
      .evaluate((node) => node === document.activeElement),
    "Navigation did not focus heading",
  );
  await page.locator("#chop-text").fill("café");
  await page.locator("#chop-preview").click();
  assert(
    (await page.locator(".token-piece").count()) === 5,
    "UTF-8 multibyte preview incorrect",
  );
  assert(
    (await page.locator("#chop-status").textContent()).includes(
      "weights unchanged",
    ),
    "Token preview claims training",
  );
  await page.locator("#chop-text").fill("");
  assert(
    (await page.locator(".token-piece").count()) === 0,
    "Edited token input retained stale preview",
  );
  await page.locator("#chop-preview").click();
  assert(
    (await page.locator("#chop-status").textContent()).includes("empty"),
    "Empty token input not handled",
  );
  report.interactions.push(
    "Harvest selection carries forward; editable byte tokenization handles Unicode, empty input, and stale results",
  );
  await page.locator("#scene-forward").click();
  await page.locator("#prepare-batch").click();
  assert(
    (await page.locator("#prepare-status").textContent()).includes(
      "5 selected → 3 kept",
    ),
    "Harvest was not carried into cleanup",
  );
  const prepared = await page.locator("#prepared-text").textContent();
  report.interactions.push(
    "Sink prepares selected harvest: exact repeat and malformed sample removed; final text re-encoded",
  );
  await page.locator("#scene-forward").click();
  assert(
    await page.locator("#cook-step").isEnabled(),
    "Prepared batch cannot cook",
  );
  assert(
    await page.locator("#send-chat").isDisabled(),
    "Model trained without explicit cooking",
  );
  report.interactions.push(
    "Prepared batch enables opt-in real cooking; no automatic model training",
  );
  await page.locator("#scene-forward").click();
  await page.locator("[data-checkpoint=sft]").click();
  assert(
    (await page.locator("#checkpoint-evidence").textContent()).includes(
      "Demonstration",
    ),
    "SFT evidence missing",
  );
  await page.locator('[data-refine-panel="1"]').click();
  await page.locator("[data-taste=b]").click();
  assert(
    (await page.locator("#preference-status").textContent()).includes(
      "weights unchanged",
    ),
    "Feedback collection claims training",
  );
  await page.locator("#simulate-feedback").click();
  assert(
    await page.locator("#feedback-demo").isVisible(),
    "Feedback optimization illustration missing",
  );
  await page.locator('[data-refine-panel="2"]').click();
  const plain = await page.locator("#served-output").textContent();
  await page.locator("#add-garnish").click();
  assert(
    (await page.locator("#served-output").textContent()).endsWith(plain),
    "Presentation garnish changed answer content",
  );
  assert(
    (await page.locator("#garnish-status").textContent()).includes(
      "not post-training",
    ),
    "Garnish conflated with training",
  );
  await page.locator("#add-garnish").click();
  assert(
    (await page.locator("#served-output").textContent()) === plain,
    "Garnish toggle not reversible",
  );
  report.interactions.push(
    "Post-training checkpoint and preference scenes retained; garnish changes presentation only",
  );
  await page.locator('.journey-nav a[href="#cleaning"]').click();
  await page.locator("#open-trainer").click();
  await page.waitForURL("**/playground?kitchen=1");
  await page.locator(".kitchen-import").waitFor({ timeout: 20000 });
  if (await page.locator("#welcome").isVisible())
    await page.locator("#welcomeSkip").click();
  assert(
    (await page.locator("#corpus").inputValue()) !== prepared,
    "Batch imported without explicit choice",
  );
  await page
    .getByRole("button", {
      name: "Replace corpus with kitchen batch",
      exact: true,
    })
    .click();
  assert(
    (await page.locator("#corpus").inputValue()) === prepared,
    "Journey batch import mismatch",
  );
  assert(
    !(await page.evaluate(() =>
      window.__kitchenMessages.some((type) =>
        ["start", "train", "continue"].includes(type),
      ),
    )),
    "Handoff started training",
  );
  report.interactions.push(
    "Journey batch transfers via explicit trainer import; no training message sent",
  );
  await context.close();
  const noScript = await browser.newContext({ javaScriptEnabled: false });
  const fallback = await noScript.newPage();
  await fallback.goto(`${base}/articles/how-to-cook-an-llm`);
  assert(
    (await fallback.locator("[data-journey-stage]").count()) === 6,
    "No-JS reading journey missing",
  );
  assert(
    (await fallback.locator(".journey-next").count()) === 6,
    "No-JS next-stop links missing",
  );
  report.interactions.push(
    "All six reading scenes and next-stop links available without JavaScript",
  );
  await noScript.close();
  assert(!report.errors.length, report.errors.join("\n"));
  await writeFile(
    path.join(evidence, "journey-browser-review.json"),
    `${JSON.stringify(report, null, 2)}\n`,
  );
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
}
