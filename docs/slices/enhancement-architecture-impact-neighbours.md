# Enhancement — Connected systems in architecture impact mapping

Scheduled 2026-09-30 by the product owner. This is the first of three slices from the review of
ontology, taxonomy and GraphRAG:
- **A. Connected systems** (this slice, ADR-0087).
- **B. Typed system relationships** (ADR-0088).
- **C. Capability domain taxonomy** (ADR-0089).

It is feature work outside the UI redesign's presentation-only rule: it adds fields to the impact
API and renders them.

## Objective

When mapping finds the systems a Feature or Story changes, also show the systems one catalogued
relationship away, so a reviewer can check whether the change reaches them.

## User outcome

- A mapped Feature shows "Connected systems to check" under its mapped systems. Each connected
  system shows:
  - its squads;
  - the catalogued relationship that connects it, for example "DCRM → CBCM / CRMGW: DCRM captures
    back-office orders against the central customer domain".
- A Story names its connected systems in one line.
- Connected systems are clearly not mapped. They do not raise cross-system risk or review flags,
  and existing approvals are not reset.
- Exports include them: the JSON `adjacent_systems` field, and a "Connected Systems" workbook
  sheet.

## In scope

- One-hop adjacency over the pinned release's relationships, in both directions, capped at 8 with
  an omitted count.
- Impact and match fields, persistence, API, export (`1.1`) and the impact panel.

## Out of scope

- Multi-hop traversal, GraphRAG and graph databases (ADR-0067, ADR-0087).
- Review flags or risks raised from connected systems.
- Relationship kinds (slice B) and capability domains (slice C).

## Domain

- `domain/architecture/neighbours.py`: `adjacent(selected_ids, relationships, limit=8) -> Adjacency`.
- `ArchitectureImpact.adjacent_systems`, `adjacent_dependencies` and `adjacent_omitted`, with these
  invariants:
  - connected ids are unique and not mapped;
  - each connecting dependency joins one mapped and one connected system;
  - every connected system is reached by a relationship;
  - `omitted` is not negative.

## Application

- `ResolveArchitectureKnowledge.match` computes adjacency from the pinned release on the seed and
  indexed paths, and adds organisation ownership to connected systems.
- The Feature and Story mappers copy the new fields through one `_impact` helper.
- Fingerprints (`approval_policy`, `breakdown_review_evidence`) are unchanged.

## Ports

- `ArchitectureKnowledgeMatch` gains the same three fields, defaulted.

## Adapters

- `shared_payloads`: new keys are written only when present and read as optional.
- Generation guidance strips the connected-system keys, so `feature-v5` and `story-v5` prompts are
  unchanged.
- Export: `EXPORT_SCHEMA_VERSION = "1.1"`; the XLSX exporter adds a "Connected Systems" sheet.

## API

- `ArchitectureImpactResponse.adjacent_systems`, `adjacent_dependencies` and `adjacent_omitted`.
  The OpenAPI snapshot and generated types are regenerated.

## UI

- `ArchitectureImpactPanel`: a "Connected systems to check" group.
  - On Features, rows are grouped under the mapped system they link to ("Linked to CWOM (6
    systems)"). Each row gives the system, its capability, and the direction in words ("Used by
    CWOM: …" / "Uses CWOM: …").
  - Squads appear only when the catalogue assigns any; otherwise one line says it assigns none.
  - On Stories, one line: "Not mapped: A; B".
  - An omitted count links to the architecture catalogue.
- Mapped system names are now semibold, so they outrank connected ones.
- Fixed the dependency list's React key, which was not unique when one pair had two descriptions.

## Business rules

- Only catalogued relationships connect systems. Nothing is inferred.
- Connected systems are advice for a reviewer, never mapped impact.

## Tests

- `tests/unit/test_architecture_neighbours.py`:
  - adjacency in both directions, selection exclusion, cap and determinism;
  - impact invariants;
  - the resolver on the seed release with ownership;
  - payload round trip and legacy shape;
  - guidance exclusion;
  - an unchanged approval fingerprint.
- `tests/unit/test_backlog_export.py`: JSON field, "Connected Systems" sheet and schema `1.1`.
- `ArchitectureImpactPanel.test.tsx`: the full list, the compact line, and absence when there are
  none.

**Evidence.**
- `pytest tests/unit`: 1,757 passed.
- `ruff check`, `ruff format --check`, `mypy src tests` and `lint-imports` (7 contracts) are clean.
- Frontend: `npm run api:check`, `lint`, `typecheck`, `test` (585 passed) and `build` are green.
- Browser, against the fake API: a requirement declaring DCRM mapped to DCRM, with CBCM / CRMGW
  under "Connected systems to check" on the Feature and in one line on its Stories. No console
  errors.
- Not run: the PostgreSQL integration suite. Only its export-version assertion changed.
- Impeccable critique (dual-agent, live seeded page with DCRM + CWOM and 7 connected systems):
  - Baseline scored 21/36 (heuristic 9 n/a), with two P1s and three P2s:
    - P1: connected names outweighed mapped ones.
    - P1: capabilities were hidden while "Squads not assigned" repeated.
    - P2: no grouping or direction.
    - P2: the compact line was ambiguous.
    - P2: an off-system 2px edge.
  - All five are fixed. Rechecked live in dark at 1440px and light at 900px, with no horizontal
    overflow. Snapshot: `.impeccable/critique/2026-09-30T15-27-21Z__architecture-architectureimpactpanel-tsx-ea055346.md`.
