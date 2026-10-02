# Slice 9 — Review and Approval Workflow

> Status: **complete locally; CI pending push**. The roadmap scope is
> covered in full and the product-policy decisions below were confirmed before
> implementation.

## Objective

Turn the current evidence review and per-artifact status flags into an
actor-attributed, durable human-governance workflow. A complete Epic → Feature
→ Story backlog can be submitted, reviewed, revised, and finally approved
without publishing anything to Azure DevOps.

## User Outcome

The Requirement Owner and assigned reviewers can see review completion and
blockers, leave comments, approve every current backlog item, request revision
of a Story, and approve the complete current backlog. Every decision identifies
who made it, when, what exact content it covered, and why it remains current or
has become stale.

## Roadmap Scope Check

| Roadmap field | Planned delivery |
|---|---|
| Domain | `BreakdownStatus`, `Approval`, `ApprovalDecision`, and `ReviewComment`; Story approval/rejection; explicit stale reconciliation. |
| Application | `SubmitForReview`, governed `ApproveEpic` / `ApproveFeature`, `ApproveStory`, `RejectStory`, `ApproveBreakdown`, comments, and a read model for workflow state/completion. |
| Ports | Reuse the current artifact, review, access, clock, transaction, job, and revision ports. No new port is justified unless policy storage is approved as external configuration. |
| Adapters | Extend memory/PostgreSQL JSON snapshot mapping and revision tracking with backward-compatible governance fields. |
| API | Preserve existing Epic/Feature approval routes, add Story/review/final-approval/comment operations, and expose workflow state and capabilities. |
| UI | Extend the existing review dashboard with lifecycle, completion, blockers, comments, approval history, and guarded actions; add Story approval/rejection controls. |
| Tests | Domain transitions, authorization, approval guards, rejection/revision paths, persistence compatibility, API/error contracts, UI states, and a browser approval journey. |

Nothing in the Slice 9 roadmap entry is planned to be dropped.

## Confirmed Product Decisions

These are business-policy choices, not technical details. The recommendations
make the slice implementable without inventing hidden governance rules.

### 1. Who may perform each action?

**Confirmed:** the Requirement Owner and assigned reviewers may approve
individual artifacts, reject a Story, and comment. Only the Requirement Owner
may submit the complete backlog for formal review and give final breakdown
approval. Observers retain read-only access.

This uses the ownership and reviewer model delivered in Slice 8A. It does not
claim four-eyes separation: an Owner may approve an artifact they own. If
independent approval is mandatory, the required reviewer count and self-approval
rules must be specified before implementation.

### 2. Which blockers prevent final approval?

**Confirmed:** strict policy. Final approval requires a fresh review with no
open blocking flags and no active blocking clarification questions. Warning
flags may remain open and are visible in the approval summary.

The approval policy will be an explicit required application dependency rather
than a condition duplicated across routes and React. Do not add speculative
policy modes or an environment switch until the roadmap owner defines another
valid policy. This satisfies the roadmap rule with one named, testable policy
and avoids a configuration option whose alternative behavior has not been
approved.

### 3. How do existing Epic/Feature approvals relate to formal review?

**Confirmed:** keep the current decomposition gates and public routes. Epic
approval remains required before Feature generation, and Feature approval
remains required before Story generation. Slice 9 enriches those actions with
an immutable actor/time/content approval record. Story approval completes the
same artifact-level lifecycle. Formal submission then pins the already reviewed
tree for final governance.

Changing those gates would redesign the delivered workflow and is outside the
smallest Slice 9 vertical slice.

### 4. What does Story rejection do?

**Confirmed:** rejection requires a non-blank reason, records a `REJECTED`
decision, moves the Story and breakdown to `NEEDS_REVISION`, and never deletes
or regenerates content automatically. The author edits/regenerates explicitly,
re-approves the new content, and resubmits the backlog.

The roadmap names only `RejectStory`; Epic/Feature rejection is therefore not
added in this slice.

## In Scope

- A Requirement-scoped governance lifecycle integrated with the existing
  `BreakdownReview` rather than a second competing review dashboard.
- Immutable, actor-attributed approval/rejection records bound to canonical
  content fingerprints.
- Story approval and Story rejection/revision behavior.
- Governed, audited Epic and Feature approvals through their existing routes.
- Submission and final breakdown approval with completeness, freshness,
  staleness, authorization, and blocker guards.
- Append-only review comments targeted to the breakdown, an Epic, Feature,
  Story, or review flag.
- Effective `NEEDS_REVISION` behavior whenever submitted/approved evidence no
  longer matches the current content.
- Worklist, revision, API, and browser representation of governance state.
- Retirement of the Slice 9 debt items in `AGENTS.md` §19.

## Out of Scope

- Azure DevOps mapping/publication (Slices 12–13).
- Neutral export (Slice 11).
- Saved views, activity projections, portfolio reporting, and SLA metrics
  (Slice 10A).
- Epic or Feature rejection, bulk approval, approval delegation, quorum rules,
  administrator override, digital signatures, or external policy engines.
- Editing/deleting comments or rewriting approval history.
- Email/chat notifications. Existing in-app job notifications are not expanded
  into a governance notification system in this slice.
- Architecture catalogue administration (Slice 14).

## Domain

### Governance values

- `BreakdownStatus`: `GENERATED`, `UNDER_REVIEW`, `NEEDS_REVISION`, `APPROVED`.
- `ApprovalDecision`: `APPROVED`, `REJECTED`.
- `ApprovalTarget`: typed reference to Epic, Feature, Story, or the complete
  breakdown; IDs must be non-blank and belong to the Requirement tree.
- `Approval`: stable ID, target, decision, canonical subject fingerprint,
  immutable actor snapshot, aware timestamp, and optional approval rationale.
  Rejection rationale is mandatory.
- `ReviewComment`: stable ID, target, non-blank body, immutable actor snapshot,
  and aware timestamp. Comments are append-only in this slice.

### Generated artifacts

- Extend the shared generated-content lifecycle with `NEEDS_REVISION` and make
  it human-owned for regeneration safeguards.
- Store artifact approval history on the artifact it attests to. This permits
  Epic/Feature approvals before a `BreakdownReview` exists and avoids a new
  repository whose only purpose would be joining approvals back to artifacts.
- `Epic.approve`, `Feature.approve`, and new `UserStory.approve` accept a
  validated current approval record. Replaying the same actor/decision/content
  is idempotent.
- `UserStory.reject` records the rejection and moves only that Story to
  `NEEDS_REVISION`; it does not alter its content.
- Editing/regeneration invalidates current approval by content fingerprint but
  preserves the immutable approval/rejection history in revisions.

### Breakdown review lifecycle

- Extend `BreakdownReview` with status, submitted subject fingerprint,
  breakdown approvals, and comments.
- First generation starts at `GENERATED`.
- `submit` transitions `GENERATED` or `NEEDS_REVISION` to `UNDER_REVIEW` and
  pins the complete approval subject fingerprint.
- `request_revision` transitions `UNDER_REVIEW` to `NEEDS_REVISION`.
- `approve` transitions only a current `UNDER_REVIEW` snapshot to `APPROVED`
  and records the final approval.
- A mismatch between the submitted fingerprint and current evidence is exposed
  as effective `NEEDS_REVISION`; it can never be presented or published as
  current approval.
- Repeated identical commands are idempotent; conflicting decisions fail
  explicitly.

### Explicit stale reconciliation

Retire the `AGENTS.md` debt where any one-word edit silently clears staleness:

- Editing a stale Epic, Feature, or Story does not clear staleness by itself.
- Edit requests/UI provide an explicit “I reconciled this item against the
  current source” acknowledgement.
- Only that acknowledgement clears staleness; every edit still revokes the
  current content approval.

### Analysis lifecycle debt

Do not introduce a duplicate `ApproveAnalysis` concept. Slice 8B already gives
analysis an owner confirmation, immutable rounds, source version, actor, and
provenance. Slice 9 treats the current confirmed analysis round as a mandatory,
pinned input to submission/final approval and documents that confirmation plus
immutable rounds is the analysis review lifecycle. Source changes supersede it
without destroying historical rounds or revisions.

## Canonical Approval Subject

Create one named, deterministic application policy for fingerprints. Routes,
React, and adapters must not reimplement it.

- Artifact fingerprints include the artifact ID, all human-visible content,
  acceptance criteria where applicable, staleness, provenance identity, and
  the relevant parent/source identity.
- The breakdown fingerprint includes Requirement version, confirmed analysis
  ID/round/source version, Epic, ordered Features, ordered Stories,
  architecture mappings, the fresh review ruleset/evidence fingerprint, and
  current flag-resolution state.
- Approval status and comments are excluded so recording an approval/comment
  does not invalidate its own subject.
- The policy uses canonical JSON plus SHA-256 and has fixed-vector tests.
- The existing Slice 8 evidence fingerprint must be corrected or wrapped so an
  Epic text edit is detectable; the current implementation fingerprints Epic
  identity/staleness but not its name, outcome, or business case.

## Application Use Cases

### `GetApprovalWorkflow`

- Load Requirement access, current analysis/question state, Epic, Features,
  Stories, review, and active AI-job state.
- Return persisted/effective status, per-artifact current approval state,
  completion counts, blockers, comments, approval history, and actor
  capabilities.
- Compute `NEEDS_REVISION` when a pinned subject no longer matches current
  evidence without mutating state on a GET.

### `SubmitForReview`

- Require the Requirement Owner under the recommended policy.
- Require a complete current tree: confirmed current analysis, current Epic,
  at least one Feature, at least one Story for every Feature, and no stale
  artifact.
- Require a generated, fresh `BreakdownReview` and current approval for every
  Epic, Feature, and Story.
- Pin the canonical breakdown fingerprint and transition to `UNDER_REVIEW`
  inside the existing transaction/revision boundary.

### Governed `ApproveEpic` and `ApproveFeature`

- Preserve existing route/resource semantics and decomposition gates.
- Require owner/reviewer team membership.
- Bind the actor/time/fingerprint approval to the exact current artifact.
- Save artifact and immutable breakdown checkpoint atomically.
- Preserve safe legacy idempotence: an old approved artifact without audit
  metadata can receive a current attributed approval record without a content
  edit or forced regeneration.

### `ApproveStory`

- Require a current non-stale Story under the Requirement/Feature path and an
  owner/reviewer actor.
- Record current approval and change Story status to `APPROVED` atomically.
- Re-approval after edit/rejection binds to the new fingerprint and preserves
  prior records in history.

### `RejectStory`

- Require a current `UNDER_REVIEW` submission, current expected fingerprint,
  owner/reviewer membership, and a non-blank reason.
- Record the rejection, set Story and breakdown to `NEEDS_REVISION`, and
  checkpoint once. Do not mutate the Story text or start an AI job.

### `ApproveBreakdown`

- Require the Requirement Owner under the recommended policy.
- Require current `UNDER_REVIEW` state, exact submitted/current fingerprint,
  current artifact approvals, fresh evidence review, no stale artifacts, and
  all blocker-policy checks.
- Record final approval and transition to `APPROVED` atomically.
- Expose the resulting state as the future publication guard; do not add any
  ADO code.

### `AddReviewComment`

- Require owner/reviewer membership and a valid target in the current tree or
  review.
- Append an actor-attributed comment inside the revision transaction.
- Comments never resolve flags, approve content, or change status implicitly.

### Existing mutation use cases

- Keep existing edit/regeneration paths. Their changed fingerprints make prior
  approvals non-current and the workflow effectively `NEEDS_REVISION`.
- Add explicit stale reconciliation input to Epic, Feature, and Story edits.
- Keep review refresh decision carry-forward rules from ADR-0017; carry
  governance comments/history without treating old approvals as current.

## Ports

- Reuse `BreakdownReviewRepositoryPort` for current governance workflow state.
- Reuse Requirement, analysis audit, Epic, Feature, Story, access, AI-job,
  clock, transaction, and breakdown revision ports.
- Do not add `ApprovalRepositoryPort`: artifact approvals live with the
  artifact; final approvals/comments live with `BreakdownReview`; immutable
  `BreakdownRevision` snapshots already preserve both.
- Pass a required `ApprovalPolicy` value/collaborator into governance use cases.
  It must not read environment variables or UI state.

## Adapters

- Extend snapshot mapping for:
  - artifact approval histories and `NEEDS_REVISION`,
  - review lifecycle fields, final approvals, and comments,
  - truthful defaults for pre-Slice-9 payloads.
- Reuse the in-memory and PostgreSQL artifact/review adapters. The PostgreSQL
  `breakdown_reviews.payload` and current artifact JSONB can carry the added
  fields, so no schema migration is planned unless implementation proves a
  database-level invariant needs one.
- Extend in-memory and PostgreSQL revision checkpointing/comparison so status,
  approvals, rejection, and comments are visible in history.
- Pre-Slice-9 `status=approved` payloads remain readable. They are shown as
  legacy approvals with actor unavailable and are not silently fabricated as
  current attributed approvals.
- Concrete wiring remains only in `interfaces/api/container.py`.

## API

- Preserve:
  - `POST /requirements/{id}/epic/approval`
  - `POST /requirements/{id}/features/{feature_id}/approval`
- Add:
  - `GET /requirements/{id}/approval-workflow`
  - `POST /requirements/{id}/review-submission`
  - `POST /requirements/{id}/features/{feature_id}/stories/{story_id}/approval`
  - `POST /requirements/{id}/features/{feature_id}/stories/{story_id}/rejection`
  - `POST /requirements/{id}/breakdown-approval`
  - `POST /requirements/{id}/breakdown-review/comments`
- Extend edit request schemas with explicit stale-reconciliation
  acknowledgement.
- Additive response fields expose approval history/current approval and
  content fingerprints; existing Epic/Feature response fields remain intact.
- Mutations accept an expected fingerprint where the user is acting on a
  displayed submitted snapshot. Stale commands return `409`.
- Map every new domain/application error centrally in
  `error_handlers.py`, with one status assertion per error. Authorization is
  `403`, missing targets `404`, stale/invalid transitions `409`, and invalid
  bodies `422`.
- Update the committed OpenAPI snapshot and generated TypeScript declarations.

Route naming may be adjusted during implementation only to match an established
resource convention; any change must be recorded here before delivery.

## UI

- Extend `/requirements/:id/review`; do not create a parallel governance page.
- Add a lifecycle header/stepper for Generated → Under review → Needs revision
  → Approved, showing effective stale state distinctly.
- Add completion cards for Epic, Feature, and Story approvals with approved /
  total counts and direct links to incomplete items.
- Show blocker-policy result, open blocking flags/questions, stale artifacts,
  active AI jobs, and the exact reason submission/final approval is disabled.
- Add owner-only “Submit for review” and “Approve complete backlog” actions with
  confirmation dialogs summarizing the pinned content and remaining warnings.
- Add current approval/rejection actor, time, and rationale to Epic, Feature,
  and Story cards.
- Add Story Approve and Reject actions; rejection requires a reason and never
  overwrites local edits on failure.
- Add an accessible comment thread with target context and append form for
  owner/reviewer actors.
- Preserve the last successful workflow/review data on mutation failures and
  announce status changes through an accessible live region.
- Disable governance mutations while a Requirement-mutating AI job is active;
  server-side fingerprint/transaction checks remain authoritative.
- Update the dashboard/worklist so `approved` means a current final breakdown
  approval, and add truthful next actions for submit, revise, and final approve.

## Business Rules

- Generated, edited, or individually approved content is not a finally
  approved backlog.
- An artifact approval attests only to the exact fingerprint recorded with it.
- A final approval attests only to the submitted current breakdown fingerprint.
- Any source/content/evidence change makes the submitted/final approval
  non-current and the effective workflow `NEEDS_REVISION`.
- A stale artifact can never be approved or included in final approval.
- A Story rejection requires rationale and never deletes content.
- Comments and Slice 8 decisions do not themselves approve or resolve content.
- Approval and rejection history is append-only and actor-attributed; legacy
  records are labelled honestly.
- Final approval follows the confirmed blocker policy and never publishes to
  ADO automatically.
- No API route, React component, or persistence adapter owns transition or
  eligibility rules.

## Tests

### Domain

- All valid and invalid `BreakdownStatus` transitions.
- Approval/comment value validation, aware timestamps, immutable actor
  snapshots, target ownership, and idempotent/conflicting replay.
- Story approve/reject/edit/re-approve behavior.
- Rejection rationale and stale-approval guards.
- Explicit stale reconciliation; a normal edit no longer clears staleness.

### Application

- Full completion calculation and canonical fingerprint fixed vectors.
- Submission guards for missing/unconfirmed analysis, missing tree levels,
  missing Story sets, stale artifacts, missing/current approvals, stale review,
  unauthorized actor, and active evidence changes.
- Governed Epic/Feature approval and legacy-approval attribution.
- Story approve/reject/revise/re-approve/resubmit paths.
- Strict blocker policy and warning-only approval.
- Final approval idempotence, stale submitted fingerprint, and revision
  checkpoint atomicity.
- Comment authorization/target validation and no implicit state transition.
- Worklist `ready_for_review`, `needs_revision`, and truthful `approved` cases.

### Adapters

- In-memory repository contract with governance fields.
- Snapshot round trips and backward-compatible pre-Slice-9 payloads.
- PostgreSQL current-state/restart and immutable revision round trips when
  `TEST_DATABASE_URL` is configured.
- Transaction rollback leaves neither partial approval nor partial status.
- Migration idempotence only if a migration becomes necessary.

### API

- All new routes, preserved Epic/Feature routes, additive response contracts,
  actor attribution, and expected-fingerprint conflicts.
- Every new error type’s centralized status mapping.
- OpenAPI snapshot and generated TypeScript contract drift.

### UI

- Lifecycle/completion/blocker/current-versus-stale states.
- Owner, reviewer, and observer capabilities.
- Story approval, rejection reason, revision recovery, comments, and final
  approval confirmation.
- Mutation error/conflict handling preserves local text and last good data.
- Worklist approved/needs-revision classification and next actions.

### Browser smoke

- Fake-provider journey at desktop and responsive viewports:
  create → analyse/confirm → approve Epic → generate/approve Features →
  generate/approve Stories → generate fresh review → submit → reject one Story
  → revise/re-approve → resubmit → final approve → reload and verify audit.

## Acceptance Criteria

- [x] Every current Epic, Feature, and Story can carry an actor-attributed,
      content-bound approval record.
- [x] A reviewer can reject a Story with rationale without losing its content.
- [x] A complete current backlog can enter `UNDER_REVIEW`, return to
      `NEEDS_REVISION`, and reach `APPROVED` through valid transitions only.
- [x] Final approval is impossible for incomplete, stale, changed, unconfirmed,
      or policy-blocked content.
- [x] Open warnings remain visible and do not block under the confirmed
      strict policy unless classified as blockers.
- [x] Comments, approvals, rejections, actors, timestamps, and prior decisions
      remain traceable in immutable revisions and after PostgreSQL restart.
- [x] Stale generated content requires explicit reconciliation; editing alone
      no longer clears the stale flag.
- [x] The worklist reports `approved` only for a current final breakdown
      approval.
- [x] The browser review dashboard exposes completion, blockers, comments,
      lifecycle, and every action required to complete the slice.
- [x] No ADO write or publication occurs.
- [x] Every Domain, Application, Ports, Adapters, API, UI, and Tests obligation
      is delivered or recorded as an agreed omission before implementation.

## Implementation Sequence

1. Confirm the four product decisions above. If a different authorization or
   blocker policy is chosen, update this spec before code.
2. Record ADR-0021 for where approval history lives, the canonical subject
   fingerprint, effective invalidation, and backward-compatible legacy state.
3. Add domain governance values/transitions, Story lifecycle, explicit stale
   reconciliation, and unit tests.
4. Extend snapshot mapping, revision comparison, memory/PostgreSQL round trips,
   and compatibility tests.
5. Implement the approval workflow read model, governed artifact actions,
   submission, rejection, comments, final approval, and worklist policy.
6. Wire only through the composition root; add API schemas/routes, centralized
   errors, OpenAPI, and API tests.
7. Extend the existing review dashboard and Story/artifact cards; add component
   tests and generated client updates.
8. Run backend/frontend gates and the complete fake-provider browser journey;
   record exact evidence below and update roadmap/debt status.

## Architecture Impact

- Dependency direction remains Interfaces/Infrastructure → Application →
  Domain.
- No external provider or new LLM operation is introduced.
- No new persistence port is planned; existing aggregate and review boundaries
  are extended because they already own the current content and review state.
- ADR-0021 records the shared generated-content lifecycle, durable governance
  representation, fingerprint policy, invalidation, and legacy compatibility.
- The composition root remains the only concrete wiring location; errors remain
  centrally translated.

## Risks and Mitigations

- **Two sources of truth between status and approvals.** Current approval is
  derived from both artifact status and matching fingerprint; final approval
  requires the canonical application read model. Fixed-vector and mutation
  tests cover every invalidation path.
- **Legacy `approved` items have no actor record.** Read them honestly and let
  the next approval action append attribution without fabricating history.
- **Review refresh could erase governance data.** Build the new evidence
  candidate first, carry comments/history deliberately, and preserve the last
  successful review on failure.
- **Concurrent AI/manual mutation after a user reviews content.** Recheck the
  fingerprint inside the transaction; the UI’s busy state is convenience only.
- **Scope growth into enterprise approval administration.** Keep one confirmed
  policy and one Requirement team; defer quorum, delegation, and overrides.

## Validation Evidence

- `pytest` — PASS: 494 passed, 9 skipped in 5.92s. The skipped tests require
  `TEST_DATABASE_URL`; PostgreSQL behavior is covered by the existing opt-in
  integration suite and the shared JSONB snapshot mapper.
- `ruff check .` — PASS: all checks passed.
- `ruff format --check .` — PASS: 312 files already formatted.
- `mypy src tests` — PASS: no issues in 258 source files.
- `lint-imports` — PASS: 2 contracts kept, 0 broken across 201 files and 1024
  dependencies.
- `npm run api:check` — PASS: generated TypeScript matches `openapi.json`.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run test` — PASS: 21 files, 85 tests.
- `npm run build` — PASS: TypeScript build and Vite production bundle.
- `npm run test:smoke` — PASS: 10 Playwright tests across desktop and
  responsive Chromium, including the full Slice 9 rejection/recovery/final
  approval/reload journey.
- CI — PENDING PUSH; local gates are green, but AGENTS.md correctly treats CI as
  authoritative.

## Deferred

- Independent-approver/quorum policy until the roadmap owner specifies it.
- Governance notifications and activity reporting to Slice 10A.
- Neutral export to Slice 11.
- ADO publication and external mappings to Slices 12–13. Slice 9 provides only
  the current final-approval state those slices must later guard on.
- Architecture knowledge administration to Slice 14.
