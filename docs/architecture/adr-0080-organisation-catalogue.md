# ADR 0080 — A static organisation catalogue, separate from versioned architecture releases

## Status

Accepted. Amends ADR-0016 and ADR-0067 on where ownership comes from.

## Context

Slice 14 stored squads inside each architecture release (`ArchitectureKnowledge.squads`) and let
a system name at most one owning squad (`SystemDefinition.squad_id`). That did not match how the
business is organised:

- A value stream has a lead, manages specific products and owns several squads.
- A squad has a name, a scrum master, and one resource (a person) from each system it works on.
  Those people come from different teams.
- One system can sit in several squads, with a different resource in each.

Ownership also changes on a different rhythm from architecture. Moving a person between squads
should not require building an evidence index and publishing a new catalogue release.

## Decision

- **Architecture releases no longer carry ownership.** `ArchitectureKnowledge.squads`,
  `SystemDefinition.squad_id`, the `Ownership` value and the YAML `squads`/`squad` keys are
  removed.
- **A new organisation catalogue** lives in `domain/organisation/catalogue.py`:
  - `Person`, `ValueStream` (with an optional lead), `Product` (linked to architecture system ids)
    and `Squad`.
  - A squad has an optional scrum master and `SquadSystemResource(system_id, person_id | None)`
    rows. A system appears at most once per squad, and in any number of squads.
  - The aggregate enforces referential integrity: known value streams, known and active people,
    unique names within a value stream, and unique emails.
- **It is static, not released.** Records are edited in place.
  - Each record carries its own `revision` for optimistic concurrency.
  - Every change is written to an audit trail (`organisation_audit`).
  - `OrganisationRepositoryPort.change` applies a change to the latest state atomically. The
    Postgres adapter holds a row lock on one JSONB aggregate (`organisation_catalogue`), and the
    in-memory adapter holds a lock.
- **System links are checked when written, not enforced afterwards.** A product or squad may
  only add systems that are in the *active* architecture release. Links that later lapse are shown
  as "not in the catalogue in use", so an architecture publish never fails because of
  organisation data.
- **Mapping takes ownership at mapping time.** `ResolveArchitectureKnowledge` looks up each
  catalogued system's squads, value streams and products in the organisation catalogue.
  - `SystemReference.squad` becomes `squads`, `value_streams` and `products`, each a tuple of
    `OrganisationReference`. People are not recorded on impacts.
  - Impacts are snapshots, so later organisation edits do not make breakdown reviews stale.
- **Access follows the knowledge roles.** Maintainers edit, and readers view. People's emails are
  only returned to maintainers.

## Consequences

- Ownership changes take effect immediately without a release. The cost is that ownership has
  no version history beyond its audit trail.
- The JSONB aggregate is simple and consistent for the expected size (hundreds of records). A
  catalogue of many thousands of people would need per-entity tables.
- This is a breaking change to the release payload, YAML and impact payload shapes. The project is
  in development, so there is no data migration: developer databases are reset. Stored releases
  still load, because extra JSON keys are ignored.
- The rule "ownership comes only from catalogue records" still holds: the organisation catalogue
  is the curated record, and AI never writes to it.

## Alternatives Considered

- **Keep squads inside releases, and make the system–squad link many-to-many.** Rejected:
  every staffing change would need an index rebuild and a publish, and releases would have to
  version people.
- **A separate versioned catalogue per squad.** Rejected: the user wants ownership to be
  static. It would also have needed composite snapshots of every squad's active version to pin a
  mapping.
- **Normalised tables per entity.** This is more work for no benefit at the current scale. The
  port hides the choice, so it can change later.
