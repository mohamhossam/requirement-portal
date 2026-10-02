# ADR 0023 — Versioned neutral backlog export

## Status

Accepted

## Context

Slice 11 must make an approved backlog portable without coupling the application
to Azure DevOps or exporting mutable current state. The system already preserves
immutable `BreakdownRevision` snapshots and content-bound final approvals. JSON
is needed for lossless machine interchange, while reviewers also require an
Excel workbook. The two formats must represent the same application-owned
contract and must not become competing business models.

## Decision

The application owns a versioned `NeutralBacklogExport` contract, currently
`1.0`, and an `ExportBreakdown` use case. The contract contains a final-approval
manifest and the approved Epic → Feature → Story tree, including structured
acceptance criteria, generation provenance, and available architecture evidence.
It deliberately excludes analysis, documents, flags, decisions, comments, and
complete approval histories.

`BacklogExportPort` renders that contract. `JsonBacklogExporter` and
`XlsxBacklogExporter` are infrastructure adapters selected only in the
composition root. JSON is deterministic UTF-8. XLSX uses fixed relational sheets
and explicit string cells; it rejects content that Excel cannot carry losslessly
rather than truncating it.

The selected immutable revision, not current aggregate state, controls export
content and approval eligibility. A revision is eligible only when its embedded
review is `APPROVED`, contains a matching formal breakdown approval, and carries
a complete Epic/Feature/Story tree. Later mutations do not invalidate a formerly
approved historical revision. Current Requirement access controls authorization:
only the current Owner or an assigned reviewer may download.

Exports are generated synchronously and are never stored. The public route names
the Requirement and exact breakdown revision and accepts `json` or `xlsx`.
Breaking neutral-contract changes increment the major schema version; compatible
additions increment the minor version.

## Consequences

Downstream tools receive one provider-neutral, hierarchy-preserving package, and
future ADO publication can consume the same approved-revision boundary without
making ADO concepts part of the export schema. Historical approvals remain
useful even when current work continues. The workbook adds `openpyxl` as a
runtime dependency and `types-openpyxl` for strict checking.

Export downloads are not an audit event and do not create persistence writes.
CSV, stored export files, background jobs, full audit archives, and ADO-specific
fields remain outside this decision.

## Alternatives Considered

- Serialize current repositories directly: rejected because a multi-read export
  could mix versions and silently detach content from its final approval.
- Let each format define its own payload: rejected because JSON and Excel would
  drift and later integrations would depend on adapter-specific shapes.
- Export every review and source record: rejected because Slice 11 is a portable
  backlog contract, not a compliance archive.
- Permit any authenticated portfolio reader: rejected because downloading is a
  controlled handoff reserved for the Requirement team.
