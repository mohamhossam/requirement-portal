# ADR 0083 — Catalogue browser, shared sample requirements and the embedding cache

## Status

Accepted.

## Context

After ADR-0082 the architecture journey still had three gaps:

- **Readers could not browse.** Readers could not see the catalogue that maps their
  requirements, and maintainers saw only counts for the version in use.
- **Testing a version was one-off.** "Try a requirement" tested one typed query against the
  draft alone, so nobody could see what a new version changes, or repeat the check for the next
  version.
- **Rebuilds were slow.** Every index build embedded every passage again, even after a one-line
  edit.

## Decision

**Browser.**
- `CatalogueBrowser` shows a release read-only: capabilities with their matching phrases,
  constraints, "Depends on" and "Used by", and owners.
- Owners are derived on the client from the organisation catalogue by the same rule as
  `OrganisationCatalogue.ownership` (`features/organisation/ownership.ts`).
- Knowledge readers get it as their page. Maintainers get it next to the version in use.
- No new endpoint is needed: readers can already read the active release and the organisation
  catalogue.

**Sample requirements.**
- One shared list of at most 20 samples, each at most 2,000 characters
  (`domain/architecture/samples.py`).
- It is stored as one JSONB row (`architecture_sample_requirements`) and replaced as a whole
  under a revision check, which answers 409 when stale.
- It is maintainer-only: `GET` and `PUT /architecture-knowledge/sample-requirements`.

**Comparison.**
- `POST /architecture-knowledge/releases/{id}/compare-impact` maps one requirement twice. The
  version in use goes through `ArchitectureKnowledgePort.match`, which handles the built-in seed.
  The built draft goes through `PreviewArchitectureImpact`.
- The route is rate-limited like other provider calls.
- The page sends one sample per request, in sequence, and can stop between samples. It labels
  each row in words: same systems, changed (with + and − systems), now finds systems, now finds
  none, or could not compare.

**Embedding cache.**
- `architecture_embedding_cache` keeps vectors by embedding model and SHA-256 of the passage
  text.
- `PostgresEvidenceIndex.store` embeds only uncached texts and records them in the same
  transaction as the index. The in-memory index keeps the same cache.

## Consequences

- Readers see what maps their work, and ownership stays authoritative in one place.
- A version is checked against the same samples every time. The team curates the list; the
  application does not pick samples.
- A sample costs two model calls. Ten samples on a slow local model take minutes, but each row
  appears as it finishes and no single request holds for the whole run.
- Rebuilding after an edit only embeds changed passages. The cache is not pruned yet, and neither
  is the document library's: its size grows with distinct passage texts per model. Pruning
  belongs with operational retention (ADR-0079) once it covers more than notifications.

## Alternatives Considered

- **One request for all samples:** it risks gateway timeouts on local models and shows nothing
  until the end.
- **A background job per comparison:** durable, but heavier than the task needs. Results are
  read immediately by the person who ran them.
- **Using recent real requirements as samples:** chosen against by the user. Results would
  depend on what was entered lately, and requirement access differs per person.
- **Samples kept per browser:** a shared list is what makes the check repeatable across
  maintainers and versions.
