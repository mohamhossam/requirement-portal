# Enhancement 11A — Requirement Knowledge Screening

> Status: **complete locally; CI pending push**.

> Operational follow-up: Enhancement 11A.1 and ADR-0030 supersede startup portfolio backfill and
> terminal automatic retry; the trusted-corpus and human-decision behavior below remains current.

## Objective

Screen every promoted Requirement version against trusted Requirement-derived knowledge and
make possible duplicate or contradictory intent visible for explicit owner review before a new
analysis can be confirmed.

## Roadmap Scope Check

| Roadmap field | Delivery |
|---|---|
| Domain | Cited chunks, immutable screens, versioned findings/decisions, duplicate linkage, bilateral resolution. |
| Application | Corpus, hybrid screening, durable scheduling, review/decision use cases, confirmation and duplicate gates. |
| Ports | Embedding, index/search, classifier, review repository, scheduler. |
| Adapters | Fake/OpenAI/local AI plus memory/PostgreSQL pgvector persistence. |
| API | Review and versioned-decision endpoints; additive job, Requirement, and worklist fields. |
| UI | Knowledge journey panel, evidence/provenance, status, owner actions, worklist states. |
| Tests | Domain, use-case, adapter, API, UI, audit, configuration, malformed output, and restart durability. |

Nothing in the Enhancement 11A roadmap entry is dropped.

## Trusted Corpus

- Include promoted Requirement source fields, attributed clarification answers,
  accepted/edited intent decisions, confirmed analysis facts/rules/constraints, and completed
  shared conflict resolutions.
- Exclude resumable drafts, pending/rejected proposals, duplicate Requirements as canonical
  candidates, and all unconfirmed AI analysis content.
- Each independently retrievable chunk records Requirement/version, source kind and field,
  current owner snapshot, normalized content fingerprint, and an immutable application-relative
  evidence path.

## Screening and Decisions

- PostgreSQL full-text and 768-dimensional vector searches are fused by reciprocal rank and
  capped at 20 candidate chunks.
- A focused provider-neutral classifier may return only possible duplicate, possible
  contradiction, or no relationship. Every finding requires supplied candidate IDs and citations;
  unusable provider output fails the complete job atomically.
- Content-fingerprinted automatic jobs run after creation, promotion, source mutation, analysis
  rounds, clarification resolution, and intent decisions. Startup schedules an idempotent,
  system-attributed backfill.
- Analysis may run while a screen is queued/running. Confirmation requires a current successful
  screen and no actionable current finding.
- Duplicate disposition closes and links the subject without deleting history and blocks new
  analysis/backlog generation. Distinct requires rationale.
- Contradictions require one shared statement and both current owners. A revised statement clears
  approvals; ownership transfer removes an incomplete former-owner approval; completed outcomes
  remain immutable.

## Persistence and Operations

Migration `010_requirement_knowledge.sql` enables pgvector, adds AI-job origin, creates knowledge
index/chunk/screen/finding/revision/suggestion tables, and installs full-text plus HNSW indexes.
Development Compose uses PostgreSQL 17 with pgvector. Automatic job success does not create a
system notification; failures notify a current owner, and contradiction findings notify both
available owners.

## Validation Evidence

- `TEST_DATABASE_URL=postgresql://smb:smb_dev@127.0.0.1:5432/smb_requirements pytest` — PASS, 604 tests; includes 13 PostgreSQL persistence/restart tests.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 363 files formatted.
- `mypy src tests` — PASS, 296 source files.
- `lint-imports` — PASS, 2 contracts kept and 0 broken.
- `npm test -- --run` — PASS, 23 files and 112 tests.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run build` — PASS (non-blocking bundle-size advisory only).
- `npm run api:check` — PASS.
- `npm run test:smoke` on isolated ports — PASS, 14 Playwright cases across desktop and responsive Chromium, including bilateral owner resolution and the knowledge gate.
- CI — pending push; local success is not CI authority.

## Architecture Impact

ADR-0027 records corpus trust boundaries, hybrid retrieval, provider validation, human authority,
and bilateral resolution. The application owns orchestration and ports; domain models remain
provider/persistence neutral; concrete adapters remain confined to the composition root.

## Deferred / Open

- No broader confidentiality model, maintained template catalogue, architecture catalogue merge,
  automatic source rewriting, or Azure DevOps behavior is introduced.
