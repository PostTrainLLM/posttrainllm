## Context

The public site is assembled from three independently generated surfaces:
Astro browser pages, Blume documentation, and deterministic fine-tune report
cards. Astro and Blume each emit their own sitemap, Blume already emits
source-derived page Markdown, and the report cards are copied as static HTML.
The checked-in root sitemap and `/api/ai` payload consequently drift from the
actual build and omit most canonical routes.

## Goals / Non-Goals

**Goals:**

- Derive one canonical HTML inventory from build output.
- Give every canonical HTML page an accurate Markdown counterpart.
- Publish one merged sitemap and one catalog with integrity checks.
- Keep public pages, machine/data resources, and private/local artifacts
  explicitly separated.
- Improve report-card discovery metadata without changing report evidence.

**Non-Goals:**

- Training, evaluation, model loading, or modifying factory-run decisions.
- Exposing local runs, model files, or unpublished evidence.
- Replacing Blume's documentation renderer or Markdown output.
- Deployment or changes to production routing.

## Decisions

### Generate the inventory after every constituent build

`build-agent-surfaces.mjs` will run after Astro and Blume have both emitted
their output. It will read their generated sitemaps plus public report-card
HTML files, normalize canonical paths, and reject duplicates or non-HTML
entries. This makes generated output—not a second hand-maintained list—the
route authority.

An authored route manifest was considered, but it would duplicate Astro
filesystem routes and Blume's documentation tree and would recreate the
existing drift risk.

### Preserve native Markdown where it exists

Blume's 297 page-level Markdown files remain canonical. The post-build step
will convert the rendered main content of Astro and report-card HTML into
substantive Markdown for their remaining 27 route records, including the
existing root page. Conversion uses a small repository-local implementation,
not a new production dependency.

### Publish pages and resources in separate catalog fields

The `/api/ai` catalog will list the 324 canonical HTML surfaces with paired
Markdown. RSS, report-card JSON, and other intentionally public machine
resources may be listed separately, while APIs, gallery data, redirects,
models, and local/private run output are never represented as pages.

### Keep report-card generation deterministic

Canonical, Open Graph, Twitter, and structured-data tags will be produced by
the existing deterministic Python renderer and regenerated through the existing
publication script. The validated payload and all decision fields remain
unchanged; `decision.json` remains terminal authority.

## Risks / Trade-offs

- **HTML-to-Markdown loses interactive presentation detail** → Preserve
  headings, paragraphs, lists, tables, code, links, and meaningful image text;
  validate that every file is substantive and tied to the same canonical URL.
- **A future generator changes sitemap shape** → Parse URLs defensively and
  fail the build on missing inputs, cross-origin URLs, duplicates, or orphaned
  Markdown.
- **A static data file is accidentally treated as a page** → Admit routes only
  from the two HTML sitemaps and explicit report-card HTML files, with
  extension and path exclusions.
- **Generated counts become stale** → Compute counts from build output and test
  set equality rather than hard-coding the current total as the algorithm.

## Migration Plan

1. Add and validate the post-build generator.
2. Regenerate report cards with their metadata.
3. Run the complete browser build and focused publication checks.
4. Ship through the normal manual deployment process after review; rollback is
   a source revert and rebuild.

## Open Questions

None. Production deployment remains a separate, manual decision.
