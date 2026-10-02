# ADR 0075 — Submitted Requirements are readable workspace-wide

## Status

Accepted (2026-09-24, confirmed with the product owner during the second
review remediation). Records the policy Slice 8A implemented but no ADR stated.

## Context

The second review found that any signed-in user can read every submitted
Requirement: its source, analysis, backlog, revision history and attachments.
Only owners and reviewers can change it, and drafts are private to their
author. This was the Slice 8A design ("signed-in users can see who owns and
reviews a Requirement", a single worklist, an "Assigned to me" filter), and
`docs/ux-plan.md` builds one information architecture that every role sees.
But nothing recorded it as a decision. An authorization refactor could narrow
or widen it by accident, and a reader could mistake it for a missing check.

## Decision

- **Read.** Every signed-in user may read every submitted Requirement and
  everything derived from it.
- **Write.** Only the Requirement's owner may run owner-level actions (for
  example ownership, reviewers and confirmation). Members (the owner and
  assigned reviewers) may run member-level actions. Nobody else may change it.
- **Drafts.** A draft is visible only to its author until it is promoted.
- `tests/unit/test_read_visibility.py` pins all three rules.
- **Search follows read.** Unified knowledge search returns every submitted
  Requirement that matches, whoever owns it. Drafts are never indexed, so
  they never appear. `test_unified_search_balances_sources_across_the_workspace`
  pins this.
  - **Amended by the third review remediation (2026-09-25, the product
    owner's decision).** Until then search returned only Requirements the
    caller was a member of. That exception was recorded during the
    authorization consolidation (ADR-0078).
  - It was removed because search narrower than read hid work anyone could
    open anyway: the duplicate or related Requirement a person was looking
    for. The worklist and knowledge screening already span the workspace.

## Consequences

- The open worklist and knowledge screening keep working across the
  workspace, which is what lets duplicate and related Requirements be found.
- A Requirement cannot be confidential within the workspace. Deployments that
  need that should scope the workspace itself, for example with separate
  deployments or identity groups.
- Narrowing read access is a product change and needs a new ADR. It would
  touch every read endpoint, the worklist, search and screening. The pinning
  test is there to make that impossible to do by accident.

## Alternatives Considered

- **Members-only read.** Rejected for now. It hides duplicates and related
  work, and contradicts the single-IA UX plan.
- **Workspace-wide read with a per-Requirement confidential flag.** Deferred.
  It is a new capability and belongs on the roadmap, not in remediation.
