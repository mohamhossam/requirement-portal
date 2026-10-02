# Enhancement — Prompt rules for catalogue tables and one id per system

Requested 2026-10-01 by the product owner. This is slice 1c of the structured-architecture-document
plan, stacked on 1b. Markdown rows now reach the model whole. Reading
`SMB_Product_Architecture_Explorer_v4.md` still left four problems:
- names with emoji;
- lost `SYS-*` IDs;
- integration rows suggested only as inferences, decided one by one;
- the same system under two ids, and the same link suggested from both ends.

The decisions are recorded as amendments to ADR-0085 and ADR-0088. There is no UI change.

## Objective

A landscape table is read as the records it holds. Each system gets one plain name and one id.
Its integrations come through as stated dependencies, each suggested once.

## User outcome

- **Plain names.** Systems are suggested as "BCRM", not "📈 BCRM". The document's ID ("SYS-BCRM")
  is kept as another name.
- **Function as a capability.** A system's Function becomes a capability, with matching phrases
  taken from the Function text.
- **Integrations are stated.** A system's Integrations become stated dependencies, so "Accept
  all" can take them.
  - "A / B" entries name two systems.
  - Group words ("Digital", "Channels") are left out.
- **One link, one suggestion.** A link listed under both systems is suggested once, and the
  reading notes say how many were merged.
- **One system, one id.** "CRM GW" in one row and "CBCM / CRMGW" in another are the same system,
  whichever call reads them. A link that resolves to a system on both ends is left out.
- **Other tables.**
  - Responsibility and activity rows give capabilities of their systems.
  - Activity-to-activity rows and flow diagrams give no dependencies.
  - Rows marked GAP are left out.
- **Documents can be read again.** A document already read can be read again, because the
  reading profile changed (`catalogue-extraction-v6`).

## In scope

- Prompt `catalogue-extraction-v6` with table rules.
- Removing pictographs from the system names the model returns.
- A run-together fallback in `find_system`.
- Canonical ids across a reading's calls.
- Merging a link listed from both ends.

## Out of scope

- Reading tables without the model (slice 1d).
- Landscape domains and system descriptions (slices 2a–2b).
- Products and journeys (phase 3).
- Owners, which stay in the squad catalogue.

## Domain

- `find_system`: when neither an exact label nor the words match, the words run together are
  compared. It answers only when exactly one system fits.

## Application

`ProposeCatalogueChanges`:
- `_canonical` re-resolves every proposal's system and target against a provisional draft that
  includes the suggested systems.
- `_one_way` merges an unspecified A→B with B→A and notes the count.

## Ports

No change.

## Adapters

- `catalogue_extraction.py`: `plain_name` and `_plain` clean system names, aliases and targets
  before resolving them.
- `catalogue_extraction_prompt.py`: `catalogue-extraction-v6`. It adds the table rules, and
  integration-table rows are no longer implied evidence.

## API

No change.

## UI

No change.

## Tests

`test_catalogue_table_reading.py` covers:
- removing name decoration while keeping letters, punctuation and Arabic;
- extractor ids and names without emoji, with the quote verbatim;
- run-together name matching and its ambiguity;
- the prompt's table rules;
- canonical ids across calls and self-links after canonicalisation;
- merging a link listed from both ends, while a typed link keeps its direction.
