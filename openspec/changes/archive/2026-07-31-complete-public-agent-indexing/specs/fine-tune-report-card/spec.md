## MODIFIED Requirements

### Requirement: Stable machine and public outputs
The compiler SHALL emit versioned JSON and a deterministic static public report
from the same validated payload, and the public report SHALL include a canonical
URL, indexability directives, social-preview metadata, and structured data
without changing the validated decision semantics.

#### Scenario: Output is rebuilt
- **WHEN** the same source artifacts and compiler version are processed twice
- **THEN** substantive JSON and public report content are identical

#### Scenario: Third party reads the report
- **WHEN** a visitor opens a published report without the repository or a GPU
- **THEN** the visitor can inspect the decision, measurements, caveats, and
  source evidence links

#### Scenario: Search or social crawler reads the report
- **WHEN** a published report page is fetched
- **THEN** its metadata identifies the stable canonical report URL and accurately
  summarizes the same validated payload
- **AND** no metadata upgrades or reinterprets the canonical decision
