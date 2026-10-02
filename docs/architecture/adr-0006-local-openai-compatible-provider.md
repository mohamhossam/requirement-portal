# ADR 0006 — Local OpenAI-compatible LLM provider

## Status

Accepted.

## Context

The delivered workflow could run with deterministic fake adapters or the
hosted OpenAI provider, but not with a model served on the user's machine.
Analysis, Epic generation, and Feature decomposition already have separate
application ports and provider-specific adapters, so local inference belongs
behind those existing boundaries.

Most local servers expose an OpenAI-compatible chat-completions endpoint. The
OpenAI Python SDK, however, expects an API credential even when a local server
does not authenticate. Supplying a made-up key would violate the project's
configuration rule against placeholder credentials.

## Decision

Add `LLM_PROVIDER=local`, selected only in the composition root. Local mode:

- requires `LOCAL_LLM_MODEL`;
- defaults `LOCAL_LLM_BASE_URL` to `http://127.0.0.1:1234/v1`;
- uses an explicit `LOCAL_LLM_TIMEOUT_SECONDS`, defaulting to 120 seconds;
- sends unauthenticated HTTP requests to `/chat/completions` using the standard
  `response_format.type=json_schema` request shape;
- validates response content with the same Pydantic schemas as OpenAI;
- implements the existing analyzer, Epic-generator, and Feature-generator
  ports with separate adapters, preserving ADR 0005.

Provider-output normalization is extracted into shared infrastructure mappers.
OpenAI and local adapters therefore apply exactly the same blank-content and
empty-result rules before returning application candidates.

No agent loop or tool calling is introduced. This remains a focused,
application-orchestrated generation workflow.

## Consequences

The complete implemented review flow can run against local models without an
external account or placeholder secret. Routes, use cases, domain objects, and
the browser are unchanged, and generated Epic/Feature provenance records the
configured local model identifier.

The local server and selected model must support JSON-schema structured output.
Not every small or base model does. Local inference can also be slower, hence a
separate timeout. Normal tests use mocked HTTP responses; a live-server smoke
test remains opt-in because CI must not download or run a model.

## Alternatives Considered

**Point the existing OpenAI adapters at a local base URL.** Rejected because
the SDK requires an API-key value even for an unauthenticated server, which
would encourage a fake credential and blur hosted versus local configuration.

**Add an Ollama-specific SDK.** Rejected because it would support one runtime
while LM Studio, Ollama, llama.cpp servers, and others already converge on an
OpenAI-compatible HTTP contract.

**Replace all adapters with one generic provider class.** Rejected because the
three application ports have different inputs and outputs. Shared transport
and mapping are extracted; domain-oriented port separation remains intact.
