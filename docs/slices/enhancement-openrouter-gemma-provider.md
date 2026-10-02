# Enhancement — OpenRouter Gemma Provider

> Status: **implemented locally; backend and frontend component gates passed; full browser smoke
> timed out on pre-existing long-flow failures**.

## Objective

Add OpenRouter as a complete development/demo LLM provider, defaulting to
`google/gemma-4-31b-it:free`, without changing product contracts or silently weakening cost and
privacy constraints.

## Roadmap Scope Check

This is a user-directed bounded enhancement to the delivered provider, structured-analysis, and
Requirement-knowledge slices. It does not start or omit any part of Slice 12.

| Field | Delivery |
|---|---|
| Domain | No change; existing invariants validate mapped provider content. |
| Application | No contract change; existing focused ports and generation errors are reused. |
| Ports | No change; OpenRouter implements the current analysis, generation, evaluation, classification, suggestion, and embedding ports. |
| Adapters | Authenticated JSON-mode chat, multimodal input, shared structured-generation cores, privacy routing, and a 768-dimensional embedding adapter. |
| API | No HTTP/OpenAPI change; the centralized existing provider-error map continues to return 502. |
| UI | No contract or component change; existing provenance surfaces show the configured model slug. |
| Tests | Settings, composition, transport, focused adapter contracts, embeddings, regression, all backend/frontend gates, and fake-provider smoke. |

## Behavior

- `LLM_PROVIDER=openrouter` wires all focused AI ports and Requirement-knowledge embeddings in the
  composition root; fake, local, and OpenAI selections are unchanged.
- Startup validates the credential, HTTPS base URL, nonblank model names, positive timeout/output
  limit, and data-collection policy.
- Chat calls use Bearer authentication, `/chat/completions`, JSON mode, a compact schema
  instruction, multimodal base64 parts, a fixed output limit, and privacy-first routing.
- Strict transport, Pydantic, adapter, and domain validation reject truncated, refused, malformed,
  blank, incomplete, or otherwise unusable responses.
- OpenRouter wrappers reuse the bounded local structured-generation and recovery behavior without
  unbounded retries or model fallback.
- Transient transport and server failures receive at most three HTTP attempts. A 429 is retried
  only when OpenRouter supplies a short `Retry-After`; absent or long delays fail immediately so
  blind retries do not multiply free-tier quota consumption.
- Embeddings call `/embeddings`, request 768 dimensions, preserve ordering, and retain the atomic
  knowledge-screen workflow.
- Sensitive traces use OpenRouter-specific event names and omit credentials and image bytes.

## Acceptance Criteria

- [x] OpenRouter is selectable by configuration and `start.ps1` / `start.cmd`.
- [x] All focused chat adapters and the embedding adapter are selected together.
- [x] JSON-mode responses receive strict schema and domain validation.
- [x] Multimodal inputs, output limits, refusals, truncation, HTTP errors, and malformed payloads
  are handled explicitly.
- [x] Provider routing requires supported parameters and denies data collection.
- [x] There is no automatic paid chat fallback.
- [x] Knowledge vectors remain ordered, finite, and exactly 768-dimensional.
- [x] Existing API/OpenAPI/frontend contracts remain unchanged.
- [x] Configuration and launch documentation warn about free limits and embedding charges.
- [ ] A credentialed opt-in live workflow has been manually verified.

## Validation Evidence

- Focused OpenRouter, local-provider regression, settings, composition, embedding, HTTP-error, and
  OpenAPI regression tests — PASS.
- Focused OpenRouter adapter suite — PASS; 31 passed.
- `pytest` — PASS; 693 passed, 18 skipped.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS; 389 files formatted.
- `mypy src tests` — PASS; 310 source files.
- `lint-imports` — PASS; 2 contracts kept, 0 broken.
- Frontend `api:check`, lint, typecheck, test, and build — PASS; 24 files / 118 tests.
- Isolated fake-provider knowledge-screen Playwright path — PASS; 1 desktop Chromium test.
- Full fake-provider Playwright smoke — FAIL/TIMEOUT. Both the 16-case full command and bounded
  eight-case desktop command exceeded five minutes while current long-flow cases reached their
  existing 60-second per-test failures. The isolated provider-adjacent knowledge path passed; no
  OpenRouter contract or UI changed in this enhancement.
- Live OpenRouter verification — NOT RUN; `OPENROUTER_API_KEY` was not present, and an opt-in
  knowledge-screen call can incur embedding charges.

## Architecture Impact

ADR-0033 records the authenticated OpenAI-compatible HTTP boundary, JSON-mode validation,
privacy policy, embedding selection, shared infrastructure generation cores, and lack of paid
fallback. Application, Domain, HTTP, OpenAPI, frontend, and database schemas are unchanged.

## Deferred / Open

- Live calls remain opt-in and outside CI.
- Free-model quota and availability are external constraints and surface as provider failures.
- CI remains pending until the branch is pushed.
