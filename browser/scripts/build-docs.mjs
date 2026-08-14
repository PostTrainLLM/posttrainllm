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
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const BROWSER_ROOT = resolve(here, "..");
const DOCS_SITE_DIR = resolve(BROWSER_ROOT, "..", "docs-site");
const DOCS_SITE_DIST = resolve(DOCS_SITE_DIR, "dist");
const DEST_DIR = resolve(BROWSER_ROOT, "dist", "docs");
const ORIGIN = "https://posttrainllm.com";

async function findHtmlFiles(directory) {
  const entries = await fs.readdir(directory, { withFileTypes: true });
  const paths = await Promise.all(
    entries.map(async (entry) => {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) return findHtmlFiles(path);
      return entry.isFile() && entry.name === "index.html" ? [path] : [];
    }),
  );
  return paths.flat();
}

async function alignCanonicalUrls() {
  const htmlFiles = await findHtmlFiles(DEST_DIR);
  for (const path of htmlFiles) {
    const outputPath = relative(DEST_DIR, path).replaceAll("\\", "/");
    const route =
      outputPath === "index.html"
        ? ""
        : outputPath.slice(0, -"index.html".length);
    const canonicalUrl = `${ORIGIN}/docs/${route}`;
    const html = await fs.readFile(path, "utf8");
    const canonicalTag = html.match(
      /<link\b(?=[^>]*\brel=["']canonical["'])[^>]*>/iu,
    )?.[0];
    const currentCanonical = canonicalTag?.match(
      /\bhref=["']([^"']+)["']/iu,
    )?.[1];
    if (!currentCanonical) {
      throw new Error(`missing canonical URL in ${outputPath}`);
    }
    if (currentCanonical !== canonicalUrl) {
      await fs.writeFile(
        path,
        html.replaceAll(currentCanonical, canonicalUrl),
        "utf8",
      );
    }
  }
  return htmlFiles.length;
}

// 1. Install and build the standalone Blume project. It is intentionally not
// part of the browser workspace, so CI must install its own frozen lockfile.
const pnpmCmd = process.platform === "win32" ? "pnpm.cmd" : "pnpm";
console.log("build-docs.mjs: installing docs-site dependencies …");
const install = spawnSync(pnpmCmd, ["install", "--frozen-lockfile"], {
  cwd: DOCS_SITE_DIR,
  stdio: "inherit",
});
if (install.status !== 0) {
  console.error(
    `build-docs.mjs: docs-site install failed (exit ${install.status ?? "signal"}).`,
  );
  process.exit(install.status ?? 1);
}

console.log("build-docs.mjs: building Blume docs in ../docs-site …");
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
const canonicalCount = await alignCanonicalUrls();

console.log(
  `build-docs.mjs: copied docs-site/dist → dist/docs/ and aligned ${canonicalCount} canonicals`,
);
