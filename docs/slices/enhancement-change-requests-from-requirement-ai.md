# Enhancement — Change Requests from Requirement AI (ADR-0101 step 7)

> Status: **complete locally; CI pending push**. Deploy knowledge-portal's
> `POST /internal/change-requests` (knowledge-portal branch `port/explorer-change-requests`)
> first; until it is there, handoffs wait and retry.

## Objective

When a breakdown's formal final approval is recorded, hand its approved backlog to the
knowledge catalogue, where it becomes a change request a knowledge admin reads into a draft or
dismisses (ADR-0101 Amendment 2).

## User Outcome

A product owner approves a breakdown here and does nothing more: the approved backlog appears in
knowledge-portal's inbox of change requests, with the requirement, revision, approver and
features it carries. Nobody downloads and re-uploads an export, and the approver's email never
leaves requirement-portal.

## In Scope

- A transactional outbox written by `ApproveBreakdown`, one row per approval.
- A background worker that renders the attested revision's export once and delivers it, with
  leases, retries and give-up rules.
- An HTTP adapter onto knowledge-portal's change-request inbox.
- The pinned knowledge-portal internal contract, refreshed (additive).
- ADR-0101 Amendment 2 and an ADR-0099 note.

## Out of Scope

- What knowledge-portal does with a change request (its inbox, reading, questions, change
  history): knowledge-portal's own slice.
- A status of the handoff on requirement-portal's screens (see UI).
- Any change to the export's schema (it stays 1.5).

## Domain

No domain change. The handoff is application state: `BacklogHandoff` with its status
(pending, delivered, skipped, failed), attempts, lease, last error, the rendered export and the
change request it became.

## Application Use Cases

- `ApproveBreakdown` takes an optional `ApprovedBacklogOutboxPort` and enqueues after saving the
  approval, inside the same transaction. The idempotent early return enqueues nothing.
- `DeliverApprovedBacklogs.deliver_next()`:
  - leases the oldest due handoff for 5 minutes;
  - the first time, finds the first revision whose formal final approval is this approval, and
    renders `approved_backlog_document(revision)` through the JSON exporter with
    `recorded_by.email` set to null; stores it before sending;
  - skips a handoff no exportable revision carries;
  - delivered on success; retried after 1 minute doubling to 1 hour on 404, 429, 5xx or an
    unreachable service, at most 48 attempts; failed on 400, 409, 413 or 422.
- `export_breakdown.approved_backlog_document(revision)` exposes the existing export document for
  an exportable revision.

## Ports

- `ApprovedBacklogOutboxPort`: `enqueue`, `get`, `claim(now, lease, token)`, `save(handoff,
  expected_version)`.
- `ChangeRequestInboxPort`: `deliver(export) -> change_request_id`.

## Adapters

- `InMemoryBacklogHandoffs`, enrolled in memory transactions (a rolled-back approval leaves no
  handoff).
- `PostgresBacklogHandoffs` on the request's `PostgresSession`, so an enqueue joins the approval
  transaction; claims use `FOR UPDATE SKIP LOCKED`; writes are optimistic on `version`.
- Migration `202610051700_approved_backlog_handoffs.sql`.
- `HttpChangeRequestInbox` (`POST /internal/change-requests`, idempotent retries in the kernel
  client), decoding the receipt or failing as `ServiceUnavailableError`.
- Composition: `KnowledgeService.change_requests` is set only with a knowledge service; then the
  approval enqueues and `approved_backlog_worker` runs, counting outcomes as
  `smb_ai_jobs_total{operation="approved_backlog_handoff", status=...}`.

## API

No route changes in requirement-portal. Outbound: knowledge-portal's
`POST /internal/change-requests` (201 created, 200 replay), pinned in
`contracts/knowledge-internal.openapi.json`.

## UI

No requirement-portal screen changes, by decision. The product owner decided the handoff is
pushed on final approval and lands in an inbox that knowledge admins work from, on
knowledge-portal's Versions page. requirement-portal's frontend is under a presentation-only
redesign rule (`CLAUDE.md`), so a handoff status on the approval screen is not part of this
slice. It is carried to a later slice, if wanted.

## Business Rules

- One handoff per approval; a replayed approval queues nothing.
- The export sent is the JSON download's document for the attested revision, except the
  approver's email, which is null.
- A handoff is never edited after it is rendered: every retry sends the same body.
- Without `KNOWLEDGE_API_BASE_URL` and `REQUIREMENT_SERVICE_TOKEN`, nothing is queued and no
  worker runs.

## Tests

- `tests/unit/test_approved_backlog_handoff.py` (12): one delivery without the email and equal to
  the download; nothing queued without a knowledge service; the worker registered only with
  one; retries on unavailable and 404 with the same body; no resend after 409, 413 or 422; a
  replayed approval queues nothing new; skip when no revision carries the approval; give up
  after the last attempt; one handoff per approval and leases; rollback.
- `tests/unit/test_knowledge_http_contract.py` (2 new): the delivered body satisfies the pinned
  contract's request schema (a subset; extra fields allowed), the receipt its 201 schema; a 409
  is a `ServiceResponseError` and an unusable receipt a `ServiceUnavailableError`.
- `tests/integration/test_backlog_handoffs_postgres.py` (3): uniqueness and reload; queued with
  its transaction or not at all; oldest-first leases, lease takeover and the stale writer
  refused.

## Acceptance Criteria

- [x] A final approval queues exactly one handoff in its own transaction.
- [x] The worker delivers the attested revision's export, without the approver's email.
- [x] Retries send identical bytes; refusals are not retried.
- [x] Nothing changes when knowledge-portal is not configured.
- [x] The pinned contract carries the route; the adapter is held to it.

## Validation Evidence

- `TEST_DATABASE_URL=postgresql://postgres@/requirement_test?host=/tmp&port=55432 pytest -o addopts=""`
  — PASS, 1687 passed in 141.54s (local PostgreSQL 16 with pgvector).
- `ruff check .` — PASS, all checks passed.
- `ruff format --check .` — PASS, 1050 files already formatted.
- `mypy src tests` — PASS, no issues found in 509 source files.
- `lint-imports` — PASS, 9 contracts kept, 0 broken.
- CI — pending push; local success is not CI authority.

## Deferred

- A handoff status on requirement-portal's approval screen (see UI): by decision, not part of
  this slice.
