# Enhancement — Owner-reviewed reference applicability

## Objective

Deliver the next vertical path from published library evidence to Requirement analysis and
owner-reviewed applicability. Implementation checkpoint; not overall production-plan completion.

## User Outcome

After a policy is reviewed, approved and indexed, analysing a related Requirement can produce a
separately labelled proposal. The owner opens its exact published passage, explains applicability,
then accepts, edits or rejects it. Only accepted content enters the existing accepted-intent input
for backlog generation. Withdrawal/replacement keeps history visible but blocks unsafe reuse.

## In Scope

- Domain citations, reference proposal provenance/conflicts and decision rationale.
- Focused hybrid reference retrieval after complete primary analysis, bounded labelled packets.
- Configured and offline proposal adapters, strict evidence membership and live-publication checks.
- Persistence, compatible API fields, existing review UI, generation/final-approval currency guards.
- Regression, adapter, API, PostgreSQL/pgvector and real browser validation.

## Out of Scope

The remaining approved ingestion/quality plan is not dropped: OCR qualification, advanced table and
parent-context chunking, unified Requirement/document retrieval, reference-based answer suggestions,
corpus generations, operational budgets/telemetry, load/evaluation and restoration remain in the
parent enhancement ledger. No external backlog publication or automatic applicability approval.

## Domain

`PublishedReference` retains exact versioned evidence and content lineage. `IntentProposal` adds
reference evidence, conflict and provenance. Its append-only decisions require a rationale for
reference-backed proposals; accepted/edited text follows the existing business-intent semantics.

## Application Use Cases

`ReferenceGrounding` supplements complete analysis with separately labelled proposals.
`AnalysisCollaboration` validates citations before persistence and owner decisions.
Confirmation, generation resume guards, review evidence and final approval check publication
currency lazily. Re-analysis preserves historical decided proposals, including stale references.

## Ports

ReferenceProposerPort, ReferenceAnalysisPort and ReferenceEvidencePort; explicit collaborators,
not optional fallbacks. Library persistence exposes publication presence, index compatibility and
transactional publication locks. The composition root alone selects concrete adapters.

## Adapters

Shared structured-output proposal adapter for configured/local/OpenRouter transports, focused
OpenAI SDK transport and deterministic offline fake. Exact snapshot serialization works in memory
and PostgreSQL; legacy payloads default safely. No new migration or environment variable.

## API

Existing analysis responses add `stale_reference_proposal_ids`. Intent proposals add
`reference_evidence`, `reference_conflict`, `reference_provenance`; decisions add `rationale`.
PATCH `/requirements/{id}/analysis/proposals/{proposal_id}` accepts a bounded rationale.
Existing mapped 422/403/409/502 errors retain their meanings. Historical rounds remain readable.

## UI

Extend the existing AnalysisPanel: reference applicability label, original excerpt, exact source
link opening separately, model/prompt provenance, conflict instruction, required rationale and
existing accept/edit/reject controls. Stale citations show reconciliation instructions and disable
accept/edit/confirmation. Decided content says the owner decision is recorded. Unsaved intent
drafts use the existing navigation guard. Passage excerpts use automatic direction and isolated
source labels. No new design system or routing workflow.

## Business Rules

- Similarity and publication approval do not establish applicability.
- Only the Requirement owner decides; rationale applies to rejection as well as acceptance.
- Unknown citations and publication changes cannot silently persist generated work.
- Rejected historical citations do not block current work; active stale ones do.
- Identical copied passages are deduplicated; the legacy Requirement index does not count
  reference-derived decisions/analysis as independent corroboration (ADR-0052).
- No published library means no added embedding/proposal call.

## Tests

New reference tests cover persistence, malformed/empty/provider responses, authority, rationale,
metadata tampering, withdrawal during analysis and Epic generation, no partial artifacts,
preserved confirmation history/re-analysis, and incompatible index generation. Existing full
tests cover confirmation/review mappings and old snapshot compatibility. PostgreSQL contract now
persists and reloads reference decisions across connection restart and checks withdrawal currency.
Browser tests exercise actual ingestion → publication → analysis → citation → decision → withdrawal
at desktop and 390px. UI tests enforce rationale and stale acceptance/rejection behavior.

## Acceptance Criteria

- [x] Published references produce proposals rather than primary facts.
- [x] Owner decisions preserve exact citations and rationale.
- [x] Stale active citations block unsafe generation while history remains readable.
- [x] Browser and API expose the complete owner-review path.
- [ ] Repository-wide lint/format and CI green (existing unrelated skill scripts fail locally).
- [ ] Overall plan's provider/OCR/quality/capacity qualification (parent enhancement).

## Validation Evidence

2026-09-21, Windows/Python 3.14, deterministic fake provider. No live provider calls.

```text
TEST_DATABASE_URL=<dedicated disposable codex_document_knowledge_test_20260921 database>
.venv/Scripts/python.exe -m pytest -rA --tb=short
1205 passed, 1 warning in 208.21s (0:03:28)

.venv/Scripts/python.exe -m mypy src tests
Success: no issues found in 378 source files

.venv/Scripts/lint-imports.exe
Contracts: 6 kept, 0 broken.

.venv/Scripts/python.exe -m ruff check . --output-format concise
Found 72 errors. All in .claude/skills/ui-ux-pro-max/scripts/{core,design_system,search}.py

.venv/Scripts/python.exe -m ruff format --check .
3 files would be reformatted, 783 files already formatted
(same unrelated skill scripts; no exclusions added)

npm --prefix frontend test -- --reporter=dot
Test Files 38 passed (38); Tests 264 passed (264)

npm --prefix frontend run lint
exit 0
npm --prefix frontend run api:check
exit 0
npm --prefix frontend run build
1999 modules transformed; built successfully
npm --prefix frontend test -- src/features/analysis/AnalysisPanel.test.tsx --reporter=dot
23 passed (final rerun after correcting test-library selector typing)

npm --prefix frontend run test:smoke -- reference-applicability.spec.ts library-flow.spec.ts analysis-sources.spec.ts
6 passed; 2 legacy source-dialog tests failed on outdated accessible labels.
The reference and library workflows passed at both project widths.
Legacy selector correction rerun:
SMOKE_API_PORT=8133 SMOKE_UI_PORT=4233 npm --prefix frontend run test:smoke -- analysis-sources.spec.ts
2 failed: current source dialog is inset x=38 at width 390; test expects x=0/full width.
The updated accessible-label, source-link, attribution and focus assertions passed before this
pre-existing drawer geometry failure. Production Modal/source-dialog code was not changed.

.venv/Scripts/python.exe -m ruff check src tests scripts/evaluate_document_knowledge.py
All checks passed!
.venv/Scripts/python.exe -m ruff format --check src tests scripts/evaluate_document_knowledge.py
379 files already formatted
```

Impeccable detector on changed UI targets returned `[]`. Independent reviewer requested one
state-copy fix, then scored it resolved with `ship` at that fix-list scope; not a whole-surface
certification. Full-page desktop/narrow pending and decided captures were inspected. React guidance
preserved existing mutation/cache paths. Documentation verification is recorded in the surface brief.
CI has not been triggered/verified; the slice is not claimed release-qualified.

## Deferred

No approved plan requirement is silently removed. See the parent enhancement ledger and ADR-0052
for the temporary derived-copy indexing restriction and all remaining delivery/qualification work.
