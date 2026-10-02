# ADR 0026 — Analysis-owned question reconciliation and provenance

## Status

Accepted

## Context

ADR-0019 retained a clarification question only when the next analysis returned
the same normalized kind and subject. That deterministic match preserved stable
identity, but could not express that confirmed answers made other questions
obsolete or changed the unresolved gap. Consequently, stale questions remained
active until answered individually, and revised wording lost an explicit link
to the work and draft it replaced.

The provider can make the semantic judgment, but it must not control durable
identity, mutate protected human questions, or partially update application
state.

## Decision

- The application supplies every active question to the analyzer as
  provider-independent context. Human-authored questions are explicitly
  protected; only AI-authored IDs require provider reviews.
- `analysis-v4` returns exactly one `retain`, `retire`, or `replace` review for
  every supplied active AI question plus a separate set of genuinely new
  uncertainties. Adapters reject incomplete, duplicate, unknown, human-targeted,
  blank, inconsistent, duplicate-current, or oversized output as provider
  failure.
- Application-owned `QuestionId` values remain authoritative. Retained
  questions keep identity and metadata. Retired questions become superseded.
  Replacements receive new IDs linked to the old question, inherit assignment,
  severity, and blocker state, and do not copy drafts.
- Each immutable `AnalysisRound` records retained, retired, replaced, and
  created decisions with rationales and replacement links. Questions and
  records remain in audit persistence; only active questions appear in the
  current workspace and confirmation blocker calculation.
- Resolution and reconciliation remain one transaction. After provider work,
  the application rechecks the Requirement version, current analysis identity,
  and the complete active-question ID/version snapshot before persisting any
  resolution, supersession, replacement, analysis, or round.
- Question and round JSON payloads carry optional link/change fields. Missing
  fields represent legacy records honestly; no relational schema change is
  required.

This decision amends only ADR-0019's exact kind-and-subject re-analysis matching
rule. Its identity, lifecycle, access, confirmation, and immutable-round
decisions remain in force.

## Consequences

Reviewers get a smaller current workspace after answers resolve related gaps,
while changed wording has an explicit lineage and archived drafts remain
inspectable. Activity can project supersession from immutable round evidence,
and human-resolution metrics remain limited to actual answers.

Provider output is larger and stricter because every active AI question must be
reviewed. Any unusable response rejects the whole generation, which can require
an existing recovery retry and means no partial progress is saved. Replacement
IDs cannot be known until application mapping, so providers describe content
but never assign durable identity.

## Alternatives Considered

- Continue exact text matching: rejected because it cannot distinguish an
  obsolete question from a semantically revised one.
- Let the model emit stable or replacement IDs: rejected because external
  output must not control application identity or target arbitrary questions.
- Delete obsolete questions: rejected because answers, drafts, attribution,
  and the basis for re-analysis must remain auditable.
- Apply each provider decision as it arrives: rejected because incomplete or
  concurrent reconciliation would leave analysis and questions inconsistent.
