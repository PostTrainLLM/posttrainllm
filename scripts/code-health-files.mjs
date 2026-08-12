import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

function git(args, allowFailure = false) {
  const result = spawnSync("git", args, { encoding: "utf8" });
  if (!allowFailure && result.status !== 0) {
    process.stderr.write(result.stderr);
    process.exit(result.status ?? 1);
  }
  return result;
}

function comparisonBase() {
  const candidates = [process.env.CODE_HEALTH_BASE, "origin/main", "HEAD^"];
  for (const candidate of candidates.filter(Boolean)) {
    if (candidate === "0000000000000000000000000000000000000000") continue;
    if (
      git(["rev-parse", "--verify", `${candidate}^{commit}`], true).status !== 0
    )
      continue;
    const mergeBase = git(["merge-base", "HEAD", candidate], true);
    return mergeBase.status === 0 ? mergeBase.stdout.trim() : candidate;
  }
  return null;
}

export function changedFiles(extensions) {
  const base = comparisonBase();
  const files = new Set();
  if (base) {
    const result = git(["diff", "--name-only", "--diff-filter=ACMR", base]);
    for (const file of result.stdout.split("\n")) files.add(file);
  }
  const untracked = git(["ls-files", "--others", "--exclude-standard"]);
  for (const file of untracked.stdout.split("\n")) files.add(file);
  return [...files]
    .filter(Boolean)
    .filter((file) => extensions.some((extension) => file.endsWith(extension)))
    .filter((file) => !file.includes("/archive/"))
    .filter((file) => !file.includes("/coverage/") && !file.includes("/dist/"))
    .filter((file) => {
      try {
        readFileSync(file);
        return true;
      } catch {
        return false;
      }
    })
    .sort();
}

export function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    stdio: "inherit",
    ...options,
  });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

export function capture(command, args, options = {}) {
  const { allowFailure = false, ...spawnOptions } = options;
  const result = spawnSync(command, args, {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
    ...spawnOptions,
  });
  if (result.status !== 0 && !allowFailure) {
    process.stdout.write(result.stdout);
    process.stderr.write(result.stderr);
    process.exit(result.status ?? 1);
  }
  return result;
}

export function commandWithUvx(command, uvxArguments) {
  const probe = spawnSync(command, ["--version"], { encoding: "utf8" });
  return probe.error
    ? { command: "uvx", prefix: uvxArguments }
    : { command, prefix: [] };
}
