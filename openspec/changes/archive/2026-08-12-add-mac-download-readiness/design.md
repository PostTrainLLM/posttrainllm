## Context

See `proposal.md` for motivation. The public product is a statically built Astro site under `browser/`; its sitemap, Markdown counterparts, `/api/ai`, and LLM indexes are generated from build output. The current signed Mac candidate is version 0.1.0 (build 1), requires macOS 14 or later, and is not notarized, stapled, or Gatekeeper-approved. The existing dark Local Research Bench design system is the visual source of truth.

## Goals / Non-Goals

**Goals:**

- Make one version-controlled record authoritative for human- and agent-readable Mac release state.
- Make an accidental link to an incomplete or unverified artifact structurally difficult.
- Add the distribution surface as a restrained extension of the existing product site.
- Keep the release-state evaluator small, deterministic, and directly testable.

**Non-Goals:**

- Hosting, uploading, notarizing, stapling, or publishing the DMG.
- Automatic promotion from candidate to downloadable release.
- Changing the Mac app binary or the Python/ML training runtime.
- Reworking the homepage, primary navigation, visual system, or product positioning.

## Decisions

### Keep one source record and derive eligibility

Add a typed, version-controlled release record under `browser/src/data/` and a small pure evaluator under `browser/src/lib/`. The source record holds factual fields; `downloadable` is derived and cannot be asserted independently. The evaluator returns unavailable on unknown fields, malformed values, non-HTTPS URLs, or any false verification gate.

This is preferable to duplicating frontmatter or copy across the page, JSON endpoint, and agent builder because duplicated readiness claims can drift. A remote CMS or runtime API was rejected because it would add availability, authentication, and secret-management concerns to static release truth.

### Expose only evaluated public metadata

Add a static JSON route for the evaluated release record. The response may include the artifact URL only when the evaluator considers the release downloadable; while pending, the public payload reports factual status and a null download URL. The download page consumes the same evaluated result at build time.

This is preferable to shipping a disabled anchor containing an unverified URL, which would still expose the artifact to users, crawlers, and page-source inspection.

### Use a dedicated page with a restrained homepage entry point

Create `/download` using the existing dark instrument styling, typography, tokens, and shared header conventions. The page will lead with honest release state, then show compact platform and verification details. A small contextual link on the homepage will provide discovery without changing primary navigation labels or displacing the research workflow.

A homepage download hero was rejected because it would over-weight distribution before the candidate is notarized. A navigation-wide redesign was rejected as unrelated scope.

### Extend the existing agent-surface generator

Astro will add `/download` to the canonical HTML inventory automatically. The agent builder will catalog the generated release JSON as a machine resource and add a concise Mac-app status link to the full index. Existing checks will be extended to assert that the JSON never exposes a download URL while eligibility is false.

This keeps agent discovery inside the existing inventory boundary instead of introducing a second indexing path.

### Require deliberate artifact-host approval

The evaluator will accept only an HTTPS URL matching a narrow approved release-host policy encoded alongside the release logic. Adding or changing an allowed host remains a reviewed code change; a metadata edit alone cannot redirect the public download to an arbitrary domain.

The first host can be selected when the notarized artifact is ready. GitHub Releases under the `PostTrainLLM/posttrainllm` organization is the recommended option because it provides immutable tagged assets and avoids storing a large DMG in the website repository.

## Risks / Trade-offs

- [A stale source record can leave a verified build marked pending] → Treat this as a safe failure; update the record only from the notarization handoff and verify the built output before deployment.
- [A binary could change behind an unchanged URL] → Publish the SHA-256 beside the link and require checksum verification before eligibility.
- [An allowlisted host could still serve a replaced asset] → Prefer an immutable tagged release URL and keep the checksum authoritative.
- [A new page can visually drift from the site] → Classify the work as a preserve change and validate browser evidence at 390, 768, and 1440 pixels before completion.
- [Agent copy can overstate readiness] → Generate status from evaluated metadata and add pending/available tests to the agent-surface checks.

## Migration Plan

1. Land the page, metadata endpoint, evaluator, tests, and agent-index integration with version 0.1.0 (build 1) marked `pending-notarization` and no public artifact URL.
2. Build and review the site at required widths; keep the download action absent in all pending-state outputs.
3. Deploy the pending-status surface through the repository's existing manual production workflow.
4. After personal-account notarization, stapling, Gatekeeper assessment, checksum verification, and host approval, update the release record in a separate reviewed change.
5. Rebuild, inspect the human and machine surfaces, and deploy the verified release manually.

Rollback is a normal revert of the website change. Because the first state exposes no artifact, rollback does not need to revoke a binary.

## Open Questions

- Confirm the final approved HTTPS artifact host before the verified release-record update. GitHub Releases is recommended; this does not block the pending-status implementation.
