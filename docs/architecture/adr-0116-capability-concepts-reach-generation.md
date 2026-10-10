# ADR 0116 — The decided product impact and its capability concepts reach generation

## Status

Proposed 2026-10-10, for the owner to accept. Amends the "show-only" rules of ADR-0089 and
ADR-0092 for capability concepts only. Phase 0 of the ontology and impact plan
([plan](https://claude.ai/code/artifact/27b1b1d1-b01b-40d4-9264-1999bc29b2bf)); built in its
Phase 4 with ADR-0115.

## Context

ADR-0089 (capability domains), ADR-0092 (system components) and ADR-0097 (product context) all
strip their fields from generation guidance, so the `feature-v5` and `story-v5` prompts never
change and existing approvals stay valid. That was right while those fields were advice.

ADR-0115 makes the product impact a decision a person takes before breakdown. A decided verdict
that never reaches generation is wasted:
- a new-offering verdict should yield Features for catalogue and product set-up;
- a capability gap should yield an architecture spike, not a Feature forced onto the nearest
  system;
- the covered capabilities say which parts of the offering the breakdown is about.

## Decision

**Generation guidance gains the decided product impact.**
- The verdict, the offering, the proposal, the covered capability concepts (id and preferred
  label) and the gaps, exactly as the reviewer accepted or overrode them.
- An impact marked unknown, or no impact at all (no knowledge portal), adds nothing, so
  generation behaves as today.
- New prompt versions, `feature-v6` and `story-v6`, read them. The new prompts must:
  - propose catalogue and product set-up Features for a new plan, a new offering or a new
    product line;
  - turn each gap into a spike recommendation (`AGENTS.md` §7, rule 7);
  - never add a system the impact did not map.

**What stays stripped.** Capability domains, landscape domains, components, product contexts and
journey steps remain show-only, as ADR-0089, ADR-0092, ADR-0094 and ADR-0097 decided. Only the
decided impact and its concepts cross.

**Fingerprints.** The decided impact is already in the review fingerprint (ADR-0115). A Feature
or Story generated with `-v6` records that prompt version, as every generation does.

## Consequences

- The breakdown follows the decision a reviewer took, including set-up work and spikes it used
  to miss.
- Two new prompt versions to evaluate; the golden set covers the verdict, but Feature quality
  still needs the existing generation-quality review.
- Requirements broken down before Phase 4 keep `-v5` content until regenerated.

## Alternatives Considered

- **Keep every catalogue field show-only.** Rejected: the decided verdict would change nothing
  downstream, and new-offering work would keep being missed.
- **Pass every catalogue field to generation.** Rejected: domains and product contexts are
  advice nobody decided, and they would move approvals with every catalogue edit.
