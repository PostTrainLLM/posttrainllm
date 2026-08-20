---
score: 37
maximum: 40
p0: 0
p1: 0
timestamp: 2026-08-20T14-08-58Z
slug: scripts-offhours-report-py
---
# OffHours standalone report critique

## Outcome

37/40. P0: 0. P1: 0. P2: 1.

The preserve-lane report now meets the professional research-artifact bar. It
has an explicit evidence ladder with separate fixture, unqualified measured,
qualified, and public-comparison states; synthetic metrics are persistently
labeled; and the fixture footer cannot be mistaken for a null model result.

## What works

- The research sequence moves from qualification to absolute quality, paired
  effects, recovery, behavior, provenance, and interpretation limits.
- Fixture, measured, qualified, and public evidence states cannot silently
  collapse into one another.
- Dense charts retain accessible adjacent tables, mobile scroll cues, sticky
  row labels, SVG titles and descriptions, and print-safe contrast.
- The artifact is deterministic, self-contained, and requires no network
  requests, scripts, images, or hidden reasoning.

## Review closure

- P1: fixture PASS styling and null-result ambiguity — fixed with DEMO gates,
  persistent fixture labels, a fixture-specific closing, and regression tests.
- P1: failed measured runs mapped to Fixture preview — fixed with an explicit
  Unqualified measured run stage and regression test.
- P1: overlapping or missing recovery series — fixed with composite overlap
  disclosure and segmented paths.
- P1: inaccessible horizontal evidence — fixed with cues, sticky row headers,
  and accessible value tables.
- Detector advisories: undocumented amber and 7px radius — fixed using the
  documented palette and 9px scale; detector not rerun under the one-pass rule.
- Print neutral series — fixed with a print-specific high-contrast SVG rule and
  verified through an eight-page A4 render.

## Remaining P2

Typography uses deliberate system fallbacks when Bricolage or Geist is not
installed. This is documented as a portability tradeoff: the standalone file
does not bundle fonts or make network requests.
