/** Real COOP/COEP pthread bootstrap regression; no valid model or inference. */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { build } from "astro";
import { chromium } from "playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cache = join(root, "node_modules", ".cache");
await mkdir(cache, { recursive: true });
const work = await mkdtemp(join(cache, "ort-bootstrap-"));
const pages = join(work, "src", "pages");
await mkdir(pages, { recursive: true });
await writeFile(
  join(pages, "index.astro"),
  `<!doctype html><title>Runtime initialization check</title><script>
const worker = new Worker(new URL('./probe-worker.ts', import.meta.url), {type: 'module'});
worker.onmessage = event => { window.__ortProbe = event.data; worker.terminate(); };
worker.onerror = event => { window.__ortProbe = {error:event.message}; worker.terminate(); };
worker.postMessage({});
</script>`,
);
await writeFile(
  join(pages, "probe-worker.ts"),
  `import {ort} from ${JSON.stringify(join(root, "src/specialists/browser-ort.ts"))};
self.onmessage = async () => {
  try {
    await ort.InferenceSession.create(new Uint8Array([0]), {executionProviders:['wasm']});
    self.postMessage({error:'Invalid model unexpectedly accepted'});
  } catch(error) {
    self.postMessage({error:String(error), isolated:crossOriginIsolated, threads:ort.env.wasm.numThreads});
  }
};`,
);
const dist = join(work, "dist");
await build({
  root: pathToFileURL(root + "/"),
  configFile: false,
  publicDir: join(work, "public"),
  cacheDir: join(work, "cache"),
  srcDir: join(work, "src"),
  outDir: dist,
  logLevel: "error",
});
const requests = [];
const server = createServer(async (request, response) => {
  const pathname = new URL(request.url, "http://localhost").pathname;
  requests.push(pathname);
  response.setHeader("Cross-Origin-Opener-Policy", "same-origin");
  response.setHeader("Cross-Origin-Embedder-Policy", "require-corp");
  response.setHeader("Cross-Origin-Resource-Policy", "same-origin");
  const file = resolve(
    dist,
    "." + (pathname === "/" ? "/index.html" : pathname),
  );
  if (!file.startsWith(dist + "/")) return response.writeHead(404).end();
  try {
    response.setHeader(
      "Content-Type",
      {
        ".html": "text/html",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".wasm": "application/wasm",
      }[extname(file)] ?? "application/octet-stream",
    );
    response.end(await readFile(file));
  } catch {
    response.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
let browser;
try {
  browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHANNEL
      ? { channel: process.env.PLAYWRIGHT_CHANNEL }
      : {}),
  });
  const page = await browser.newPage();
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.waitForFunction(() => window.__ortProbe, null, { timeout: 15000 });
  const result = await page.evaluate(() => window.__ortProbe);
  assert.equal(result.isolated, true);
  assert.equal(result.threads, 2);
  // A protobuf error proves runtime initialization and session admission
  // completed. No valid model was loaded, and no inference is requested.
  assert.match(result.error, /protobuf/i);
  const helpers = requests.filter((path) =>
    /ort-wasm-simd-threaded.*\.mjs$/.test(path),
  );
  assert(helpers.length >= 2, "The standalone glue must serve the pthread too");
  assert.equal(new Set(helpers).size, 1);
  console.log(
    JSON.stringify({
      result,
      helper_requests: helpers,
      model_loaded: false,
      inference_run: false,
    }),
  );
} finally {
  await browser?.close();
  await new Promise((resolve) => server.close(resolve));
}
