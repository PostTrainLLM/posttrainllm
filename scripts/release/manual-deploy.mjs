#!/usr/bin/env node
import { execFileSync } from 'node:child_process';

const [workflowFile, ciWorkflowFile = 'ci.yml'] = process.argv.slice(2);

if (!workflowFile) {
  fail('Usage: manual-deploy.mjs <deploy-workflow.yml> [ci-workflow.yml]');
}

function run(command, args, options = {}) {
  return execFileSync(command, args, {
    encoding: 'utf8',
    stdio: options.stdio ?? ['ignore', 'pipe', 'pipe'],
  }).trim();
}

function fail(message) {
  console.error(`deploy blocked: ${message}`);
  process.exit(1);
}

function githubSlug() {
  const url = run('git', ['remote', 'get-url', 'origin']);
  if (url.startsWith('git@github.com:')) {
    return url.slice('git@github.com:'.length).replace(/\.git$/, '');
  }
  if (url.startsWith('https://github.com/')) {
    return url.slice('https://github.com/'.length).replace(/\.git$/, '');
  }
  fail(`origin remote is not a GitHub URL: ${url}`);
}

const branch = run('git', ['branch', '--show-current']);
if (branch !== 'main') {
  fail(`current branch is ${branch || 'DETACHED'}, expected main`);
}

const dirty = run('git', ['status', '--porcelain']);
if (dirty) {
  fail('working tree is dirty');
}

run('git', ['fetch', '--quiet', 'origin']);
const upstream = run('git', ['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']);
const [behind, ahead] = run('git', ['rev-list', '--left-right', '--count', `${upstream}...HEAD`])
  .split(/\s+/)
  .map(Number);
if (behind !== 0 || ahead !== 0) {
  fail(`branch is not synced with ${upstream}: ahead ${ahead}, behind ${behind}`);
}

try {
  run('gh', ['auth', 'status']);
} catch {
  fail('gh is not authenticated');
}

const slug = githubSlug();
let ciRuns;
try {
  ciRuns = JSON.parse(
    run('gh', [
      'run',
      'list',
      '-R',
      slug,
      '--workflow',
      ciWorkflowFile,
      '--branch',
      'main',
      '--limit',
      '1',
      '--json',
      'status,conclusion,headSha,url',
    ])
  );
} catch {
  fail(`could not read ${ciWorkflowFile} runs from GitHub`);
}

if (!ciRuns.length) {
  fail(`no ${ciWorkflowFile} run found on main`);
}

const headSha = run('git', ['rev-parse', 'HEAD']);
const ci = ciRuns[0];
if (ci.headSha !== headSha) {
  fail(
    `${ciWorkflowFile} has not run on current main ${headSha.slice(0, 7)}; latest is ${(ci.headSha || 'unknown').slice(0, 7)} ${ci.url || ''}`
  );
}
if (ci.status !== 'completed' || ci.conclusion !== 'success') {
  fail(`${ciWorkflowFile} is not green: ${ci.status}/${ci.conclusion || 'none'} ${ci.url || ''}`);
}

console.log(`Dispatching ${workflowFile} for ${slug}@main`);
execFileSync('gh', ['workflow', 'run', workflowFile, '--ref', 'main'], { stdio: 'inherit' });
