# ADR 0070 — Requirement commands own their unit of work

## Status

Accepted. Amended by ADR-0103 (2026-10-07): `RequirementCommands` moves to `workflows/`, and
domain-event handlers run inside its unit of work. The step order is unchanged.

## Context

A guarded Requirement action needs the same steps in the same order: take a
consistent, locked snapshot; authorize the actor; confirm the generation context
the caller last saw is still current; run the use case, which may suspend the
transaction around provider I/O (ADR-0069's `external_call`); reauthorize before
its writes commit; and build the response view — including the next context
tokens — from that same snapshot.

The 2026-09-24 review found route handlers assembling those steps themselves in
about 30 places: nesting `generation_context.read_snapshot()` around
`access.execute_member_mutation(...)` around
`lambda: generation_context.require(...) or use_case.execute(...)`. The idiom
relied on `require()` returning `None`, the order differed slightly between
routes, and several routes fenced use cases that already fence themselves
(breakdown review, decisions, flag resolution, architecture mapping, document
upload/inclusion/removal). Document routes also decided draft visibility
themselves.

## Decision

- `application/use_cases/requirement_commands.py` provides `RequirementCommands`:
  `run` (fence + optional `ExpectedContext` check, member or owner permission),
  `run_and_present` (the same inside a locked snapshot, presenting the result
  there), and `read` (a snapshot for views that carry context tokens).
- Routes name the command, its permission and expected context, and how to
  present the result. They do not open snapshots, take locks, fence, or check
  context tokens. An architecture test forbids those primitives in route modules.
- A use case that already fences itself is called directly; its route wrapper is
  removed. Draft-attachment visibility moved into `ListDocuments.visible_to`,
  `ListDocuments.for_owned_draft` and `GetDocument` (which now take the actor).
- Synchronous generation endpoints are kept alongside the job API (product
  decision, 2026-09-24); both paths use the same use cases.

## Consequences

- One definition of the step order; a change to it (for example, a new check
  after resume) is made once.
- Routes still pass closures: the command and presenter. That is the price of a
  single generic runner over one handler class per operation.
- Two authorization styles remain in the application layer — self-fencing use
  cases and use cases fenced by `RequirementCommands`. Both keep authorization
  out of delivery code; converging on self-fencing would require changing about
  twenty use-case signatures and is not done here.

## Alternatives Considered

- **One command-handler class per operation.** Rejected for now: about thirty
  near-identical classes repeating the same ten lines is the duplication this
  decision removes.
- **Moving every fence into its use case.** Cleaner end state, but a much larger
  signature change across use cases and their tests; recorded as a possible
  follow-up rather than done under a remediation phase.
- **Retiring the synchronous generation endpoints.** Declined by the product
  owner; the job API and synchronous endpoints coexist.
