# ADR 0084 — Named catalogue versions, one draft, and team-owned remapping

## Status

Accepted.

## Context

The architecture journey review left five gaps:

- **Hash names.** Catalogue versions were known by a hash (`draft-9a62…`), and several drafts
  could pile up unnoticed. A browser run showed four at once.
- **Dependencies only as text.** A wrong or missing link was hard to spot.
- **Publishing said too little.** It warned that existing mappings "are flagged" but not how
  many, or who must act. Remapping a requirement resets its approvals, and knowledge maintainers
  are not members of every requirement.
- **Suggestions were hard to review.** They could not be grouped by system or rejected together,
  and a citation could not be read in its document.
- **Unclear image wording.** Upload copy implied that images become evidence. They only feed
  suggestions.

## Decision

**Names and one draft.**
- `ArchitectureKnowledge` carries `name` (1–80 characters, whitespace collapsed) and
  `created_by`. They are stored in the existing release payload, so no migration is needed. The
  packaged seed is "Initial catalogue".
- `create_draft(actor, name)` checks the name first, then refuses with 409 while a draft exists.
  The message names that draft and who started it.
- `PUT /architecture-knowledge/releases/{id}/name` renames a draft. A name is not content, so a
  built index stays valid.
- `DELETE /architecture-knowledge/releases/{id}` discards a draft. Postgres removes its indexes,
  chunks, suggestions and extraction runs in the same transaction. Both actions are audited.
- The page shows names everywhere, with ids kept as secondary text.

**Dependency diagram.**
- `DependencyDiagram` draws an inline SVG in the catalogue browser: the users of a system on the
  left, and what it depends on on the right, eight per side at most.
- Its `role="img"` label repeats the counts, and the text lists stay beside it. It is hidden on
  phones.

**Publish impact and remapping.**
- `ArchitectureMappingStatsPort.by_release()` counts mapped requirements, features and stories
  per release. Postgres groups the feature and story JSONB; in-memory persistence walks the
  repositories.
- `GET /architecture-knowledge/mapping-impact` (maintainers) returns totals, and totals mapped
  with a release that is not in use. It returns counts only, never titles.
- The publish confirmation and the in-use card show these counts.
- Remapping stays with each requirement's team. `ArchitectureRemapBanner` appears on a breakdown
  mapped with an older version, names the version in use, and remaps after a confirmation that
  says approvals reset.
- There is no bulk remap.

**Suggestions.**
- They can be grouped by kind or by system. A group with more than one waiting suggestion offers
  "Reject all N waiting" after confirmation, through
  `POST /releases/{id}/suggestions/rejection`. It skips suggestions that were already decided.
- "Show in document" calls `GET /releases/{id}/documents/{vid}/passage?location=`. This re-reads
  the stored document with the located extractor and returns the cited passage, with a
  "(part i of n)" suffix stripped, plus two passages either side.
- An image answers 422.
- The dialog marks the quote when it appears word for word.

**Copy.** Upload text and image rows state that images are for suggestions only and are not
quoted as evidence in mapping.

## Consequences

- One version is in progress at a time, with a recognisable name. A forgotten draft now blocks
  new work until someone publishes or discards it, which is deliberate.
- Maintainers see how much of the backlog a publication leaves on an older version, but not
  which requirements. Teams remap on their own schedule, and approvals are reset only by the
  people who own them.
- The passage view re-extracts the document on every request. That is acceptable for occasional
  reviews of drafts. The originally planned "open the PDF at this page" link was dropped:
  document content is served behind API authentication, which a plain link cannot carry.

## Alternatives Considered

- **Maintainer-triggered bulk remap:** rejected by the user. It would reset approvals on
  requirements the maintainer cannot see.
- **Several named drafts in parallel:** rejected by the user. One draft keeps review and
  publication unambiguous.
- **A dedicated table for names:** unnecessary, because the release payload already versions
  every field under the revision check.
