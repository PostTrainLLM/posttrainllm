#!/usr/bin/env node

/**
 * Verify every same-origin href in the production build, including fragments.
 * The check is intentionally dependency-free and runs after Astro, docs, and
 * agent surfaces have all been merged into `dist/`.
 */

import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, relative, sep } from "node:path";

const root = new URL("../", import.meta.url);
const dist = new URL("dist/", root);
const distPath = dist.pathname;

if (!existsSync(distPath)) {
  console.error(
    "built-link check: browser/dist is missing; run the build first",
  );
  process.exit(2);
}

function walk(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? walk(path) : [path];
  });
}

function pageRoute(file) {
  const path = `/${relative(distPath, file).split(sep).join("/")}`;
  if (path === "/index.html") return "/";
  if (path.endsWith("/index.html")) return path.slice(0, -"index.html".length);
  return path;
}

function decode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function resolveBuiltPath(pathname) {
  const decoded = decode(pathname).replace(/^\/+/, "");
  const candidates = decoded
    ? [join(distPath, decoded)]
    : [join(distPath, "index.html")];
  if (!extname(decoded)) {
    candidates.push(join(distPath, decoded, "index.html"));
    candidates.push(join(distPath, `${decoded}.html`));
  }
  return candidates.find(
    (candidate) => existsSync(candidate) && statSync(candidate).isFile(),
  );
}

function targetIds(file) {
  if (!file.endsWith(".html")) return new Set();
  const html = readFileSync(file, "utf8");
  return new Set(
    [...html.matchAll(/\s(?:id|name)=(?:"([^"]+)"|'([^']+)')/gu)].map(
      (match) => match[1] ?? match[2],
    ),
  );
}

const pages = walk(distPath).filter((file) => file.endsWith(".html"));
const idCache = new Map();
const failures = [];
let checkedLinks = 0;
let checkedFragments = 0;

const coreRoutes = [
  "/",
  "/experiments",
  "/recipes",
  "/learn",
  "/artifacts",
  "/docs/cli-reference",
];
for (const route of coreRoutes) {
  const page = resolveBuiltPath(route);
  if (!page) {
    failures.push(`${route}: core surface is missing`);
    continue;
  }
  const html = readFileSync(page, "utf8");
  const mainCount = [...html.matchAll(/<main(?:\s|>)/gu)].length;
  const h1Count = [...html.matchAll(/<h1(?:\s|>)/gu)].length;
  if (mainCount !== 1)
    failures.push(`${route}: expected one main, found ${mainCount}`);
  if (h1Count !== 1)
    failures.push(`${route}: expected one h1, found ${h1Count}`);
  if (!/<title>[^<]+<\/title>/u.test(html)) {
    failures.push(`${route}: missing a non-empty document title`);
  }
  if (!route.startsWith("/docs/") && !/href="#main"/u.test(html)) {
    failures.push(`${route}: missing skip-to-content link`);
  }
}

for (const page of pages) {
  const html = readFileSync(page, "utf8");
  const route = pageRoute(page);
  for (const match of html.matchAll(/\shref=(?:"([^"]*)"|'([^']*)')/gu)) {
    const raw = (match[1] ?? match[2]).replaceAll("&amp;", "&").trim();
    if (!raw || raw.startsWith("//")) continue;

    let url;
    try {
      url = new URL(raw, `https://posttrainllm.invalid${route}`);
    } catch {
      failures.push(`${route}: invalid href ${JSON.stringify(raw)}`);
      continue;
    }
    if (url.origin !== "https://posttrainllm.invalid") continue;

    checkedLinks += 1;
    const target = resolveBuiltPath(url.pathname);
    if (!target) {
      failures.push(`${route}: ${raw} has no built target`);
      continue;
    }
    if (!url.hash || !target.endsWith(".html")) continue;

    checkedFragments += 1;
    const fragment = decode(url.hash.slice(1));
    if (!idCache.has(target)) idCache.set(target, targetIds(target));
    if (!idCache.get(target).has(fragment)) {
      failures.push(`${route}: ${raw} has no matching fragment target`);
    }
  }
}

if (failures.length) {
  for (const failure of failures) console.error(`BROKEN LINK: ${failure}`);
  console.error(`built-link check failed: ${failures.length} broken links`);
  process.exit(1);
}

console.log(
  `built-link check ok: ${pages.length} HTML pages, ${coreRoutes.length} core landmark audits, ${checkedLinks} internal links, ${checkedFragments} fragments`,
);
