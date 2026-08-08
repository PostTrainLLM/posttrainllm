# published-model-case-studies Specification

## Purpose
TBD - created by archiving change publish-all-model-case-studies. Update Purpose after archive.
## Requirements
### Requirement: Complete public model inventory

The public artifact surface SHALL contain one case study for every public model
repository owned by the PostTrainLLM Hugging Face organization.

#### Scenario: A model is publicly downloadable

- **WHEN** a visitor scans `/artifacts`
- **THEN** every public PostTrainLLM model is represented by a first-class card
- **AND** each card links to a dedicated static detail page and its Hub repo

### Requirement: Evidence-grounded case-study shape

Every model case study SHALL state the problem or artifact purpose, measured or
recorded evidence, comparison context, limitations, decision, and next action.

#### Scenario: Evidence is incomplete

- **WHEN** a model has public weights but no current reproducible eval
- **THEN** the case study labels the result as historical, inconclusive,
  conversion-only, rejected, or missing evidence as appropriate
- **AND** it does not infer a win from the existence of weights

### Requirement: Negative results remain first-class

Rejected and regressed public models SHALL receive the same discoverable
case-study treatment as successful specialists.

#### Scenario: A model regressed breadth

- **WHEN** the multibackend-distilled model is displayed
- **THEN** its preserved 100% depth and 31% breadth are shown together
- **AND** the page states that it is a failed negative-transfer artifact

### Requirement: Adoption claims fail closed

Public Hub request counters SHALL NOT be described as unique people, confirmed
users, full model downloads, or successful model runs.

#### Scenario: Hub metadata reports downloads

- **WHEN** publication metadata is reviewed
- **THEN** it may establish that the repository is public
- **AND** it is excluded from adoption claims unless independent user evidence
  exists

### Requirement: Crawlable case-study publication

Every model case study SHALL be emitted as full static HTML and included in the
site's generated Markdown, sitemap, and agent-readable catalog surfaces.

#### Scenario: A crawler does not execute JavaScript

- **WHEN** it requests a model artifact route
- **THEN** the claim, evidence, decision, blockers, and Hub link are present in
  the response HTML

