# Ontology plan Phase 5 — Decided verdicts sent back as precedents

## Objective

Teach the catalogue from the decisions people make. Each time a Requirement Owner accepts,
overrides or marks unknown a suggested product impact (Phase 4), this service sends the decision
to knowledge-portal's `POST /internal/architecture/precedents`, which keeps it as a precedent.
Phase 5 of the ontology and impact plan
([plan](https://claude.ai/code/artifact/27b1b1d1-b01b-40d4-9264-1999bc29b2bf)); the receiving
side is knowledge-portal v0.4.0 (its slice `docs/slices/ontology-phase-5-retrieval-quality.md`).

## User Outcome

Nothing changes on a requirement's screens. Later assessments in the knowledge portal show the
nearest decided requirements to the model as worked examples, may borrow their systems when two
of them agree for the same offering and need, and a knowledge admin sees on the portal's front
page how often suggested verdicts were changed, and for which needs.

## In Scope

- Queuing each decision, already rendered as the contract's `PrecedentBody`, in the decision's
  own transaction (the `precedent_handoffs` outbox).
- A worker delivering it, retried until the service answers.
- Sending the requirement's id with each assessment, so its own earlier decision is never offered
  to it as a precedent.
- The vendored knowledge contract moved to knowledge-portal v0.4.0.

## Out of Scope

- Sending decisions made before this release: there is no backfill.
- Showing the override rate here: it lives on the knowledge portal's front page.
- The Epic-closed hook comparing what was delivered with the verdict (Phase 7).

## Domain

```mermaid
flowchart LR
  O[Owner decides<br/>accept / override / unknown] --> T{{One transaction}}
  T --> A[(Analysis<br/>version 7)]
  T --> H[(precedent_handoffs<br/>ANA-1@7, pending)]
  W[Precedent worker] -->|lease due row| H
  W -->|POST /internal/architecture/precedents| K[(knowledge portal)]
  K -->|201 kept / 200 already kept| D[delivered]
  K -->|404, 429, 5xx, unreachable| R[retry: 1 min, 2, 4 … 1 h]
  K -->|400, 409, 413, 422| F[failed, not sent again]
  R --> W
```

A `PrecedentHandoff` (`references/application/ports/precedent_handoff.py`) is keyed by the
analysis and its version (`ANA-1@7`), so deciding again queues the later decision as well, and
the knowledge service keeps whichever was decided last. The payload is fixed when the decision is
made; nothing is read again when it is sent.

An example, for an override of the Phase 4 example:

```json
{
  "precedent_id": "ANA-1",
  "requirement_id": "REQ-42",
  "version": "ANA-1@7",
  "release_id": "rel-2026-10",
  "text": ["Static IP quota", "SMB fibre customers need a static IP.",
           "Each customer gets at most 4 static IPs."],
  "decision": "overridden",
  "decided_at": "2026-10-11T09:14:00+00:00",
  "suggested_verdict": "change_existing_offering",
  "verdict": "new_plan",
  "offering_id": "offering:business-fiber",
  "concept_ids": ["cap:static-ip"],
  "systems": [{"id": "bcrm", "role": "primary", "change_type": "modify"}]
}
```

| Field | Taken from |
|---|---|
| `text` | the text assessed: title, description, facts, constraints, rules, answered questions |
| `concept_ids` | the needs the assessment linked, without weak links (≤ 40) |
| `systems` | the product impact's systems, one per id (≤ 60) |
| `verdict` | the decided verdict; none when marked unknown |

## Application Use Cases

- `AnalysisCollaboration.decide_product_impact` queues `precedent_handoff(requirement, analysis)`
  after saving the decision, when a knowledge service is linked.
- `DeliverPrecedents.deliver_next` leases one due handoff for five minutes and sends it. Kept or
  already kept → delivered. Refused as it is (400, 409, 413, 422) → failed. Anything else →
  retried after 1 minute, doubling to an hour, and failed after 48 attempts (about two days).
- `AssessProductImpact` sends `requirement_id` with each assessment (`assessed_text` builds the
  text for both).

## Ports

- `PrecedentOutboxPort` (`enqueue`, `get`, `claim`, `save`) and `PrecedentInboxPort`
  (`record(precedent) -> bool`), in `references/application/ports/precedent_handoff.py`.
- `AssessmentQuery.requirement_id` (optional).

## Adapters

- `InMemoryPrecedentHandoffs` joins memory transactions; `PostgresPrecedentHandoffs` joins the
  caller's transaction, leases with `FOR UPDATE SKIP LOCKED`, and refuses a stale write by
  version.
- `HttpPrecedentInbox` posts to `/internal/architecture/precedents` (idempotent, so the shared
  client retries it) and reads the receipt's `recorded`.
- The `precedent_worker` background worker ("decided-verdicts"), metrics job
  `precedent_handoff`. It exists only with a remote knowledge service.

## Migration

`202610111200_precedent_handoffs` (expand only: a new table).

## Business Rules

- With no knowledge portal linked, nothing is queued and no worker runs (ADR-0104).
- A decision and its handoff are saved together or not at all.
- An unknown verdict is sent too: the knowledge portal counts it, but never learns systems from
  it.
- A knowledge portal older than v0.4.0 answers 404, which is retried, so decisions made before an
  upgrade arrive once it lands, within about two days.

## Tests

- `tests/unit/analysis/test_precedent_handoff.py`: each decision queues one handoff whose
  payload the pinned contract allows, assess carries the requirement id, deciding again queues
  the later decision, nothing offline, the worker only with a knowledge service, delivery,
  retries and their pauses, refusals, giving up, the lease and a rollback.
- `tests/integration/test_precedent_handoffs_postgres.py`: one row per version, transactional,
  leased oldest first to one worker.
- `tests/unit/test_knowledge_http_contract.py`: the precedent as the contract describes it, a
  refused or unusable receipt, and assess with `requirement_id`.

## Acceptance Criteria

- [x] Every decided verdict reaches the knowledge portal, with its systems, through a retried
  outbox.
- [x] A requirement's own decision is never its own precedent.
- [x] Without a knowledge portal, deciding behaves as before.

## Validation Evidence

Run on 2026-10-11 against this branch:

- `pytest` with PostgreSQL 16 — PASS
- `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports` — PASS
