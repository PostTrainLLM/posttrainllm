import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Judged payloads are immutable evidence. Verify them instead of reformatting
// their bytes; the ordinary Python lint gate still checks every changed file.
export function verifiedKernelSnapshots(root = process.cwd()) {
  const read = (file) => readFileSync(resolve(root, file));
  const manifest = JSON.parse(
    read("experiments/openkernel/immutable-sources.json"),
  );
  const results = JSON.parse(read("experiments/openkernel/results.json"));
  const files = new Set();
  for (const entry of manifest) {
    assert.match(
      entry.file,
      /^experiments\/openkernel\/[a-z0-9_]+\/[a-z-]+\.py$/,
    );
    assert(!files.has(entry.file), `Duplicate immutable source: ${entry.file}`);
    const sha = createHash("sha256").update(read(entry.file)).digest("hex");
    assert.equal(sha, entry.sha256, `Judged source changed: ${entry.file}`);
    const job = results.jobs.find((item) => item.job_id === entry.job_id);
    assert(job, `Missing judge receipt: ${entry.job_id}`);
    assert.equal(job.source_sha256, sha);
    assert.equal(job.status, "done");
    assert.equal(job.mode, "run");
    assert.equal(job.passed, true);
    assert.deepEqual(job.flags, []);
    files.add(entry.file);
  }
  for (const selected of results.selected_candidates) {
    const entry = manifest.find((item) => item.file === selected.file);
    assert(
      entry,
      `Selected source lacks an immutable receipt: ${selected.file}`,
    );
    assert.equal(entry.sha256, selected.source_sha256);
    assert.equal(entry.job_id, selected.job_id);
  }
  return files;
}
