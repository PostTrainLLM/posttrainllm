import test from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import {
  mkdtempSync,
  mkdirSync,
  rmSync,
  readFileSync,
  writeFileSync,
  existsSync,
} from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  qualifyAuditFinding,
  qualifyStaticContext,
  TEMPORARY_ADVISORY,
  verifyQualificationEvidence,
} from "./temporary-static-astro-qualification.mjs";

const now = "2026-10-04T00:00:00.000Z";
const pagesMiddleware = readFileSync(
  new URL("../../browser/functions/_middleware.ts", import.meta.url),
  "utf8",
);
const pagesMiddlewareTest = readFileSync(
  new URL("../../browser/functions/_middleware.test.ts", import.meta.url),
  "utf8",
);
const safeContext = () => ({
  packages: {
    browser: { devDependencies: { astro: "^7.2.8" }, dependencies: {} },
    docsSite: {
      devDependencies: { astro: "7.2.8" },
      dependencies: { blume: "1.5.3" },
    },
  },
  lockfile: `  browser:\n    devDependencies:\n      astro:\n        specifier: ^7.2.8\n        version: 7.2.8(browser)\n  docs-site:\n    devDependencies:\n      astro:\n        specifier: 7.2.8\n        version: 7.2.8(docs)\n  astro@7.2.8(browser):\n  astro@7.2.8(docs):\n  http-cache-semantics@4.2.0:`,
  astroConfigs: {
    browser: `import { defineConfig } from "astro/config"; export default defineConfig({ outDir: "./dist" });`,
    docs: `import { defineConfig } from "astro/config"; export default defineConfig({ output: "static" });`,
  },
  sourceFiles: {
    browser: { "src/page.astro": "---\n---\n<main>Static</main>" },
    browserFunctions: {
      "browser/functions/_middleware.ts": pagesMiddleware,
      "browser/functions/_middleware.test.ts": pagesMiddlewareTest,
    },
    docs: { "src/index.astro": "---\n---\n<main>Docs</main>" },
  },
  outputFiles: {
    "index.html": "<html></html>",
    _headers: "/*\n  Cache-Control: public, max-age=300\n",
  },
  httpResponses: [
    "/",
    "/playground.html",
    "/devlog.html",
    "/docs/",
    "/docs/architecture/how-it-works",
  ].map((url) => ({ url, status: 200, setCookie: false })),
});
const advisory = () => ({
  module_name: "http-cache-semantics",
  url: "https://github.com/advisories/GHSA-ch52-4w7c-c8xp",
  severity: "high",
  vulnerable_versions: "<=4.2.0",
  patched_versions: "<0.0.0",
  findings: [
    { version: "4.2.0", paths: ["browser>astro>http-cache-semantics"] },
  ],
});

test("static baseline fixture is analyzable and qualifies", () => {
  assert.deepEqual(qualifyStaticContext(safeContext()), {
    qualified: true,
    reason:
      "static assets, pinned Pages-function source, output, and response-header guards passed",
  });
});

test("only the exact high advisory and Astro dependency path are eligible", () => {
  const base = {
    id: TEMPORARY_ADVISORY.id,
    advisory: advisory(),
    context: {
      repoRoot: "/unavailable",
      evidence: null,
      expectedCommit: "abc",
    },
    now,
  };
  assert.equal(
    qualifyAuditFinding(base).qualified,
    false,
    "missing same-run evidence fails closed",
  );
  for (const change of [
    { id: "1240992" },
    { advisory: { ...advisory(), severity: "critical" } },
    { advisory: { ...advisory(), patched_versions: "4.2.1" } },
    {
      advisory: {
        ...advisory(),
        findings: [
          { version: "4.2.0", paths: ["browser>other>http-cache-semantics"] },
        ],
      },
    },
    {
      advisory: {
        ...advisory(),
        findings: [
          {
            version: "4.2.0",
            paths: ["browser>wrapper>astro>http-cache-semantics"],
          },
        ],
      },
    },
    {
      advisory: {
        ...advisory(),
        findings: [
          { version: "4.2.1", paths: ["browser>astro>http-cache-semantics"] },
        ],
      },
    },
  ]) {
    assert.equal(qualifyAuditFinding({ ...base, ...change }).qualified, false);
  }
});

test("SSR, hybrid, adapter, dynamic config, and unknown config fail closed", () => {
  for (const config of [
    `defineConfig({ output: "server" })`,
    `defineConfig({ output: "hybrid" })`,
    `import cloudflare from "@astrojs/cloudflare"; defineConfig({ adapter: cloudflare() })`,
    `defineConfig({ adapter() { return customAdapter(); } })`,
    `defineConfig({ ["adapter"]: customAdapter() })`,
    `defineConfig(options)`,
    `defineConfig({ ...base, output: "static" })`,
    `import("@astrojs/cloudflare"); defineConfig({ output: "static" })`,
  ]) {
    const context = safeContext();
    context.astroConfigs.browser = config;
    assert.equal(qualifyStaticContext(context).qualified, false, config);
  }
});

test("route opt-outs, Astro remote asset APIs, and custom caches fail closed", () => {
  for (const source of [
    `---\nexport const prerender = false;\n---`,
    `---\nexport const prerender = false as const;\n---`,
    `import { Image } from "astro:assets";`,
    `<Image src={remote} alt="" />`,
    `import CachePolicy from "http-cache-semantics";`,
    `const sharedUserCache = new Map();`,
    `const policy = new CachePolicy(request, response);`,
  ]) {
    const context = safeContext();
    context.sourceFiles.browser["src/page.astro"] = source;
    assert.equal(qualifyStaticContext(context).qualified, false, source);
  }
});

test("Pages function inventory and pinned middleware fail closed", () => {
  const changedMiddleware = safeContext();
  changedMiddleware.sourceFiles.browserFunctions[
    "browser/functions/_middleware.ts"
  ] += '\nimport "http-cache-semantics";\n';
  assert.equal(qualifyStaticContext(changedMiddleware).qualified, false);

  const changedMiddlewareTest = safeContext();
  changedMiddlewareTest.sourceFiles.browserFunctions[
    "browser/functions/_middleware.test.ts"
  ] += '\nexport const onRequest = () => new Response("route");\n';
  assert.equal(qualifyStaticContext(changedMiddlewareTest).qualified, false);

  const newFunction = safeContext();
  newFunction.sourceFiles.browserFunctions["browser/functions/api/handler.ts"] =
    'export const onRequest = () => import("http-cache-semantics");';
  assert.equal(qualifyStaticContext(newFunction).qualified, false);

  const missingMiddleware = safeContext();
  delete missingMiddleware.sourceFiles.browserFunctions[
    "browser/functions/_middleware.ts"
  ];
  assert.equal(qualifyStaticContext(missingMiddleware).qualified, false);

  const missingMiddlewareTest = safeContext();
  delete missingMiddlewareTest.sourceFiles.browserFunctions[
    "browser/functions/_middleware.test.ts"
  ];
  assert.equal(qualifyStaticContext(missingMiddlewareTest).qualified, false);
});

test("server files, shipped vulnerable markers, cookie headers and responses fail closed", () => {
  for (const [name, text] of [
    ["_worker.js", ""],
    ["functions/handler.js", ""],
    ["_routes.json", "{}"],
    ["_astro/app.js", `import CachePolicy from "http-cache-semantics";`],
    ["_headers", "/*\n  Set-Cookie: session=private\n"],
  ]) {
    const context = safeContext();
    context.outputFiles[name] = text;
    assert.equal(qualifyStaticContext(context).qualified, false, name);
  }
  const cookie = safeContext();
  cookie.httpResponses[0].setCookie = true;
  assert.equal(qualifyStaticContext(cookie).qualified, false);
  const missing = safeContext();
  missing.httpResponses.pop();
  assert.equal(qualifyStaticContext(missing).qualified, false);
});

test("expiry, missing build, runtime dependency path and changed lock versions fail closed", () => {
  for (const change of [
    (context) => {
      context.outputFiles = {};
    },
    (context) => {
      context.packages.browser.dependencies.astro = "7.2.8";
    },
    (context) => {
      context.lockfile = context.lockfile.replaceAll("7.2.8", "7.2.9");
    },
    (context) => {
      context.astroConfigs.docs = "";
    },
  ]) {
    const context = safeContext();
    change(context);
    assert.equal(qualifyStaticContext(context).qualified, false);
  }
  const context = {
    repoRoot: "/unavailable",
    evidence: null,
    expectedCommit: "abc",
  };
  assert.equal(
    qualifyAuditFinding({
      id: TEMPORARY_ADVISORY.id,
      advisory: advisory(),
      context,
      now: TEMPORARY_ADVISORY.expiresAt,
    }).qualified,
    false,
  );
});

const digest = (value) =>
  crypto.createHash("sha256").update(value).digest("hex");

function fixtureFiles() {
  return {
    "browser/astro.config.mjs": `import { defineConfig } from "astro/config"; export default defineConfig({});`,
    "browser/functions/_middleware.ts": pagesMiddleware,
    "browser/functions/_middleware.test.ts": pagesMiddlewareTest,
    "browser/package.json": JSON.stringify({
      devDependencies: { astro: "^7.2.8" },
      dependencies: {},
    }),
    "browser/src/index.astro": "<main>static</main>",
    "browser/public/_headers": "/*\n  Cache-Control: public, max-age=300\n",
    "browser/scripts/build-agent-surfaces.mjs": "// deterministic build step\n",
    "browser/scripts/build-docs.mjs": "// deterministic docs build step\n",
    "docs/README.md": "# Generated Blume content\n",
    "docs-site/blume.config.ts": "export default {};\n",
    "docs-site/package.json": JSON.stringify({
      dependencies: { blume: "1.5.3" },
      devDependencies: { astro: "7.2.8" },
    }),
    "docs-site/theme.css": ":root {}\n",
    "pnpm-lock.yaml": `lockfileVersion: '9.0'
importers:
  browser:
    devDependencies:
      astro:
        specifier: ^7.2.8
        version: 7.2.8(browser)
  docs-site:
    devDependencies:
      astro:
        specifier: 7.2.8
        version: 7.2.8(docs)
packages:
  astro@7.2.8:
  http-cache-semantics@4.2.0:
snapshots:
  astro@7.2.8(browser):
  astro@7.2.8(docs):
  http-cache-semantics@4.2.0: {}
`,
    "pnpm-workspace.yaml": `packages:
  - browser
  - docs-site
`,
  };
}

function createFixtureRepo(repoRoot, files) {
  for (const [name, contents] of Object.entries(files)) {
    const target = path.join(repoRoot, name);
    mkdirSync(path.dirname(target), { recursive: true });
    writeFileSync(target, contents);
  }
  execFileSync("git", ["init", "-q"], { cwd: repoRoot });
  execFileSync("git", ["add", "."], { cwd: repoRoot });
  execFileSync(
    "git",
    [
      "-c",
      "user.name=Fixture",
      "-c",
      "user.email=fixture@example.test",
      "commit",
      "-qm",
      "fixture",
    ],
    { cwd: repoRoot },
  );
  return execFileSync("git", ["rev-parse", "HEAD"], {
    cwd: repoRoot,
    encoding: "utf8",
  }).trim();
}

function fixtureEvidence(files, commit) {
  const lock = files["pnpm-lock.yaml"];
  const generatedConfig = `import { defineConfig } from "astro/config"; export default defineConfig({ output: "static" });`;
  const generatedSources = {
    "docs-site/.blume/src/index.astro": digest("<main>docs</main>"),
  };
  const outputFiles = { "index.html": digest("<html>static</html>") };
  return {
    schemaVersion: 1,
    advisoryId: TEMPORARY_ADVISORY.id,
    ghsa: TEMPORARY_ADVISORY.ghsa,
    package: TEMPORARY_ADVISORY.moduleName,
    vulnerableVersion: TEMPORARY_ADVISORY.vulnerableVersion,
    expiresAt: TEMPORARY_ADVISORY.expiresAt,
    commit,
    generatedAt: now,
    lockfileSha256: digest(lock),
    buildInputs: Object.fromEntries(
      Object.entries(files).map(([name, text]) => [name, digest(text)]),
    ),
    generatedDocs: {
      config: generatedConfig,
      configSha256: digest(generatedConfig),
      sourceFiles: generatedSources,
      sourceDigest: digest(JSON.stringify(generatedSources)),
      scanResult: "passed",
    },
    output: {
      count: 1,
      files: outputFiles,
      digest: digest(JSON.stringify(outputFiles)),
      findings: [],
    },
    responses: [
      "/",
      "/playground.html",
      "/devlog.html",
      "/docs/",
      "/docs/architecture/how-it-works",
    ].map((url) => ({ url, status: 200, setCookie: false })),
    result: "qualified",
  };
}

test("fresh code-health checkout verifies same-run evidence without generated Blume or private ignored files", () => {
  const repoRoot = mkdtempSync(
    path.join(os.tmpdir(), "posttrain-astro-qualification-"),
  );
  const files = fixtureFiles();
  try {
    const commit = createFixtureRepo(repoRoot, files);
    const evidence = fixtureEvidence(files, commit);
    assert.equal(existsSync(path.join(repoRoot, "docs-site/.blume")), false);
    const verified = verifyQualificationEvidence(
      repoRoot,
      evidence,
      commit,
      new Date(now),
    );
    assert.equal(verified.qualified, true, verified.reason);

    writeFileSync(
      path.join(repoRoot, "docs-site/theme.css"),
      ":root { color: red }\n",
    );
    assert.equal(
      verifyQualificationEvidence(repoRoot, evidence, commit, new Date(now))
        .qualified,
      false,
      "committed generation input drift is rejected",
    );
    writeFileSync(
      path.join(repoRoot, "docs-site/theme.css"),
      files["docs-site/theme.css"],
    );

    writeFileSync(
      path.join(repoRoot, "browser/functions/_middleware.ts"),
      `${pagesMiddleware}\n// changed edge behavior\n`,
    );
    assert.equal(
      verifyQualificationEvidence(repoRoot, evidence, commit, new Date(now))
        .qualified,
      false,
      "middleware drift is rejected",
    );
    writeFileSync(
      path.join(repoRoot, "browser/functions/_middleware.ts"),
      pagesMiddleware,
    );

    writeFileSync(
      path.join(repoRoot, "browser/functions/new-route.ts"),
      'export const onRequest = () => new Response("new route");',
    );
    assert.equal(
      verifyQualificationEvidence(repoRoot, evidence, commit, new Date(now))
        .qualified,
      false,
      "untracked edge function is rejected",
    );
    rmSync(path.join(repoRoot, "browser/functions/new-route.ts"));
    rmSync(path.join(repoRoot, "browser/functions/_middleware.ts"));
    assert.equal(
      verifyQualificationEvidence(repoRoot, evidence, commit, new Date(now))
        .qualified,
      false,
      "missing middleware is rejected",
    );
    writeFileSync(
      path.join(repoRoot, "browser/functions/_middleware.ts"),
      pagesMiddleware,
    );
    assert.equal(
      verifyQualificationEvidence(repoRoot, evidence, commit, new Date(now))
        .qualified,
      true,
      "restored middleware qualifies before receipt mutation tests",
    );

    for (const bad of [
      { ...evidence, generatedAt: "not-a-date" },
      { ...evidence, generatedAt: "2026-10-03T00:00:00.000Z" },
      { ...evidence, commit: "another-commit" },
      { ...evidence, lockfileSha256: "0".repeat(64) },
      { ...evidence, output: { ...evidence.output, count: 0 } },
      { ...evidence, output: { ...evidence.output, digest: "0".repeat(64) } },
      { ...evidence, responses: [] },
      {
        ...evidence,
        generatedDocs: {
          ...evidence.generatedDocs,
          config: "defineConfig(options)",
          configSha256: digest("defineConfig(options)"),
        },
      },
    ]) {
      assert.equal(
        verifyQualificationEvidence(repoRoot, bad, commit, new Date(now))
          .qualified,
        false,
      );
    }
  } finally {
    rmSync(repoRoot, { recursive: true, force: true });
  }
});
