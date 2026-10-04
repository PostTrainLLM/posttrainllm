import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";
import { execFileSync, spawn } from "node:child_process";
import { setTimeout as delay } from "node:timers/promises";
import { prerenderOptOut } from "./prerender-check.mjs";
import { packageAndLockFailure } from "./package-lock-guard.mjs";

const requireFromBrowser = createRequire(path.resolve("browser/package.json"));
const ts = requireFromBrowser("typescript");

export const TEMPORARY_ADVISORY = Object.freeze({
  id: "1240991",
  ghsa: "GHSA-ch52-4w7c-c8xp",
  moduleName: "http-cache-semantics",
  vulnerableVersion: "4.2.0",
  expiresAt: "2026-10-18T00:00:00.000Z",
});

const MARKERS = [
  "http-cache-semantics",
  "CachePolicy",
  "cachePolicy",
  "max-stale",
  "sharedUserCache",
];
const BUILD_INPUTS = [
  "browser/astro.config.mjs",
  "browser/functions",
  "browser/package.json",
  "browser/public",
  "browser/scripts/build-agent-surfaces.mjs",
  "browser/scripts/build-docs.mjs",
  "browser/src",
  "docs",
  "docs-site/blume.config.ts",
  "docs-site/package.json",
  "docs-site/theme.css",
  "pnpm-lock.yaml",
  "pnpm-workspace.yaml",
];
// Wrangler discovers Functions from browser/functions during deploy. Pin the
// complete known directory (including its colocated test source) fail-closed.
const PAGES_FUNCTION_SHA256 = new Map([
  [
    "browser/functions/_middleware.ts",
    "0564433dd6b3c729f7925a23ad51507c70a50ad8fa89571127e61756b4c2060e",
  ],
  [
    "browser/functions/_middleware.test.ts",
    "297573986933db23dbab6f4639eab02af94cd95076f098eba57f01013d9d9805",
  ],
]);
const MAX_EVIDENCE_AGE_MS = 6 * 60 * 60 * 1000;

function configFindings(text, fileName) {
  const findings = [];
  const source = ts.createSourceFile(
    fileName,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.JS,
  );
  if (source.parseDiagnostics.length) return ["Astro config failed to parse"];
  const isAdapterOrUnknownIntegration = (specifier) =>
    /adapter/i.test(specifier) ||
    (specifier.startsWith("@astrojs/") &&
      !new Set(["@astrojs/mdx", "@astrojs/sitemap"]).has(specifier));
  const visitAdapter = (node) => {
    const imported =
      ts.isImportDeclaration(node) &&
      ts.isStringLiteral(node.moduleSpecifier) &&
      isAdapterOrUnknownIntegration(node.moduleSpecifier.text);
    const dynamic =
      ts.isCallExpression(node) &&
      node.expression.kind === ts.SyntaxKind.ImportKeyword &&
      node.arguments[0] &&
      ts.isStringLiteral(node.arguments[0]) &&
      isAdapterOrUnknownIntegration(node.arguments[0].text);
    if (imported) findings.push("Astro adapter import present");
    if (dynamic) findings.push("dynamic Astro adapter import present");
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "setAdapter"
    )
      findings.push("Astro setAdapter hook present");
  };
  const property = (obj, name) =>
    obj.properties.find(
      (p) =>
        p.name &&
        ((ts.isIdentifier(p.name) && p.name.text === name) ||
          (ts.isStringLiteral(p.name) && p.name.text === name)),
    );
  let defineConfigCalls = 0;
  function visit(node) {
    visitAdapter(node);
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "defineConfig"
    ) {
      defineConfigCalls += 1;
      const arg = node.arguments[0];
      if (arg && ts.isObjectLiteralExpression(arg)) {
        if (
          arg.properties.some(
            (p) => p.name && ts.isComputedPropertyName(p.name),
          )
        )
          findings.push("Astro config uses computed keys");
        if (arg.properties.some((p) => ts.isSpreadAssignment(p)))
          findings.push("Astro config uses a spread");
        if (property(arg, "adapter")) findings.push("Astro adapter configured");
        const output = property(arg, "output");
        if (output) {
          const value = output.initializer;
          if (!value || !ts.isStringLiteral(value) || value.text !== "static") {
            findings.push("Astro output is not the literal static mode");
          }
        } else if (
          arg.properties.some(
            (p) =>
              (ts.isIdentifier(p.name) && p.name.text === "output") ||
              (ts.isStringLiteral(p.name) && p.name.text === "output"),
          )
        ) {
          findings.push(
            "Astro output configuration is not statically understood",
          );
        }
      } else
        findings.push("Astro defineConfig argument is not a literal object");
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  if (defineConfigCalls !== 1)
    findings.push(
      "Astro config must have one statically analyzable defineConfig call",
    );
  return findings;
}

function hasLiteralStaticOutput(text, fileName) {
  const source = ts.createSourceFile(
    fileName,
    text,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.JS,
  );
  if (source.parseDiagnostics.length) return false;
  let matches = 0;
  let safe = false;
  function visit(node) {
    if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === "defineConfig"
    ) {
      matches += 1;
      const arg = node.arguments[0];
      if (!arg || !ts.isObjectLiteralExpression(arg)) {
        safe = false;
        return;
      }
      const setting = arg.properties.find(
        (p) =>
          ts.isPropertyAssignment(p) &&
          ((ts.isIdentifier(p.name) && p.name.text === "output") ||
            (ts.isStringLiteral(p.name) && p.name.text === "output")),
      );
      safe = Boolean(
        setting &&
        ts.isStringLiteral(setting.initializer) &&
        setting.initializer.text === "static",
      );
    }
    ts.forEachChild(node, visit);
  }
  visit(source);
  return matches === 1 && safe;
}

function auditIdentityFailure(id, advisory) {
  if (String(id) !== TEMPORARY_ADVISORY.id) return "wrong advisory id";
  if (advisory?.module_name !== TEMPORARY_ADVISORY.moduleName)
    return "wrong package";
  if (advisory?.severity !== "high") return "severity changed";
  if ((advisory.vulnerable_versions ?? "").replace(/\s/g, "") !== "<=4.2.0")
    return "affected-version range changed";
  if (!new Set(["<0.0.0", "none", "None"]).has(advisory.patched_versions ?? ""))
    return "upstream patch is available or patch state is unknown";
  if (
    !advisory.url?.toLowerCase().includes(TEMPORARY_ADVISORY.ghsa.toLowerCase())
  )
    return "GHSA identity changed";
  return "";
}

function auditPathsFailure(advisory) {
  const findings = advisory.findings ?? [];
  if (findings.length === 0) return "audit has no concrete dependency paths";
  const exactPaths = findings.every((finding) => {
    const paths = finding.paths ?? [];
    return (
      finding.version === TEMPORARY_ADVISORY.vulnerableVersion &&
      paths.length > 0 &&
      paths.every(
        (p) =>
          p === "browser>astro>http-cache-semantics" ||
          p === "docs-site>astro>http-cache-semantics",
      )
    );
  });
  if (!exactPaths) return "resolved version or dependency path changed";
  const allowedRoots = new Set(["browser", "docs-site"]);
  if (
    findings
      .flatMap((finding) => finding.paths ?? [])
      .some((p) => !allowedRoots.has(p.split(">", 1)[0]))
  )
    return "unexpected audit dependency root";
  return "";
}

export function qualifyAuditFinding({ id, advisory, context, now }) {
  const deny = (reason) => ({ qualified: false, reason });
  const identityFailure = auditIdentityFailure(id, advisory);
  if (identityFailure) return deny(identityFailure);
  const pathFailure = auditPathsFailure(advisory);
  if (pathFailure) return deny(pathFailure);
  if (Date.parse(now) >= Date.parse(TEMPORARY_ADVISORY.expiresAt))
    return deny("temporary qualification expired");
  const sourceResult = verifyQualificationEvidence(
    context.repoRoot,
    context.evidence,
    context.expectedCommit,
    new Date(now),
  );
  if (!sourceResult.qualified) return sourceResult;
  return {
    qualified: true,
    reason:
      "exact temporary static-assets and pinned Pages-function scope passed",
  };
}

function sha256(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function equalHashMaps(first, second) {
  if (!first || !second) return false;
  const left = Object.entries(first).sort(([a], [b]) => a.localeCompare(b));
  const right = Object.entries(second).sort(([a], [b]) => a.localeCompare(b));
  return JSON.stringify(left) === JSON.stringify(right);
}

async function startPreview(repoRoot) {
  const port = 41000 + Math.floor(Math.random() * 10000);
  const host = "127.0.0.1";
  const child = spawn(
    "pnpm",
    [
      "--dir",
      "browser",
      "exec",
      "astro",
      "preview",
      "--host",
      host,
      "--port",
      String(port),
    ],
    {
      cwd: repoRoot,
      stdio: "ignore",
      detached: process.platform !== "win32",
    },
  );
  const origin = `http://${host}:${port}`;
  try {
    let ready = false;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      if (child.exitCode !== null)
        throw new Error(`Astro preview exited early (${child.exitCode})`);
      try {
        const response = await fetch(`${origin}/`, {
          redirect: "manual",
          signal: AbortSignal.timeout(1000),
        });
        if (response.status === 200) {
          ready = true;
          break;
        }
      } catch {}
      await delay(250);
    }
    if (!ready) throw new Error("Astro preview did not become ready");
    return { child, origin };
  } catch (error) {
    stopPreview(child);
    throw error;
  }
}

function stopPreview(child) {
  if (child.exitCode !== null) return;
  try {
    if (process.platform !== "win32" && child.pid)
      process.kill(-child.pid, "SIGTERM");
    else child.kill("SIGTERM");
  } catch {}
}

async function responseEvidence(origin) {
  const routes = [
    "/",
    "/playground.html",
    "/devlog.html",
    "/docs/",
    "/docs/architecture/how-it-works",
  ];
  const result = [];
  for (const route of routes) {
    const response = await fetch(new URL(route, origin), {
      redirect: "manual",
      signal: AbortSignal.timeout(5000),
    });
    result.push({
      url: route,
      status: response.status,
      setCookie: response.headers.has("set-cookie"),
      contentType: response.headers.get("content-type"),
    });
    await response.body?.cancel();
  }
  return result;
}

export function trackedBuildInputs(repoRoot) {
  const paths = execFileSync("git", ["ls-files", "-z", "--", ...BUILD_INPUTS], {
    cwd: repoRoot,
    encoding: "utf8",
  })
    .split("\0")
    .filter(Boolean)
    .sort();
  const files = {};
  for (const rel of paths) {
    if (!fs.existsSync(path.join(repoRoot, rel))) return {};
    files[rel] = sha256(fs.readFileSync(path.join(repoRoot, rel)));
  }
  return files;
}

function generatedDocsEvidence(context) {
  const sourceFiles = Object.fromEntries(
    Object.entries(context.sourceFiles.docs)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, contents]) => [name, sha256(contents)]),
  );
  return {
    config: context.astroConfigs.docs,
    configSha256: sha256(context.astroConfigs.docs),
    sourceFiles,
    sourceDigest: sha256(JSON.stringify(sourceFiles)),
    scanResult: "passed",
  };
}

function outputEvidence(repoRoot) {
  const base = path.join(repoRoot, "browser/dist");
  const files = {};
  const findings = [];
  let count = 0;
  const markers = MARKERS;
  const visit = (dir) => {
    for (const item of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, item.name);
      const rel = path.relative(base, full).split(path.sep).join("/");
      if (item.isDirectory()) {
        visit(full);
        continue;
      }
      count += 1;
      if (
        /(?:^|\/)(?:_worker\.js|functions\/|server\/entry\.|_routes\.json)/.test(
          rel,
        )
      )
        findings.push(`server runtime output present: ${rel}`);
      if (
        /\.(?:html?|js|mjs|cjs|css|xml|json|txt)$/i.test(rel) ||
        item.name === "_headers"
      ) {
        const bytes = fs.readFileSync(full);
        const text = bytes.toString("utf8");
        files[rel] = sha256(bytes);
        for (const marker of markers)
          if (text.toLowerCase().includes(marker.toLowerCase()))
            findings.push(`shipped marker ${marker}: ${rel}`);
        if (
          /(?:^|\/)\_headers$/i.test(rel) &&
          /^\s*Set-Cookie\s*:/im.test(text)
        )
          findings.push(`cookie directive in ${rel}`);
      }
    }
  };
  if (!fs.existsSync(base))
    throw new Error("browser/dist does not exist after build");
  visit(base);
  return { count, files, digest: sha256(JSON.stringify(files)), findings };
}

export async function createQualificationEvidence(repoRoot, commit) {
  const head = execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: repoRoot,
    encoding: "utf8",
  }).trim();
  if (head !== commit)
    throw new Error("Checkout HEAD differs from evidence commit");
  const dirtyTracked = execFileSync(
    "git",
    ["status", "--porcelain", "--untracked-files=no"],
    { cwd: repoRoot, encoding: "utf8" },
  ).trim();
  if (dirtyTracked)
    throw new Error(
      "Tracked source is dirty; evidence must bind to the exact commit",
    );
  const context = readCurrentContext(repoRoot);
  const staticCheck = qualifyStaticContext({ ...context, httpResponses: [] });
  if (
    !staticCheck.qualified &&
    !staticCheck.reason.includes("preview response evidence")
  )
    throw new Error(staticCheck.reason);
  const output = outputEvidence(repoRoot);
  if (output.findings.length) throw new Error(output.findings.join("\n"));
  const server = await startPreview(repoRoot);
  try {
    const responses = await responseEvidence(server.origin);
    const responseCheck = qualifyStaticContext({
      ...context,
      httpResponses: responses,
    });
    if (!responseCheck.qualified) throw new Error(responseCheck.reason);
    return {
      schemaVersion: 1,
      advisoryId: TEMPORARY_ADVISORY.id,
      ghsa: TEMPORARY_ADVISORY.ghsa,
      package: TEMPORARY_ADVISORY.moduleName,
      vulnerableVersion: TEMPORARY_ADVISORY.vulnerableVersion,
      expiresAt: TEMPORARY_ADVISORY.expiresAt,
      commit,
      generatedAt: new Date().toISOString(),
      lockfileSha256: sha256(
        fs.readFileSync(path.join(repoRoot, "pnpm-lock.yaml")),
      ),
      buildInputs: trackedBuildInputs(repoRoot),
      generatedDocs: generatedDocsEvidence(context),
      output,
      responses,
      result: "qualified",
    };
  } finally {
    stopPreview(server.child);
  }
}

export function verifyQualificationEvidence(
  repoRoot,
  evidence,
  expectedCommit,
  now = new Date(),
) {
  const deny = (reason) => ({ qualified: false, reason });
  const nowMs = Date.parse(now);
  if (
    !Number.isFinite(nowMs) ||
    nowMs >= Date.parse(TEMPORARY_ADVISORY.expiresAt)
  )
    return deny("temporary qualification expired or clock invalid");
  if (evidence?.schemaVersion !== 1 || evidence.result !== "qualified")
    return deny("qualification evidence missing or invalid");
  if (
    evidence.advisoryId !== TEMPORARY_ADVISORY.id ||
    evidence.ghsa !== TEMPORARY_ADVISORY.ghsa ||
    evidence.package !== TEMPORARY_ADVISORY.moduleName ||
    evidence.vulnerableVersion !== TEMPORARY_ADVISORY.vulnerableVersion ||
    evidence.expiresAt !== TEMPORARY_ADVISORY.expiresAt
  )
    return deny("qualification identity changed");
  if (evidence.commit !== expectedCommit)
    return deny("build evidence is for a different commit");
  const generatedAt = Date.parse(evidence.generatedAt);
  if (
    !Number.isFinite(generatedAt) ||
    generatedAt > nowMs + 5 * 60 * 1000 ||
    nowMs - generatedAt > MAX_EVIDENCE_AGE_MS
  )
    return deny("build evidence is invalid, future-dated, or stale");
  if (
    evidence.lockfileSha256 !==
    sha256(fs.readFileSync(path.join(repoRoot, "pnpm-lock.yaml")))
  )
    return deny("lockfile differs from build evidence");
  if (
    !evidence.buildInputs ||
    Object.keys(evidence.buildInputs).length === 0 ||
    Object.values(evidence.buildInputs).some(
      (hash) => !/^[a-f0-9]{64}$/.test(hash),
    ) ||
    !equalHashMaps(evidence.buildInputs, trackedBuildInputs(repoRoot))
  )
    return deny("committed build inputs differ from build evidence");
  const generated = evidence.generatedDocs;
  if (
    !generated?.config ||
    generated.configSha256 !== sha256(generated.config) ||
    !generated.sourceFiles ||
    Object.keys(generated.sourceFiles).length === 0 ||
    Object.values(generated.sourceFiles).some(
      (hash) => !/^[a-f0-9]{64}$/.test(hash),
    ) ||
    generated.sourceDigest !== sha256(JSON.stringify(generated.sourceFiles)) ||
    generated.scanResult !== "passed"
  )
    return deny(
      "generated Blume source/config evidence missing or inconsistent",
    );
  const outputFiles = evidence.output?.files;
  if (
    !evidence.output ||
    !Number.isInteger(evidence.output.count) ||
    evidence.output.count < 1 ||
    !outputFiles ||
    Object.keys(outputFiles).length < 1 ||
    evidence.output.count < Object.keys(outputFiles).length ||
    Object.values(outputFiles).some((hash) => !/^[a-f0-9]{64}$/.test(hash)) ||
    !Array.isArray(evidence.output.findings) ||
    evidence.output.digest !== sha256(JSON.stringify(outputFiles)) ||
    evidence.output.findings?.length
  ) {
    return deny("built output evidence incomplete, inconsistent, or unsafe");
  }
  if (
    Object.keys(outputFiles).some((name) =>
      /(?:^|\/)(?:_worker\.js|functions\/|server\/entry\.|_routes\.json)/.test(
        name,
      ),
    )
  )
    return deny("server runtime file listed in build evidence");
  const current = readCurrentContext(repoRoot, {
    includeOutput: false,
    includeGenerated: false,
  });
  current.astroConfigs.docs = generated.config;
  const responseCheck = qualifyStaticContext({
    ...current,
    outputFiles: { "same-run-static-output-attested": "" },
    httpResponses: evidence.responses,
  });
  if (!responseCheck.qualified) return responseCheck;
  return {
    qualified: true,
    reason:
      "same-commit static build, pinned Pages-function, output, and preview response evidence passed",
  };
}

export function readCurrentContext(
  repoRoot,
  { includeOutput = true, includeGenerated = true } = {},
) {
  const read = (p) => fs.readFileSync(path.join(repoRoot, p), "utf8");
  const readTree = (base) => {
    const out = {};
    const visit = (dir) => {
      for (const ent of fs.readdirSync(path.join(repoRoot, dir), {
        withFileTypes: true,
      })) {
        const rel = path.posix.join(dir, ent.name);
        if (ent.isDirectory()) visit(rel);
        else if (/\.(?:astro|mjs|js|ts|tsx)$/.test(ent.name))
          out[rel] = read(rel);
      }
    };
    visit(base);
    return out;
  };
  const readOutput = () => {
    const out = {};
    const visit = (dir) => {
      for (const ent of fs.readdirSync(path.join(repoRoot, dir), {
        withFileTypes: true,
      })) {
        const rel = path.posix.join(dir, ent.name);
        if (ent.isDirectory()) visit(rel);
        else if (
          /\.(?:html|js|mjs|cjs|css|xml|json)$/i.test(ent.name) ||
          ent.name === "_headers"
        )
          out[rel] = read(rel);
      }
    };
    visit("browser/dist");
    return out;
  };
  return {
    packages: {
      browser: JSON.parse(read("browser/package.json")),
      docsSite: JSON.parse(read("docs-site/package.json")),
    },
    lockfile: read("pnpm-lock.yaml"),
    astroConfigs: {
      browser: read("browser/astro.config.mjs"),
      docs: includeGenerated ? read("docs-site/.blume/astro.config.mjs") : "",
    },
    sourceFiles: {
      browser: readTree("browser/src"),
      browserFunctions: readTree("browser/functions"),
      docs: includeGenerated ? readTree("docs-site/.blume/src") : {},
    },
    outputFiles: includeOutput ? readOutput() : {},
    httpResponses: [],
  };
}

function configFailure(context) {
  for (const [label, config] of Object.entries(context.astroConfigs ?? {})) {
    const findings = configFindings(config, `${label}.astro.config.mjs`);
    if (findings.length) return `${label} ${findings.join(", ")}`;
  }
  if (
    !context.astroConfigs?.browser ||
    !context.astroConfigs?.docs ||
    !hasLiteralStaticOutput(
      context.astroConfigs.docs,
      "docs-site/.blume/astro.config.mjs",
    )
  )
    return "browser or generated Blume Astro config is absent, or Blume is not explicitly static";
  return "";
}

function sourceFailure(context) {
  const pagesFunctions = context.sourceFiles?.browserFunctions;
  const middlewarePath = "browser/functions/_middleware.ts";
  if (!pagesFunctions || !pagesFunctions[middlewarePath])
    return "Pages edge middleware source is missing";
  const unknownFunction = Object.keys(pagesFunctions).find(
    (name) => !PAGES_FUNCTION_SHA256.has(name),
  );
  if (unknownFunction)
    return `unknown Pages edge function source present: ${unknownFunction}`;
  for (const [name, expectedHash] of PAGES_FUNCTION_SHA256) {
    if (!pagesFunctions[name])
      return `pinned Pages function source is missing: ${name}`;
    if (sha256(pagesFunctions[name]) !== expectedHash)
      return `pinned Pages function source changed: ${name}`;
  }
  for (const [label, files] of Object.entries(context.sourceFiles ?? {})) {
    for (const [name, text] of Object.entries(files)) {
      if (prerenderOptOut(text, name, ts))
        return `${label}/${name} opts out of prerendering`;
      if (/astro:assets|<\s*(?:Image|Picture)\b|\bgetImage\s*\(/.test(text))
        return `${label}/${name} uses Astro asset/image handling`;
      if (
        /http-cache-semantics|\b(?:CachePolicy|cachePolicy)\b|\bmax-stale\b|\bshared(?:User)?Cache\b/.test(
          text,
        )
      )
        return `${label}/${name} uses the vulnerable cache API`;
    }
  }
  return "";
}

function outputFailure(context) {
  const output = context.outputFiles ?? {};
  if (Object.keys(output).length === 0)
    return "built static output evidence missing";
  for (const [name, text] of Object.entries(output)) {
    if (
      /(?:^|\/)(?:_worker\.js|functions\/|server\/entry\.|_routes\.json)/.test(
        name,
      )
    )
      return `server runtime output present: ${name}`;
    if (
      /\.(?:js|mjs|cjs)$/i.test(name) &&
      MARKERS.some((marker) => text.includes(marker))
    )
      return `vulnerable cache marker in shipped bundle: ${name}`;
    if (/(?:^|\/)_headers$/i.test(name) && /^\s*Set-Cookie\s*:/im.test(text))
      return `static response header config sets cookies: ${name}`;
  }
  return "";
}

function responseFailure(context) {
  const responses = context.httpResponses ?? [];
  const requiredRoutes = [
    "/",
    "/playground.html",
    "/devlog.html",
    "/docs/",
    "/docs/architecture/how-it-works",
  ];
  if (
    !Array.isArray(responses) ||
    responses.length !== requiredRoutes.length ||
    new Set(responses.map((response) => response.url)).size !==
      requiredRoutes.length ||
    !requiredRoutes.every((route) =>
      responses.some(
        (response) => response.url === route && response.status === 200,
      ),
    )
  )
    return "preview response evidence missing or route not static/200";
  for (const response of responses) {
    if (response.setCookie !== false)
      return `static route response sets cookies: ${response.url}`;
  }
  return "";
}

export function qualifyStaticContext(context) {
  const checks = [
    packageAndLockFailure,
    configFailure,
    sourceFailure,
    outputFailure,
    responseFailure,
  ];
  for (const check of checks) {
    const reason = check(context);
    if (reason) return { qualified: false, reason };
  }
  return {
    qualified: true,
    reason:
      "static assets, pinned Pages-function source, output, and response-header guards passed",
  };
}
