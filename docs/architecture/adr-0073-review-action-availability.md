# ADR 0073 — Review action availability is a domain rule the API reports

## Status

Accepted. Backend delivered; the browser switches over as part of the UI redesign.

## Context

Whether a reviewer may approve, regenerate or generate downstream work was
decided twice. Use cases refused a command (`GenerateFeatures` checked the Epic
was approved and current; the Story workflow checked the Feature). Separately,
`frontend/src/review/rules.ts` restated the same rules so it could disable a
control and explain why. The two used different wording and could drift: a
rule changed on the server would leave the browser offering, or hiding, the
wrong action.

## Decision

- `domain/shared/actions.py` defines `ActionAvailability` (`allowed`, `reason`,
  `confirmation`). A blocked action always carries a reason. An allowed action
  that replaces human work carries a confirmation the caller must show before
  sending `force`.
- Each aggregate states its own rules once:
  - `ReviewableGeneration.approval_availability` / `regeneration_availability`
    apply to every Epic, Feature and Story;
  - `Epic.decomposition_availability`;
  - `Feature.story_availability`;
  - `RequirementAnalysis.epic_generation_availability`.
- The use cases refuse commands with those same predicates, and the refusal
  message is the availability reason.
- API responses report availability as typed `actions` objects:
  - `RequirementAnalysisResponse.actions.generate_epic`;
  - `EpicResponse.actions.{approve, regenerate, generate_features}`;
  - `FeatureResponse.actions.{approve, generate_stories}`;
  - `StoryResponse.actions.{approve, regenerate}`.
- Availability covers review state only. Authorization stays with the action
  itself (403), because it depends on the caller, not the content.

## Consequences

- A client can enable controls and explain blocked ones without knowing the
  rules. The API tests assert that a blocked action's reason is exactly the
  message the refused command returns.
- "Already approved" reports approval as unavailable even though repeating an
  exact approval is an idempotent no-op on the server. There is nothing further
  to approve, and reporting it that way matches the existing UI.
- Refusal messages for Feature and Story generation changed wording; they no
  longer embed item identifiers.
- The browser still uses `review/rules.ts`. CLAUDE.md limits frontend changes
  to presentation during the redesign, so switching the UI to these fields is
  recorded as a redesign prerequisite (AGENTS.md §19), not done here.

## Alternatives Considered

- **A generic `allowed_actions: list[str]`.** Rejected: an untyped list loses
  the reason and confirmation text, and the generated TypeScript types could
  not tell a client which actions exist.
- **Compute availability in the API layer.** Rejected: that would be a third
  statement of the rules, alongside the use cases and the browser.
