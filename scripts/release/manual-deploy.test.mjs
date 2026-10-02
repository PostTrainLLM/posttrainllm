import assert from "node:assert/strict";
import {
  chmod,
  mkdir,
  mkdtemp,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";

const script = fileURLToPath(new URL("./manual-deploy.mjs", import.meta.url));

test("manual deploy resolves the exact current CI run by workflow path", async () => {
  const root = await mkdtemp(path.join(tmpdir(), "posttrainllm-deploy-gate-"));
  const bin = path.join(root, "bin");
  await mkdir(bin);

  const git = `#!/usr/bin/env node
const args = process.argv.slice(2);
const key = args.join(" ");
const responses = {
  "remote get-url origin": "https://github.com/PostTrainLLM/posttrainllm.git",
  "branch --show-current": "main",
  "status --porcelain": "",
  "rev-parse --abbrev-ref --symbolic-full-name @{u}": "origin/main",
  "rev-list --left-right --count origin/main...HEAD": "0\\t0",
  "rev-parse HEAD": process.env.EXPECTED_SHA,
};
if (key === "fetch --quiet origin") process.exit(0);
if (!(key in responses)) process.exit(2);
process.stdout.write(responses[key]);
`;

  const gh = `#!/usr/bin/env node
const fs = require("node:fs");
const args = process.argv.slice(2);
fs.appendFileSync(process.env.GH_LOG, JSON.stringify(args) + "\\n");
if (args[0] === "auth" && args[1] === "status") process.exit(0);
if (args[0] === "run" && args[1] === "list") {
  const workflow = args[args.indexOf("--workflow") + 1];
  const headSha = workflow === "123456" ? "stale-sha" : process.env.EXPECTED_SHA;
  process.stdout.write(JSON.stringify([{
    status: "completed",
    conclusion: "success",
    headSha,
    url: "https://github.com/PostTrainLLM/posttrainllm/actions/runs/123",
  }]));
  process.exit(0);
}
if (args[0] === "workflow" && args[1] === "run") process.exit(0);
process.exit(2);
`;

  try {
    for (const [name, contents] of Object.entries({ git, gh })) {
      const executable = path.join(bin, name);
      await writeFile(executable, contents);
      await chmod(executable, 0o755);
    }

    const logPath = path.join(root, "gh.jsonl");
    const result = spawnSync(
      process.execPath,
      [script, "deploy.yml", "ci.yml"],
      {
        cwd: root,
        encoding: "utf8",
        env: {
          ...process.env,
          PATH: `${bin}${path.delimiter}${process.env.PATH}`,
          EXPECTED_SHA: "current-main-sha",
          GH_LOG: logPath,
        },
      },
    );

    assert.equal(result.status, 0, result.stderr);
    assert.match(result.stdout, /Dispatching deploy\.yml/);
    const ghCalls = (await readFile(logPath, "utf8"))
      .trim()
      .split("\n")
      .map((line) => JSON.parse(line));
    const runList = ghCalls.find(
      (args) => args[0] === "run" && args[1] === "list",
    );
    assert.ok(runList);
    assert.equal(runList[runList.indexOf("--workflow") + 1], "ci.yml");
    assert.ok(!ghCalls.some((args) => args[0] === "api"));
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
