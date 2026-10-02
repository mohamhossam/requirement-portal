# Enhancement — Local Structured Analysis Recovery

> Status: **implemented locally; deterministic validation passed; full live retry incomplete**.

## Objective

Recover safely when a local structured-output model omits evidence citations or invents question
reviews, without weakening source validation or persisting partial analysis.

## Roadmap Scope Check

This is a user-directed bounded enhancement to delivered Enhancement 5D.2 and the local-provider
adapter. It does not start Slice 12 or drop any active roadmap field.

| Field | Delivery |
|---|---|
| Domain | No change; evidence and review invariants remain strict. |
| Application | Packet cache writes are staged until all analysis and citation validation succeeds. |
| Ports | The internal fragment-cache port gains an atomic batch-write operation. |
| Adapters | Staged content/citation mapping, one indexed citation repair, question-review normalization, and deterministic Ollama alias. |
| API | No contract change; terminal failures retain the existing provider-failure behavior. |
| UI | No change; existing job status and retry controls expose the result. |
| Tests | First-call success, repair success/failure, questions, images, trace events, tooling, and all gates. |

## Behavior

- A complete provider response succeeds without an extra call.
- Citation validation failure triggers one focused request over frozen numbered outputs and
  numbered packet evidence. The adapter restores exact subjects and block IDs before applying the
  existing validator.
- Unsupported, missing, duplicate, overlapping, or out-of-range recovery decisions fail the job.
  No content is dropped. New packet-cache entries are staged and committed as one adapter batch
  only after all packets, consolidation, and final citation validation succeed.
- Placeholder reviews are ignored when no active AI question exists. Active AI questions retain
  numbered reconciliation; protected human questions are never changed.
- Missing open-question or ambiguity rationales receive one focused numbered repair before
  question reconciliation and citation repair. Subjects and kinds remain frozen.
- The prompt version is `analysis-v15-explicit-gap-evidence-recovery`. The Ollama project alias and new
  prompt version create distinct provenance and cache keys.
- Debug tracing records repair start, success, unsupported output, and invalid recovery without
  exposing image bytes or hidden reasoning.

## Acceptance Criteria

- [x] Valid first responses remain a one-call path.
- [x] Missing or invalid citations receive at most one focused repair.
- [x] Recovery uses application-owned values rather than copied provider IDs or text.
- [x] Unsupported or incomplete recovery fails atomically.
- [x] A later packet failure commits none of the newly generated packet fragments.
- [x] Invented reviews cannot mutate absent or protected questions.
- [x] Blank uncertainty rationales are repaired without rewriting their subjects or kinds.
- [x] Image evidence is resent to a focused repair.
- [x] The deterministic Ollama alias is reproducibly created and verified.
- [x] All mandatory backend, frontend, tooling, and parser gates pass.
- [ ] The reported BRD completes a full live retry on the local machine.

## Validation Evidence

- Duplicate-uncertainty latency correction (2026-09-10):
  `pytest tests/unit/test_local_llm_adapters.py -q` — PASS. A schema-valid response with two
  same-kind, case-insensitively identical uncertainty subjects now produces one normalized item,
  keeps the more detailed usable rationale, and completes without a full-analysis retry. The
  mapper still rejects conflicting classifications and duplicates of retained or protected human
  questions.
- Duplicate-uncertainty correction full gates (2026-09-10): `pytest -q` — PASS (PostgreSQL-only
  tests skipped because `TEST_DATABASE_URL` was not set); `ruff check .` — PASS;
  `ruff format --check .` — PASS (429 files); `mypy src tests` — PASS (339 source files);
  `lint-imports` — PASS (6 contracts kept, 0 broken).
- Reported duplicate-uncertainty Requirement live retry (2026-09-10) — PASS in 66 seconds. The
  trace records one `RequirementAnalysisSchema` request, one response, one normalized candidate,
  zero transport failures, and a persisted analysis with 11 unique ambiguities.
- Focused local-provider and structured-evidence tests — PASS.
- Ollama alias creation/probe — PASS; vision capability and 16,384-token live allocation.
- `pytest -q` — PASS.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS; 383 files formatted.
- `mypy src tests` — PASS; 306 source files.
- `lint-imports` — PASS; 2 contracts kept, 0 broken.
- Frontend `api:check`, lint, typecheck, test, build — PASS; 24 files / 118 tests.
- Frontend Playwright smoke — PASS; 16 tests on isolated ports.
- PowerShell parser checks — PASS for `start.ps1` and the Ollama setup script.
- Reported BRD live retry — INCOMPLETE. A v14 run validated 12/12 outputs in packet 1, 21/21 in
  the image packet, and 36/36, 27/27, and 9/9 outputs in consolidation before a later packet's
  repair marked two generated ambiguities unsupported; strict validation rejected the run. The
  final v15 attempt validated packet 1 but the image request reached the configured 300-second
  read timeout. No final analysis round or new packet-cache batch was persisted. Prompt-version
  changes prevent reuse of the pre-atomic v11 fragment.

## Architecture Impact

ADR-0032 records focused local recovery and delayed atomic fragment-cache publication. Domain,
HTTP contracts, and persistence schemas are unchanged.

The duplicate-uncertainty correction is boundary normalization in the shared infrastructure
mapper. It does not weaken domain uniqueness, change application ports, or require a new ADR.

## Deferred / Open

- Recovery is local-provider-specific. The OpenAI adapter retains its existing structured-output
  path until evidence demonstrates the same failure mode.
- Existing failed jobs are not replayed automatically; the owner explicitly retries analysis.
- CI remains pending until the branch is pushed.
- The full BRD live acceptance remains open. The local 8B vision model is variable: one
  image-bearing response took about 31 minutes, another completed in about one minute, and the
  final attempt reached the configured five-minute read timeout despite the 16K allocation.
- Strict mode also correctly rejects a run when focused repair identifies unsupported generated
  content. Resolving that requires a more reliable local vision model or another explicit product
  decision; this enhancement does not silently drop or accept those outputs.
