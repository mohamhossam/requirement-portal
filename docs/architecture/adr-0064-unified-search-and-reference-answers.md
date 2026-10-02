# ADR-0064: Unified search and reference-backed answers

## Status
Accepted for the user-requested Search and AI grounding checkpoint.
Amended by ADR-0075 (third review remediation, 2026-09-25): unified search
now returns every submitted Requirement, not only the caller's. The
"member-filtered" wording below records the original decision.

## Decision
Compose the existing Requirement and published-document indexes in an application use case.
Do not compare embedding distances across index generations. Interleave bounded source-ranked
results, cap passages per source and collapse identical wording. Preserve the existing document
search endpoint; expose a separately typed unified endpoint with member-filtered Requirements.

Clarification suggestions retain published references separately from Requirement citations.
The focused suggestion port receives labelled references; the model selects supplied evidence
numbers and cannot invent citation metadata. Publication currency is validated before persistence
and every subsequent selection. Existing JSON snapshots default to no references.

Screening continues to own bilateral Requirement relationships. Document applicability and
conflicts use the existing owner proposal workflow, exposed alongside screening. A published
document is never manufactured into a Requirement or granted automatic authority.

Reference-derived human answers remain out of the independent Requirement corpus. The conservative
ADR-0052 exclusion remains for confirmed analysis and reference intent decisions: generalized
lineage throughout every derived artifact is parent-enhancement work, not silently inferred.

Semantic evaluation consumes explicit judgments of support, applicability, conflict handling and
abstention. Deterministic fixtures validate metric arithmetic; they do not certify model quality.
