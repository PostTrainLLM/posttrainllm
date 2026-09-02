// measure_webgpu_paired.mjs — Issue #138's fail-closed hardware receipt.
//
// Runs the same browser preset, corpus, seed, and step count in ABBA order.
// The receipt is written even on failure. Software/fallback/unknown adapters
// are rejected before training so a SwiftShader result cannot become evidence.

import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import { dirname, resolve } from "node:path";
import process from "node:process";
import { chromium } from "playwright";

function parseArgs(argv) {
  const options = {
    baseUrl: "http://127.0.0.1:4173",
    output: "../runs/verified-wins/webgpu-paired-hardware-v1/receipt.json",
    preset: "large",
    seed: 42,
    steps: 20,
    sourceRevision: null,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const name = argv[index];
    if (name === "--") continue;
    const value = argv[index + 1];
    if (name === "--base-url") options.baseUrl = value;
    else if (name === "--output") options.output = value;
    else if (name === "--preset") options.preset = value;
    else if (name === "--seed") options.seed = Number(value);
    else if (name === "--steps") options.steps = Number(value);
    else if (name === "--source-revision") options.sourceRevision = value;
    else throw new Error(`unknown argument: ${name}`);
    index += 1;
  }
  if (!Number.isInteger(options.seed))
    throw new Error("--seed must be an integer");
  if (options.seed !== 42) {
    throw new Error(
      "--seed must be 42 because the Playground uses pinned DEFAULT_CONFIG.seed",
    );
  }
  if (
    !Number.isInteger(options.steps) ||
    options.steps < 1 ||
    options.steps > 200
  ) {
    throw new Error("--steps must be an integer from 1 through 200");
  }
  if (!options.sourceRevision) throw new Error("--source-revision is required");
  return options;
}

function median(values) {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2
    ? sorted[middle]
    : (sorted[middle - 1] + sorted[middle]) / 2;
}

function relativeDrift(left, right) {
  return Math.abs(left - right) / Math.max(Math.abs(left), 1e-9);
}

async function sha256(path) {
  return createHash("sha256")
    .update(await readFile(path))
    .digest("hex");
}

async function inspectAdapter(page) {
  return page.evaluate(async () => {
    if (!navigator.gpu)
      return { accepted: false, reason: "navigator.gpu unavailable" };
    const adapter = await navigator.gpu.requestAdapter();
    if (!adapter)
      return { accepted: false, reason: "requestAdapter returned null" };
    let info = adapter.info;
    if (!info && typeof adapter.requestAdapterInfo === "function") {
      info = await adapter.requestAdapterInfo();
    }
    const normalized = {
      vendor: info?.vendor ?? "",
      architecture: info?.architecture ?? "",
      device: info?.device ?? "",
      description: info?.description ?? "",
    };
    const text = Object.values(normalized).join(" ").toLowerCase();
    const fallback = adapter.isFallbackAdapter === true;
    const software =
      /swiftshader|llvmpipe|lavapipe|software|software rasterizer/.test(text);
    const appleHardware =
      /apple/.test(normalized.vendor.toLowerCase()) ||
      /metal/.test(normalized.architecture.toLowerCase());
    const accepted =
      Boolean(text.trim()) && appleHardware && !fallback && !software;
    return {
      accepted,
      reason: accepted
        ? "identified Apple hardware adapter"
        : "adapter is fallback, software, unknown, or not Apple hardware",
      fallback,
      software,
      info: normalized,
      features: [...adapter.features].sort(),
      limits: {
        maxBufferSize: adapter.limits.maxBufferSize,
        maxComputeWorkgroupSizeX: adapter.limits.maxComputeWorkgroupSizeX,
        maxStorageBufferBindingSize: adapter.limits.maxStorageBufferBindingSize,
      },
    };
  });
}

async function runArm(context, options, backend, sequenceIndex) {
  const page = await context.newPage();
  const errors = [];
  let timingStarted = false;
  page.on("pageerror", (error) => {
    if (timingStarted) errors.push(`pageerror: ${error.message}`);
  });
  page.on("console", (message) => {
    if (timingStarted && message.type() === "error") {
      errors.push(`console.error: ${message.text()}`);
    }
  });
  page.on("dialog", (dialog) => dialog.accept().catch(() => {}));

  try {
    await page.goto(new URL("/playground", options.baseUrl).href, {
      waitUntil: "networkidle",
    });
    await page
      .locator("#welcomeSkip")
      .click({ timeout: 1500 })
      .catch(() => {});
    await page.locator("#sizePreset").selectOption(options.preset);
    const configured = await page.evaluate(
      ({ selectedBackend, selectedSeed, selectedSteps }) => {
        const setValue = (id, value) => {
          const element = document.getElementById(id);
          if (!element) throw new Error(`missing control #${id}`);
          element.value = String(value);
          element.dispatchEvent(new Event("input", { bubbles: true }));
          element.dispatchEvent(new Event("change", { bubbles: true }));
        };
        setValue("maxSteps", selectedSteps);
        const seedControl = document.getElementById("seed");
        if (seedControl) setValue("seed", selectedSeed);
        setValue("backend", selectedBackend);
        document.getElementById("backend").dataset.userPicked = "1";
        return {
          preset: document.getElementById("sizePreset").value,
          layers: Number(document.getElementById("layers").value),
          dModel: Number(document.getElementById("dModel").value),
          ctx: Number(document.getElementById("ctx").value),
          batchSize: Number(document.getElementById("batchSize").value),
          steps: Number(document.getElementById("maxSteps").value),
          seed: selectedSeed,
          seedSource: seedControl
            ? "rendered-control"
            : "pinned-default-config",
          backend: document.getElementById("backend").value,
          corpusCharacters: document.getElementById("corpus").value.length,
        };
      },
      {
        selectedBackend: backend,
        selectedSeed: options.seed,
        selectedSteps: options.steps,
      },
    );
    const mismatches = [
      configured.preset !== options.preset && "preset",
      configured.steps !== options.steps && "steps",
      configured.seed !== options.seed && "seed",
      configured.backend !== backend && "backend",
    ].filter(Boolean);
    if (mismatches.length)
      throw new Error(`configuration mismatch: ${mismatches.join(", ")}`);

    timingStarted = true;
    const startedAt = performance.now();
    await page.locator("#start").click({ force: true });
    const outcome = await page
      .waitForFunction(
        (target) => {
          const stepText = document.getElementById("stStep")?.textContent ?? "";
          const status = document.getElementById("status")?.textContent ?? "";
          const match = stepText.match(/^(\d+)\s*\/\s*(\d+)/);
          if (match && Number(match[1]) >= target) return { ok: true, status };
          if (/error|failed|device lost|non-finite/i.test(status))
            return { ok: false, status };
          return false;
        },
        options.steps,
        { timeout: 300_000, polling: 100 },
      )
      .then((handle) => handle.jsonValue())
      .catch((error) => ({ ok: false, status: error.message }));
    const elapsedMs = performance.now() - startedAt;
    const observed = await page.evaluate(() => ({
      step: document.getElementById("stStep")?.textContent ?? "",
      loss: Number.parseFloat(
        document.getElementById("stTrain")?.textContent ?? "NaN",
      ),
      tokensPerSecond: Number(
        (document.getElementById("stToks")?.textContent ?? "0").replaceAll(
          ",",
          "",
        ),
      ),
      backend: document.getElementById("stBackend")?.textContent ?? "",
      status: document.getElementById("status")?.textContent ?? "",
    }));
    const finite =
      Number.isFinite(observed.loss) &&
      Number.isFinite(observed.tokensPerSecond);
    return {
      sequenceIndex,
      backend,
      configured,
      ok: outcome.ok && finite && errors.length === 0,
      elapsedMs,
      msPerStep: elapsedMs / options.steps,
      finalLoss: observed.loss,
      displayedTokensPerSecond: observed.tokensPerSecond,
      observed,
      errors,
      failure:
        outcome.ok && finite ? null : outcome.status || "non-finite metric",
    };
  } finally {
    await page.close();
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const repoRoot = resolve(import.meta.dirname, "..");
  const output = resolve(import.meta.dirname, options.output);
  const sequence = ["wasm", "webgpu", "webgpu", "wasm"];
  const receipt = {
    schema_version: "posttrainllm.webgpu-paired-receipt.v1",
    manifest: "evals/verified-wins/webgpu-v1.json",
    manifest_id: "webgpu-paired-hardware-v1",
    source_revision: options.sourceRevision,
    started_at: new Date().toISOString(),
    command: process.argv.join(" "),
    environment: {
      platform: process.platform,
      architecture: process.arch,
      os_release: os.release(),
      cpu: os.cpus()[0]?.model ?? "unknown",
      logical_cpus: os.cpus().length,
      total_memory_bytes: os.totalmem(),
    },
    inputs: {
      preset: options.preset,
      steps: options.steps,
      seed: options.seed,
      sequence,
      sizing_sha256: await sha256(resolve(repoRoot, "browser/src/sizing.ts")),
      default_config_sha256: await sha256(
        resolve(repoRoot, "browser/src/types.ts"),
      ),
      corpus_sha256: await sha256(
        resolve(repoRoot, "browser/public/shakespeare.txt"),
      ),
    },
    adapter: null,
    browser: null,
    user_agent: null,
    runs: [],
    summary: null,
    decision: "reject",
  };

  const browser = await chromium.launch({
    headless: false,
    args: [
      "--enable-unsafe-webgpu",
      "--enable-features=Vulkan",
      "--use-vulkan",
    ],
  });
  try {
    receipt.browser = await browser.version();
    const context = await browser.newContext({
      viewport: { width: 1400, height: 900 },
    });
    const probePage = await context.newPage();
    await probePage.goto(options.baseUrl, { waitUntil: "networkidle" });
    receipt.user_agent = await probePage.evaluate(() => navigator.userAgent);
    receipt.adapter = await inspectAdapter(probePage);
    await probePage.close();
    if (!receipt.adapter.accepted) throw new Error(receipt.adapter.reason);

    for (let index = 0; index < sequence.length; index += 1) {
      const backend = sequence[index];
      console.log(`[${index + 1}/${sequence.length}] ${backend}`);
      const run = await runArm(context, options, backend, index + 1);
      receipt.runs.push(run);
      console.log(
        `  ${run.ok ? "ok" : "failed"}: ${run.msPerStep.toFixed(1)} ms/step, loss=${run.finalLoss}`,
      );
      if (!run.ok) throw new Error(`${backend} run ${index + 1} failed`);
    }

    const wasmRuns = receipt.runs.filter((run) => run.backend === "wasm");
    const gpuRuns = receipt.runs.filter((run) => run.backend === "webgpu");
    const wasmMedianMs = median(wasmRuns.map((run) => run.msPerStep));
    const webgpuMedianMs = median(gpuRuns.map((run) => run.msPerStep));
    const medianSpeedup = wasmMedianMs / webgpuMedianMs;
    const pairDrifts = [
      relativeDrift(receipt.runs[0].finalLoss, receipt.runs[1].finalLoss),
      relativeDrift(receipt.runs[3].finalLoss, receipt.runs[2].finalLoss),
    ];
    const summary = {
      wasm_median_ms_per_step: wasmMedianMs,
      webgpu_median_ms_per_step: webgpuMedianMs,
      median_speedup: medianSpeedup,
      paired_final_loss_relative_drifts: pairDrifts,
      maximum_final_loss_relative_drift: Math.max(...pairDrifts),
      gates: {
        hardware_adapter: receipt.adapter.accepted,
        median_speedup_above_1_25: medianSpeedup > 1.25,
        every_loss_drift_below_0_05: pairDrifts.every((value) => value < 0.05),
        zero_runtime_errors: receipt.runs.every(
          (run) => run.errors.length === 0,
        ),
      },
    };
    receipt.summary = summary;
    receipt.decision = Object.values(summary.gates).every(Boolean)
      ? "promote"
      : "reject";
  } catch (error) {
    receipt.failure = error instanceof Error ? error.message : String(error);
  } finally {
    receipt.completed_at = new Date().toISOString();
    await browser.close();
    await mkdir(dirname(output), { recursive: true });
    await writeFile(output, `${JSON.stringify(receipt, null, 2)}\n`, "utf-8");
    console.log(`receipt: ${output}`);
    console.log(`decision: ${receipt.decision}`);
  }
  return receipt.decision === "promote" ? 0 : 1;
}

process.exitCode = await main();
