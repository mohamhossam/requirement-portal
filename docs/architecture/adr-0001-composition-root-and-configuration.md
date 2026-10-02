# ADR 0001 — Composition root and configuration

## Status

Accepted

## Context

Slice 02 wired the application in `interfaces/api/dependencies.py` at module
import time: every repository, adapter, and use case was constructed as a
module-level singleton, including
`OpenAIRequirementAnalyzer(api_key=os.getenv("OPENAI_API_KEY", "dummy"))`.

Four problems followed from that one shape:

1. The whole test suite shared a single mutable object graph, so isolation
   depended on `dependency_overrides` reaching private module members
   (`_repository`, `_analysis_repository`).
2. A missing `OPENAI_API_KEY` silently became the string `"dummy"`. The
   application booted successfully and failed on the first analysis request
   with a provider error, far from the actual cause.
3. `LLM_PROVIDER` was documented in `.env.example` but read nowhere.
   `FakeRequirementAnalyzer` shipped in the production package yet could not be
   selected, so the application could not run without an OpenAI account —
   contradicting `WORKSPACE.md §5`.
4. Nothing loaded `.env`, making the documented `cp .env.example .env` workflow
   inert.

import-linter reported no violation throughout. The dependency direction was
correct; the lifecycle was not.

## Decision

Configuration and wiring are separated, and neither happens at import time.

- `infrastructure/config/settings.py` is the only module that reads the
  environment. `Settings.from_env()` loads `.env`, resolves `LLM_PROVIDER`,
  `OPENAI_API_KEY`, and `OPENAI_MODEL`, and raises `ConfigurationError` for an
  unknown provider or a missing required credential. There is no placeholder
  fallback.
- `interfaces/api/container.py` is the single composition root.
  `build_container(settings)` is the only place a concrete adapter is named,
  and `build_analyzer` selects the adapter from `LLMProvider`.
- `interfaces/api/main.py` builds the container in a FastAPI `lifespan`, so
  misconfiguration fails the boot. Dependency providers read it from
  `app.state`.
- Tests build their own container per test via `tests/conftest.py`.

## Consequences

Misconfiguration now fails at startup with a message naming the variable and
the fix. `LLM_PROVIDER=fake` runs the full application with no provider
account, which keeps CI and local development free of credentials. Tests no
longer share state or reach into private members.

The costs: an extra indirection between a route and its use case, and one more
module to touch when adding an adapter. Wiring is no longer visible from the
module that consumes it — `build_container` must be read to know what is
actually running.

`app.state` is untyped, so `get_container` casts. This is accepted for now; a
typed application subclass is not worth the ceremony at this size.

## Alternatives Considered

**Keep module-level singletons, add a provider switch.** Cheapest change, but
leaves the shared-state and import-time-failure problems, which are the ones
that actually bite as slices accumulate.

**A lazily-built module-level container.** Avoids import-time construction, but
configuration errors would still surface on the first request rather than at
startup — the loud-failure property was the main goal.

**A dependency-injection framework.** Real wiring is a few dozen lines; a
framework would add a dependency and a second mental model for no present gain.
