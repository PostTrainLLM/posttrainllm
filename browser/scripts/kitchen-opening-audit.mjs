import { mkdir } from "node:fs/promises";
await mkdir(
  process.env.KITCHEN_EVIDENCE_DIR || "../artifacts/design/llm-kitchen",
  { recursive: true },
);
// Opening is a real data decision, with the primary action in the first viewport.
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
const browser = await chromium.launch({ headless: true });
const results = [];
const errors = [];
const base = `${process.env.KITCHEN_URL || "http://127.0.0.1:4173"}/articles/how-to-cook-an-llm`;
const assert = (value, message) => {
  if (!value) throw new Error(message);
};
try {
  for (const [width, height] of [
    [1440, 900],
    [1366, 768],
    [768, 1024],
    [390, 844],
    [320, 740],
  ]) {
    const page = await browser.newPage({
      viewport: { width, height },
      reducedMotion: "reduce",
    });
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(base);
    await page.locator(".opening-crops:not([hidden])").waitFor();
    await page.evaluate(() => document.fonts.ready);
    assert(
      (await page.locator("#opening-count").textContent()).includes("empty"),
      "Basket did not start empty",
    );
    assert(
      await page
        .locator(width <= 600 ? ".opening-goal" : ".opening-invitation p")
        .isVisible(),
      "Dinner goal hidden",
    );
    const next = await page.locator(".start-journey").boundingBox();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    );
    assert(!overflow, `Horizontal overflow ${width}`);
    assert(
      next.y + next.height <= height,
      `Primary action below viewport ${width}: ${next.y + next.height}`,
    );
    for (const label of await page.locator(".opening-crop").all()) {
      const box = await label.boundingBox();
      assert(
        box.y >= 0 && box.y + box.height <= height,
        `Source card below viewport ${width}`,
      );
      assert(
        await label.evaluate((el) => {
          const b = el.getBoundingClientRect();
          const hit = document.elementFromPoint(
            b.x + b.width / 2,
            b.y + b.height / 2,
          );
          return el === hit || el.contains(hit);
        }),
        `Source card occluded ${width}`,
      );
    }
    await page.screenshot({
      path: `${process.env.KITCHEN_EVIDENCE_DIR || "../artifacts/design/llm-kitchen"}/opening-final-${width}.png`,
    });
    const source = page.locator("[data-opening-source=explanation]");
    await source.focus();
    await page.keyboard.press("Space");
    assert(await source.isChecked(), "Keyboard did not pick the sample");
    assert(
      await page.locator("[data-ingredient][value=explanation]").isChecked(),
      "Canonical source mismatch",
    );
    assert(
      (await page.locator("#opening-count").textContent()).includes(
        "1 text sample",
      ),
      "Basket mismatch",
    );
    await page.reload();
    await page.locator(".opening-crops:not([hidden])").waitFor();
    assert(await source.isChecked(), "Reload lost opening selection");
    await source.check();
    assert(
      await page
        .locator(".crop-explanation")
        .evaluate((el) => getComputedStyle(el).animationName === "none"),
      "Reduced motion ignored",
    );
    await page.locator(".start-journey").click();
    await page.locator("#chopping[data-open=true]").waitFor();
    assert(
      await page.locator("[data-ingredient][value=explanation]").isChecked(),
      "Cutting board lost selection",
    );
    await page.goBack();
    await page.locator("#welcome:not([hidden])").waitFor();
    for (const id of ["weather", "dairy", "explanation"])
      await page.locator(`[data-opening-source=${id}]`).uncheck();
    assert(
      (await page.locator("#opening-count").textContent()).includes("empty"),
      "Empty basket not explained",
    );
    assert(
      (await page.locator(".start-journey").getAttribute("aria-disabled")) ===
        "true",
      "Empty basket can continue",
    );
    await page.locator(".start-journey").focus();
    await page.locator(".start-journey").press("Enter");
    assert(
      await source.evaluate((el) => el === document.activeElement),
      "Empty basket did not focus a source",
    );
    await page.locator(".opening-inspect").click();
    await page.locator("#ingredients[data-open=true]").waitFor();
    await page.locator("[data-ingredient][value=explanation]").check();
    await page.goBack();
    await page.locator("#welcome:not([hidden])").waitFor();
    assert(
      await page.locator("[data-opening-source=explanation]").isChecked(),
      "Inspector did not update opening",
    );
    results.push({
      width,
      height,
      primaryBottom: Math.round(next.y + next.height),
      overflow,
      keyboard: true,
      reload: true,
      emptyRecovery: true,
      inspectorSync: true,
    });
    await page.close();
  }
  const plain = await browser.newPage({
    javaScriptEnabled: false,
    viewport: { width: 390, height: 844 },
  });
  await plain.goto(base);
  assert(await plain.locator("#ingredients").isVisible(), "No-JS article lost");
  assert(
    (await plain.locator(".start-journey").getAttribute("href")) ===
      "#ingredients",
    "No-JS action skips harvest",
  );
  assert(
    await plain.locator(".opening-crops").isHidden(),
    "No-JS inert controls exposed",
  );
  await plain.close();
  assert(!errors.length, errors.join("\n"));
  const report = {
    status: "pass",
    results,
    errors,
    noJS: "Full reading fallback and harvest anchor remain available",
  };
  await writeFile(
    `${process.env.KITCHEN_EVIDENCE_DIR || "../artifacts/design/llm-kitchen"}/opening-final-review.json`,
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
}
