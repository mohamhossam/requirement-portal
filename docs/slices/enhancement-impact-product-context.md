# Enhancement — Product and journey context on impacts

Requested 2026-10-01 by the product owner. This is slice 3e, the last of the
structured-architecture-document plan, and is recorded in ADR-0097. Slices 1b–3d are merged
([#99](https://github.com/mohamhossam/smb-ai-requirement-agent/pull/99) the last of them). The
catalogue now holds Business Pro Plus and its New Activation journey, but impact mapping did not
use them.

**Scope.** The product owner confirmed the file list on 2026-10-01 and asked for the export to
carry the notes too. **This slice includes frontend feature work beyond the presentation-only rule
in `CLAUDE.md`:** two new groups in the impact panel.

## Objective

An impact tells a reviewer which systems the catalogue makes responsible for the product offering
an item names, and where each mapped system acts in that offering's journeys. Neither changes
what is mapped.

## User outcome

- **"Product offering named."** An item that names "Business Pro Plus", its code, or one of its
  components shows:
  - the offering, and the order type when named;
  - the words in common;
  - per component, the responsible systems with their roles and what they do.

  Naming a component, or an order type, narrows the list.
- **"Journey steps to check."** Each mapped system's journey activities are listed. Each says
  whether the system performs or supports it, and what the journey fulfils, with the activities
  just before and after and their systems.
- **Show-only.** Mapped systems, approvals and generated Features and Stories are unchanged.
- **Export.** JSON and Excel exports carry both notes (contract 1.5): a Product Context sheet and a
  Journey Steps sheet.

## In scope

- `ProductContext`, `OfferingDuty`, `JourneyStep` and `JourneyNeighbour` on impacts.
- Matching and focusing.
- Payloads, guidance stripping, the API and the export.
- The impact panel.

## Out of scope

- Mapping systems from offerings.
- Offering aliases.
- Re-mapping existing impacts automatically.

## Domain

`entities.py`:
- `OfferingDuty`, `ProductContext`, `JourneyNeighbour` and `JourneyStep`;
- `ArchitectureImpact.product_contexts` and `.journey_steps`, where a journey step must be of a
  mapped system.

## Application

- **New `use_cases/impact_product_context.py`:**
  - `product_contexts`: at most 2, an offering named outranking a component;
  - `journey_steps`: at most 12, focused on the named offering and order type.
- **`ResolveArchitectureKnowledge.match`** adds both from the pinned release.
- **`ArchitectureKnowledgeMatch`** carries them, and **`architecture_mapping._impact`** passes them
  on.
- **Export contract `1.5`:** `ExportProductContext`, `ExportOfferingDuty`, `ExportJourneyStep`
  and `ExportJourneyNeighbour`.

## Ports

`ArchitectureKnowledgeMatch.product_contexts` and `.journey_steps`.

## Adapters

- **`shared_payloads.py`:** both are written only when present, and read when absent.
- **`generation_guidance.py`:** both are stripped.
- **`xlsx_exporter.py`:** the Product Context and Journey Steps sheets. JSON follows the contract.

## API

- `ArchitectureImpactResponse.product_contexts` and `.journey_steps`.
- Regenerated OpenAPI types.

## UI

`ArchitectureImpactPanel.tsx` adds two groups, "Product offering named" and "Journey steps to
check", each with a compact form.

## Tests

- **`test_impact_product_context.py`:**
  - an offering named by name or code;
  - narrowing by component and order type;
  - ranking, and nothing for an order type alone;
  - steps with before and after through a decision and a loop;
  - focusing and the cap;
  - mapping end to end from a pinned release;
  - payload round trip;
  - fingerprints and guidance unchanged;
  - refusals;
  - the Excel and JSON export.
- **`test_backlog_export.py` and the Postgres export test:** the contract version and the sheet
  list.
- **`ArchitectureImpactPanel.test.tsx`:** both groups, full and compact.
