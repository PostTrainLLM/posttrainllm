#!/usr/bin/env node
import { execSync } from 'node:child_process';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = join(root, '../browser/src/content/docs/');
const dest = join(root, 'docs/');
execSync(
  `rsync -a --delete --include='*/' --include='*.md' --include='*.mdx' --exclude='*' "${src}" "${dest}"`,
  { stdio: 'inherit' }
);
console.log('Synced content from browser/src/content/docs → docs/');
