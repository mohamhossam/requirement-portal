# Slice 14 — Architecture Knowledge Administration and Local RAG

## Objective

Let maintainers publish versioned architecture knowledge and let reviewers map
Feature/Story impacts against cited evidence from one pinned release.

## User Outcome

A maintainer edits systems, ownership, relationships, constraints, and
supporting documents in the browser; builds and previews an index; and
publishes or reactivates a reviewed release. An authenticated reader can see
published mapping evidence, uncertainty, provenance, and outdated knowledge.

## In Scope

- Approved expansion beyond the original roadmap entry: local English/Arabic
  hybrid RAG from curated PDF/DOCX/TXT uploads (and XLSX/CSV/TSV, ADR-0086), reader/maintainer roles integrated
  with the existing provider-neutral identity boundary, and durable architecture
  build/mapping jobs.
- Versioned shared catalogue, immutable document versions, source locations,
  PostgreSQL full-text and exact pgvector retrieval, local structured reasoning,
  and deterministic fake adapters.
- Explicit remapping and review refresh; old snapshots remain readable.

## Out of Scope

- Enterprise connectors, OCR, diagrams, general chat, backlog-generation RAG,
  rerankers, approximate vector indexes, GraphRAG, and LangChain.
- Changes to Requirement ownership/reviewer assignment, generic AI jobs, or
  notifications already delivered by Slices 8A and 8C.

## Domain

- `ArchitectureKnowledge`, `SystemDefinition`, capabilities, ownership,
  directed relationships, immutable document versions, and audit events.
- Validate identifiers, aliases including Arabic names, referential integrity,
  document selection, publication readiness, and immutable releases.
- Architecture impacts retain constraints, citations, classification,
  uncertainty, release/index identity, and model/prompt provenance.

## Application Use Cases

- Create/edit draft, YAML import/export, upload/select versions, build, preview
  retrieval and candidate impacts, publish/reactivate, inspect history/audit.
- Queue/execute build and mapping jobs with attempts, heartbeat leases,
  idempotent fingerprints, cancellation, and retry.
- Map all current Features/Stories against one pinned release, then recheck
  source fingerprint before committing. Reject a review refresh or decision
  against outdated architecture evidence.

## Ports

- Knowledge repository, YAML codec, located extraction, embeddings, evidence
  index, structured reasoner, identity, architecture jobs, and existing blob,
  clock, and transaction ports.

## Adapters

- PostgreSQL releases/audit/jobs and `simple` full-text plus `vector(1024)`
  chunks; shared document blobs; YAML import/export; local embedding and
  structured-output HTTP clients; a matching local embedding tokenizer file;
  OIDC JWT verification.
- In-memory repositories/index/jobs, deterministic fake embedding/reasoning,
  and fake identity for development and CI.

## API

- `/identity/me`, knowledge release/system/document/YAML/audit/build/preview/publish/
  activate/evidence routes, version retrieval, and `/jobs/{id}` recovery.
- Asynchronous mapping-job endpoint returning `202`; existing synchronous
  endpoint preserved. Errors continue through the central API error map.

## UI

- Architecture Knowledge area for searchable systems/capabilities, ownership,
  relationships, immutable uploads and version selection, draft YAML, build
  progress, retrieval/candidate preview, publication, history, and reactivation.
- Feature/Story impact panels show maintained constraints, citations,
  uncertainty, model provenance, and older-release notices. The browser uses
  the shared OIDC PKCE session in configured production mode and preserves authenticated PDF
  previews. English interface content preserves Arabic source text direction.

## Business Rules

- Ownership comes only from curated catalogue records — since 2026-09-29 the
  organisation catalogue (ADR-0080), no longer the release. AI evidence cannot
  create catalogue systems or squads on its own: document suggestions apply only
  when a maintainer accepts them (ADR-0081). Unknown human-declared systems remain
  unassigned. Conflicts and insufficient evidence are explicit.
- Only a draft built with the active embedding profile may publish. Publication
  atomically changes the active release, never backlog history. Reactivation
  requires a compatible index or the original deterministic seed.
- A mapping failure or concurrent edit never overwrites an earlier successful
  result. Retrieved documents cannot supply instructions or invoke tools.

## Tests

- Domain integrity, authorization, invalid token claims, upload signatures and
  duplicates, located extraction, embedding shape, invented citations/quotes,
  job lease recovery, pinned releases, stale review, and legacy snapshots.
- Thirty curated English/Arabic/identifier/conflict/no-answer retrieval cases
  exercise deterministic top-eight citation resolution in CI.
- Browser smoke covers administration on desktop and responsive viewports,
  reader restrictions, and the existing breakdown mapping/review flow.
- PostgreSQL/pgvector migration, index, release, and job integration runs in a
  dedicated CI service job.

## Acceptance Criteria

- [x] Maintainer can edit, upload, build, preview, publish, and reactivate a release.
- [x] Reader can inspect published citations but cannot inspect drafts or mutate knowledge.
- [x] Mapping pins a release, validates cited selections, preserves old output on failure,
      and prevents decisions on outdated evidence.
- [x] Local fake path and 30-case deterministic retrieval evaluation exist.
- [ ] Deployment-specific real local-model English/Arabic evaluation passes
      90% relevant top-eight evidence, 100% citation resolution, and zero
      invented ownership before `KNOWLEDGE_EVALUATION_APPROVED=true`.
- [ ] CI PostgreSQL/pgvector and all quality jobs report green on a push/PR.

## Validation Evidence

Merge-resolution validation, 2026-09-24:

```text
.venv\Scripts\python.exe -m pytest -q
1428 collected; 39 PostgreSQL tests skipped; all executed tests passed.

.venv\Scripts\ruff.exe check .
All checks passed!

.venv\Scripts\ruff.exe format --check .
892 files already formatted

.venv\Scripts\mypy.exe src tests
Success: no issues found in 448 source files

.venv\Scripts\lint-imports.exe
Analyzed 387 files, 2801 dependencies. Contracts: 6 kept, 0 broken.

npm run api:check
Generated OpenAPI types matched the committed snapshot; exit 0.

npm run lint
exit 0

npm run typecheck
exit 0

npm run test
Test Files 41 passed (41); Tests 278 passed (278).

npm run build
2007 modules transformed; production build completed; exit 0.

npx playwright test tests/architecture-knowledge.spec.ts --project=chromium
3 passed (11.1s)

TEST_DATABASE_URL=<disposable pgvector database> pytest tests/integration/test_postgres_architecture.py -q
2 passed on both a legacy Slice 14 schema and a fresh schema.
```

The merge moved the Slice 14 migrations from the now-occupied `006`/`007`
numbers to `025`/`026`. The migration runner records the new names without
reapplying DDL when it sees the legacy Slice 14 names, while a fresh database
applies the renumbered files normally. The full Playwright suite exceeded the
local command window; the directly affected architecture workflow was rerun
after correcting its duplicate page heading and passed all scenarios.

Review remediation, 2026-09-23:

| Finding | Implemented correction |
|---|---|
| Stale build overwrites published chunks | Immutable index per build attempt, attached only after the draft revision check; migration 007 preserves existing indexes. |
| Mapping overwrites concurrent edits | Always capture the fingerprint; final comparison and saves share a serializable PostgreSQL transaction or memory repository locks. |
| Build deduplication ignores profile | Build and mapping job fingerprints include processing profiles; workers reject changed profiles. |
| Deselected documents disappear | Independent durable version registry with published visibility; browser selection reads that registry. |
| Shared job is inaccessible to another reader | Mapping status is reader-visible in the shared corpus; build diagnostics stay maintainer-only. |
| Expired browser token cannot recover | Shared authenticated fetch clears a rejected token and notifies the sign-in gate, without clearing a newer session. |
| Citations lose quotes/system associations | Preserve validated system/chunk/quote triples in domain results, snapshots, API responses, and impact panels. |
| RAG policy belongs to infrastructure/routes | Move orchestration to `application/use_cases/resolve_architecture_knowledge.py`; move evidence access/readiness to application use cases; root selects job execution policy. |
| Multi-value typing removes delimiters | Preserve raw newline/comma input and normalize only when saving. |
| Failed saves clear forms | Clear squad/relationship fields only after success and only if unchanged since submission. |
| Integration fixture republishes an immutable release | Reuse the first publication result. |

Added regressions cover stale-build interleaving, edits during reasoning and during
commit, profile changes, cross-reader job deduplication, document deselection and
reselection, quoted citation association/round-trip, late 401 responses, and browser
typing/failed saves. PostgreSQL regressions additionally cover serialization
conflicts after the final read, immutable index attempts, and registry restart.

Final remediation command output (2026-09-23):

```text
.venv/Scripts/python.exe -m pytest -o addopts='' -q -rs
461 passed, 8 skipped, 1 warning in 11.38s

.venv/Scripts/python.exe -m ruff check .
All checks passed!

.venv/Scripts/python.exe -m ruff format --check .
299 files already formatted

.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 250 source files

.venv/Scripts/lint-imports.exe
Analyzed 195 files, 850 dependencies.
Contracts: 2 kept, 0 broken.

npm run api:check
OpenAPI types generated and matched the committed snapshot; exit 0.

npm run lint
exit 0

npm run typecheck
exit 0

npm test -- --reporter=dot
Test Files 17 passed (17)
Tests 76 passed (76)

npm run build
1917 modules transformed; production build completed; exit 0.

npm run test:smoke
10 passed (18.7s)
```

- Eight PostgreSQL/pgvector integration tests are collected but skipped because
  `TEST_DATABASE_URL` is not configured. `docker info` confirms the Docker engine
  pipe is absent. Their execution remains a CI/environment acceptance gate;
  passing fake adapters is not evidence that migration 007 has run on PostgreSQL.
- CI has not been run from this workspace. No push or pull request was requested.
- Actual local-model evaluation remains unavailable: no model endpoint is
  configured. Production enablement still requires the deployment evaluation.
- The frontend suite passes with an existing React render-update warning in
  `NewRequirementPage`/`RequirementForm`; backend tests report a Starlette/AnyIO
  deprecation warning. These do not originate in the architecture fixes.
- Initial validation caught a browser test selector mismatch, a strict TypeScript
  fixture access, and mixed line endings. Each was corrected before the final runs.

## Deferred

- Approximate vector index only after measured corpus scale; GraphRAG and
  LangChain remain unnecessary for the current relationship and retrieval
  workload. Requirement ownership and generic jobs remain in 8A/8C.
