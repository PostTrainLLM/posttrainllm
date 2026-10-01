// Real verification uses ONE optimizer step; UI/lifecycle uses a controlled worker.
import { chromium } from "playwright";
import { writeFile, readFile } from "node:fs/promises";
const live = process.env.LIVE_COOK === "1";
const browser = await chromium.launch({ headless: true, args: ["--disable-webgpu"] });
const report = { mode: live ? "real WASM: one training step, same-weight generation/export" : "controlled worker: UI and lifecycle", results: [], errors: [] };
const assert = (value, message) => { if (!value) throw new Error(message); };
try {
  for (const width of live ? [1366] : [1366, 390]) {
    const context = await browser.newContext({ viewport: { width, height: width === 390 ? 844 : 768 }, reducedMotion: "reduce" });
    await context.addInitScript(({ live }) => {
      const Real = window.Worker;
      window.__cookingMessages = [];
      window.Worker = class {
        constructor(url, options) {
          if (live) {
            const worker = new Real(url, options);
            const post = worker.postMessage.bind(worker);
            worker.postMessage = (m, ...args) => { window.__cookingMessages.push(m.type); if (m.type === "train") m.config.maxSteps = 1; post(m, ...args); };
            return worker;
          }
          this.stopped = false;
        }
        postMessage(m) {
          window.__cookingMessages.push(m.type);
          const emit = data => { if (!this.stopped) this.onmessage?.({ data }); };
          if (m.type === "train" || m.type === "continue") {
            emit({ type:"progress", progress:{ step:0,maxSteps:256,trainLoss:5.6,tokensPerSecond:0 } });
            this.pending = setTimeout(() => {
              emit({ type:"progress", progress:{ step:256,maxSteps:256,trainLoss:2.4,tokensPerSecond:1800 } });
              emit({ type:"checkpoint", state:new Uint8Array([0,1,2,3]).buffer });
              emit({ type:"done", reason:"finished" });
            }, 150);
          }
          if (m.type === "stop") { clearTimeout(this.pending); emit({type:"checkpoint",state:new Uint8Array([0,1,2,3]).buffer}); emit({type:"done",reason:"stopped"}); }
          if (m.type === "sample") this.pending = setTimeout(() => emit({ type:"sample_done",text:"Controlled completion, not model evidence." }), 120);
          if (m.type === "restore") setTimeout(() => emit({ type:"restored" }), 20);
        }
        terminate() { this.stopped = true; clearTimeout(this.pending); }
      };
    }, { live });
    const page = await context.newPage();
    page.on("pageerror", e => report.errors.push(e.message));
    await page.goto("http://127.0.0.1:4173/articles/how-to-cook-an-llm");
    await page.locator("[data-opening-source=explanation]").check();
    await page.locator(".start-journey").click();
    await page.locator("#chop-preview").click();
    await page.locator("#scene-forward").click();
    await page.locator("#prepare-batch").click();
    const batch = await page.locator("#prepared-text").textContent();
    await page.locator("#scene-forward").click();
    assert(await page.locator("#cook-step").isEnabled(), "Prepared batch cannot cook");
    const start = Date.now();
    await page.locator("#cook-step").click();
    await page.waitForFunction(() => document.querySelector("#send-chat").disabled === false, { timeout: 15000 });
    assert((await page.locator("#cook-loss").textContent()) !== "—", "No actual progress");
    const stoveNav = await page.locator("#scene-controls").boundingBox();
    await page.screenshot({path:`../artifacts/design/llm-kitchen/stove-ready-${width}.png`});
    assert(stoveNav.y + stoveNav.height <= (width === 390 ? 844 : 768), "Cooked stove navigation below viewport");
    if (!live) {
      await page.locator("#reset-cook").click();
      await page.locator("#stop-cook").click();
      await page.waitForFunction(() => document.querySelector("#send-chat").disabled === false);
    }
    await page.locator("#scene-forward").click();
    await page.locator("[data-checkpoint=sft]").click();
    await page.locator("#scene-forward").click();
    await page.locator("[data-taste=b]").click();
    await page.locator("#simulate-feedback").click();
    await page.locator("#scene-forward").click();
    await page.locator("#add-garnish").click();
    await page.locator("#scene-forward").click();
    assert(await page.locator("#send-chat").isEnabled(), "Lost cooked model along journey");
    await page.locator("#try-dinner").click();
    const prompt = await page.locator("#chat-prompt").inputValue();
    assert(batch.startsWith(prompt), "Suggested prompt unrelated to cooked corpus");
    await page.locator("#send-chat").click();
    await page.waitForFunction(() => document.querySelector("#chat-status").textContent.includes("Actual output"), { timeout: 10000 });
    const messages = await page.evaluate(() => window.__cookingMessages);
    const completion = await page.locator("#chat-log").textContent();
    const downloadPromise = page.waitForEvent("download");
    await page.locator("#download-cooked").click();
    const download = await downloadPromise;
    const bytes = await readFile(await download.path());
    assert(bytes.subarray(0,4).toString() === "TGPT", "Not trainer file");
    const header = JSON.parse(bytes.subarray(12,12+bytes.readUInt32LE(8)).toString());
    assert(header.corpus.includes(batch), "Export lost training corpus");
    if (live) await download.saveAs("../artifacts/design/llm-kitchen/one-step-kitchen.tinygpt");
    const controls = await page.locator("#send-chat").boundingBox();
    const nav = await page.locator("#scene-controls").boundingBox();
    console.log({width, controls, nav});
    await page.screenshot({ path:`../artifacts/design/llm-kitchen/cooked-${width}.png` });
    assert(controls.y + controls.height <= (width === 390 ? 844 : 768), "Final generation below viewport");
    assert(nav.y + nav.height <= (width === 390 ? 844 : 768), "Final navigation below viewport");
    await page.screenshot({ path:`../artifacts/design/llm-kitchen/cooked-${width}.png` });
    await page.locator("#scene-back").click();
    await page.locator('[data-journey-link][href="#ingredients"]').click();
    await page.locator("[data-ingredient][value=weather]").check();
    await page.locator('[data-journey-link][href="#chat"]').click();
    assert((await page.locator("#chat-status").textContent()).includes("previous batch"), "Model misrepresented after ingredient change");
    if (!live) {
      await page.locator("#send-chat").click();
      await page.locator("#stop-chat").click();
      await page.waitForFunction(() => document.querySelector("#send-chat").disabled === false);
      assert(await page.locator("#download-cooked").isEnabled(), "Stop lost trained checkpoint");
    }
    await page.reload();
    assert(await page.locator("#send-chat").isDisabled(), "Reload silently restored invented model");
    report.results.push({ width, trainingMs:Date.now()-start, prompt, completion, checkpointBytes:bytes.length, viewport:true, messages });
    await context.close();
  }
  assert(!report.errors.length, report.errors.join("\n"));
} finally { await browser.close(); await writeFile(`../artifacts/design/llm-kitchen/cook-${live ? "real" : "ui"}.json`, JSON.stringify(report,null,2)); }
console.log(JSON.stringify(report,null,2));
