# ADR 0002 — Central error translation at the interface boundary

## Status

Accepted

## Context

Each route handler translated domain errors to HTTP status codes itself, with
its own `try`/`except` chain raising `HTTPException`.

This produced a real defect. `RequirementAnalysisSchema` types every field as
`list[str]` with no minimum length, so an empty string is a schema-valid model
response. The analysis value objects reject blank content with
`InvalidAnalysisContentError`, but `routes/analysis.py` caught only
`RequirementNotFoundError` and `RequirementAnalysisGenerationError`. Ordinary
provider output therefore reached the client as an HTTP 500.

The per-route pattern makes this failure mode structural rather than
accidental: whether an error is handled depends on which route it passes
through, and adding an error type to one route's handling does nothing for the
others. `DuplicateRequirementError` was mapped nowhere at all.

## Decision

Domain and application errors are mapped to status codes in exactly one place,
`interfaces/api/error_handlers.py`, which holds an ordered
`(error type, status code)` map and registers a handler per entry.

- Route handlers contain no `try`/`except` for domain errors and raise no
  `HTTPException` for them.
- Every new domain or application error is added to the map in the commit that
  introduces it, with a test asserting its status code.
- Status codes are chosen by fault: 4xx for the caller, 502 for a misbehaving
  external provider, 500 only for a genuine bug in this codebase.
- Provider output is separately sanitised in the adapter (see
  `infrastructure/llm/response_sanitizer.py`) so the domain is not handed
  content it will reject in the first place. The error map is the backstop, not
  the primary defence.

`InvalidAnalysisContentError` maps to 502: the requirement is valid and the
request is well-formed, so a rejected analysis entry means the provider
returned unusable content.

## Consequences

An error type can no longer be handled in one route and escape as a 500 from
another. Routes shrank to a call and a mapping. Adding an endpoint no longer
means re-deriving the error translation. The change also closed the unmapped
`DuplicateRequirementError` case with a 409.

The costs: the status code for an error is no longer visible in the route that
can raise it, so the map has to be consulted. An error type absent from the map
still yields a 500 — the registration is the safeguard, and only the test rule
above enforces it.

Ordering matters: the map is scanned most-specific first, so a new error type
that subclasses an existing one must be inserted above its parent.

## Alternatives Considered

**Keep per-route handling, add the missing cases.** Fixes the instance, not the
pattern; the next endpoint reintroduces it.

**Map errors in the use-case layer.** Would put HTTP concerns in the
application layer, breaking the dependency direction.

**A single catch-all handler returning 500 with a message.** Loses the
distinction between caller error, provider error, and internal bug, which is
exactly what a client needs in order to react correctly.
