// Open the kitchen checkpoint in a fresh Web Lab session, without training.
import { chromium } from "playwright";
import { writeFile } from "node:fs/promises";
const browser = await chromium.launch({headless:true,args:["--disable-webgpu"]});
const report = {errors:[], restored:false};
try {
  const page = await browser.newPage();
  page.on("pageerror",e => report.errors.push(e.message));
  await page.addInitScript(() => {
    const Real = window.Worker;
    window.Worker = class {
      constructor(url, options) {
        const worker = new Real(url, options);
        const post = worker.postMessage.bind(worker);
        worker.postMessage = (m, ...args) => { if (m.type === "continue") m.extraSteps = 1; post(m, ...args); };
        return worker;
      }
    };
  });
  await page.goto("http://127.0.0.1:4173/playground");
  if (await page.locator("#welcome").isVisible()) await page.locator("#welcomeSkip").click();
  await page.locator("#uploadModel").setInputFiles("../artifacts/design/llm-kitchen/one-step-kitchen.tinygpt");
  await page.waitForFunction(() => document.querySelector("#sample").disabled === false, {timeout:15000});
  report.status = await page.locator("#modelStatus").textContent();
  report.corpus = (await page.locator("#corpus").inputValue()).slice(0,150);
  if (!(report.status.includes("loaded") || report.status.includes("restored"))) throw new Error(report.status);
  report.restored = true;
  if (await page.locator("#welcome").isVisible()) await page.locator("#welcomeSkip").click();
  await page.locator("#modelMenuBtn").click();
  await page.locator("#continueBtn").click();
  await page.waitForFunction(() => document.querySelector("#stStep").textContent.includes("2") && document.querySelector("#sample").disabled === false, {timeout:10000});
  report.continuedOneStep = await page.locator("#stStep").textContent();
  if (report.errors.length) throw new Error(report.errors.join("\n"));
} finally { await browser.close(); await writeFile("../artifacts/design/llm-kitchen/export-reopen.json",JSON.stringify(report,null,2)); }
console.log(JSON.stringify(report,null,2));
