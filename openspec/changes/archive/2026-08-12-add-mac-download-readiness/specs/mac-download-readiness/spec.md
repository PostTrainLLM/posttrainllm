## Purpose

Defines a trustworthy public path for discovering the PostTrainLLM Mac app while preventing any unverified distribution artifact from being presented as downloadable.

## ADDED Requirements

### Requirement: Dedicated Mac release surface
The public website SHALL provide a canonical Mac download page that identifies the product, current version, supported macOS version, release state, and verification state in user-readable language.

#### Scenario: Release is still being prepared
- **WHEN** a visitor opens the Mac download page before every release gate has passed
- **THEN** the page states that the signed build is not yet available for download
- **AND** it does not render an active artifact link

#### Scenario: Release is verified and available
- **WHEN** a visitor opens the Mac download page after every release gate has passed
- **THEN** the page presents the verified version and an active HTTPS download action
- **AND** it exposes the artifact checksum for independent verification

### Requirement: Fail-closed download eligibility
The website MUST expose an active DMG download only when one release record simultaneously declares an available state, a non-empty version and build, a supported macOS version, a 64-character SHA-256 checksum, an approved HTTPS artifact URL, and successful notarization, stapling, Gatekeeper assessment, and checksum verification.

#### Scenario: One verification gate is absent or false
- **WHEN** any required field is missing, malformed, or does not affirm success
- **THEN** the release is treated as unavailable
- **AND** no user-facing element links to the artifact URL

#### Scenario: All verification gates pass
- **WHEN** every required release field is present and valid
- **THEN** the release may be presented as available
- **AND** the public status accurately lists the completed verification gates

### Requirement: Shared release truth
Human-readable and machine-readable release surfaces SHALL derive from one version-controlled release record and SHALL present the same version, build, platform requirement, availability, verification state, artifact URL eligibility, and checksum.

#### Scenario: Release metadata changes
- **WHEN** the version-controlled release record is updated and the site is rebuilt
- **THEN** the download page and machine-readable output reflect the same resulting state
- **AND** contradictory hand-maintained availability copy is not required

### Requirement: Restrained product entry point
The existing product site SHALL provide a discoverable link to the Mac download page without replacing the current research workflow or overstating an unavailable release.

#### Scenario: Visitor enters through the homepage
- **WHEN** the Mac release is pending or available
- **THEN** the visitor can navigate to its canonical status page
- **AND** the entry point uses release-state language consistent with the shared release record

