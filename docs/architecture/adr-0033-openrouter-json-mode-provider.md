# ADR 0033 — OpenRouter JSON-Mode Provider

## Status

Accepted.

## Context

The complete AI workflow needs a fourth provider option using OpenRouter and the
development/demo model `google/gemma-4-31b-it:free`. OpenRouter exposes OpenAI-compatible HTTP
endpoints, but this free model does not enforce JSON Schema. Requirement knowledge also relies on
the existing 768-dimensional embedding contract. Provider privacy and the absence of accidental
paid chat fallback are product constraints.

## Decision

OpenRouter is an infrastructure-only provider selected in the composition root. A dedicated
`httpx` transport authenticates with a Bearer token and calls `/chat/completions`. It requests
JSON mode, includes the compact Pydantic JSON Schema in the system instruction, and validates the
decoded object with Pydantic before any domain mapping. Missing choices, refusal, blank or
malformed content, truncation, schema failure, and HTTP/provider errors are explicit generation
failures. The transport supports base64 multimodal image parts and never records credentials or
image bytes in the opt-in trace.

The reusable high-level structured generation, reconciliation, citation recovery, bounded
completeness, and Story repair behavior lives in provider-neutral infrastructure cores. Thin
local and OpenRouter wrappers supply their transports and provider-specific error labels. No
provider type crosses the Application or Domain boundary.

Chat requests set `provider.require_parameters=true` and
`provider.data_collection=deny`. Embedding requests apply the same data-collection policy. If no
eligible endpoint honors those requirements, the operation fails; it does not weaken privacy.
There is no automatic model switch or paid chat fallback.

Requirement-knowledge embeddings use OpenRouter `/embeddings` with
`openai/text-embedding-3-small` and `dimensions=768`. The adapter preserves input ordering and
rejects count, dimension, type, malformed-payload, and non-finite-value failures before returning
vectors to the application.

## Consequences

The full workflow can use OpenRouter without changing HTTP, OpenAPI, browser, Application, or
Domain contracts. Provenance records the configured OpenRouter model slug. JSON mode is less
reliable than provider-enforced schema output, so failures remain visible as the existing HTTP
502 generation errors and retries remain bounded. The default free chat endpoint is appropriate
only for development and demos. Knowledge embeddings may be separately billable through
OpenRouter.

## Alternatives Considered

- OpenAI SDK with a custom base URL: rejected because the raw HTTP boundary makes OpenRouter's
  response, privacy-routing, and secret-safe trace rules explicit and independently testable.
- Pretend the free model supports strict JSON Schema: rejected because schema support is an
  endpoint capability, not implied by an OpenAI-compatible API shape.
- Fall back to a paid model or allow data collection when routing fails: rejected because it can
  create unapproved cost or weaken privacy without user consent.
- Change PostgreSQL vector dimensions: rejected because the embedding endpoint supports the
  established 768-dimensional application contract.
