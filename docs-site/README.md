# posttrainllm docs (Blume)

AI-ready documentation site powered by [Blume](https://github.com/haydenbleasel/blume).

## Why Blume

- `llms.txt` + `llms-full.txt` generated from the full corpus
- Every page available as raw markdown at `{route}.md`
- Sitemap, OG, robots, agent-readability manifest
- Static HTML (fast CWV) for Cloudflare Pages

## Develop

Requires Node.js **22.12+**.

```bash
pnpm install
pnpm dev
```

## Build

```bash
pnpm build   # → dist/
```

## Content

`docs/` is a copy of `browser/src/content/docs` (285 files). Re-sync with:

```bash
rsync -a --delete --include='*/' --include='*.md' --include='*.mdx' --exclude='*' \
  ../browser/src/content/docs/ docs/
# then re-run frontmatter normalizer if needed
```

## Deploy

Cloudflare Pages:

- Build command: `pnpm build`
- Output: `dist`
- Root directory: `docs-site`
- Custom domain (recommended): `docs.posttrainllm.com`

Until the custom domain is wired, you can also ship `dist/` under a Pages preview URL.
