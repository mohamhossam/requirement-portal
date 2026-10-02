# Enhancement — Typed system relationships

Scheduled 2026-09-30 by the product owner. This is slice B of three from the ontology, taxonomy
and GraphRAG review (ADR-0088). It follows slice A (connected systems, ADR-0087) and comes before
slice C (capability domains, ADR-0089). It is feature work outside the UI redesign's
presentation-only rule.

## Objective

Record how one system depends on another, when a maintainer, a catalogue file or a cited document
says so, and show it wherever dependencies appear.

## User outcome

- A maintainer picks how each dependency works: calls its API, sends it events, sends it data,
  orchestrates it, or not stated. They can do this when adding a dependency or later on the same
  row.
- AI suggestions from documents carry a kind only when the passages show one. The maintainer can
  change it before accepting.
- Excel, YAML and JSON catalogues carry the kind. Older files still import.
- The review of changes lists a changed kind as "how it depends".
- Mapped and connected dependencies on Features and Stories show the kind: "(API call)",
  "(Data transfer)" and so on.

## In scope

`RelationshipKind` on relationships, dependencies and candidates, extraction prompt v3, files,
diff, evidence words, impacts, export `1.2`, and the catalogue and impact UI.

## Out of scope

- Inferring kinds from descriptions.
- Filtering or reporting by kind.
- Capability domains (slice C).

## Domain

- `RelationshipKind` and `relationship_kind()` in `domain/architecture/knowledge.py`.
- `SystemRelationship.kind` and `ArchitectureDependency.kind`, defaulted and coerced.
- `ArchitectureDependency.digest_fields()` adds the kind only when specified.
- `diff_releases` reports a `changed` relationship with field `kind`.
- `CandidateContent.relationship_kind`, where only a dependency may carry one. `classify` and
  `apply_candidate` set a stated kind and never clear one.

## Application

- Proposals are merged by relationship identity, and `_settled` chooses the kind.
- Evidence chunks add kind words only when specified.
- The resolver and connected systems carry the kind.

## Ports

No new ports.

## Adapters

- Catalogue files: an optional `kind` in YAML and JSON, and an optional Excel column with a
  label-tolerant reader.
- Seed kinds follow the descriptions.
- The legacy YAML adapter reads `kind`.
- Extraction `catalogue-extraction-v3` with `relationship_kind`. The fake extractor reads "calls"
  and "sends".
- Impact payloads write `kind` only when specified.
- Export `1.2`, with `kind` columns.

## API

- `SystemRelationshipSchema.kind`, `CandidateContentSchema.relationship_kind` and
  `ArchitectureDependencyResponse.kind`.
- OpenAPI and the generated types are regenerated.

## UI

- `SystemsEditor`: a per-row "How" picker and an add-form "How".
- `SuggestionEditor`: "How it depends".
- `SuggestionList`, `CatalogueBrowser`, `DependencyDiagram` (tooltips; also fixes a React key
  collision) and `ArchitectureImpactPanel` show direction-neutral kind words.
- `changeStory` counts changed dependencies.

## Business rules

- A kind is recorded only when someone or something with evidence says how. Otherwise it is
  unspecified.
- A kind is an attribute of a relationship, never part of its identity.

## Tests

- `tests/unit/test_relationship_kinds.py`:
  - coercion, refusal and legacy releases;
  - seed kinds;
  - diff;
  - suggestions set but never clear a kind;
  - merge settling;
  - every file format, old workbooks and labels;
  - mapping and connected systems;
  - payloads and fingerprints;
  - the fake extractor.
- Updated exact-shape assertions for the release API, chunk text, export `1.2` and the
  `ChangeOutput` helpers.
- Frontend:
  - `ArchitectureCataloguePage.test.tsx` covers the row picker, the add form and the changed-kind
    review;
  - `ArchitectureImpactPanel.test.tsx` covers kind words on mapped and connected rows.

**Evidence.**
- `pytest tests/unit`: 1,770 passed.
- `ruff check`, `ruff format --check`, `mypy src tests` and `lint-imports` (7 contracts) are clean.
- Frontend: `api:check`, `lint`, `typecheck`, `test` (588 passed) and `build` are green.
- Browser, against the fake API:
  - Connected rows show "(Data transfer)", "(Events)" and "(Orchestration)"; DCRM → CBCM / CRMGW
    shows none.
  - The dossier shows "Felix (Events)".
  - In a draft, every dependency row has its "How" picker. Changing DCRM → CBCM / CRMGW to "Calls
    its API" saved `calls_api`, and the review read "1 dependency changed" with "(how it
    depends)".
  - No errors on the catalogue page load.
- `impeccable detect` on the six changed UI files: clean. The full dual-agent critique was not
  run for this slice. Its UI reuses the existing picker, badge-free text and label patterns.
