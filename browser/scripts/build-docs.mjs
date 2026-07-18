// build-docs.mjs — post-build step for the browser site's /docs surface.
//
// posttrainllm.com/docs is served by the Blume docs project in ../docs-site,
// which reads the single canonical docs tree at repo-root docs/ and emits a
// static site with base '/docs' (see docs-site/blume.config.ts). There is no
// competing renderer inside this Astro app anymore.
//
// This script:
//   1. Builds the Blume project in ../docs-site (produces docs-site/dist/*
//      with every asset already prefixed by /docs/).
//   2. Copies that output into browser/dist/docs/ so the merged Cloudflare
//      Pages deploy serves the Astro app at / and the Blume docs at /docs.
//
// It MUST run AFTER `astro build`, otherwise it would be clobbered when Astro
// wipes dist/. The npm build script wires it after `astro build`.

import { spawnSync } from "node:child_process";
import { promises as fs } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const BROWSER_ROOT = resolve(here, "..");
const DOCS_SITE_DIR = resolve(BROWSER_ROOT, "..", "docs-site");
const DOCS_SITE_DIST = resolve(DOCS_SITE_DIR, "dist");
const DEST_DIR = resolve(BROWSER_ROOT, "dist", "docs");

// 1. Build the Blume docs project.
console.log("build-docs.mjs: building Blume docs in ../docs-site …");
const pnpmCmd = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
const build = spawnSync(pnpmCmd, ["run", "build"], {
  cwd: DOCS_SITE_DIR,
  stdio: "inherit",
});
if (build.status !== 0) {
  console.error(
    `build-docs.mjs: docs-site build failed (exit ${build.status ?? "signal"}).`,
  );
  process.exit(build.status ?? 1);
}

// 2. Copy docs-site/dist/* → browser/dist/docs/.
try {
  await fs.access(DOCS_SITE_DIST);
} catch {
  console.error(
    `build-docs.mjs: expected ${DOCS_SITE_DIST} to exist after the docs build.`,
  );
  process.exit(1);
}

// Wipe any stale docs output so removed pages don't linger.
await fs.rm(DEST_DIR, { recursive: true, force: true });
await fs.mkdir(DEST_DIR, { recursive: true });
await fs.cp(DOCS_SITE_DIST, DEST_DIR, { recursive: true });

console.log(`build-docs.mjs: copied docs-site/dist → dist/docs/`);
