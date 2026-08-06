## Context

The Astro browser site already keeps educational pages in a typed
`educationContent` registry rendered by a shared editorial component. See
`proposal.md` for motivation and the capability spec for observable behavior.

## Goals / Non-Goals

**Goals:**

- Add two routes through the existing content and metadata model.
- Explain hardware, training, evaluation, and artifact boundaries with primary sources.
- Connect exact comparison intent to existing Mac and MLX guides.

**Non-Goals:**

- Run training, publish models, add dependencies, or change runtime behavior.
- Claim a cross-platform speed, memory, or quality result.
- Deploy or redesign the browser site.

## Decisions

1. Extend `educationContent` and render with `EditorialPage`. This keeps page
   metadata, structured data, and visual language consistent. A new comparison
   subsystem was rejected as unnecessary.
2. Use separate exact-intent pages for Unsloth and Axolotl. Combining them into a
   generic tools list was rejected because their Mac-support boundaries differ.
3. Treat hardware-support statements as dated primary-source observations. The
   pages will link to official requirements because these boundaries can change.

## Risks / Trade-offs

- [Framework support changes] -> Show a checked date and official source links.
- [Readers infer an unrun benchmark] -> Explicitly state the missing controlled run
  and prohibit performance superiority claims.
- [Pages become disconnected from product proof] -> Link to the existing Mac,
  MLX, evaluation, artifact, and recipe surfaces.

## Migration Plan

Land the two static routes and registry changes on a source branch. A later manual
site deployment can publish them. Rollback is a normal source revert; no model,
data, or runtime migration exists.
