## Purpose

Define public comparisons that explain PostTrainLLM's Apple Silicon-first factory
against adjacent training frameworks without unsupported performance claims.

## ADDED Requirements

### Requirement: Direct training-framework comparisons
The site SHALL publish canonical comparison pages for Unsloth and Axolotl using
the existing public editorial surface.

#### Scenario: Visitor opens a comparison
- **WHEN** a visitor requests either approved comparison route
- **THEN** the site returns a readable page with a unique title, description, and canonical URL

### Requirement: Current platform boundaries
Each comparison MUST use dated official sources for hardware and framework
support and MUST state that no controlled speed, memory, or quality comparison
has been run.

#### Scenario: Reader chooses a training stack
- **WHEN** a reader compares Apple Silicon and supported accelerator workflows
- **THEN** the page explains where each product fits without inventing parity or superiority

### Requirement: Search and internal discovery
Each comparison SHALL appear in the sitemap and SHALL link to the Mac fine-tuning,
MLX LoRA, evaluation, specialist, artifact, and recipe surfaces where relevant.

#### Scenario: A crawler discovers the page
- **WHEN** a crawler follows the site's generated sitemap or internal links
- **THEN** it can retrieve the comparison and navigate to supporting first-party evidence
