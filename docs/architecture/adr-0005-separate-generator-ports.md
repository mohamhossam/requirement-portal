# ADR 0005 — Separate generator ports per artifact

## Status

Accepted. Answers the shared-port suggestion in `ROADMAP.md` Slice 3.

## Context

`ROADMAP.md` proposed that Epic generation "extend a domain-oriented
decomposition port, e.g. `BacklogDecompositionPort`, rather than exposing
provider-specific operations".

Slice 03 deferred the decision because `AGENTS.md` §16 requires evidence of a
second use case before introducing an abstraction, and at that point only one
generator existed. Slice 04 supplies the second, so the question is now
answerable rather than speculative.

## Decision

Each generated artifact gets its own port. `EpicGeneratorPort` and
`FeatureGeneratorPort` stand alone, and Slice 05 will add a third unless it
finds a genuine reason not to.

The evidence is the two signatures side by side:

```
EpicGeneratorPort.generate(requirement, analysis)          -> EpicCandidate
FeatureGeneratorPort.generate(requirement, analysis, epic) -> list[FeatureCandidate]
```

Different inputs, different cardinality, different candidate shapes, and no
shared behaviour. Combining them would produce an interface whose two methods
have nothing in common beyond both calling an LLM, and every implementer would
have to satisfy both to provide either.

The roadmap's underlying concern — that ports must be domain-oriented rather
than provider-shaped — is met and remains binding. Neither port mentions
OpenAI, and both return neutral `TypedDict` candidates. What is rejected is the
grouping, not the principle.

## Consequences

Each port stays small enough to implement alone, so a future provider can serve
Feature generation without also serving Epic generation, and a fake for one
does not have to stub the other. The composition root gains one selector
function per artifact, which is the visible cost: `build_container` grows a
line per generator rather than resolving one object.

Adding a fourth and fifth generator in later slices will make that repetition
worth revisiting — but the thing to extract then is the *provider selection*,
which really is identical across generators, not the port interface, which is
not.

This diverges from a literal reading of `ROADMAP.md`. `AGENTS.md` §2 gives
`AGENTS.md` precedence on engineering shape while the roadmap governs
sequencing, so the divergence is in-bounds; recording it here is what keeps it
from looking like an oversight.

## Alternatives Considered

**One `BacklogDecompositionPort` with a method per artifact.** The literal
roadmap reading. Rejected: an interface segregation violation with no benefit,
since nothing consumes the two methods together.

**A generic `Generator[TInput, TCandidate]` protocol.** Would unify the shape
at the cost of erasing what each generator actually needs; the type parameters
would carry all the meaning and the port would carry none.

**Defer again to Slice 05.** The evidence needed is already here, and leaving
it open a second time would mean building Story generation without knowing
which shape it is meant to fit.
