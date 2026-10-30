# ADR-0120 — Non-functional requirements and business use cases as analysis categories

Status: Accepted
Date: 2026-10-30

## Context

A standard Business Requirements Document carries two things the analysis never produced:
non-functional requirements (the qualities a solution must have, by type) and business use cases
(how the business, as a black box, delivers value to an external actor). Both are in the BABOK
requirement classification and in every common BRD template. Our analysis extracted known facts,
business rules and constraints only, so statements of either kind landed unlabelled in those lists
or were lost, and the document (ADR-0119) could not print them without guessing at export time,
which its rule forbids (`docs/slices/enhancement-brd-completeness.md`, Phase C).

Two properties of the analysis pipeline shaped the design. Every extracted item on the
structured-document route must cite a source passage, is recovered or set aside when it cannot
(ADR-0032), and reaches the final analysis through packet consolidation, where the model re-emits
findings from synthetic text blocks (ADR-0029). And the owner confirms the analysis as a whole, so
anything the analysis records is reviewed before the backlog or the document uses it.

## Decision

1. **Two settled categories.** `RequirementAnalysis` gains `non_functional_requirements`
   (`NonFunctionalRequirement(statement, kind, evidence_references)`, `kind` one of performance,
   availability, security, compliance, usability, data, scalability, other) and
   `business_use_cases` (`BusinessUseCase(name, actor, goal, main_steps, trigger=None,
   alternate_paths, business_rules, evidence_references)`). Both default to empty, so analyses
   recorded before them read unchanged. They are settled content like facts, rules and
   constraints: extracted with evidence, carried whole into every round, confirmed with the
   analysis, never turned into clarification questions. The trigger is optional because many
   sources leave it unstated; a use case needs a name, an actor, a goal and at least one step.
2. **Cited only.** The structured-output schema asks for both with citations; the citation
   validator expects a key for each (`non_functional_requirement:<statement>`,
   `business_use_case:<name>`, steps uncited); citation recovery judges a use case by its name and
   goal and sets aside an uncited one like any other new output. Plain-text requirements stay
   exempt, as facts are. The prompt is `analysis-v28-nfr-and-business-use-cases`.
3. **Both categories bypass the consolidation model.** The packet planner already starts a new
   packet at each `BUC n` heading, so a use case is section-local, and both kinds of record were
   validated against real passages in the packet stage; cross-section reconciliation would only ask
   the consolidation model to re-emit a record from a synthetic sentence, losing steps or the type.
   `ConsolidateEvidenceAnalysis` therefore merges use cases by normalised name and non-functional
   requirements by normalised statement, holds both and their references aside before the first
   consolidation round, emits no synthetic blocks for them, and re-attaches them to whatever the
   model (or the merged fallback) returns. A held record wins over anything the model emitted under
   the same key. The fragment cache key is `evidence-fragment-v4`.
4. **Nothing already recorded changes.** The payload codec writes both categories only when
   non-empty; the review fingerprint and the generation context token include them only when
   present; the story-quality evidence adds non-functional statements. Stored rows, the
   characterisation goldens, existing approvals and live tokens are unchanged.
5. **Where they are read.** The API returns both; the Confirm and Clarify screens list them in the
   settled column (statement with a kind label; a use case set as document prose with actor, goal,
   trigger and numbered steps); the knowledge index chunks them; the Epic, Feature and Story prompts receive the
   non-functional requirements (and the Feature prompt the use cases as scope framing), together
   with Phase B's out-of-scope and proposed-state fields, in one prompt bump (`epic-v5`,
   `feature-v9`, `story-v9`); the document renders "7. Business use cases" (BUC-nn) and "10.
   Non-functional requirements" (NF-nn), schema 1.3.

## Consequences

- The owner sees and confirms non-functional requirements and business use cases before anything
  is generated from them or printed; the document prints only what was confirmed.
- Two analysis prompt versions in one slice (v27 in Phase B, v28 here) mean two fragment-cache
  invalidations; each costs one re-analysis per requirement per deploy.
- A use case the source states across sections may appear twice under two names; the merge keeps
  distinct names, the document dedupes by name, and the owner sees both on Confirm.
- Generation prompts grow; the Feature prompt is asked to cover each non-functional requirement as
  a condition or a Feature, which its rules already encouraged.
- The live-model record for this change is kept in `docs/evaluation/`, referenced from the slice.

## Alternatives Considered

- **Infer the categories at export time** from constraints and enabler-kind Features. Rejected:
  guesswork in the document, unreviewed by the owner.
- **Serialise use-case steps into the consolidation text and rely on the model to re-emit them.**
  Rejected: the most rewriting on the one path that must preserve a record exactly.
- **Make them clarification questions.** Rejected: they are statements the source makes, not
  uncertainties a person resolves.
- **A required trigger.** Rejected: it would set aside otherwise good use cases from sources that
  omit one.
