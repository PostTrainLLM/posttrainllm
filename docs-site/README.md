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

**The committed Markdown under `../docs` is the source of truth.** Blume reads
that tree directly via `content.root: '../docs'` in `blume.config.ts`. There is
no copy step and no second docs tree to keep in sync — edit `../docs/*.md` and
rebuild.

`docs-site/docs/` is a gitignored scratch dir (kept only for local
experimentation); never edit it, and never commit it. The old
`scripts/sync-content.mjs` rsync step was removed when Blume was pointed at the
canonical tree.

## Validation

```bash
# From repo root — golden-path + structural checks
python3 scripts/check_docs_world_class.py
```

Wrapped by `evals/docs-world-class-smoke.sh`. Note this check is **not** wired
into CI today — run it locally before changing the docs tree.

## Deploy

Cloudflare Pages:

- Build command: `pnpm build`
- Output: `dist`
- Root directory: `docs-site`
- Custom domain (recommended): `docs.posttrainllm.com`

Until the custom domain is wired, you can also ship `dist/` under a Pages preview URL.
