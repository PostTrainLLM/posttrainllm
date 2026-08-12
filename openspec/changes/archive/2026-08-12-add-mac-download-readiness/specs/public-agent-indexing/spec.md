## ADDED Requirements

### Requirement: Mac release state discovery
The public agent catalog and full LLM index SHALL expose the canonical Mac download page and its public machine-readable release record while preserving the release record's fail-closed availability state.

#### Scenario: Mac app is not yet downloadable
- **WHEN** the public release record does not pass every download eligibility gate
- **THEN** agent-readable surfaces identify the release as unavailable or pending
- **AND** they do not describe the artifact as ready to download

#### Scenario: Mac app becomes verified and downloadable
- **WHEN** the public release record passes every download eligibility gate
- **THEN** agent-readable surfaces identify the verified release and its canonical download page
- **AND** the machine-readable release record is cataloged as a public resource rather than an HTML page

