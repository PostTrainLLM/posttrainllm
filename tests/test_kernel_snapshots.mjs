import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { verifiedKernelSnapshots } from "../scripts/quality/verified-kernel-snapshots.mjs";

function fixture(change = () => {}) {
  const root = mkdtempSync(join(tmpdir(), "kernel-receipt-"));
  const file = "experiments/openkernel/muse_decode_layer/submission.py";
  mkdirSync(join(root, "experiments/openkernel/muse_decode_layer"), {
    recursive: true,
  });
  const source = "# exact judged bytes\n";
  const sha = createHash("sha256").update(source).digest("hex");
  const manifest = [{ file, job_id: "scored", sha256: sha }];
  const results = {
    jobs: [
      {
        job_id: "scored",
        source_sha256: sha,
        status: "done",
        mode: "run",
        passed: true,
        flags: [],
      },
    ],
    selected_candidates: [{ file, job_id: "scored", source_sha256: sha }],
  };
  writeFileSync(join(root, file), source);
  change({ root, file, manifest, results });
  writeFileSync(
    join(root, "experiments/openkernel/immutable-sources.json"),
    JSON.stringify(manifest),
  );
  writeFileSync(
    join(root, "experiments/openkernel/results.json"),
    JSON.stringify(results),
  );
  return root;
}

test("accepts exact scored bytes", () => {
  assert.equal(verifiedKernelSnapshots(fixture()).size, 1);
});
test("rejects a formatting-only source change", () => {
  const root = fixture(({ root, file }) =>
    writeFileSync(join(root, file), "# exact judged bytes\n\n"),
  );
  assert.throws(() => verifiedKernelSnapshots(root), /Judged source changed/);
});
for (const [field, value] of [
  ["passed", false],
  ["mode", "check"],
  ["status", "queued"],
  ["flags", ["invalid"]],
]) {
  test(`rejects unqualified receipt: ${field}`, () => {
    const root = fixture(({ results }) => {
      results.jobs[0][field] = value;
    });
    assert.throws(() => verifiedKernelSnapshots(root));
  });
}
test("rejects a selected source with no immutable receipt", () => {
  const root = fixture(({ manifest }) => {
    manifest.length = 0;
  });
  assert.throws(
    () => verifiedKernelSnapshots(root),
    /lacks an immutable receipt/,
  );
});
