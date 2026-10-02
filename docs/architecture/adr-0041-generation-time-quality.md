# ADR 0041 — Generation-time quality and remaining concerns

## Status
Accepted by the implementation request.

## Context
The generation ports did not receive architecture matches or assessment feedback. Stories could
therefore be saved and only subsequently fail INVEST with advice to split them.

## Decision
- Application-owned generation checks assess unsaved candidates, reuse architecture mapping and the
  deterministic review policy, and allow at most one corrective generation pass before final checks.
- Supply typed, labelled guidance through focused generator ports. Keep semantic Story assessment
  behind its existing port; deterministic rules remain provider-independent.
- Save content, mappings, assessments and a refreshed review in the owning atomic mutation, after
  external calls and existing authorization/context/job-fencing checks.
- Store assessed proposal candidates as immutable preview evidence and recheck the full source set
  and generation context before applying it. Existing unchecked proposals remain readable.
- Reuse current content-bound quality on review refresh. GETs never call providers; unevaluated
  current content blocks approval and offers explicit reassessment.

## Consequences
This supersedes the explicit-only mapping/refresh workflow in ADRs 0016 and 0017. Their knowledge
boundary, evidence provenance, decision carry-forward and read-only GET guarantees remain intact.
ADR 0015's semantic/deterministic split remains intact. Generation takes additional provider work
for quality and, when needed, one refinement; unresolved concerns are honest output, not a retry loop.
No new deployment setting or relational migration is needed. Existing edits and approvals are not
silently regenerated, and no ADO integration or automatic approval is introduced.

The PostgreSQL replacement adapters temporarily move existing positions above both the old and
new ranges within the version-guarded transaction. This permits insertion/reordering without
violating unique-position constraints or deleting retained IDs. Applying a prepared proposal
increments the retained Story's optimistic version. These are correctness fixes to the existing
replacement contract, not new persistence abstractions or schema changes.

## Correction following the local-model regression

The reported run used the new workflow, but its corrective response repeated an oversized Story
and added unsupported acceptance behavior. Corrective tasks now have an explicit application
section separate from catalogue evidence, quoted findings and the failed AI draft. Failed
Estimable findings receive SPIDR discovery guidance. A sole oversized candidate failing two
or more criteria must produce at least two replacements when cardinality permits; ignoring that
contract is a provider failure, preserving saved state. Single regeneration and merge retain one.

Semantic assessment receives typed source facts, human decisions, uncertainty and the Feature
boundary. Quality fingerprints include that evidence, and review fingerprints include the same
context. Old assessments remain readable but are stale until explicit reassessment; review reads
never repair them through provider calls. The six criteria and failure thresholds are unchanged.
The review rubric distinguishes security value and business obligations from implementation
design, and requires a boolean verdict consistent with its evidence message. Story provider
schemas require populated Stories and acceptance criteria instead of silently defaulting to empty
arrays. These changes do not turn semantic model output into proof of business correctness.
