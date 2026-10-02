# ADR 0015 — Semantic Story Quality Boundary

## Status

Accepted

## Context

INVEST combines checks that code can prove with judgments that depend on
meaning. Treating all six criteria as prompt output would make deterministic
rules provider-dependent; treating all six as string heuristics would embed
unmaintainable business guesses in the domain. Quality results must also retain
the model, prompt version, and generation time used by a reviewer.

## Decision

`StoryQualityEvaluatorPort` owns only semantic evaluation and returns findings
for the requested criteria. The application evaluates `Testable`
deterministically from the Story's structured acceptance criteria and asks the
port to evaluate the other five INVEST criteria.

Fake, local OpenAI-compatible, and OpenAI adapters implement the same port and
are selected with the existing `LLM_PROVIDER` setting in
`interfaces/api/container.py`. Provider output is normalized and rejected at
the infrastructure boundary before domain objects are constructed.

`InvestAssessment` owns the complete six-criterion result, the two-or-more
failure split threshold, and generation provenance. SPIDR suggestions are
derived by the application from failed criteria and do not require another
provider call.

## Consequences

Deterministic behavior remains fast and testable without an LLM, while semantic
judgment remains replaceable. Every displayed finding has a clear source and
provenance. Reading quality currently invokes the configured semantic adapter;
a future durable assessment or async-job slice may cache it without changing
the domain contract.

## Alternatives Considered

- Evaluate every criterion with the LLM: rejected because structured Given /
  When / Then completeness is already deterministic.
- Implement semantic checks with keyword rules: rejected because those rules
  would be brittle, opaque, and contrary to the replaceable-reasoning boundary.
- Put SPIDR mapping in each provider prompt: rejected because identical failed
  criteria must produce stable recommendations across providers.

## Workflow update

ADR-0041 adds generation-time candidate checks and automatic evidence persistence. Existing
semantic/deterministic and architecture boundaries remain; current saved assessments are reused
on review refresh, and reading the review does not invoke a provider.
