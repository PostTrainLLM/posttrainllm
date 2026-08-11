## Why

PostTrainLLM has a signed macOS distribution candidate, but its website does not yet provide an accurate, fail-closed path from product discovery to a verified download. The site should communicate release readiness now while preventing an unnotarized or otherwise unverified DMG from becoming public.

## What Changes

- Add a dedicated `/download` surface for the PostTrainLLM Mac app, linked unobtrusively from the existing homepage.
- Show the current release state, supported platform, version, and verification status using the existing Local Research Bench visual language.
- Keep the download action disabled unless release metadata explicitly marks an artifact as notarized, stapled, Gatekeeper-accepted, checksum-verified, and hosted at an approved HTTPS URL.
- Publish the same release truth through a machine-readable public metadata endpoint so the website and agent-readable surfaces cannot drift.
- Preserve the current public routes, primary navigation, product copy, analytics identifiers, legal copy, and existing research-oriented presentation.
- Do not upload a binary, notarize an artifact, introduce automatic production release, or access credentials as part of this change.

## Capabilities

### New Capabilities

- `mac-download-readiness`: Defines the public Mac release-status surface, machine-readable release metadata, and the fail-closed rules governing when a DMG download may be exposed.

### Modified Capabilities

- `public-agent-indexing`: Extends the existing agent-readable product surface so Mac release availability and verification state are discoverable without overstating readiness.

## Impact

- Affects the Astro website under `browser/`, including a new download route, a restrained homepage entry point, shared release metadata, and agent-indexing output.
- Adds no production dependency and changes no Python training/runtime behavior.
- Requires a separately approved, notarized DMG host URL and checksum before the public download can become active.
- Production deployment remains manual and outside this proposal's implementation scope.
