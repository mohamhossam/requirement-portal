# ADR 0007 — Local reasoning control and operational error logs

## Status

Accepted. The decision prohibiting all provider-body logging is superseded by
ADR-0031 for explicit local debug sessions only.

## Context

The first live run of `qwen3-vl:8b` through Ollama spent the full configured
120-second timeout generating internal reasoning. Ollama then returned HTTP 500
when the client cancelled the unfinished completion. A diagnostic request with
`reasoning_effort=none` completed in under one second, but Ollama 0.33 placed
the schema-valid JSON in `message.reasoning` while leaving `message.content`
empty.

The failure was difficult to diagnose because the PowerShell startup launched
Uvicorn and Vite without visible consoles or redirected output. Mapped 502
errors were returned to the browser but not logged by the central error
handler.

## Decision

Local LLM configuration gains optional `LOCAL_LLM_REASONING_EFFORT`, accepting
`none`, `low`, `medium`, or `high`. The transport omits the field when unset.
When explicitly set to `none`, an empty `content` may fall back to `reasoning`,
but that value must independently validate against the requested Pydantic
schema. Reasoning traces are never returned or persisted.

The API's central error handler logs mapped 5xx failures with method, path,
error type, message, and exception chain. It does not deliberately log request
bodies or provider payloads.

The PowerShell startup writes timestamped API and UI stdout/stderr files under
the ignored `logs/` directory and prints their paths. CMD startup retains its
visible API and UI windows.

## Consequences

Thinking models can perform deterministic extraction without spending the
timeout on hidden reasoning, while other compatible servers see no new request
field unless configured. Ollama's current empty-content behavior is handled
narrowly rather than weakening response validation.

Provider failures become diagnosable after the fact. Log files may grow across
runs, so developers should remove old files when no longer needed; no automatic
deletion policy is introduced.

## Alternatives Considered

**Only increase the timeout.** Rejected because the observed model was still
reasoning when cancelled and a longer wait would not address the wrong mode.

**Always disable reasoning.** Rejected because `local` supports more than
Ollama and some OpenAI-compatible servers may reject or interpret the field
differently.

**Accept `message.reasoning` for every response.** Rejected because reasoning
is not normally final output. The fallback is limited to explicitly disabled
reasoning and still schema-validated.

**Log provider request and response bodies.** Rejected because requirements may
contain sensitive business information and the error type/chain is sufficient
for operational diagnosis.
