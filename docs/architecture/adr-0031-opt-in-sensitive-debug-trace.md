# ADR 0031 — Opt-in sensitive single-file debug trace

## Status

Accepted.

## Context

ADR-0007 deliberately excluded provider request and response bodies from operational logs because
Requirements may contain confidential business information. Structured multimodal analysis later
added exact cross-field citation validation. A schema-valid provider response can now fail because
one generated item lacks a citation, while the ordinary exception log retains neither the parsed
provider result nor the normalized citation sets needed to identify that item.

The existing timestamped process stdout/stderr files remain appropriate for normal operations but
cannot explain this class of provider defect after the fact. A developer explicitly requested one
detailed local file for diagnosis.

## Decision

Infrastructure provides a composition-root-built debug trace with null and JSON Lines
implementations. It is disabled by default and enabled only with `DEBUG_TRACE_ENABLED=true` or the
local launcher's `-DebugTrace` switch. `DEBUG_TRACE_PATH` defaults to `logs/debug.log`, so all
backend lifecycle, local structured-output, mapping, citation-comparison, and mapped-error events
for a debug session append to one file.

The trace may contain requirement/document text, system and user prompts, final completion JSON,
and normalized candidate content. It must always redact credentials, cookies, database URLs,
binary values, image data URLs, and hidden reasoning. A schema-valid JSON value carried in
Ollama's `message.reasoning` compatibility field is recorded only as the parsed final model, never
as an unvalidated reasoning trace. Normal mode creates no trace file and performs no trace I/O.

The trace is an infrastructure diagnostic, not audit history or product data. It is not persisted
through application repositories, exposed by an API, or shown in the UI. Developers must delete
it after diagnosis and inspect it before sharing.

This supersedes ADR-0007 only where that ADR rejected provider request/response logging under all
circumstances. Normal operational logging remains unchanged.

## Consequences

Future provider failures can be reconstructed precisely, including the raw final response, parsed
schema, normalized candidate, and missing citation keys. The opt-in file is intentionally
sensitive, can grow without rotation, and must be handled like the source BRD. Redaction makes it
unsuitable for debugging image-payload corruption or hidden model reasoning, which are explicitly
outside this diagnostic boundary.

## Alternatives Considered

**Always log provider bodies.** Rejected because it silently persists confidential content during
normal use.

**Log only counts and categories.** Rejected because exact subject matching is the failure mode;
counts cannot reveal punctuation, wording, or classification differences.

**Persist failed completions in the database.** Rejected because debug material is not business
state, would require retention/access policy, and would enlarge the trusted data boundary.
