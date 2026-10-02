# Enhancement â€” Direct Gemini and configuration-driven LLM integration

Approved scope: the user's Direct Gemini integration plan, following attachment-backed input.

Domain: retain requirements, source-document versions, reviews, citations and approved content.
Application: classify safe model failures; scope evidence caches to meaningful model settings;
rebuild derived knowledge through isolated, resumable generations and source-change checks.
Ports: retain focused generation/embedding ports; introduce provider-neutral index-generation operations.
Adapters: versioned YAML configuration, compatible chat/embedding HTTP transports, native Google
embedding batching, and equivalent PostgreSQL/in-memory generation storage. No new per-provider
business-operation adapters.
API/UI: preserve existing contracts and job correlation IDs; distinguish safe provider failures in
the existing job UI. No admin settings screen or secrets returned to clients.
Operations: local configuration check, explicit synthetic text/image/embedding smoke check,
resumable rebuild, retained generation inspection/rollback and profile-aware launchers.
Documentation: ADR-0043, `docs/llm-configuration.md`, configuration examples and workspace/roadmap entries.

Validation is recorded in the delivery report. CI remains pending commit/push. Live Gemini validation
and the operational backend switch require working Google project quota, separately from deterministic
contract tests and PostgreSQL validation. No blanket regeneration or provider fallback is authorized.


## Local validation — 2026-09-18

- Backend regression: 834 passed, 23 PostgreSQL cases skipped in the default environment.
- Separate isolated PostgreSQL run: all 23 passed, including durable generation resume,
  identity isolation, stale-source activation prevention, search and explicit rollback.
- Ruff lint and formatting, strict mypy, all six import contracts and git diff whitespace checks passed.
- Frontend: all 141 tests across 24 files, ESLint, generated API contract check, TypeScript/build passed.
- Browser smoke: all 22 desktop/responsive cases passed on isolated fake API/UI ports 8011/4183.
- Windows launcher check passed for legacy and Gemini profiles; explicit `-Provider local`
  with a configured profile was rejected as expected. Bash/CMD selection changes were inspected;
  they were not launched in a separate OS shell.
- Migration 018 applied to the user's database. Snapshot counts and content hashes for existing
  requirements, source documents, analyses, Epics and Features were unchanged by the migration.

The explicit live smoke failed with HTTP 429. A separate safe provider diagnostic confirmed
that generation and embedding requests both returned RESOURCE_EXHAUSTED with the message
"Your prepayment credits are depleted." The supplied key was never printed, persisted in YAML,
or sent to the browser. No project billing changes were performed.

The configured Gemini text/image/embedding smoke, complete production index rebuild, graceful
worker drain/backend switch, saved Markdown retry and live DOCX/visual-PDF/backlog/review/search
journeys remain pending working Google project credits. The active legacy backend was preserved;
LLM_CONFIG_PATH was not enabled in the user's .env. Contract/fake/browser results are not presented
as successful live-provider validation. Existing Starlette/Node deprecations and the frontend
bundle-size warning remain. An earlier attachment-delivery report records an intermittent
in-memory background-job/saved-view rollback risk; this browser run passed all saved-view cases.

CI has not run for these uncommitted changes. Unrelated working-tree changes remain intact.


## OpenRouter citation failure correction — 2026-09-18

The user's legacy OpenRouter configuration selected google/gemini-3.1-flash-lite. HTTP 200
returned a valid nine-reference support mapping for a nine-layer RAG statement, but the shared
repair schema capped references at eight. Remove that arbitrary cap and retain nonempty support,
unique references and strict current-packet range checks. ADR-0032 records the correction.

The exact captured response now parses, and a regression test preserves every one of nine required
references. Backend regression: 835 passed, 23 PostgreSQL cases skipped; lint, formatting, typing,
six architecture contracts and git diff whitespace validation pass. No frontend contract changed.

With no active jobs, the existing API was signaled to shut down gracefully. Completed worker/app
shutdown was verified, then the same OpenRouter configuration and review UI were restarted.
Saved Markdown retry job 306e67fb-770d-4559-8dd3-9ac1eb6a8783 succeeded in 18 seconds. Its
analysis stores 11 facts; 11 checked source citations resolve to immutable document versions,
matching checksums and stored evidence blocks. The typed description remains empty and analysis
unconfirmed. The direct Google credit blocker remains separate from this successful OpenRouter run.

## Word attachment analysis investigation — 2026-09-18

Failed job 2ca9065f-c544-4fdc-8d7b-ecc8a732840f reached BUC9 after successful Word extraction
and multiple HTTP 200 model responses. The model invented an ambiguity about how "Test word"
relates to the BUC9 section. Its numbered support decision was false, so the strict evidence
boundary rejected the complete job. This is separate from the previous eight-reference cap.

Shared prompt guidance now makes attachment association, valid empty typed input and partial
document-section context explicit. Genuine missing business decisions and source conflicts
remain uncertainties. A regression covers the attachment-only prompt, images, instruction
isolation and text-only compatibility; prompt-version assertions were updated. No domain,
application, transport, API or frontend contract changed. Workers were idle, graceful shutdown
completed, and the app restarted with the same OpenRouter configuration.

The proposed live retry was rejected by automatic approval review because it would transmit
this saved Word document to OpenRouter without document-specific confirmation. No new retry
was created. Live verification remains pending explicit permission; local checks are reported
separately and do not establish provider success.

Local verification: full backend suite passes (836 passed, 23 PostgreSQL cases skipped).
Lint, formatting, typing and all six architecture contracts pass. No frontend contract
changed; live document retry remains pending explicit approval.

## Reliable citation repair — 2026-09-18

Approved follow-up: packet-specific output/reference ranges and exact decision count; retain
strict coverage, uniqueness and source-version checks. One additional citation-only correction
may repair malformed mapping JSON, shape or references. Both calls use identical frozen outputs,
evidence and images. Explicit unsupported items, refusals and transport failures are terminal.
Existing provider configuration, API/frontend schemas, saved requirements and analysis persistence
remain unchanged. No migrations, provider fallback or automatic saved-job retries were added.

Shared typed completed-response validation markers cover configured compatible transports and
legacy local/OpenRouter clients. Safe feedback cannot copy arbitrary provider text into prompts.
Legacy OpenRouter timed-out generation is not repeated. Exhausted citation validation reports
model_invalid_citations through the existing HTTP 502/job UI path. Trace entries record attempts,
validation category and durations; transports retain available token usage. Prompt/cache version
is analysis-v18-bounded-citation-correction. ADR-0032 records the bounded policy.

Deterministic contracts reproduce 24 outputs with 12 blocks and an invalid reference to block 13
across six transport setups, plus JSON/count/duplicate/empty support defects, unsupported content,
timeouts/authentication/rate limits/server exhaustion/refusals/filtering/truncation, immutable
citations, retained images and injection-safe correction feedback. Atomic failed-cache regressions
remain covered. Live OpenRouter analysis of authored text and a generated image passed in 16.02
seconds with five facts and eight checked source references. No saved user document was sent;
the saved Word document's live retry remains pending document-specific approval.

Final local verification: 952 backend tests passed, 23 PostgreSQL cases skipped in the default
environment. Ruff lint and formatting, strict typing, all six import contracts, generated
frontend contract checks and git diff whitespace validation pass. No new persistence changes
were made; the earlier isolated PostgreSQL run remains recorded separately. CI is pending push.
Workers had no queued/running jobs; graceful shutdown completed, and the app restarted with
the unchanged legacy OpenRouter configuration. API health and review UI HTTP checks passed.

## Post-credit retry: upstream rate limit — 2026-09-18

Job 473bbd2e-b503-4256-af75-6f08d72ffa45 failed at 11:42:11 local time after five successful
packet citation repairs. The final OpenRouter response was HTTP 200 but contained finish_reason
error and choices[0].error.code=429. Google reported google/gemini-3.1-flash-lite temporarily
rate-limited upstream. Incomplete JSON was a consequence of this provider failure, not a new
citation mapping defect. The earlier HTTP 402 payment failure did not recur in this attempt.

Shared compatible and legacy local/OpenRouter transports now classify embedded provider errors
before parsing partial JSON. Jobs expose the existing model_rate_limit message and correlation
instead of generic JSON failure. Payment errors also have a safe ModelTransportError message;
HTTP/API schemas remain unchanged. Deterministic six-transport contracts cover embedded
429/402/401/503 failures and partial JSON without citation correction, plus top-level errors,
string codes and error finish reasons without details. No saved document or paid generation
request was sent during this investigation. Provider capacity remains an external blocker.

Post-credit correction verification: 980 backend tests passed, 23 PostgreSQL tests skipped.
Lint, formatting, strict typing, all six architecture contracts, generated frontend contracts
and whitespace checks passed. No new paid provider call was made. Workers were idle before
graceful restart; API shutdown and restart with unchanged OpenRouter settings completed.
The provider's external rate limit is not resolved by this classification change. The saved
failed job and document remain preserved; no automatic retry or fallback was performed.
