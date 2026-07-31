# public-agent-indexing Specification

## Purpose
TBD - created by archiving change complete-public-agent-indexing. Update Purpose after archive.
## Requirements
### Requirement: Source-derived canonical route inventory
The browser build SHALL derive the public HTML inventory from generated Astro
and Blume sitemaps plus published report-card HTML, normalize equivalent route
forms, and MUST reject cross-origin, duplicate, redirect-only, or non-HTML page
entries.

#### Scenario: All public generators complete
- **WHEN** the browser, documentation, and report-card surfaces are assembled
- **THEN** the merged inventory contains every unique canonical public HTML URL
- **AND** no API, JSON, RSS, redirect, or private/local artifact is counted as a
  page

### Requirement: Complete agent-readable counterparts
Every canonical public HTML page SHALL have a same-origin Markdown counterpart
derived from the same source or rendered content, with a title and substantive
page information.

#### Scenario: Catalog integrity is checked
- **WHEN** agent surfaces are generated
- **THEN** every catalog page URL is present in the merged sitemap
- **AND** every referenced Markdown file exists and contains substantive text

### Requirement: Unified public discovery
The build SHALL publish one root sitemap, one `/api/ai` catalog, and concise and
full `llms.txt` indexes from the same normalized inventory, and robots and
page-level sitemap metadata SHALL point to that merged sitemap.

#### Scenario: A crawler starts at robots
- **WHEN** a crawler follows the advertised sitemap and catalog
- **THEN** it can discover all canonical public HTML pages and their Markdown
  counterparts from consistent route truth

### Requirement: Page and resource boundary
The agent catalog MUST distinguish canonical HTML pages from intentionally
public machine or data resources and MUST NOT expose model files, local runs,
private artifacts, or unpublished evidence.

#### Scenario: A public JSON report exists beside an HTML report
- **WHEN** the catalog is built
- **THEN** the HTML report is listed as a page with Markdown
- **AND** its JSON payload is listed only as a machine resource, if listed

### Requirement: Decision authority preservation
Agent-readable report-card output SHALL faithfully represent the validated
public report and MUST NOT infer, upgrade, or replace its canonical decision.

#### Scenario: Report Markdown is generated
- **WHEN** a report card is converted to an agent-readable counterpart
- **THEN** its outcome and caveats match the deterministic HTML report
- **AND** `decision.json` remains the terminal quality and product authority

