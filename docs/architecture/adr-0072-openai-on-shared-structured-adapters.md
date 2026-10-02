# ADR 0072 — OpenAI runs on the shared structured-generation adapters

## Status

Accepted. Refines ADR-0005 (separate generator ports) and ADR-0011 (provider
selection); the ports are unchanged.

## Context

Local and OpenRouter providers already shared one set of provider-neutral
`Structured…Adapter` classes over a `StructuredOutputClient` protocol. OpenAI
did not: it had its own copy of the analyzer, Epic, Feature, Story, quality,
relationship-classifier and answer-suggester adapters, each calling the SDK's
beta `parse` directly with a hard-coded 60-second timeout.

The copies had drifted. The OpenAI analyzer lacked behaviour the shared
analyzer had gained: the focused desired-outcome review when a source states
none, discarding question reviews when no AI questions are active, repairing
missing uncertainty rationales, the content-candidate path, and one completeness
retry. `LLM_PROVIDER=openai` therefore produced older, less careful analysis
than the other providers. The dependency also allowed `openai>=1.0.0` while the
code relied on APIs added much later.

## Decision

- `infrastructure/llm/openai_structured_output.py` provides
  `OpenAIStructuredOutputClient`, an implementation of `StructuredOutputClient`
  over the SDK's stable `chat.completions.parse`, with images sent as data-URL
  parts. SDK failures map to `ModelTransportError` kinds (timeout, rate limit,
  authentication, configuration, unavailable, invalid output) in the cause
  chain, so public error codes match the other providers and no provider text
  reaches clients.
- `infrastructure/llm/openai_adapters.py` declares the named OpenAI adapters as
  thin subclasses of the shared adapters. The five `openai_*` adapter modules and
  the OpenAI-only reference, classifier and suggester classes are removed.
- `OPENAI_TIMEOUT_SECONDS` (default 60) replaces the hard-coded timeout.
- The dependency is bounded to the verified major version: `openai>=3.8,<4`.

## Consequences

- OpenAI users now get the same analysis behaviour as local and OpenRouter
  users, including the extra focused calls (outcome review, completeness
  retry). That is a deliberate behaviour change, and it can mean more than one
  provider call per analysis.
- Error messages for OpenAI failures now name the provider the same way the
  others do ("OpenAI analysis failed: …").
- A prompt or response-cleaning fix in a shared adapter now reaches every
  provider at once.

## Alternatives Considered

- **Keep the OpenAI copies and port the missing behaviour into them.** Rejected:
  the drift is the defect, and a second copy would drift again.
- **Keep the beta `parse` API.** Rejected: the stable API exists in the pinned
  SDK, and the beta namespace is the one more likely to disappear.
