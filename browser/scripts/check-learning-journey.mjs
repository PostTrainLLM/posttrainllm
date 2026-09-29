// Bounded browser-local acceptance smoke for the inference learning workspace.
// Run against a built local preview. Uses isolated Chromium contexts and no real learner data.
import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = process.env.BASE_URL ?? "http://127.0.0.1:4173";
const browser = await chromium.launch();

try {
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));

  await page.goto(`${base}/learn`);
  await page
    .getByRole("link", { name: "Continue the inference sprint" })
    .click();
  assert.match(page.url(), /route=inference-systems-13w/);
  await page
    .locator("[data-current-title]")
    .getByText("From token IDs to next-token scores")
    .waitFor();
  assert.match(
    await page.locator("[data-current-lesson]").innerText(),
    /embedding table/,
  );
  assert.match(
    await page.locator("[data-current-starter]").innerText(),
    /NotImplementedError/,
  );
  assert.equal(await page.locator("#actual-work").inputValue(), "");
  assert.equal(
    (await page.locator("[data-learning-status]").textContent())?.trim(),
    "reading",
  );

  await page
    .locator("#diagnostic")
    .fill("x is input, w/b are parameters; y=7; axes batch and position");
  await page
    .locator("#prediction")
    .fill(
      "x [2,4,8], logits [2,4,32], probabilities [2,32], next_ids [2]; prefix cannot affect last",
    );
  await page
    .locator("#actual-work")
    .fill("Fixture shape and same-weight prefix comparison checked on CPU");
  await page
    .locator("#explanation")
    .fill(
      "Each position has only lookup and projection, so no path connects earlier IDs to the last output.",
    );
  const answerToggle = page.locator("[data-inference-answer] summary");
  await answerToggle.focus();
  await page.keyboard.press("Enter");
  assert.equal(
    await page
      .locator("[data-inference-answer]")
      .evaluate((element) => element.open),
    true,
  );
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Record immediate pass" }).click();
  await page.locator("[data-learning-status]").getByText("applied").waitFor();
  assert.match(
    await page.locator("[data-recall-region]").innerText(),
    /\+2 day recall/,
  );
  await page.getByRole("button", { name: "Continue to Week 1, Day 2" }).click();
  await page
    .locator("[data-current-title]")
    .getByText("Token bytes, tensor axes, and position")
    .waitFor();
  assert.equal(
    (await page.locator("[data-learning-status]").textContent())?.trim(),
    "reading",
  );
  await page.reload();
  await page
    .locator("[data-current-title]")
    .getByText("Token bytes, tensor axes, and position")
    .waitFor();
  await page.goBack();
  await page
    .locator("[data-current-title]")
    .getByText("Token bytes, tensor axes, and position")
    .waitFor();
  await page.goto(
    `${base}/learn/session?route=inference-systems-13w&session=inference-w01-d01`,
  );
  await page
    .locator("[data-current-title]")
    .getByText("From token IDs to next-token scores")
    .waitFor();
  assert.equal(
    await page.locator("#prediction").inputValue(),
    "x [2,4,8], logits [2,4,32], probabilities [2,32], next_ids [2]; prefix cannot affect last",
  );

  await page.getByRole("link", { name: "Ground-up foundations" }).click();
  await page
    .locator("[data-current-title]")
    .getByText("Functions, data, and parameters")
    .waitFor();
  await page.locator("#actual-work").fill("unfinished foundation draft");
  await page.getByRole("link", { name: "Inference sprint" }).click();
  await page
    .locator("[data-current-title]")
    .getByText("From token IDs to next-token scores")
    .waitFor();
  await page.getByRole("link", { name: "Ground-up foundations" }).click();
  await page
    .locator("[data-current-title]")
    .getByText("Functions, data, and parameters")
    .waitFor();
  assert.equal(
    await page.locator("#actual-work").inputValue(),
    "unfinished foundation draft",
  );
  await page.goto(
    `${base}/learn/session?route=ground-up&session=inference-w01-d01`,
  );
  await page
    .locator("[data-route-alert]")
    .getByText(/does not belong/)
    .waitFor();
  assert.equal(
    await page.locator("#actual-work").inputValue(),
    "unfinished foundation draft",
  );
  await page.goto(
    `${base}/learn/session?route=inference-systems-13w&session=inference-w01-d01`,
  );
  await page
    .locator("[data-current-title]")
    .getByText("From token IDs to next-token scores")
    .waitFor();
  await page.evaluate(async () => {
    const database = await new Promise((resolve, reject) => {
      const request = indexedDB.open("posttrainllm-learning", 1);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const state = await new Promise((resolve, reject) => {
      const transaction = database.transaction("workspace", "readonly");
      const request = transaction.objectStore("workspace").get("state");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    state.checkpoints[0].recalls[0].dueDate = "2020-01-01";
    await new Promise((resolve, reject) => {
      const transaction = database.transaction("workspace", "readwrite");
      transaction.objectStore("workspace").put(state, "state");
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    database.close();
  });
  await page.reload();
  const firstRecall = page.locator('[data-recall="plus-2"]');
  await firstRecall
    .locator("[data-recall-response]")
    .fill("I still confused the two axes");
  await firstRecall.getByRole("button", { name: "Needs repair" }).click();
  await firstRecall.getByText("repair retry").waitFor();
  assert.match(
    await page.locator("[data-repair-guidance]").innerText(),
    /Repair this gap/,
  );
  assert.match(
    await firstRecall.innerText(),
    /Previous answer: I still confused the two axes/,
  );
  await firstRecall
    .locator("[data-recall-response]")
    .fill(
      "For B=1,T=3,V=16,D=4 the lookup is [1,3,4], logits [1,3,16], and only same-position inputs reach the output.",
    );
  await firstRecall.getByRole("button", { name: "I can explain it" }).click();
  await page
    .locator("[data-history-region] details")
    .first()
    .locator("summary")
    .click();
  assert.match(
    await page.locator("[data-history-region]").innerText(),
    /I still confused the two axes/,
  );
  await page.locator(".planned-weeks summary").click();
  assert.match(
    await page.locator(".planned-week-grid").innerText(),
    /NVIDIA execution requires separately approved compatible hardware/,
  );
  assert.match(
    await page.locator(".planned-week-grid").innerText(),
    /Pass criterion:/,
  );
  await context.close();

  const noStorage = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  await noStorage.addInitScript(() =>
    Object.defineProperty(window, "indexedDB", { value: undefined }),
  );
  const narrow = await noStorage.newPage();
  await narrow.goto(
    `${base}/learn/session?route=inference-systems-13w&session=inference-w01-d01`,
  );
  await narrow
    .locator("[data-current-title]")
    .getByText("From token IDs to next-token scores")
    .waitFor();
  assert.match(
    await narrow.locator("[data-save-status]").innerText(),
    /unavailable/i,
  );
  assert.match(
    await narrow.locator("[data-current-lesson]").innerText(),
    /embedding table/,
  );
  const overflow = await narrow.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  assert.equal(
    overflow,
    false,
    "narrow viewport should not overflow horizontally",
  );
  await narrow.goto(
    `${base}/learn/session?route=inference-systems-13w&session=inference-w01-d02`,
  );
  await narrow
    .locator("[data-current-title]")
    .getByText("Token bytes, tensor axes, and position")
    .waitFor();
  assert.match(
    await narrow.locator("[data-current-lesson]").innerText(),
    /byte-v1/,
  );
  await noStorage.close();

  const older = await browser.newContext();
  const migrated = await older.newPage();
  await migrated.goto(`${base}/learn`);
  await migrated.evaluate(async () => {
    const database = await new Promise((resolve, reject) => {
      const request = indexedDB.open("posttrainllm-learning", 1);
      request.onupgradeneeded = () =>
        request.result.createObjectStore("workspace");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    await new Promise((resolve, reject) => {
      const transaction = database.transaction("workspace", "readwrite");
      transaction.objectStore("workspace").put(
        {
          schemaVersion: 1,
          updatedAt: "2026-09-19T10:00:00.000Z",
          currentModuleId: "functions-data-parameters",
          status: "reading",
          draft: {
            actualWork: "legacy unfinished work",
            explanation: "my words",
            repoConnection: "model.py",
            openQuestions: "",
          },
          checkpoints: [],
        },
        "state",
      );
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error);
    });
    database.close();
  });
  await migrated.goto(`${base}/learn/session`);
  await migrated
    .locator("[data-current-title]")
    .getByText("Functions, data, and parameters")
    .waitFor();
  assert.equal(
    await migrated.locator("#actual-work").inputValue(),
    "legacy unfinished work",
  );
  await migrated.goto(
    `${base}/learn/session?route=inference-systems-13w&session=inference-w01-d01`,
  );
  await migrated
    .locator("[data-current-title]")
    .getByText("From token IDs to next-token scores")
    .waitFor();
  await migrated.goto(
    `${base}/learn/session?route=ground-up&session=functions-data-parameters`,
  );
  await migrated
    .locator("[data-current-title]")
    .getByText("Functions, data, and parameters")
    .waitFor();
  assert.equal(
    await migrated.locator("#actual-work").inputValue(),
    "legacy unfinished work",
  );
  const legacyBackup = {
    kind: "posttrainllm-learning-backup",
    exportedAt: "2026-09-21T11:00:00.000Z",
    state: {
      schemaVersion: 1,
      updatedAt: "2026-09-21T11:00:00.000Z",
      currentModuleId: "functions-data-parameters",
      status: "applied",
      draft: {
        actualWork: "imported foundation work",
        explanation: "my imported explanation",
        repoConnection: "model.py",
        openQuestions: "",
      },
      checkpoints: [
        {
          id: "legacy-checkpoint-1",
          moduleId: "functions-data-parameters",
          createdAt: "2026-09-19T10:00:00.000Z",
          actualWork: "old completed work",
          explanation: "older own words",
          repoConnection: "model.py",
          immediateResult: "pass",
          openQuestions: "",
          recalls: [
            {
              id: "plus-2",
              dueDate: "2026-09-21",
              completedAt: "2026-09-21T10:00:00.000Z",
              prompt: "first old prompt",
              response: "first old recall",
              result: "pass",
            },
            {
              id: "plus-7",
              dueDate: "2026-09-26",
              completedAt: null,
              prompt: "second old prompt",
              response: "",
              result: "pending",
            },
          ],
        },
      ],
    },
  };
  await migrated.locator("#learning-import").setInputFiles({
    name: "newer.json",
    mimeType: "application/json",
    buffer: Buffer.from(
      JSON.stringify({
        ...legacyBackup,
        state: { ...legacyBackup.state, schemaVersion: 3 },
      }),
    ),
  });
  assert.match(
    await migrated.locator("[data-save-status]").innerText(),
    /unsupported/,
  );
  assert.equal(
    await migrated.locator("#actual-work").inputValue(),
    "legacy unfinished work",
  );
  await migrated.locator("#learning-import").setInputFiles({
    name: "legacy.json",
    mimeType: "application/json",
    buffer: Buffer.from(JSON.stringify(legacyBackup)),
  });
  await migrated
    .locator("[data-import-preview]")
    .getByText("Validated backup")
    .waitFor();
  await Promise.all([
    migrated.waitForEvent("download"),
    migrated.getByRole("button", { name: "Replace", exact: true }).click(),
  ]);
  assert.match(
    migrated.url(),
    /route=ground-up&session=functions-data-parameters/,
  );
  assert.equal(
    await migrated.locator("#actual-work").inputValue(),
    "imported foundation work",
  );
  await migrated
    .locator("[data-history-region] details")
    .first()
    .locator("summary")
    .click();
  assert.match(
    await migrated.locator("[data-history-region]").innerText(),
    /first old recall/,
  );
  await migrated.reload();
  await migrated
    .locator("[data-current-title]")
    .getByText("Functions, data, and parameters")
    .waitFor();
  assert.equal(
    await migrated.locator("#actual-work").inputValue(),
    "imported foundation work",
  );
  await older.close();
  assert.deepEqual(errors, []);
  console.log(
    "learning journey: fresh, resume, URL, draft, invalid route, recall repair, storage failure, narrow viewport, v1 migration and backup import passed",
  );
} finally {
  await browser.close();
}
