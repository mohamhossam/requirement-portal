# Ubiquitous language

The terms used in code, API, UI and conversation, and the bounded context that owns each.
Contexts are defined in [`context-map.md`](context-map.md) (ADR-0103, proposed). Where code and
this glossary disagree, fix one of them; do not let the two drift.

The business hierarchy and quality rules (Epic, Feature, Story, INVEST, SPIDR) are defined
authoritatively in `AGENTS.md` §5–6. This page adds ownership and settles the terms that mean
different things in different places.

## Core terms

| Term | Owning context | Meaning |
|---|---|---|
| Requirement | requirements | A business need submitted by its owner. It holds title, description, desired outcome, customer context, channels, systems, business rules and constraints. It is versioned; editing it publishes `RequirementRevised`. |
| Draft (Requirement draft) | requirements | Resumable, partial intake. A draft cannot be analysed until it is promoted to a Requirement (ADR-0013). |
| Source document | requirements | A file attached to one Requirement as evidence. Its versions are immutable (ADR-0014). Including, excluding or removing one revises the Requirement. Not the same as a *reference document*. |
| Attachment | requirements | An upload in progress that becomes a source document once ingestion succeeds (ADR-0042, ADR-0065). |
| Analysis (Requirement analysis) | analysis | AI-generated decomposition of what is known and unknown: known facts, constraints, business rules, assumptions, open questions, ambiguities and dependencies. It is disposable: a Requirement revision deletes it. |
| Confirmation | analysis | The owner's explicit acceptance of the current analysis. Breakdown generation requires it (ADR-0010). |
| Clarification question | analysis | A stable, assignable question raised by AI or a human, with its own lifecycle: open → in progress → resolved, or superseded (ADR-0019). |
| Intent proposal | analysis | An AI-suggested change to the Requirement's desired outcome, business rules or constraints. It changes nothing until the owner accepts, edits or rejects it (ADR-0025). |
| Round (analysis round) | analysis | One immutable record of an analysis generation and the question changes it caused. A round is not a revision. |
| Epic | breakdown | A portfolio-level business outcome with a business case. Exactly one per Requirement. |
| Feature | breakdown | One customer-recognisable capability with one measurable outcome. It traces to exactly one Epic. |
| Story (User Story) | breakdown | One small, testable slice of a Feature: "As a…, I want…, so that…", with Given/When/Then acceptance criteria. |
| Story change proposal | breakdown | An AI-suggested split or merge of Stories. It changes nothing until applied. |
| Quality (INVEST assessment) | breakdown | A deterministic and semantic assessment of a Story against INVEST, with SPIDR split suggestions (ADR-0015, ADR-0041). |
| Architecture impact | breakdown | The systems, squads and dependencies a Feature or Story touches. It is part of the approved content. |
| Architecture catalogue | knowledge | The system, squad, product and journey model published by knowledge-portal. Impact mapping reads it; this service does not own it. |
| Breakdown review | governance | The single review of a Requirement's whole breakdown: flags, decisions, dependencies, risks, recommendations, submission and final approval (ADR-0017). |
| Flag | governance | A review finding with a category (open question, assumption, ambiguity, dependency, architecture, quality, staleness) and a severity. A *blocking* flag prevents final approval until resolved. |
| Revision | governance | An immutable snapshot of the Requirement (*requirement revision*) or of the whole breakdown (*breakdown revision*), taken at commit (ADR-0009). |
| Export | governance | A versioned, neutral file produced from an approved breakdown revision (ADR-0023). It is not ADO publication. |
| Knowledge finding | knowledge | Something the knowledge screen found in the library or in historic requirements that bears on a Requirement, such as a conflict, a duplicate or prior art. A person decides it. |
| Reference document | knowledge | A reviewed library document published through knowledge-portal and cited as grounding. Not a *source document*. |
| Prior art | knowledge | Historic requirements that resemble this one, with their ADO lineage (ADR-0102). |
| Owner, reviewer, member | identity | Roles on one Requirement (ADR-0018, ADR-0078). The owner confirms and approves; reviewers are assigned. |
| AI job | jobs | A durable, leased unit of model work with progress, cancellation, retry and a notification on completion (ADR-0020). |
| Worklist, activity | reporting | Read models derived from the other contexts. Nothing writes to them directly (ADR-0012, ADR-0022). |

## Terms that are easy to confuse

**Review vs approval**
- *Review* is the governance process over the whole breakdown (`BreakdownReview`): submit, request revision, approve the breakdown.
- *Approval* is an attributed decision on exactly one Epic, Feature or Story, bound to a fingerprint of its content (ADR-0021).
- A breakdown can be under review while some of its artifacts are not yet approved. Final approval requires both.

**Generated, edited, needs revision, approved** (`GenerationStatus`)
- These are the lifecycle of one Epic, Feature or Story.
- *Edited* means a human changed AI content. Such an artifact is *human-owned*, and regenerating it needs an explicit force.
- These statuses are not the breakdown's status (`BreakdownStatus`: generated, under review, needs revision, approved).

**Stale vs superseded vs deleted**
- *Stale*: an Epic, Feature or Story whose upstream changed (`StaleReason`: requirement changed, Epic changed, Feature changed). The content is kept and must be reconciled before approval.
- *Superseded*: a clarification question replaced by a newer analysis. It stays in the audit trail.
- *Deleted*: only the analysis, which nobody approves. This asymmetry is ADR-0004's rule and survives ADR-0103.

**Approval subject and fingerprint**
- The *subject* is the canonical content an approval attests to.
- The *fingerprint* is its SHA-256.
- An approval stays in the artifact's history, but it is *current* only while its fingerprint matches the artifact's present content (`current_approval(fingerprint)`). Any content change makes it non-current.

**Evidence fingerprint**
- The fingerprint of everything the breakdown review was built from.
- When it changes, the review must be refreshed before approval.

**Expected-context token**
- A precondition sent with a model-backed command. It proves the client saw the current content (`generation_context`).
- It guards generation. It does not record approval.

**Round vs revision vs version**
- A *round* is one analysis generation (analysis).
- A *revision* is an immutable snapshot of the Requirement or the breakdown (governance).
- A *version* is the optimistic-concurrency counter on one aggregate.

**Source document vs reference document**
- A *source document* is evidence for one Requirement (requirements).
- A *reference document* is shared library knowledge (knowledge).

**Domain event vs knowledge event**
- A *domain event* (ADR-0103) is in-process and dispatched inside one transaction of this service.
- A *knowledge event* is an integration event in knowledge-portal's feed, consumed by cursor (ADR-0099).

## Domain events

The catalogue is in ADR-0103 §3. Events are named in the past tense for what changed in the owning
context, never for what a consumer will do:
- right: `RequirementRevised`;
- wrong: `InvalidateAnalysis`.
