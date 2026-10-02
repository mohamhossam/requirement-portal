# Enhancement — Local single-file debug trace

> Status: **implemented and validated locally**.

## Objective

Allow a developer to reconstruct local structured-output and citation failures from one explicit,
sensitive debug file without weakening provider validation or changing normal operational logs.

## Roadmap Scope Check

This is a user-directed bounded enhancement to the delivered local-provider and structured BRD
analysis capabilities. It does not start Slice 12 or drop any field from an active roadmap slice.

| Field | Delivery |
|---|---|
| Domain | No change; diagnostics are not business state. |
| Application | No use-case or port change. |
| Ports | No application port; an infrastructure-only trace abstraction is injected by the composition root. |
| Adapters | Null and single-file JSONL traces; local structured-output and analysis-mapping events. |
| API | No contract change; request lifecycle and mapped failures are traced internally when enabled. |
| UI | No change; developers inspect the local file and sensitive content is not exposed in-browser. |
| Tests | Disabled/enabled behavior, redaction, raw/parsed output, exact missing citations, and all gates. |

## Behavior

- Normal operation creates no debug file and retains existing timestamped stdout/stderr logs.
- `start.ps1 -DebugTrace` or `DEBUG_TRACE_ENABLED=true` appends JSON Lines to the single configured
  `DEBUG_TRACE_PATH`, defaulting to `logs/debug.log`.
- The trace records backend request lifecycle, local LLM request/response, parsed schema,
  normalized analysis, expected/returned/missing citation keys, focused citation-repair outcomes,
  and mapped exception chains.
- Requirement and document text are deliberately included for exact local diagnosis.
- Credentials, cookies, database URLs, binary/image payloads, and hidden reasoning are always
  redacted. The file is not an audit record and must be deleted after debugging.

## Tests

- Null tracing performs no file I/O.
- Enabled tracing appends valid JSON Lines to one file and flushes each event.
- Sensitive fields, bytes, image data URLs, and hidden reasoning are redacted.
- Local structured-output tracing retains the request, raw final response, and parsed model.
- Citation failure tracing names the exact normalized missing key.
- Settings parse and validate the opt-in configuration.

## Acceptance Criteria

- [x] Debug tracing is explicit and disabled by default.
- [x] One configured file contains the events needed to reconstruct the observed citation failure.
- [x] Existing validation remains strict; citations are not inferred or fabricated.
- [x] Secrets, image bytes, and hidden reasoning cannot enter the trace.
- [x] API/UI contracts and Domain/Application behavior remain unchanged.
- [x] All mandatory quality gates pass.

## Validation Evidence

- `pytest` — PASS (`636 passed, 18 skipped`).
- `ruff check .` — PASS.
- `ruff format --check .` — PASS (`381 files already formatted`).
- `mypy src tests` — PASS (`306 source files`).
- `lint-imports` — PASS (`2 kept, 0 broken`).
- `npm.cmd test -- --run` — PASS (`118 passed`).
- `npm.cmd run lint` — PASS.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run build` — PASS (chunk-size advisory only).
- `npm.cmd run api:check` — PASS.
- PowerShell parser check — PASS.

## Architecture Impact

ADR-0031 narrows ADR-0007 for explicit local debug sessions. The trace remains Infrastructure,
is selected in `interfaces/api/container.py`, and does not enter Domain or Application.

## Deferred / Open

- No log rotation or retention automation is introduced; the developer removes the file.
- OpenAI SDK request/response bodies are not traced; this enhancement targets the configured local
  OpenAI-compatible transport involved in the reported failure.
