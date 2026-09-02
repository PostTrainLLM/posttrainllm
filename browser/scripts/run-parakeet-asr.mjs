#!/usr/bin/env node
// Run the official FluidInference Parakeet v3 browser engine on a frozen local fixture.

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import { chromium } from "playwright";

const SOFTWARE_ADAPTER =
  /swiftshader|llvmpipe|lavapipe|software|software rasterizer/i;

function parseArgs(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || value === undefined) {
      throw new Error(`invalid argument near ${key ?? "end of command"}`);
    }
    values[key.slice(2)] = value;
  }
  for (const required of [
    "base-url",
    "fixture",
    "audio-dir",
    "output",
    "source-revision",
    "source-root",
    "weights-revision",
    "vocab-revision",
  ]) {
    if (!values[required]) throw new Error(`--${required} is required`);
  }
  return values;
}

function mulberry32(seed) {
  return () => {
    let value = (seed += 0x6d2b79f5);
    value = Math.imul(value ^ (value >>> 15), value | 1);
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61);
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffled(items, seed) {
  const result = [...items];
  const random = mulberry32(seed);
  for (let index = result.length - 1; index > 0; index -= 1) {
    const swap = Math.floor(random() * (index + 1));
    [result[index], result[swap]] = [result[swap], result[index]];
  }
  return result;
}

async function sha256(file) {
  return createHash("sha256")
    .update(await readFile(file))
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
    return {
      fallback: adapter.isFallbackAdapter === true,
      info: {
        vendor: info?.vendor ?? "",
        architecture: info?.architecture ?? "",
        device: info?.device ?? "",
        description: info?.description ?? "",
      },
      features: [...adapter.features].sort(),
    };
  });
}

async function loadFixture(options) {
  const fixturePath = path.resolve(options.fixture);
  const audioDir = path.resolve(options["audio-dir"]);
  const sourceRoot = path.resolve(options["source-root"]);
  const observedSourceRevision = execFileSync(
    "git",
    ["-C", sourceRoot, "rev-parse", "HEAD"],
    { encoding: "utf8" },
  ).trim();
  if (observedSourceRevision !== options["source-revision"]) {
    throw new Error(
      `upstream source revision mismatch: ${observedSourceRevision}`,
    );
  }
  const fixture = JSON.parse(await readFile(fixturePath, "utf8"));
  const seed = fixture.execution_seed ?? 13802;
  const items = shuffled(fixture.items, seed);
  const audio = new Map();
  for (const item of items) {
    const file = path.join(audioDir, `${item.id}.flac`);
    const digest = await sha256(file);
    if (digest !== item.audio_sha256) {
      throw new Error(`${item.id}: audio SHA-256 mismatch`);
    }
    audio.set(item.id, await readFile(file));
  }
  return { fixture, seed, items, audio };
}

async function setupPage(browser, baseUrl, audio, telemetry) {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
  });
  const page = await context.newPage();
  page.on("console", (message) =>
    telemetry.consoleMessages.push({
      type: message.type(),
      text: message.text(),
    }),
  );
  page.on("pageerror", (error) => telemetry.pageErrors.push(error.message));
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (
      ["warmup", "timed"].includes(telemetry.phase) &&
      url.origin !== baseUrl.origin
    ) {
      telemetry.externalWarmRequests.push({
        phase: telemetry.phase,
        url: request.url(),
      });
    }
  });
  page.on("response", (response) => {
    const url = response.url();
    if (telemetry.phase !== "load" || !url.includes("huggingface.co")) return;
    const headers = response.headers();
    telemetry.modelResponses.push({
      url,
      status: response.status(),
      content_length: Number(headers["content-length"] ?? 0),
      etag: headers.etag ?? "",
      repo_commit: headers["x-repo-commit"] ?? "",
    });
  });
  await page.route(baseUrl.href, (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!doctype html><meta charset=utf-8><title>Parakeet benchmark</title>",
    }),
  );
  await page.route(`${baseUrl.origin}/__fixture/**`, async (route) => {
    const id = path.basename(new URL(route.request().url()).pathname, ".flac");
    const body = audio.get(id);
    if (!body) return route.abort("failed");
    await route.fulfill({ status: 200, contentType: "audio/flac", body });
  });
  await page.goto(baseUrl.href, { waitUntil: "networkidle" });
  return page;
}

async function qualifyAdapter(page) {
  const adapter = await inspectAdapter(page);
  const adapterText = Object.values(adapter.info).join(" ");
  const appleHardware = /apple|metal/i.test(adapterText);
  adapter.software = SOFTWARE_ADAPTER.test(adapterText);
  adapter.accepted =
    Boolean(adapterText.trim()) &&
    appleHardware &&
    !adapter.fallback &&
    !adapter.software;
  adapter.reason = adapter.accepted
    ? "identified Apple hardware adapter"
    : "adapter is fallback, software, unknown, or not Apple hardware";
  if (!adapter.accepted) throw new Error(adapter.reason);
  return adapter;
}

async function loadEngine(page, options, modelResponses) {
  const load = await page.evaluate(async () => {
    const { ParakeetV3Engine } =
      await import("/src/engines/asr-parakeet/index.ts");
    const engine = new ParakeetV3Engine();
    const progress = {};
    await engine.load((event) => {
      const prior = progress[event.file];
      if (!prior || event.loaded >= prior.loaded) progress[event.file] = event;
    });
    globalThis.__posttrainllmParakeet = engine;
    globalThis.__posttrainllmProgress = progress;
    return progress;
  });
  const downloadBytes = Object.entries(load)
    .filter(([file]) => file !== "FluidInference/fluidaudio-web")
    .reduce((sum, [, progress]) => sum + Number(progress.loaded), 0);
  if (downloadBytes > 1 << 30) {
    throw new Error(`model download exceeded 1 GiB: ${downloadBytes}`);
  }
  for (const revision of [
    options["weights-revision"],
    options["vocab-revision"],
  ]) {
    const observed = modelResponses.some(
      (response) =>
        response.repo_commit === revision || response.url.includes(revision),
    );
    if (!observed)
      throw new Error(`model response did not verify revision ${revision}`);
  }
  return downloadBytes;
}

async function runItem(page, item) {
  return page.evaluate(async (selected) => {
    const { decodeToMono16k } = await import("/src/core/audio.ts");
    const response = await fetch(`/__fixture/${selected.id}.flac`);
    if (!response.ok)
      throw new Error(`fixture fetch failed: ${response.status}`);
    const decoded = await decodeToMono16k(await response.arrayBuffer());
    const started = performance.now();
    const result = await globalThis.__posttrainllmParakeet.transcribe(decoded);
    return {
      id: selected.id,
      text: result.text,
      audio_seconds: decoded.samples.length / decoded.sampleRate,
      decode_ms: performance.now() - started,
      engine_metrics: result.metrics ?? null,
    };
  }, item);
}

async function runBrowserExperiment(options, input, browser) {
  const baseUrl = new URL(options["base-url"]);
  const telemetry = {
    phase: "setup",
    consoleMessages: [],
    pageErrors: [],
    externalWarmRequests: [],
    modelResponses: [],
  };
  const page = await setupPage(browser, baseUrl, input.audio, telemetry);
  const adapter = await qualifyAdapter(page);
  telemetry.phase = "load";
  const downloadBytes = await loadEngine(
    page,
    options,
    telemetry.modelResponses,
  );
  telemetry.phase = "warmup";
  const warmup = await runItem(page, input.items[0]);
  telemetry.phase = "timed";
  const transcripts = [];
  for (const item of input.items) transcripts.push(await runItem(page, item));
  telemetry.phase = "dispose";
  await page.evaluate(async () => {
    await globalThis.__posttrainllmParakeet.dispose();
    delete globalThis.__posttrainllmParakeet;
  });
  const receipt = {
    schema_version: "posttrainllm.asr-predictions.v1",
    fixture_id: input.fixture.fixture_id,
    model_id: "fluidinference-parakeet-tdt-0.6b-v3-browser",
    model_revision: `source=${options["source-revision"]}; weights=${options["weights-revision"]}; vocab=${options["vocab-revision"]}`,
    browser: await browser.version(),
    user_agent: await page.evaluate(() => navigator.userAgent),
    adapter,
    execution_seed: input.seed,
    execution_order: input.items.map((item) => item.id),
    model_download_bytes: downloadBytes,
    model_responses: telemetry.modelResponses,
    external_warm_requests: telemetry.externalWarmRequests,
    warmup,
    transcripts,
    console_messages: telemetry.consoleMessages,
    page_errors: telemetry.pageErrors,
  };
  if (telemetry.externalWarmRequests.length) {
    throw new Error(
      `${telemetry.externalWarmRequests.length} external request(s) during warm decode`,
    );
  }
  if (telemetry.pageErrors.length) {
    throw new Error(`${telemetry.pageErrors.length} page error(s) during run`);
  }
  return receipt;
}

async function main() {
  const options = parseArgs(process.argv.slice(2));
  const input = await loadFixture(options);
  const browser = await chromium.launch({
    headless: false,
    args: [
      "--enable-unsafe-webgpu",
      "--enable-features=Vulkan",
      "--use-vulkan",
    ],
  });
  try {
    const receipt = await runBrowserExperiment(options, input, browser);
    await writeFile(options.output, `${JSON.stringify(receipt, null, 2)}\n`);
    console.log(JSON.stringify(receipt, null, 2));
  } finally {
    await browser.close();
  }
}

await main();
