# Fix — Human answer citations during question resolution

Status: implemented and validated locally; CI pending push.

## Objective

Repair the reported `Resolving 1 question failed` error caused by an empty document citation
for a fact derived from a supplied human answer.

## User Outcome

The existing question-resolution action can create the next analysis round using human-only
evidence. Reviewers see who supplied the supporting answer, its text and its timestamp.

## In Scope

- Corrective work on delivered Enhancements 8B.2/8B.3 and structured analysis Enhancement 5D.2.
- Separate human support, strict reference validation, bounded recovery and consolidation.
- Immutable round/snapshot/API provenance and the existing browser review surface.

## Out of Scope

- New roadmap slices, providers, database tables, changes to authorization or approval.
- Automatic replay of saved failed jobs, provider fallback, or external backlog publication.

## Domain

`AnalysisClarificationEvidence` identifies a generated output's supporting answer numbers in
the round's existing immutable clarification tuple. Numbers must be nonempty, unique, positive
and in range; duplicate output records fail. Existing answer attribution remains authoritative.

## Application Use Cases

Packet and final citation validation accept document and human sources separately. Consolidation
preserves human support through temporary findings and restores answer references before final
validation. Existing batch resolution retains atomic commit, authorization, version checks and
one analysis round. A failed provider response commits no resolution or round.

## Ports

The existing analyzer candidate adds optional `clarification_references`. All analyzer,
repository, cache, transaction, job and publication interfaces otherwise remain unchanged.

## Adapters

Initial citation schemas permit empty document lists so boundary validation can initiate the
existing bounded repair. A supplied human answer can support an output without a document block.
Focused mappings independently bound document and answer numbers; unsupported findings still
fail. JSON snapshots add default-empty human evidence with no relational migration. Shared and
legacy OpenAI adapters receive the actual answer count. Prompt version is analysis-v19.

## API

Existing analysis and round responses add default-empty `clarification_evidence`, containing
output keys and supporting answer numbers. Existing clarification records contain answer text,
question identity, actor and timestamp. OpenAPI and generated TypeScript include the addition.

## UI

Known facts, rules, constraints, proposals and active questions display separate expandable
human-answer source details. Document links retain their existing behavior. The existing batch
action, failed-job retry control and preservation of typed answers remain available.

## Business Rules

- Human evidence must never acquire a fabricated document identity or checksum.
- Human support does not approve AI interpretation or clear current blocker questions.
- Every structured output retains support; unsupported output is never silently dropped.
- Saved failed jobs are retried explicitly after the updated API is restarted.

## Tests

- Authored DEL/PABX regression through six real transport paths with mocked HTTP responses.
- Human-only first-call success and repair, empty document citation repair, unknown-answer
  rejection, bounded terminal failures and safe failure messages.
- Consolidation restores answer provenance without temporary document identities.
- Domain/application number validation, batch API attribution, immutable round history,
  JSON round-trip/legacy compatibility and browser source details.

## Acceptance Criteria

- [x] Empty initial citation lists can reach focused recovery without becoming empty success.
- [x] Human-only support preserves the answer source without fabricated document evidence.
- [x] Invalid references and unsupported findings fail without a partial resolution/round.
- [x] Consolidation, snapshots, API responses and browser review preserve human provenance.
- [x] Every field of the affected roadmap entries remains delivered; nothing was dropped.
- [x] All five mandatory backend gates and relevant frontend/browser checks pass locally.
- [ ] CI validates these changes after push.

## Validation Evidence

- `.venv\Scripts\python.exe -m pytest -o addopts="" -q` — PASS:
  `1016 passed, 23 skipped, 1 warning in 60.62s (0:01:00)`.
  The 23 skipped PostgreSQL tests require `TEST_DATABASE_URL`; it is not configured.
- `.venv-uv\Scripts\ruff.exe check .` — PASS: `All checks passed!`.
- `.venv-uv\Scripts\ruff.exe format --check .` — PASS: `456 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS:
  `Success: no issues found in 356 source files`.
- `.venv\Scripts\lint-imports.exe` — PASS: `Analyzed 321 files, 2243 dependencies`;
  `Contracts: 6 kept, 0 broken`.
- Frontend `npm.cmd run api:check` — PASS: generated schema has no drift.
- Frontend `npm.cmd run lint`, `npm.cmd run typecheck` — PASS.
- Frontend `npm.cmd run test -- --run` — PASS: `24 passed (24)` files;
  `142 passed (142)` tests, `Duration 22.23s`.
- Frontend `npm.cmd run build` — PASS: `1928 modules transformed`, `built in 616ms`.
  Existing Node shell deprecation and Vite chunk-size advisories remain non-fatal.
- First targeted browser run — FAIL: desktop counted zero questions during the persona
  refresh between a count assertion and a separate count read; responsive passed. The test
  now uses the known expected count for the remaining three questions and waits for inputs.
- Final frontend `npm.cmd run lint`, `npm.cmd run typecheck` — PASS.
- Final frontend `npm.cmd run test -- --run src/features/analysis/AnalysisPanel.test.tsx`
  — PASS: `1 passed (1)` file; `20 passed (20)` tests, `Duration 6.10s`.
- Final frontend `npm.cmd run build` — PASS: `1928 modules transformed`, `built in 323ms`.
- With `SMOKE_API_PORT=8058`, `SMOKE_UI_PORT=4228`, empty `LLM_CONFIG_PATH` and
  `DEBUG_TRACE_ENABLED=false`, frontend
  `npm.cmd run test:smoke -- --grep 'owner assigns a reviewer who drafts and resolves before owner confirmation'`
  — PASS: desktop `4.3s`, responsive `4.7s`, `2 passed (13.2s)`.
  The isolated API used fake providers and in-memory state.
- `git diff --check` — PASS; Git emitted only its existing LF/CRLF notices.
- CI — NOT RUN for this uncommitted working tree; pending push.
- Follow-up diagnosis, 2026-09-18 15:42: the retry still used the pre-fix process started
  at 14:44. Its transport requests contained neither `clarification_numbers` nor numbered
  human-answer guidance. Recovery marked the DEL/PABX human-supported fact unsupported.
- Local runtime restarted at approximately 15:51 with explicit `-Provider openrouter`
  and the existing PostgreSQL store. Launcher reports the schema current; `/health` is
  `ok`, and live OpenAPI exposes `clarification_evidence`. No failed job has been replayed.
- Automatic approval review rejected a live retry because it would send saved requirement
  and answer data to external OpenRouter without explicit transfer authorization. Retry
  awaits the user's approval; no alternate execution was attempted.
- Subsequent user-triggered live retry at 15:52 used the new schema and numbered human-answer
  guidance. Four packet repairs succeeded (16, 22, 21 and 14 cited outputs). Job
  `0b9bd9fc-d4ce-418e-9c12-65ecc120d646` then failed at 15:53:07 because the next OpenRouter
  response contained choice error `429`, metadata `rate_limit_exceeded`, and reported
  `google/gemini-3.1-flash-lite` temporarily rate-limited upstream. No exact reset time was
  supplied. This is a provider availability failure; the original schema failure was not
  observed in that attempt. A complete successful live round remains unverified.

## Changed Files

- `src/smb_requirement_agent/application/ports/requirement_analyzer.py`
- `src/smb_requirement_agent/application/use_cases/analysis_mapping.py`
- `src/smb_requirement_agent/application/use_cases/evidence_analysis.py`
- `src/smb_requirement_agent/domain/analysis/entities.py`
- `src/smb_requirement_agent/domain/analysis/value_objects.py`
- `src/smb_requirement_agent/infrastructure/llm/candidate_mappers.py`
- `src/smb_requirement_agent/infrastructure/llm/local_requirement_analyzer.py`
- `src/smb_requirement_agent/infrastructure/llm/openai_requirement_analyzer.py`
- `src/smb_requirement_agent/infrastructure/llm/prompts/analysis_prompt.py`
- `src/smb_requirement_agent/infrastructure/llm/schemas/analysis_schema.py`
- `src/smb_requirement_agent/infrastructure/persistence/snapshot_mapper.py`
- `src/smb_requirement_agent/interfaces/api/routes/analysis.py`
- `src/smb_requirement_agent/interfaces/api/schemas/analysis.py`
- `frontend/openapi.json`
- `frontend/src/api/schema.d.ts`
- `frontend/src/features/analysis/AnalysisPanel.tsx`
- `frontend/src/features/analysis/AnalysisPanel.test.tsx`
- `frontend/src/test/fixtures.ts`
- `frontend/src/styles.css`
- `frontend/tests/review-flow.spec.ts`
- `tests/unit/test_citation_recovery.py`
- `tests/unit/test_structured_evidence_analysis.py`
- `tests/unit/test_analysis_collaboration_api.py`
- `tests/unit/test_analysis_clarification_evidence.py`
- `tests/unit/test_local_llm_adapters.py`
- `tests/unit/test_openai_analyzer.py`
- `docs/architecture/adr-0032-focused-local-citation-recovery.md`
- `docs/architecture/adr-0044-human-answer-analysis-citations.md`
- `docs/architecture/README.md`
- `docs/slices/fix-human-answer-analysis-citations.md`

## Deferred / Open

- CI cannot validate this uncommitted working tree until it is pushed.
- The running API loads human-answer support, mandatory-rule guidance, source-content
  cardinality correction, early governed-intent normalization and uncertainty-context citation
  guidance. No successful live resolution round is yet verified; the single authorized live
  attempt failed on gap questions before the final guidance was loaded, as recorded below.
- Live provider work is not part of deterministic regression tests. The agent did not invoke
  the rejected retry; the subsequent live attempt was user-triggered.

## Follow-up: unsupported mandatory-rule exception, 2026-09-18

The 16:23 user-triggered retry supplied a packet stating "IP Phone shall be mandatory for each
user line" and one human answer defining DEL as single-user and PABX as multi-user plans. The
model generated both the mandatory rule and "An IP phone is required for each user line where
no soft client option exists." At 12:23:54 UTC, focused recovery reported output 6 unsupported.
This is a genuine invented exception, not a document extraction, human-answer citation, or
frontend request-loading defect. The failed batch did not save a replacement analysis.

Maintenance of Enhancement 8B.2 retains every delivered roadmap field: existing atomic
stable-ID resolution, authorization/version checks and immutable rounds; existing analyzer,
job and persistence ports/adapters; existing API and batch UI; and existing rollback coverage.
This follow-up changes only shared infrastructure prompt guidance and offline transport tests.
No domain, application, API, UI, provider configuration or database changes are required.

The shared prompt explicitly preserves mandatory obligations and their scope, rejects invented
conditional variants, and distinguishes a conflicting human answer from a silent rule change.
Version `analysis-v20-preserve-source-obligations` prevents old fragments from being reused.
ADR-0032 records the observation without changing its unsupported-output rejection decision.
Tests exercise the supported mandatory rule and the rejected invented exception through six
real transport paths using authored fixtures and mocked HTTP; no paid provider calls are made.
This is a preventive prompt correction, not proof that future live output cannot hallucinate.

### Follow-up Validation Evidence

- Targeted `.venv\Scripts\python.exe -m pytest -o addopts="" -q tests/unit/test_citation_recovery.py`
  — PASS: `178 passed, 1 warning in 1.99s`.
- Initial lint and format checks — FAIL: one long test line and one missing blank line.
  Formatting was corrected before final gates.
- Initial full pytest — FAIL: `2 failed, 1026 passed, 23 skipped, 1 warning in 60.42s`.
  Both failures were the legacy adapter tests expecting the previous prompt version. Updated
  those assertions; no functional failure was observed. An intermediate format check then
  detected mixed line endings in those two edited files; both were normalized.
- Final `.venv-uv\Scripts\ruff.exe check .` — PASS: `All checks passed!`.
- Final `.venv-uv\Scripts\ruff.exe format --check .` — PASS: `457 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS:
  `Success: no issues found in 356 source files`.
- `.venv\Scripts\lint-imports.exe` — PASS: `Analyzed 321 files, 2243 dependencies`;
  `Contracts: 6 kept, 0 broken`.
- Final `.venv\Scripts\python.exe -m pytest -o addopts="" -q` — PASS:
  `1028 passed, 23 skipped, 1 warning in 59.55s`.
  PostgreSQL integration skips still require the unconfigured `TEST_DATABASE_URL`.
- Local runtime reload at 16:31 — PASS: verified the existing launcher process tree and
  read-only PostgreSQL query returned `Active jobs before local reload: 0`. Restarted the
  existing OpenRouter/PostgreSQL configuration. Launcher states `Configuration is valid; no
  paid model requests were made`, schema current, and `Application ready`.
  API `/health` returned `{"status":"ok"}`; review UI returned HTTP `200`.
  No question-resolution job or paid provider call was initiated by this reload.
- `git diff --check` — PASS; only existing LF/CRLF notices were emitted.
- CI — NOT RUN for this uncommitted working tree; pending push.

Additional files changed in this follow-up are the existing prompt-version assertions in
`tests/unit/test_local_llm_adapters.py` and `tests/unit/test_openai_analyzer.py`.

## Follow-up: complete supported content cardinality, 2026-09-18

Job `0247b175-996a-4165-960a-cecc40d8b6a4` failed at 12:32:47 UTC (16:32 Dubai) before citation
validation: its completed model response contained 15 known facts, exceeding the internal
schema's maximum of 12. The resulting `too_long` validation marker lacked a safe classified
cause on the legacy OpenRouter path, so the job displayed the generic service failure.

Remove arbitrary maxima from source-backed known facts, constraints and business rules;
do not drop facts or aggregate unrelated statements to satisfy a reviewer question limit.
Keep uncertainty/proposal limits and strict normalization/citation coverage. Remove the
repair-only fixed 64-output ceiling, retaining dynamic exact-count and per-packet reference
bounds. Provider token/context limits remain unchanged. Increment the prompt version to
`analysis-v21-complete-source-content` to invalidate old fragment identities. Structural
validation markers carry the existing safe `ModelTransportError("invalid_output")` cause;
the analyzer wraps both legacy and configured transport errors. No provider text is exposed.

This remains maintenance of the delivered Enhancement 8B.2/8B.3 analyzer path; no roadmap
field is omitted, domain rule changed, provider configured, database migrated, or API/UI schema
changed. The existing atomic batch/round rollback remains authoritative. ADR-0032 records the
cardinality correction and retained bounds. Unrelated working-tree changes are preserved.

Changed files for this follow-up:

- `src/smb_requirement_agent/infrastructure/llm/schemas/analysis_schema.py`
- `src/smb_requirement_agent/infrastructure/llm/structured_output.py`
- `src/smb_requirement_agent/infrastructure/llm/local_requirement_analyzer.py`
- `src/smb_requirement_agent/infrastructure/llm/prompts/analysis_prompt.py`
- `tests/unit/test_citation_recovery.py`
- `tests/unit/test_local_llm_adapters.py`
- `tests/unit/test_openai_analyzer.py`
- `docs/architecture/adr-0032-focused-local-citation-recovery.md`
- `docs/slices/fix-human-answer-analysis-citations.md`

### Cardinality Validation Evidence

- Initial targeted test run — FAIL: `4 failed, 384 passed, 1 warning in 9.97s`.
  Configured transports raised the expected `ModelTransportError` directly, while the test
  expected the analyzer's `RequirementAnalysisGenerationError`. The shared analyzer now wraps
  both transport error types consistently, preserving the safe classified cause.
- Final `.venv\Scripts\python.exe -m pytest -o addopts="" -q tests/unit/test_citation_recovery.py
  tests/unit/test_local_llm_adapters.py tests/unit/test_openai_analyzer.py tests/unit/test_error_handlers.py`
  — PASS: `388 passed, 1 warning in 9.67s`. Authored fixtures and mocked HTTP cover 15/65 items
  in each source-backed list through six transport paths, complete citation coverage, rejected
  missing mappings, unsupported findings, and safe malformed-response errors with no retry.
- `.venv-uv\Scripts\ruff.exe check .` — PASS: `All checks passed!`.
- `.venv-uv\Scripts\ruff.exe format --check .` — PASS: `457 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS:
  `Success: no issues found in 356 source files`.
- `.venv\Scripts\lint-imports.exe` — PASS: `Analyzed 321 files, 2243 dependencies`;
  `Contracts: 6 kept, 0 broken`.
- Frontend `npm.cmd run api:check` — PASS: generated public API types have no drift.
- Full `.venv\Scripts\python.exe -m pytest -o addopts="" -q` — PASS:
  `1070 passed, 23 skipped, 1 warning in 60.23s (0:01:00)`.
  The PostgreSQL integration skips require the unconfigured `TEST_DATABASE_URL`.
- Exact rejected response replay, local only — PASS:
  `Offline replay of rejected response: PASS (15 facts, 3 constraints, 3 rules)`.
  This proves the initial schema failure is corrected; it does not claim the full response's
  citation semantics pass or that a new live resolution succeeded.
- Local runtime reload at 16:37 — PASS: read-only database check returned
  `Active jobs before local reload: 0`. Verified and restarted only the existing app process
  tree using its existing OpenRouter/PostgreSQL configuration. Launcher reports schema current,
  no paid configuration-check requests, and `Application ready`. API `/health` returned
  `{"status":"ok"}`; UI returned HTTP `200`. No failed question job was replayed.
- `git diff --check` — PASS.
- CI — NOT RUN for this uncommitted working tree; pending push.
- Live resolution remains unverified; offline provider fixtures do not establish a successful
  paid-provider round. No agent-initiated question retry is included in this follow-up.

## Follow-up: governed intent before packet citations, 2026-09-18

At 16:39, job `e7369d66-68dd-4dca-93bb-683f11298107` repaired earlier packets successfully,
then failed on the BUC4 add-on packet. Its only unsupported output (number 9) repeated the
requirement-wide desired outcome already accepted by the owner. Add-on evidence and the DEL/PABX
human answer did not mention financial reporting. This was not a newly invented outcome: the
application already carries the owner's decision forward and excludes redundant generated
outcomes, but that exclusion occurred after packet citation validation. Prompt rules 18 and 21
also conflicted when typed outcome was absent but an accepted outcome existed.

Extract the existing proposal-selection policy into `is_additional_intent_proposal` in the
domain and reuse it in application construction and shared provider-boundary normalization.
Normalize only proposal fields excluded by that policy before freezing citation outputs, along
with their redundant proposal citations. Retain citations shared with a still-eligible proposal.
Source/accepted/edited outcomes remain authoritative; decided original/effective statement echoes,
including rejected repeats, cannot become new proposals. No genuine fact, question or eligible
new proposal is removed to bypass an unsupported finding. Prior owner decisions retain all
identity, version, measures, attribution, history and evidence; no new provenance type is needed.
The prompt requires a candidate outcome only if neither source nor accepted/edited intent
supplies it. Version `analysis-v22-governed-intent-context` invalidates prior fragment identities.

Maintenance scope covers the existing Enhancements 8B.2/8B.3 and structured analysis path,
preserving every delivered roadmap field. Existing analyzer ports, provider configuration,
batch API/UI, authorization, optimistic checks, failure-atomic commit and persistence schema
remain unchanged. Domain/application changes factor the existing rule; they introduce no new
business behavior. ADR-0032 records the earlier normalization boundary. Unrelated edits remain.

Changed files in this follow-up:

- `src/smb_requirement_agent/domain/analysis/value_objects.py`
- `src/smb_requirement_agent/application/use_cases/analysis_mapping.py`
- `src/smb_requirement_agent/infrastructure/llm/candidate_mappers.py`
- `src/smb_requirement_agent/infrastructure/llm/local_requirement_analyzer.py`
- `src/smb_requirement_agent/infrastructure/llm/openai_requirement_analyzer.py`
- `src/smb_requirement_agent/infrastructure/llm/prompts/analysis_prompt.py`
- `tests/unit/test_citation_recovery.py`
- `tests/unit/test_local_llm_adapters.py`
- `tests/unit/test_openai_analyzer.py`
- `docs/architecture/adr-0032-focused-local-citation-recovery.md`
- `docs/slices/fix-human-answer-analysis-citations.md`

### Governed Intent Validation Evidence

- Initial lint — FAIL: unsorted new test imports; corrected with targeted import sorting.
- Intermediate mypy — FAIL: three unsupported TypedDict keyword-update arguments in the new
  SDK fixture. Corrected with a typed dictionary replacement; production typing was unaffected.
- Targeted `.venv\Scripts\python.exe -m pytest -o addopts="" -q tests/unit/test_citation_recovery.py
  tests/unit/test_openai_analyzer.py tests/unit/test_local_llm_adapters.py
  tests/unit/test_analysis_use_cases.py tests/unit/test_structured_evidence_analysis.py`
  — PASS: `356 passed, 1 warning in 9.68s`.
  Shared transport tests cover source/accepted/edited outcomes, one-call and repaired citation
  paths, immutable carried decisions and continued rejection of unsupported new outcomes.
  Legacy SDK tests cover all three proposal kinds and accepted/edited/rejected decisions,
  remove only redundant proposal citations, and leave original provider objects unchanged.
- Full `.venv\Scripts\python.exe -m pytest -o addopts="" -q` — PASS:
  `1121 passed, 23 skipped, 1 warning in 59.86s`.
  Skipped PostgreSQL integration tests require the unconfigured `TEST_DATABASE_URL`.
- `.venv-uv\Scripts\ruff.exe check .` — PASS: `All checks passed!`.
- `.venv-uv\Scripts\ruff.exe format --check .` — PASS: `457 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS:
  `Success: no issues found in 356 source files`.
- `.venv\Scripts\lint-imports.exe` — PASS: `Analyzed 321 files, 2243 dependencies`;
  `Contracts: 6 kept, 0 broken`.
- Frontend `npm.cmd run api:check` — PASS: public generated types have no drift.
- Local exact failed-packet replay, using read-only persisted decisions — PASS:
  `Exact failed packet normalization: PASS (9 outputs -> 8 genuinely generated outputs)`;
  `Owner decisions preserved: 1; active jobs before reload: 0`.
- Local reload at 16:47 — PASS: restarted only the verified idle app process tree with its
  existing OpenRouter/PostgreSQL configuration. Schema current, `Application ready`, health `ok`.
- User explicitly approved one live retry, including transmission of the saved requirement,
  selected document evidence and answer through configured OpenRouter. Started exactly one
  retry via the existing API, idempotency key stored in ignored local logs; new job
  `7a146b1a-e819-4bcb-bd99-77faa684b067` retries the failed job above and reports one answer.
  No additional live retry is authorized or started. Actual result: FAIL at 16:49:18,
  `model_invalid_citations`, correlation `747d3184-04c3-4eff-b9b3-f9ecef98c18a`.
  Five packet units completed before BUC4 recovery rejected questions 10 and 11 about failure
  handling and whether audit requirements exist. The accepted-outcome issue did not recur;
  no final analysis/answer was saved. Read-only state remained round 1 with zero clarifications.
- CI — NOT RUN for this uncommitted working tree; pending push.

### Final follow-up: operation context for missing-decision questions

The authorized retry exposed a different semantic-support disagreement. The generation prompt
requires checking relevant failure/audit decisions, while recovery already allows a question's
business context to expose a gap without stating its answer. The flow exists in evidence;
asking about its missing failure handling or whether it requires auditing does not assert a
new rule. Recovery instead marked both unsupported. Do not drop these reviewer questions,
fabricate answers, or accept the unsupported decision automatically.

Add explicit positive and negative examples to citation-recovery guidance: cite a documented
add/delete flow for its missing failure-handling decision and a question about whether auditing
is required; do not treat that flow as support for a fact mandating an audit record, an invented
regulatory rule, or a question about an unrelated operation. Existing strict reference checks,
unsupported-terminal behavior and fact/rule support requirements remain unchanged.
Prompt version `analysis-v23-uncertainty-context-citations` invalidates earlier fragments.
Six mocked transport regressions prove the supported question shape preserves the questions,
attaches the flow evidence and does not turn them into facts or business rules. These fixtures
cannot prove a live model will follow the revised guidance. No second paid retry was run.

Final guidance changes are confined to the shared prompt, its two expected-version assertions,
`tests/unit/test_citation_recovery.py`, ADR-0032 and this spec. Domain/application changes above
remain a refactor of the existing governed-intent rule; API/UI/ports/provider settings remain
compatible, and every maintenance roadmap field remains delivered.

### Final Validation Evidence

- `.venv\Scripts\python.exe -m pytest -o addopts="" -q` — PASS:
  `1127 passed, 23 skipped, 1 warning in 60.31s (0:01:00)`.
  PostgreSQL integration skips require the unconfigured `TEST_DATABASE_URL`.
- `.venv-uv\Scripts\ruff.exe check .` — PASS: `All checks passed!`.
- `.venv-uv\Scripts\ruff.exe format --check .` — PASS: `457 files already formatted`.
- `.venv\Scripts\python.exe -m mypy src tests` — PASS:
  `Success: no issues found in 356 source files`.
- `.venv\Scripts\lint-imports.exe` — PASS: `Analyzed 321 files, 2243 dependencies`;
  `Contracts: 6 kept, 0 broken`.
- Public API contract check above remains valid; final changes affect internal prompt guidance
  and tests only. No API schema changed afterward.
- Final app reload at 16:52 — completed with the existing OpenRouter/PostgreSQL configuration,
  after read-only job-state check found zero active jobs. No failed job was replayed.
- Final launcher — PASS: `Application ready`, PostgreSQL schema current. API `/health`
  returned `{"status":"ok"}`; review UI returned HTTP `200`; `git diff --check` — PASS.
- Live verification — FAIL for the one authorized attempt; final guidance NOT VERIFIED LIVE.
- CI — NOT RUN; pending push. A complete successful resolution is still an open acceptance item.

## Follow-up: preserve business context in citation recovery, 2026-09-18

User-triggered job `fb2a8809-a6a3-4fbd-9f70-c8396515be0f` failed at 12:54:53 UTC (16:54 Dubai),
correlation `bc5dfa93-f2a5-4a2e-abcf-09f14d14b0b3`. The add-on failure/audit issue did not recur;
the external-shift packet reported only output 13 unsupported: a question asking about financial
or billing implications of shifting the account. Its generated rationale explicitly says the
desired outcome mentions financial reporting but the source leaves shift billing unspecified.
The owner-accepted outcome exists in the generation request, while focused recovery omits it
and the rationale. This is a concrete context loss between stages.

Preserve requirement business need, structured source context and accepted/edited effective
owner intent as unnumbered relevance context in recovery. Include question/ambiguity rationales
alongside the same frozen subjects. This context can explain why a missing decision matters to
a supplied operation; it is not a new evidence source and cannot independently prove a factual
claim or create a document/answer reference. Questions still cite only their operation's supplied
document block or human answer. Generated rationales must be checked against inputs, not assumed
true. Pending/rejected owner intent is excluded from relevance context. Structural correction
reuses the exact same base prompt so context is not lost on its second bounded attempt.

The prompt version becomes `analysis-v24-citation-business-context`. No business rule, public
API/UI schema, domain provenance, provider settings or database schema changes are introduced.
This maintains the existing delivered 8B.2/8B.3 and structured-analysis slices; all roadmap
fields, existing job/round atomicity and authorization remain delivered. No slice field is
dropped. ADR-0032 records the context boundary. Unrelated working-tree changes are preserved.

Changed files for this follow-up:

- `src/smb_requirement_agent/infrastructure/llm/local_requirement_analyzer.py`
- `src/smb_requirement_agent/infrastructure/llm/prompts/analysis_prompt.py`
- `tests/unit/test_citation_recovery.py`
- `tests/unit/test_local_llm_adapters.py`
- `tests/unit/test_openai_analyzer.py`
- `docs/architecture/adr-0032-focused-local-citation-recovery.md`
- `docs/slices/fix-human-answer-analysis-citations.md`

### Recovery Context Validation Evidence

- Targeted `.venv\Scripts\python.exe -m pytest -o addopts="" -q tests/unit/test_citation_recovery.py
  tests/unit/test_openai_analyzer.py tests/unit/test_local_llm_adapters.py`
  — PASS: `363 passed, 1 warning in 10.00s`.
  Six mocked real transport paths prove confirmed intent and question rationales reach initial
  recovery and structural correction unchanged, operation citations survive, no synthetic human
  or document support is created, and an unsupported asserted billing rule still fails.
  Existing governed-outcome tests now distinguish retained relevance context from frozen outputs.
- Initial mypy — FAIL: two test list-invariance errors; corrected with `list[object]` annotation.
- Final `.venv-uv\Scripts\ruff.exe check .` — PASS: `All checks passed!`.
- Final `.venv-uv\Scripts\ruff.exe format --check .` — PASS: `457 files already formatted`.
- Final `.venv\Scripts\python.exe -m mypy src tests` — PASS:
  `Success: no issues found in 356 source files`.
- `.venv\Scripts\lint-imports.exe` — PASS: `Analyzed 321 files, 2243 dependencies`;
  `Contracts: 6 kept, 0 broken`.
- Frontend `npm.cmd run api:check` — PASS: no public API type drift.
- Full `.venv\Scripts\python.exe -m pytest -o addopts="" -q` — PASS:
  `1151 passed, 23 skipped, 1 warning in 146.97s (0:02:26)`.
  PostgreSQL integration skips still require the unconfigured `TEST_DATABASE_URL`.
- Local app reloaded at 17:00 after a read-only database check returned
  `Active jobs before local reload: 0`. Only the verified launcher process tree was restarted;
  existing OpenRouter/PostgreSQL configuration is unchanged. Launcher reports schema current
  and `Application ready`; API `/health` returned `{"status":"ok"}` and UI returned HTTP `200`.
  No failed job was replayed or paid provider request initiated.
- `git diff --check` — PASS.
- No further agent-initiated live retry was authorized or run. The last live attempt was
  user-triggered; final recovery-context wiring is NOT VERIFIED LIVE.
- CI — NOT RUN for this uncommitted working tree; pending push.
