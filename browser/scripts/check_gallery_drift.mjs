// check_gallery_drift.mjs — guard against the published gallery artifacts
// (browser/public/gallery/*.bin + manifest.json) silently drifting from the
// canonical training data they're derived from.
//
// WHY THIS EXISTS
//   Cloudflare Pages deploys with a plain `git clone` + `npm run build`. It
//   never runs finalize_gallery.ts, so the committed *.bin files are the
//   source of truth at deploy time. If someone retrains a model in
//   data/gallery/ but forgets to re-run `npm run gallery` and commit, the
//   site ships stale weights with no error. This check catches that.
//
// WHAT IT DOES
//   1. Regenerates the gallery into a throwaway temp dir (GALLERY_OUT_DIR),
//      so the working tree is never touched.
//   2. For every regenerated file, compares it against the COMMITTED git blob
//      (git show HEAD:browser/public/gallery/<f>) — not the working tree — so
//      it verifies what's actually in version control.
//   3. Comparison is drift-meaningful, not byte-literal: the finalize scripts
//      stamp a fresh `convertedAt` timestamp and an absolute `sourceConvertedFrom`
//      path into each header (and a `submittedAt` into the manifest), so a raw
//      byte diff would always fail. We instead require:
//        - the weight PAYLOAD (everything after the JSON header) to be byte-exact
//        - the JSON header to match after deleting the known-nondeterministic fields
//      For manifest.json we compare per-model entries by id (ignoring
//      submission.submittedAt) and only fail on entries that exist in BOTH —
//      committed-only extras (e.g. curated models with no data/gallery source)
//      are reported but tolerated.
//
// EXIT CODES
//   0  no drift (or data/gallery absent — nothing to check, skipped)
//   1  drift detected — committed artifact differs from a fresh regenerate
//   2  harness error (couldn't run the generators / read a blob)
//
// SKIP BEHAVIOUR
//   data/gallery/ is gitignored and absent in CI. When it's missing there is
//   nothing to regenerate from, so the check exits 0 with a SKIP notice. It
//   only does real work locally / wherever the canonical training data lives.

import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const BROWSER_DIR = resolve(__dirname, "..");
const ROOT = resolve(BROWSER_DIR, "..");
const DATA_GALLERY = resolve(ROOT, "data/gallery");
const COMMITTED_PREFIX = "browser/public/gallery";

// Header fields the generators stamp at run time — not real drift.
const NONDETERMINISTIC_HEADER_FIELDS = ["convertedAt", "sourceConvertedFrom"];

function fail(msg) {
  console.error(`\n❌ gallery drift check FAILED: ${msg}`);
  process.exit(1);
}
function harnessError(msg) {
  console.error(`\n⚠️  gallery drift check could not run: ${msg}`);
  process.exit(2);
}

// --- Skip gracefully when there's no canonical data to regenerate from. ---
if (!existsSync(DATA_GALLERY)) {
  console.log(
    "ℹ️  data/gallery/ absent — no canonical training data to regenerate from. " +
      "Skipping gallery drift check (this is expected in CI).",
  );
  process.exit(0);
}

// --- 1. Regenerate into a temp dir. ---
const outDir = mkdtempSync(join(tmpdir(), "tinygpt-gallery-"));
const env = { ...process.env, GALLERY_OUT_DIR: outDir };
console.log(`Regenerating gallery into ${outDir} …`);
for (const script of ["finalize_gallery.ts", "finalize_gallery_int4.ts"]) {
  const r = spawnSync(process.execPath, [join(BROWSER_DIR, script)], {
    cwd: BROWSER_DIR,
    env,
    stdio: "inherit",
  });
  if (r.status !== 0) {
    rmSync(outDir, { recursive: true, force: true });
    harnessError(`${script} exited with status ${r.status}`);
  }
}

// --- Helpers ---
/** Read the committed blob for a gallery file, or null if it isn't tracked. */
function committedBlob(name) {
  const r = spawnSync("git", ["show", `HEAD:${COMMITTED_PREFIX}/${name}`], {
    cwd: ROOT,
    maxBuffer: 1024 * 1024 * 256, // gallery bins are ~19 MB; give plenty of headroom
  });
  return r.status === 0 ? r.stdout : null;
}

/** Split a .bin into { header (parsed JSON), payload (Buffer after header) }. */
function splitBin(buf) {
  if (buf.length < 12) throw new Error("file too short to be a .bin");
  const dv = new DataView(buf.buffer, buf.byteOffset, buf.byteLength);
  const magic = String.fromCharCode(buf[0], buf[1], buf[2], buf[3]);
  if (magic !== "TGPT") throw new Error(`bad magic ${JSON.stringify(magic)}`);
  const headerLen = dv.getUint32(8, true);
  const header = JSON.parse(buf.subarray(12, 12 + headerLen).toString("utf8"));
  const payload = buf.subarray(12 + headerLen);
  return { header, payload };
}

function normalizeHeader(header) {
  const c = { ...header };
  for (const f of NONDETERMINISTIC_HEADER_FIELDS) delete c[f];
  return JSON.stringify(c);
}

// --- 2 + 3. Compare each regenerated file vs the committed blob. ---
const regenFiles = readdirSync(outDir);
const binFiles = regenFiles.filter((f) => f.endsWith(".bin"));
const drift = [];
let checked = 0;

for (const name of binFiles) {
  const regen = readFileSync(join(outDir, name));
  const committed = committedBlob(name);
  if (committed === null) {
    drift.push(`${name}: regenerated but NOT committed (run \`npm run gallery\` and commit it)`);
    continue;
  }
  let a, b;
  try {
    a = splitBin(committed);
    b = splitBin(regen);
  } catch (err) {
    drift.push(`${name}: could not parse (${err.message})`);
    continue;
  }
  checked++;
  if (Buffer.compare(a.payload, b.payload) !== 0) {
    drift.push(
      `${name}: WEIGHT PAYLOAD differs (committed ${a.payload.length} B vs regenerated ${b.payload.length} B)`,
    );
  } else if (normalizeHeader(a.header) !== normalizeHeader(b.header)) {
    drift.push(`${name}: header metadata differs (ignoring ${NONDETERMINISTIC_HEADER_FIELDS.join("/")})`);
  } else {
    console.log(`  ✓ ${name} (payload + header match committed)`);
  }
}

// --- manifest.json: compare the finalize-OWNED, weight-linked fields per
//     model, by id. We deliberately compare a fixed allow-list rather than the
//     whole entry because the manifest is co-authored by a multi-tool pipeline:
//       - finalize_gallery       writes file/fileBytes/params/stats/sample  ← what we guard
//       - finalize_gallery_int4  patches fileInt4/fileInt4Bytes (carries a
//                                fresh convertedAt → its byte length, and thus
//                                fileInt4Bytes, drifts by a few bytes per run)
//       - score_gallery          writes the `benchmarks` scores after the fact
//     Comparing benchmarks/fileInt4/submittedAt would flag tool-ordering noise,
//     not real weight drift. The allow-list fields are deterministic functions
//     of the canonical .tinygpt source + static slot descriptors, so they're a
//     stable invariant: if a model is retrained but not re-finalized+committed,
//     fileBytes / trainLoss / params here will diverge and fail the check. ---
const MANIFEST_MODEL_FIELDS = [
  "file", "fileBytes", "params", "paramCount", "trainLoss", "steps",
  "gpuBytes", "prompt", "sample", "name", "icon", "blurb", "corpus", "corpusUrl",
];
if (regenFiles.includes("manifest.json")) {
  const committedRaw = committedBlob("manifest.json");
  if (committedRaw === null) {
    drift.push("manifest.json: regenerated but NOT committed");
  } else {
    const regenManifest = JSON.parse(readFileSync(join(outDir, "manifest.json"), "utf8"));
    const committedManifest = JSON.parse(committedRaw.toString("utf8"));
    if (JSON.stringify(committedManifest.note) !== JSON.stringify(regenManifest.note)) {
      drift.push("manifest.json: top-level `note` differs");
    }
    const committedById = new Map((committedManifest.models ?? []).map((m) => [m.id, m]));
    for (const rm of regenManifest.models ?? []) {
      const cm = committedById.get(rm.id);
      if (!cm) {
        drift.push(`manifest.json: model "${rm.id}" regenerated but missing from committed manifest`);
        continue;
      }
      const fieldDiffs = MANIFEST_MODEL_FIELDS.filter(
        (k) => JSON.stringify(cm[k]) !== JSON.stringify(rm[k]),
      );
      if (fieldDiffs.length) {
        drift.push(`manifest.json: model "${rm.id}" differs in [${fieldDiffs.join(", ")}]`);
      } else {
        checked++;
        console.log(`  ✓ manifest model "${rm.id}"`);
      }
    }
    const regenIds = new Set((regenManifest.models ?? []).map((m) => m.id));
    const extras = (committedManifest.models ?? []).map((m) => m.id).filter((id) => !regenIds.has(id));
    if (extras.length) {
      console.log(
        `  ℹ️  committed-only manifest models (no data/gallery source, not checked): ${extras.join(", ")}`,
      );
    }
  }
}

rmSync(outDir, { recursive: true, force: true });

if (drift.length) {
  fail(
    `${drift.length} artifact(s) drifted from a fresh regenerate:\n` +
      drift.map((d) => `  - ${d}`).join("\n") +
      "\n\nRun `npm run gallery` in browser/ and commit the updated browser/public/gallery/* files.",
  );
}

console.log(`\n✅ gallery drift check passed — ${checked} committed artifact(s) match a fresh regenerate.`);
