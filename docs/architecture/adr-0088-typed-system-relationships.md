# ADR 0088 — Typed system relationships

## Status

Accepted. Extends ADR-0067, ADR-0081 and ADR-0085. Builds on ADR-0087.

## Context

A catalogue relationship recorded only its two systems and a free-text description. The words
said what a dependency was for, but not how it worked. For a reviewer weighing impact, the
difference matters:
- A change to an API breaks its callers at once.
- An event consumer only breaks when the event shape changes.
- A batch transfer can fail silently until the next run.

ADR-0087 now shows systems one relationship away from a mapped impact. Without a kind, those
rows could only say "linked".

## Decision

- **A small fixed set of kinds.** `RelationshipKind` is one of:
  - `calls_api`
  - `publishes_events_to`
  - `transfers_data_to` (files, batches, synchronised records)
  - `orchestrates`
  - `unspecified`

  `SystemRelationship.kind` and `ArchitectureDependency.kind` default to `unspecified`. Unknown
  values are refused, never guessed.
- **An attribute, not identity.** A relationship is still identified by source, target and
  description.
  - Changing its kind is an edit. The diff reports it as `changed` with field `kind` and keeps
    the key and label formats the workbench parses.
  - A suggestion with a stated kind that differs from the record classifies as
    `updates_existing` and sets the kind.
  - A suggestion without a kind never clears one.
- **Extraction says how only when the passages show it.**
  - The prompt moves to `catalogue-extraction-v3` and asks for `relationship_kind`. It tells the
    model to answer `unspecified` rather than guess, and never to infer a kind from product
    knowledge (the ADR-0085 rule).
  - Proposals of the same dependency are merged by relationship identity, ignoring kind. A kind
    from a stated proposal wins. Proposals that disagree leave it `unspecified`.
- **Files.**
  - YAML and JSON carry an optional `kind` per dependency, written only when specified.
  - The Excel Relationships sheet gains an optional `kind` column. Old three-column workbooks
    still import, and "Calls API" is read as `calls_api`.
- **The seed names kinds only where its descriptions show them.** For example, B2B Web calls the
  BFF's API, and RTF orchestrates CWOM. "DCRM captures back-office orders against the central
  customer domain" does not say how, so it stays unspecified. The seed's kinds are a reading of
  its own descriptions, and maintainers should confirm them.
- **Evidence text.**
  - A specified kind adds a word to the system's structured chunk:
    `Depends on: B2B BFF (API call) — …`.
  - An unspecified kind adds nothing, so chunks and content hashes built before kinds existed
    are unchanged.
  - The index profile is unchanged. A new build picks up the words.
- **Impacts.**
  - Mapped and connected dependencies carry their kind.
  - Payloads write it only when specified.
  - Approval and review-evidence fingerprints include it only when specified, so existing
    approvals keep their hashes.
- **Export.**
  - The neutral contract moves to `1.2`, a compatible addition: `ExportArchitectureDependency`
    gains `kind`.
  - The workbook's Dependencies and Connected Systems sheets gain a `kind` column.
- **UI.**
  - The dependency editor has a "How" picker on each row and in the add form, defaulting to
    "Not stated".
  - The suggestion editor has "How it depends".
  - Suggestions, the system dossier, the diagram tooltips and the impact panel show the kind as a
    direction-neutral word ("API call", "Events", "Data transfer", "Orchestration").

## Consequences

- Reviewers and connected-system rows say how systems depend, where the catalogue knows.
- Most existing relationships stay `unspecified` until a maintainer or a document says
  otherwise. That is the honest default.
- Prompt v3 costs a few more tokens per extraction. Old suggestions keep `catalogue-extraction-v2`
  as their recorded prompt version.
- Remapping a Feature whose dependencies gain a kind changes its fingerprint. This is the same
  rule as any other change to mapped content; remapping already resets approvals (ADR-0084).

## Alternatives Considered

- **Kind in the relationship's identity.** Rejected. The same fact could then exist twice under
  two kinds, and a kind edit would read as a removal plus an addition.
- **Free-text kinds or an open vocabulary.** Rejected. It could not be filtered, compared or
  worded consistently, and it would drift toward a formal ontology this product does not need.
- **Inferring kinds from descriptions with a model.** Rejected. It would present a model's
  reading as catalogue fact. Kinds come from maintainers, files, or cited document passages.

## Amendment — A link listed from both systems (2026-10-01)

An integrations column lists BCRM under CBCM and CBCM under BCRM. Read as stated dependencies
(ADR-0085 amendment), that is two suggestions for one link. When both are `unspecified`, the
second is merged into the first: its citations join the first, and a stated copy outweighs an
inference. The reading notes say how many were merged. Connected systems are found in both
directions (ADR-0087), so impact mapping loses nothing. A dependency whose kind is known keeps
its direction and is never merged with its reverse.
