# ADR-0008: Preserve Human Clarifications as Separate Analysis Context

## Status
Accepted

## Context
The review UI displayed uncertainty but offered no way to answer it. Editing the source
requirement would blur source text with follow-up decisions, while converting answers to
known facts would falsely claim they were extracted from the original requirement.

## Decision
Store reviewer answers as `HumanClarification` values on `RequirementAnalysis`, with an
explicit uncertainty kind, original subject, and answer. Pass these values through the
provider-independent analyzer port and label them as confirmed human context in prompts.

The clarification use case accepts answers only for unresolved items in the current
analysis. It returns a conflict for outdated subjects, regenerates the same analysis, and
preserves accumulated answers across later re-analysis. Downstream Epic and Feature
prompts may use these answers as confirmed context while retaining their origin.

## Consequences
- The UI supports an analyze → clarify → re-analyze loop.
- Human decisions remain distinguishable from source extraction and AI inference.
- All analyzer adapters accept clarification context.
- Durable history and timestamps remain in planned governance/persistence slices.
