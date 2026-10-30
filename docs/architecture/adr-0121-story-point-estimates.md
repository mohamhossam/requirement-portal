# ADR 0121 — Story point estimates: AI suggests, the team confirms

## Status

Accepted 2026-10-30. Implemented on `feat/story-point-estimates`
(`docs/slices/enhancement-story-point-estimates.md`).

## Context

Teams size User Stories in story points before sprint planning, and the tracker the backlog is
published to (Azure DevOps) has a field for it. The portal had no size anywhere: not on the Story,
in the export, or in the publication. The INVEST *Estimable* and *Small* checks judge whether a
Story *can* be sized, but say nothing about its size, and the quality prompt deliberately forbids
the model from producing point estimates.

Two product rules constrain any answer:

- *Generated content is never business truth* (`PRODUCT.md`). A number the model produced cannot
  become a Story's size on its own, and AGENTS.md §7 requires AI inference and a human decision to
  stay distinguishable.
- *Nothing reaches an external backlog except an explicitly approved revision.* Export and Azure
  DevOps publication read the formally approved `BreakdownRevision`, so whatever a size is, it must
  either be inside what approval attests to or stay out of the hand-off.

Points are also relative: they mean something only against the other Stories a team sized, and the
portal holds no velocity or team capacity to anchor them to.

## Decision

**Two things, kept apart.**

1. **A suggestion is AI output.** `SuggestStoryEstimates` (breakdown) sizes all of one Feature's
   Stories in a single pass through `StoryEstimatorPort`, relative to each other, on the fixed scale
   1, 2, 3, 5, 8, 13. Each `EstimateSuggestion` carries a rationale; the model may return no size,
   with the reason, when a Story rests on an unmade business decision or is too large to size.
   `FeatureEstimateSuggestions` is stored per Feature (`feature_estimate_suggestions`) with the
   `story_set_fingerprint` of the content it read and its provenance, exactly like the quality
   snapshot: it goes out of date when Story content changes, never marks the requirement dirty, and
   never enters a revision, an export or a publication. It runs as the durable job
   `suggest_story_estimates`, on the `review` model profile.
2. **A size is a human decision on the Story.** `UserStory.estimate` is an optional
   `StoryEstimate(points, basis, decided_by, decided_at)`, where `basis` is `accepted_suggestion`
   or `team_entered`. `SetStoryEstimate` records, changes or clears it. Accepting is only allowed
   for the current suggestion's exact size for that Story; anything else is entered by the team.

**Approval covers the size.** A size is part of what is handed off, so `artifact_fingerprint` (and
through it `breakdown_fingerprint`) includes `story_points` — only when a size is set, so every
existing approval and golden fingerprint stays valid. Setting or changing a size is a human edit
(`UserStory.sized` → status `edited`, version +1, staleness kept) and publishes `StoriesChanged`;
re-recording the same size is a no-op. Who decided and how is recorded but not attested to.

**Only confirmed sizes count.** `estimate_total` sums confirmed points and reports how many Stories
are sized; an unsized Story is never treated as zero. Edits keep the size; regenerate, split and
merge produce unsized Stories (regenerating a sized Story already asks for confirmation, because a
size makes the Story human-owned).

**Downstream.** Export schema 1.8 adds `story_points` on Story, a Feature total and manifest counts;
the Excel sheets gain the columns. The Business Requirements Document (schema 1.4) shows a Story's
size and a Feature total once something is sized. Publication sends the size to
`ADO_STORY_POINTS_FIELD` (default `Microsoft.VSTS.Scheduling.StoryPoints`; empty leaves sizes out),
and the size is part of the item's content fingerprint, so a changed size is republished. The field
name stays in settings and the adapter (AGENTS.md §9).

## Consequences

- A team can go from generated Stories to sized, approved, exported and published Stories without
  leaving the portal, and every size says whether a person typed it or accepted the AI's.
- Re-sizing an approved Story reopens its approval. That is deliberate — the alternative lets an
  unreviewed number reach the tracker — but it is friction for teams that re-estimate late.
- Generation context tokens and the revision diff see a size change as a Story change; tokens are
  unchanged for unsized Stories.
- The scale is fixed in the domain. A different scale, or T-shirt sizes, would be a new decision.
- One more model call per sizing pass, on demand only; Story generation is not slower.

## Alternatives Considered

- **Size as planning metadata outside approval.** Re-sizing would not reopen approval, but export
  and publication would then send a number nobody approved. Rejected for the hand-off rule.
- **The AI's size as the Story's size until someone changes it.** Turns AI output into backlog
  truth by default. Rejected by `PRODUCT.md` and AGENTS.md §7.
- **A deterministic formula** (criteria count, systems touched). Looks precise, is not relative to
  the team's other Stories, and would be trusted for the wrong reasons. Kept only as the offline
  fake.
- **Suggesting sizes during Story generation.** Adds a model call to every generation, and sizes
  would go stale on the first edit. Left as a possible later step.
