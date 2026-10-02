# Enhancement — Document ownership and dependency visibility

## Objective
Complete the requested library governance checkpoint. The user explicitly selected ownership
transfer and the dependency view; delegated document reviewers are outside this checkpoint.
Status: implemented and locally validated; CI/release completion remains pending.

## User Outcome
An owner can hand a document to a known workspace user with an audit reason, and inspect which
accessible Requirements cite its publications before withdrawing or replacing evidence.

## In Scope
- Owner-only transfer, concurrency precondition, immutable attributed history and immediate access change.
- Current and historical analysis reference proposals, exact citations, decision status and publication currency.
- Requirement membership filtering, pagination, API and browser controls.

## Out of Scope
Delegated reviewers, invitations, administrator recovery, generalized copied-content lineage,
automatic notifications or cascading rewrites, unified search and external backlog publication.
This checkpoint does not close the wider ingestion/retrieval enhancement's delivery ledger.

## Domain
OwnershipTransfer records previous/new owners, actor, time and rationale. LibraryDocument appends
transfers without rewriting uploads, reviews, approvals or publication identities.

## Application Use Cases
LibraryGovernance transfers ownership and queries dependencies. Historical rounds stay immutable;
current analysis decisions take precedence over their original round snapshot.

## Ports
Reuse library, known-actor, Requirement, analysis, audit, access, clock and transaction ports.

## Adapters
Memory/PostgreSQL library adapters keep submission keys scoped to original uploaders and update
the current-owner projection atomically. Missing JSON history defaults to empty; no migration.

## API
POST /library/documents/{id}/ownership; GET ownership/history; GET dependencies with offset/limit.
Transfer returns only its receipt, because the previous owner has surrendered private access.

## UI
Extend the existing Library workspace with ownership transfer/history and an explicit dependency
query. Show current versus historical analysis, decision status, cited version and publication
currency. Guard unsaved passage edits; remove private cached library data after handover.

## Business Rules
Only the current owner can transfer or inspect governance. The target must be a known actor and
different from the owner. A document owner sees only Requirements where they are owner/reviewer.
No hidden Requirement counts or titles are exposed. Rejected proposals remain traceable but do
not imply active reliance. Publication currency does not establish policy applicability.

## Tests
Domain invariants; memory/API transfer, stale-write, authorization and retry regressions;
dependency decision/history/privacy/pagination/withdrawal; PostgreSQL persistence; UI/browser flows.

## Acceptance Criteria
- [x] Handover preserves content/provenance and immediately changes private access.
- [x] Ownership changes are attributed, durable and concurrency guarded.
- [x] Dependency view distinguishes current/historical decisions and withdrawn/replaced publications.
- [x] Requirement access filters every result.
- [x] API/UI and local static quality gates validated.
- [ ] Green CI for a pushed revision.

## Validation Evidence
Executed 2026-09-22 with `.venv/Scripts/python.exe` and frontend npm tooling.
Python and final browser/tooling runs required execution outside the Windows sandbox because the
interpreter and generated cache files were denied inside it. No runtime permissions were changed.

```text
python -m pytest -o addopts= -q
1333 passed, 36 skipped, 1 warning in 151.46s (0:02:31)

python -m pytest tests/unit/test_library_governance.py -o addopts= -q
8 passed, 1 warning in 6.29s

python -m pytest tests/integration/test_library_postgres.py -o addopts= -q
12 passed, 1 warning in 11.49s

python -m ruff check .
All checks passed!

python -m ruff format --check .
833 files already formatted

python -m mypy src tests
Success: no issues found in 401 source files

lint-imports
Analyzed 346 files, 2476 dependencies.
Contracts: 6 kept, 0 broken.

npm run test
Test Files  40 passed (40)
Tests  273 passed (273)

npm run test -- src/app/LibraryPage.test.tsx
Test Files  1 passed (1)
Tests  6 passed (6)

npm run test:smoke -- library-governance.spec.ts
2 passed (20.3s)

npm run lint
exit 0
npm run typecheck
exit 0
npm run api:check
exit 0
npm run build
2001 modules transformed; built successfully; exit 0

impeccable detect --json frontend/src/app/LibraryGovernance.tsx frontend/src/app/LibraryPage.tsx
[]
git diff --check
exit 0
```

PostgreSQL used the existing disposable `codex_document_knowledge_test_20260921`, with an explicit
`select current_database()` check before testing. No production database was used. The twelve
contracts cover library round trips, exclusions, indexing and owner projection/history/key changes.
The added transfer contract passed before the later pure-domain chain validation; the final unit
run covers that validation and legacy missing-history decoding.

The initial whole-tree lint/format gates failed on three existing tracked UI helper scripts
(`.claude/skills/ui-ux-pro-max/scripts`). Mechanical formatting/import cleanup, unchanged string
wrapping and removal of unused local reads restored green gates; their design-system CLI smoke
also completed successfully. No lint exclusions were added.

Browser evidence: full-page and ownership-section captures at 1440px and 390px in
`.impeccable/review/governance-{desktop,mobile}.png` and `ownership-{desktop,mobile}.png`.
Both passes verified no horizontal overflow, publication staleness, transfer, former-owner loss of
private access, new-owner history and membership-filtered empty dependencies. Final browser tests
also cover clearing selection/acknowledgement when changing user search.
The independent reviewer marked its one recipient-search finding resolved and returned `ship`
at the fix-list scope. The documenter confirmed no new visual-system decisions or shipping assets.

The final full backend suite passed with 1,333 tests; 36 environment-dependent tests were skipped
without `TEST_DATABASE_URL`. The separate library PostgreSQL run above exercised all twelve
library contracts against the explicitly verified disposable database. Local completion does not
claim green CI or deployment: this working-tree change has not been pushed.

## Changed Files
- Domain: `src/smb_requirement_agent/domain/document/library.py`.
- Application: `application/use_cases/library_governance.py`, `application/use_cases/document_library.py`.
- Persistence: `infrastructure/persistence/document_library.py`.
- API: `interfaces/api/routes/library.py`, `interfaces/api/container.py`, `interfaces/api/dependencies.py`.
  The application/persistence/API paths above are under `src/smb_requirement_agent/`.
- Browser: `frontend/src/app/LibraryGovernance.tsx`, `LibraryPage.tsx`, `LibraryPage.test.tsx`,
  `frontend/src/api/client.ts`, `schema.d.ts`, `frontend/openapi.json`,
  `frontend/tests/library-governance.spec.ts`.
- Tests: `tests/unit/test_library_governance.py`, `tests/integration/test_library_postgres.py`.
- Documentation: this spec, `enhancement-document-knowledge.md`, ADR-0063, architecture index,
  `docs/operations/document-knowledge.md`, `ROADMAP.md`, `WORKSPACE.md`, `AGENTS.md`, library surface brief.
- Gate cleanup: `.claude/skills/ui-ux-pro-max/scripts/core.py`, `design_system.py`, `search.py`.
- Visual evidence: the four governance/ownership captures listed above.
Existing unrelated working-tree changes were retained.

## Deferred / Open
Wider ingestion/retrieval scope remains in enhancement-document-knowledge.md. Dependency queries
reuse existing Requirement/round read ports; indexed portfolio-scale lineage is separate work.
CI must be verified for a pushed revision before release completion is claimed.
