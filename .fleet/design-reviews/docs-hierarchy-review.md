# Course-first docs release review — 2026-09-29

Method: single-context visual and technical review of the public Cloudflare deployment at `f0e5dfd`; owner selected Course workspace. The browser showed `/docs/`, `/docs/learn/`, `/docs/library/`, and `/docs/learn/legacy-walkthrough/`. The Learn page was captured at 390, 768, and 1440 px. The 390 px navigation drawer exposed all six named groups.

## Critique — 35/40

| Heuristic | Score | Evidence |
| --- | ---: | --- |
| System status | 3 | Active page and current learning are visible; the course has no automatic progress claim. |
| Match to learner language | 4 | Start, repair, explore, and archive labels match the learning task. |
| Control and freedom | 4 | All shelves remain reachable; the historic walkthrough has a clear route. |
| Consistency | 4 | Blume navigation, page titles, and Markdown mirrors use the existing system. |
| Error prevention | 3 | One Next Session reduces competing assignments; links still need learner judgment. |
| Recognition | 4 | Current route, Week 1, and reference shelves are named directly. |
| Flexibility | 3 | Search and library map reach long-tail articles; some sidebar titles truncate visually. |
| Minimal design | 3 | Restrained reading layout; the reference shelf is necessarily dense. |
| Recovery | 3 | Breadcrumbs, sidebar, and page links provide return paths. |
| Help and documentation | 4 | Week contract, prerequisites, and library map are linked at point of need. |

The hierarchy is specific to the Mac-local inference sprint and retained factory corpus. P2: long sidebar titles truncate in narrow navigation, though the accessible link names remain complete. No P0 or P1 finding was observed.

## Technical audit — 17/20

| Dimension | Score | Evidence |
| --- | ---: | --- |
| Accessibility | 3 | One visible H1, named navigation controls, semantic links, and a validated internal-link graph. A full WCAG audit was outside this release. |
| Performance | 4 | Static generated pages, no new runtime dependency or animation. |
| Responsive | 4 | 390/768/1440 px full-page captures; no horizontal overflow; mobile drawer works. |
| Theming | 3 | Existing Blume dark theme and project tokens retained; theme switching was not separately audited. |
| Integrity | 3 | Source headings remain in Markdown mirrors; built pages have one visible H1. Detector returned no findings; old design sidecar remains stale. |

`pnpm --dir browser build` passed: 319 docs merged, 536 agent-readable page pairs, 31,787 internal links and 10,261 fragments checked. The Impeccable detector returned `[]` for the changed docs and theme targets. The old `.impeccable/design.json` sidecar predates `DESIGN.md`; refreshing it is a separate design-maintenance task.
