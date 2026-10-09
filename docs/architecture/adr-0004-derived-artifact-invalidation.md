# ADR 0004 — Derived-artifact invalidation

## Status

Accepted. Supersedes the optional-collaborator arrangement introduced in Slice 02.

Mechanism superseded by ADR-0103 (2026-10-07). `InvalidateDerivedArtifacts` is replaced by
domain-event handlers, which run in the same order inside the same unit of work. The
delete-versus-stale rule recorded here is unchanged.

## Context

`UpdateRequirement` invalidated the analysis through an optional constructor
dependency:

```python
analysis_repository: RequirementAnalysisRepositoryPort | None = None
```

That shape had two problems. It created two configurations, only one of which
was exercised — the production wiring passed a repository, while
`test_requirement_use_cases.py` constructed the use case without one, so the
path where a stale analysis outlives its requirement was the *tested* path. And
it did not scale: Slice 03 adds a second derived artifact, which under the same
pattern means a second optional parameter, and Slices 04–05 add two more.

The two artifacts also need different treatment, so a single "delete everything
downstream" rule would be wrong.

## Decision

A dedicated collaborator, `InvalidateDerivedArtifacts`, owns the rule.
`UpdateRequirement` takes it as a **required** dependency.

The rule distinguishes artifacts by whether a human can have invested in them:

- an **analysis** is disposable AI output that nobody approves, so it is
  **deleted** and regenerated on demand;
- an **Epic** may carry a human edit or approval, so it is **marked stale** and
  never destroyed.

New derived artifacts extend this one class rather than adding a parameter to
`UpdateRequirement`.

## Consequences

The untested second configuration is gone — there is exactly one behaviour.
The delete-versus-flag asymmetry is stated in one place with its rationale,
instead of being implicit in whichever repository call a use case happens to
make. Slices 04 and 05 extend one method.

The costs: `UpdateRequirement` now depends on a class that reaches two
repositories, which is a wider blast radius than the single repository it used
to touch, and every test constructing it must supply the collaborator (hence
`make_invalidation` in `tests/conftest.py`).

The two writes are not transactional. With in-memory adapters nothing can
interleave, but once Slice 10 introduces a database, a crash between deleting
the analysis and saving the stale Epic leaves inconsistent state. Slice 10's
spec must address this; it is recorded in that slice's risks, not silently
carried.

## Alternatives Considered

**Domain events with a dispatcher.** The textbook answer and the right one
eventually. It needs an event bus, subscriber registration, and a story for
ordering and failure — real machinery for two subscribers, and `AGENTS.md` §16
requires evidence before abstraction. Revisit when a third consumer that is not
simple invalidation appears.

**Keep it in `UpdateRequirement`, just make the parameters required.** Fixes
the untested-path problem but not the growth problem: the use case accumulates
a repository per derived artifact and quietly becomes the place where
cross-aggregate policy lives.

**Invalidate lazily on read.** Would avoid the write entirely, but every reader
would need to know the rule, and staleness would depend on who looked last.
