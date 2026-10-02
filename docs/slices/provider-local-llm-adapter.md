# Provider Enhancement — Local LLM Adapter

> Status: **implemented locally**. This is a bounded enhancement to delivered
> Slices 02–04, not the start or partial delivery of active Slice 05.

## Objective

Run the existing Requirement Analysis → Epic → Feature workflow against an
OpenAI-compatible model server on the user's machine without an external
provider account or placeholder credential.

## User Outcome

A developer can select `LLM_PROVIDER=local`, name a loaded local model, and use
the existing API and browser review workflow unchanged.

## In Scope

- Local structured-output HTTP transport.
- Local adapters for Analysis, Epic, and Feature generation.
- Startup configuration and provider selection.
- Shared provider-output normalization.
- Startup documentation and adapter tests.
- Optional reasoning control for thinking models.
- Timestamped API/UI process logs and mapped 5xx exception logging.

## Out of Scope

- User Stories or any other Slice 05 behavior.
- Agent loops or tool calling.
- Model download, lifecycle, or GPU management.
- Authenticated or remote OpenAI-compatible gateways.
- Live-model calls in the normal test suite.

## Domain

No changes. Existing invariants and generation errors are reused.

## Application Use Cases

No changes. `AnalyzeRequirement`, `GenerateEpic`, and `GenerateFeatures` use
their existing provider-independent ports.

## Ports

No changes. The three existing generation ports remain separate per ADR 0005.

## Adapters

- `LocalStructuredOutputClient` for unauthenticated OpenAI-compatible HTTP.
- `LocalRequirementAnalyzer`.
- `LocalEpicGenerator`.
- `LocalFeatureGenerator`.
- Shared candidate mappers used by both OpenAI and local adapters.

## API

No contract changes. The existing endpoints execute the configured adapters.

## UI

No UI changes. Provider selection is deployment configuration; the existing
review UI continues to consume only the stable HTTP API.

## Business Rules

- Local output is schema-validated and content-sanitized before Domain use.
- Empty or unusable output is a generation failure, not an empty success.
- Local provider failures map through existing generation errors to HTTP 502.
- Thinking control is sent only when explicitly configured; Ollama's
  schema-valid `reasoning` fallback is accepted only with effort `none`.
- Epic and Feature provenance records the configured local model and existing
  prompt version.

## Tests

- Configuration validation and environment resolution.
- Composition-root selection of all three local adapters.
- JSON-schema request construction and typed response parsing.
- Blank fields, partial pairs, empty result sets, malformed responses, and
  connection failures.
- Existing OpenAI adapter regression tests after mapper extraction.
- Qwen/Ollama reasoning-field compatibility and server-error logging.

## Acceptance Criteria

- [x] `LLM_PROVIDER=local` requires an explicit model identifier.
- [x] No API credential is required or fabricated for local mode.
- [x] Analysis, Epic, and Feature generation use the local endpoint.
- [x] No provider type leaks into Application or Domain.
- [x] Existing API and browser contracts are unchanged.
- [x] All five quality gates pass locally.

## Validation Evidence

- `pytest` — PASS, 256 tests
- `ruff check .` — PASS, all checks passed
- `ruff format --check .` — PASS, 142 files already formatted
- `mypy src tests` — PASS, no issues in 117 source files
- `lint-imports` — PASS, 2 contracts kept and 0 broken
- live Ollama analysis — PASS, `qwen3-vl:8b` completed the production
  analysis prompt/schema path in 19.2 seconds
- PowerShell parser check for `start.ps1` — PASS; execution-based `-CheckOnly`
  was not run because the machine policy blocks script execution

## Deferred

- An opt-in smoke test against a developer-supplied live local model server.
- Authenticated OpenAI-compatible gateways; local mode is deliberately
  unauthenticated.
