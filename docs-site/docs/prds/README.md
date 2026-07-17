---
title: "docs/prds/ — Product Requirement Briefs"
description: "Active work starts in `../NEXT.md`, not here."
---

# docs/prds/ — Product Requirement Briefs

> **Status: reference.**
>
> This directory is not the active queue. Start with [`../README.md`](../README.md)
> and [`../NEXT.md`](../NEXT.md). Use PRDs only when the active factory plan
> names one or needs acceptance criteria.

Active work starts in [`../NEXT.md`](../NEXT.md), not here.

Use this directory only when the active factory plan points to a PRD or when
you need exact acceptance criteria for a deferred lane.

## Start Here

1. Read [`../../PROJECT_STATUS.md`](../../PROJECT_STATUS.md).
2. Read [`../NEXT.md`](../NEXT.md).
3. Read [`../factory/`](../factory/).
4. Use [`PRIORITY.md`](PRIORITY.md) to find the relevant PRD.
5. Open the PRD file only if it is P0/P1 for the current target or explicitly
   named by the task.

## Current Triage

[`PRIORITY.md`](PRIORITY.md) is the working map for all PRDs on disk:

- **P0** — build next for the first canonical factory run.
- **P1** — useful immediately after the first candidate exists.
- **P2** — later support.
- **P3** — parked research.
- **Archive candidates** — shipped, superseded, negative-result closed, or
  upstream-blocked.

Per-PRD frontmatter is stale in many files. `PRIORITY.md` and
[`STATUS.md`](STATUS.md) win over frontmatter when they disagree.

## Do Not

- Do not pick a broad PRD just because it exists.
- Do not revive browser/WebGPU, ANE/CoreML, VLM, Tier 5, broad app polish, or
  coding-agent product work unless it directly unblocks the current factory run.
- Do not write a new PRD for exploratory research. Record exploration in a
  short session note or factory report instead.

## Archive Policy

This repo uses a soft archive first. Closed/superseded PRDs stay in place but
are listed under `PRIORITY.md` archive candidates.

Physically moving PRDs is allowed only when links are updated in the same
change. This avoids breaking old session docs and PLAN references.

## Coordination Rule

Every PRD's "don't touch" section names files that can conflict under parallel
agent work. For the current factory push, prefer the new factory docs and avoid
editing global dispatch/status files unless the task explicitly requires it.
