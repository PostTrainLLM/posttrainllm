---
target: OffHours persistent-tension publication report
total_score: 20
max_score: 32
na_heuristics: 3,9
p0_count: 0
p1_count: 3
timestamp: 2026-08-21T05-19-45Z
slug: lts-devin-glm52-persistent-tension-2026-08-21-html
---
Method: dual-agent (A: /root/offhours_visual_a · B: /root/offhours_visual_b)

# Design Health Score

| # | Heuristic | Score | Key issue |
| --- | --- | ---: | --- |
| 1 | Visibility of system status | 2 | Passed task gates, held qualification, and unqualified maturity are not reconciled. |
| 2 | Match system / real world | 3 | Strong research language; a few terms need inline definition. |
| 3 | User control and freedom | n/a | Static read-only evidence artifact. |
| 4 | Consistency and standards | 3 | Cohesive system, but teal also marks provenance-limited evidence. |
| 5 | Error prevention | 2 | The failed no-context-truncation check is not visible. |
| 6 | Recognition rather than recall | 3 | Primary estimate is buried among controls. |
| 7 | Flexibility and efficiency | 2 | No TOC, deep links, or artifact links. |
| 8 | Aesthetic and minimalist design | 3 | Calm composition; mobile delays the finding. |
| 9 | Error recovery | n/a | No editable action or recovery flow. |
| 10 | Help and documentation | 2 | No glossary, invocation, or linked evidence paths. |
| **Total** |  | **20/32** | **Acceptable; evidence hierarchy needs work.** |

# Design Specificity Verdict

The report is strongly product-specific: its local-research-bench palette,
qualification gates, paired-workday sequence, evidence ladder, provenance
ledger, and restrained typography could not be reused unchanged by unrelated
SaaS. The visual system is close to publication grade; the remaining material
issues concern evidence semantics and hierarchy.

The isolated detector found one advisory only: print-specific `#111` falls
outside DESIGN.md. It is an intentional high-contrast monochrome print override,
not screen-theme drift. Supplied true-width captures show no page-level overflow
at 390, 768, or 1440 pixels. Browser overlay injection was unavailable because
the assessment environment exposed no browser; screenshot and source geometry
were used as fallback evidence.

# Overall Impression

The artifact reads like an evidence instrument rather than a dashboard. Its
largest opportunity is to make qualification truth and the primary paired null
as precise visually as they already are in the machine-readable analysis.

# What's Working

- The wide editorial composition and research-bench visual language are
  distinctive, calm, and grounded in the product.
- Status, maturity, uncertainty, missing provenance, limitations, and raw values
  all have deliberate structures.
- Semantic HTML, SVG descriptions, table captions/scopes, text labels,
  reduced-motion handling, print rules, and narrow-width reflow form a strong
  accessibility foundation.

# Priority Issues

1. **[P1] Qualification states are irreconcilable.** Render the missing
   no-context-truncation evidence as its own held gate, distinguish task quality
   from provenance completeness, and label unattached ceiling evidence exactly.
2. **[P1] Closing copy overstates the null.** Replace “work quality did not” with
   “no work-quality penalty was detected,” retaining the estimate, interval,
   five paired days, and provenance limitation.
3. **[P1] Charts conceal the evidence scale.** Use a declared low-error recovery
   domain with ticks and give the effect plot stable percentage-point ticks.
4. **[P2] Mobile readers reach the estimate too late.** Move a compact result
   abstract before the four-step sequence at 390 px.
5. **[P2] The primary estimate is visually buried.** Add a labeled primary
   unresolved-minus-resolved band and group other effects as controls.

# Persona Red Flags

- **Alex, power user:** cannot extract estimate, interval, qualification, and
  next action in the first mobile viewport; no direct artifact links.
- **Sam, accessibility-dependent:** strong semantics, but the qualification
  contradiction is costly in linear reading; small muted text is only narrowly
  above AA and horizontal evidence regions need explicit labels/focus treatment.
- **Priya, Mac-local ML practitioner:** hashes and seeds are visible, but exact
  invocation, hardware/OS, and direct config/JSON/Markdown links are absent.

# Minor Observations

- Named fonts are not embedded, so a shared standalone file can reflow under
  system fallbacks.
- The 2x2 mobile evidence ladder weakens the continuous maturity sequence.
- The lone detector advisory is an intentional print-only palette override.

# Questions to Consider

- What exact claim and caveat must travel together in the first phone viewport?
- Is the six-condition apparatus the subject, or support for one primary
  resolved-versus-unresolved comparison?
- Should narrative and audit layers be more explicitly separated?

Questions skipped: the three P1 evidence defects and their fixes are concrete,
and the active parent workflow requires resolving them before completion.
