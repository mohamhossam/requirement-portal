# ADR 0115 — A requirement-level product verdict, decided in analysis

## Status

Accepted 2026-10-10 by the owner. Extends ADR-0097. Phase 0 of the ontology and
impact plan ([plan](https://claude.ai/code/artifact/27b1b1d1-b01b-40d4-9264-1999bc29b2bf));
built in its Phase 4, on knowledge-portal's assessment route from Phase 3. Pairs with ADR-0114
and ADR-0116.

## Context

"Is this an existing product or a new one?" is a question about the whole requirement, and its
answer changes what the breakdown should contain. Today nothing answers it:
- The only requirement-level mapping runs when Features are generated
  (`GenerationChecks.guidance`), after the analysis is confirmed. Its result is used as guidance
  and then dropped.
- ADR-0097 shows the offering a text names as advice on each impact. An offering described but
  not named gets none, and no one records a decision.
- A requirement such as "add a new device" cannot be placed at all, yet nothing asks which
  offering or device it means before the breakdown starts.

Slice 13's publication record already has room for an accepted verdict and its version
(`PublicationRecord.product_verdict`), empty until analysis decides one.

## Decision

**The analysis carries a `ProductImpact`.**
- Fields: verdict, offering, proposal, needed capability concepts, gaps, release id, who decided,
  and the decision: accepted, overridden or unknown.
- Verdicts are knowledge-portal's: change to an existing offering, new plan, new offering in an
  existing family, new product line. No verdict while questions are open.

**Analysis decides it, before breakdown.**
- After the analysed facts exist, analysis calls knowledge-portal's
  `POST /internal/architecture/assess` with the requirement and those facts.
- Missing facets come back as AI-sourced clarification questions with options from the
  catalogue. They block confirmation like other blocker questions. Answering one re-runs assess.
- Confirming the analysis needs a verdict decision from a person: accept it, override it, or
  mark it unknown.
- With no knowledge portal connected (ADR-0104), assess answers nothing and confirmation is not
  blocked.
- **The verdict gate** (set by the owner 2026-10-10): the verdict is shown to reviewers only once
  the live models score at least 80% verdict accuracy on knowledge-portal's golden set, and call
  no new-offering or new-product-line case a change to an existing offering. Until then it is a
  suggestion only, and "unknown" is always allowed.

**Breakdown reads the decision.**
- `GenerationChecks.guidance` takes the stored verdict and covered capabilities instead of a
  fresh match. Features and Stories are still mapped to systems, as today.
- What generation may do with them is ADR-0116.

**Governance.**
- New review flags: a gap needs an architect, the verdict is not decided, a concept link is weak.
- The verdict and its decision join the review fingerprint, so a changed verdict re-opens review.
- On publication, the accepted verdict and its version fill the publication record (ADR-0113).

## Consequences

- Product impact is decided once, by a person, early enough to shape the breakdown.
- Analysis gets one more blocking step whenever the knowledge portal is connected. A requirement
  that cannot be placed now asks why, instead of being broken down on a guess.
- Re-running assess on every answered question costs a model call each time; caching by
  analysis revision is left to Phase 4.
- Existing approvals change fingerprint only once a verdict is decided; nothing is migrated.

## Alternatives Considered

- **Decide the verdict during breakdown.** Rejected: by then the Epics are shaped, and a
  new-offering verdict needs product set-up work that the breakdown would already have missed.
- **Keep the verdict as advice on each impact (ADR-0097).** Rejected: advice nobody decides is
  dropped, and Phase 7 needs a decided verdict to compare with what was delivered.
- **Let the knowledge portal store the decision.** Rejected: the decision belongs to the
  requirement's reviewers, and the knowledge portal never stores requirement work (ADR-0104).
