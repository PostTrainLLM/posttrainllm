# Specialist Factory Walkthrough Specification

## ADDED Requirements

### Requirement: One coherent factory journey

The public site SHALL provide a statically rendered walkthrough whose primary
sequence is `target -> data -> post-training -> eval -> package -> report`.

#### Scenario: A new visitor opens the walkthrough

- **WHEN** the visitor loads `/learn`
- **THEN** the complete factory sequence is visible without client JavaScript
- **AND** each stage explains the question it answers and the artifact it emits

### Requirement: Canonical evidence links

Every walkthrough chapter SHALL link to at least one canonical repository
document and one relevant source module or executable entrypoint.

#### Scenario: A reader wants implementation detail

- **WHEN** the reader reaches a chapter
- **THEN** they can open the canonical explanation and exact code from that chapter
- **AND** the walkthrough does not present copied prose as a new source of truth

### Requirement: Honest case-file states

The walkthrough SHALL distinguish shipped improvements, routed specialists,
rejected attempts, failed benchmark rulers, and unqualified candidates.

#### Scenario: Negative evidence is displayed

- **WHEN** Character 2048 or candidate chess evidence appears
- **THEN** its failed or unqualified state is visible beside the result
- **AND** no specialist win or qualified rating is implied

### Requirement: Crawlable editorial surface

The walkthrough SHALL ship as full static HTML with a unique title,
description, canonical URL, social metadata, structured data, sitemap entry,
Markdown counterpart, and agent-catalog entry.

#### Scenario: A crawler does not execute JavaScript

- **WHEN** it requests the built walkthrough document
- **THEN** the heading, chapters, evidence states, and links are present in HTML

### Requirement: Accessible responsive reading

The walkthrough SHALL preserve logical heading order, visible focus, semantic
links, readable measures, and no horizontal page overflow at 390, 768, and
1440 CSS pixels.

#### Scenario: A keyboard or narrow-screen reader uses the walkthrough

- **WHEN** they navigate the page
- **THEN** all primary content and links remain reachable and legible
- **AND** the chapter sequence remains understandable without decorative graphics
