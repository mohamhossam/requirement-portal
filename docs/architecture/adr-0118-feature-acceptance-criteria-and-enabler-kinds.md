# ADR-0118 — Feature-level acceptance criteria and business/enabler work kinds

Status: Accepted
Date: 2026-10-15

## Context

The breakdown model followed SAFe's hierarchy (AGENTS.md §6) but deviated from
the published definitions in two places:

- SAFe defines a Feature as a phrase, a benefit hypothesis **and acceptance
  criteria** — the conditions Product Management confirms the Feature by.
  Guardrail 4 of the feature prompt forbade acceptance criteria at the Feature
  level, so the only checkable conditions lived on Stories.
- SAFe types every Feature and Story as business work or an **enabler**
  (exploration, architecture, infrastructure, compliance). The application
  already produced enablers in all but name — discovery Stories, the explicit
  security/compliance Feature of guardrail 7, `component_system` splits — but
  nothing recorded the type, so a reviewer could not tell runway from customer
  value without reading every outcome.

## Decision

- `Feature` carries `acceptance_criteria: tuple[FeatureAcceptanceCriterion, ...]`
  — plain checkable conditions, deliberately not Given/When/Then, which remains
  the Story register. Generation supplies at least one (`feature-v8`, schema
  `min_length=1`); the domain permits an empty tuple so Features persisted
  before the field existed stay loadable and editable.
- `Feature` and `UserStory` carry `kind: WorkKind` — `business` (default) or one
  of the four SAFe enabler kinds. Generation types every item (`feature-v8`,
  `story-v8`); humans can retype on edit; manual split/merge keeps the source's
  kind.
- **Compatibility is default-elision.** Persisted payloads, approval
  fingerprints (ADR-0021) and review-evidence fingerprints write the new fields
  only at non-default values, so rows written and approvals recorded before
  this change re-encode byte-for-byte and stay current (the golden files prove
  it). The neutral export becomes schema 1.6 → 1.7 with defaulted additions;
  ADO publication renders the new fields as description rows only when present,
  so republishing an older handoff renders the card it always did.
- Story generation-context tokens change once (the state fingerprint now sees
  `kind`), which clients heal by reloading — the documented behaviour for
  changed generation evidence.

## Consequences

- An Epic's Feature list now shows what SAFe expects a Product Manager to see:
  the benefit hypothesis, the conditions of satisfaction and whether the item
  is runway or customer value. Exports, the XLSX workbook and ADO work items
  carry both fields.
- The INVEST evaluator keeps assessing Stories semantically; a discovery Story
  is now also *labelled* exploration rather than only recognisable by its
  wording. Deterministic policy on kinds (for example "an exploration Story
  must name its decision artifact") is possible later without re-reading prose.
- Feature-level criteria are conditions for Product Management, not a second
  test register: nothing generates Given/When/Then at the Feature level, and
  the UI renders them as a plain list.
