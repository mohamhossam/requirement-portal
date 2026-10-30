# ADR-0119 — A Business Requirements Document export, separate from the neutral backlog export

Status: Accepted
Date: 2026-10-30

## Context

The product consumes business requirements documents and produces an approved backlog. Its one
download, the neutral backlog export (ADR-0023, schema 1.x, JSON and XLSX), deliberately excludes
the analysis, and knowledge-portal reads the same bytes as a change request (ADR-0101 Amendment 2).
The confirmed analysis — facts, business rules, constraints, assumptions, dependencies, open
questions, ambiguities, the clarification answers, the product verdict — is on the Confirm screen and
in every `BreakdownRevision` snapshot, but nobody could take it away.

The owner asked for a Business Requirements Document "in the standard way": a conventional document
a stakeholder who never opens the portal can read, sign and file. Three decisions followed:

- Word and Markdown, not PDF.
- Available as soon as the Requirement Owner confirms the analysis, not only after final approval.
  When the same revision also carries a formally approved backlog, the document gains a functional
  requirements section; otherwise it says the backlog is not approved.
- Offered on the Confirm view and on the History screen beside the JSON/XLSX export.

Two constraints shaped where it lives. "BRD" and "document" already mean the *uploaded* source
file here (`document_references`, the `/documents` routes, `historic_brd`), so the artefact needs a
name of its own. And widening `ExportFormat` with `docx`/`md` would have put formats that are not
backlog exports into the handoff worker's filter, the frontend's format table and a route whose
precondition would then depend on the format — a business rule in a handler (AGENTS.md §4.4).

## Decision

1. **A contract of its own.** `governance/application/specification.py` defines
   `RequirementSpecification`, schema `1.0`, with `SpecificationFormat` {`docx`, `md`}. It is built
   only from a `BreakdownRevision` and the `RequirementRevision` the analysis was made from (matched
   by `source_requirement_version`, else the newest snapshot not later than the revision). The
   neutral backlog export and its 1.x schema are unchanged. The UI and filenames say "Business
   Requirements Document"; code and the API say *specification*.
2. **Gate.** `is_specification_available(revision)` is "the revision has an analysis the owner
   confirmed". The functional requirements section is filled only when
   `is_exportable_revision(revision)` holds — the same formal final approval and complete tree the
   export demands. An unapproved backlog never reaches the document, which instead states that the
   backlog has not received formal final approval.
3. **Deterministic, never generated.** Every value is copied from the snapshot; no model is called.
   Uncertainty stays explicit: assumptions, dependencies, open questions and ambiguities carry an
   `Open` or `Resolved` status with the answer, who gave it and when; the assumptions heading says
   they are not confirmed requirements. Statements are numbered (`BR-`, `RL-`, `CN-`, `AS-`, `DP-`,
   `OQ-`, `AM-`, `FR-nn`, `FR-nn.m`) identically in both formats, because both render one outline
   (`specification_outline.py`).
4. **Renderers under governance infrastructure only.** `DocxSpecificationExporter` (python-docx)
   and `MarkdownSpecificationExporter` implement `SpecificationExportPort`. `python-docx` becomes a
   runtime dependency, confined by `.importlinter` to infrastructure, and passes the supply-chain
   gates of ADR-0077. The Word archive is rewritten with sorted entries and fixed timestamps so the
   same revision always renders to the same bytes; core properties are set from the revision's time.
   Text that XML cannot carry raises `SpecificationExportFormatError` (422) through the guard the
   XLSX exporter now shares (`xml_text.py`), never a bare `ValueError`.
5. **Route and permission.** `GET /requirements/{id}/revisions/{n}/specification?format=docx|md`,
   a sibling of `/export`, synchronous, never stored, not an audit event (as ADR-0023). It requires
   `RequirementPermission.MEMBER`, the owner or a reviewer, which is exactly what
   `can_export_approved_revisions` already tells the browser; no new permission flag. An unconfirmed
   revision answers 409 `requirement_specification_not_available`. `BreakdownRevisionResponse`
   gains `specification_available`, `analysis_confirmed_by` and `analysis_confirmed_at`.
6. **Names only.** The document leaves the system, so it carries display names and never email
   addresses or actor ids, as the knowledge handoff already does.
7. **Where.** History shows a Business Requirements Document card under the approved export, for the
   approved version so both downloads describe the same backlog, or else the newest confirmed one.
   The Confirm view's status strip offers the same document once the analysis is confirmed. The
   shell header keeps its three fixed actions (ADR-0117).

## Consequences

- Stakeholders get a conventional document from a confirmed analysis without waiting for the
  backlog, and a complete one — with functional requirements — once the backlog is approved.
- `python-docx` and `lxml` ship in the API image; the image grows by lxml's compiled wheel.
- A python-docx upgrade may change internal XML. Tests assert content, headings and self-equality,
  never golden bytes.
- Clarification questions a person asked by hand are not part of the analysis snapshot and so are
  not in the document; the clarifications the analysis recorded are. Deferred with PDF output.
- knowledge-portal is untouched: schema 1.x, `ExportFormat`, the handoff worker and the approval
  outbox do not change.

## Alternatives Considered

- **Widen `ExportFormat` with `docx` and `md`.** Rejected: it couples two artefacts with different
  gates and errors to one route and one enum that the handoff worker and the frontend both key on,
  and ADR-0023 keeps the 1.x contract analysis-free.
- **Let a model write the prose.** Rejected: it would invent requirements and blur the line between
  source facts, assumptions and confirmed decisions that AGENTS.md §7 requires.
- **PDF.** Rejected for now: a heavier rendering dependency, harder to keep deterministic, and
  stakeholders edit a BRD. Word opens in every office suite; Markdown diffs in version control.
- **A print stylesheet on the Confirm screen.** Rejected: no deterministic artefact, nothing to
  download from History, and no functional requirements section.

## Amendment 1 — schema 1.1: version history, actors and scenarios, risks (2026-10-30)

Measured against the standard BRD (`docs/slices/enhancement-brd-completeness.md`), the document
gains three sections, all from data the revision already holds:

- **Version history**, under Document control: every requirement revision and breakdown revision up
  to the one exported, each labelled against its predecessor by two pure functions in
  `revision_history.py` (`describe_requirement_revision`, `describe_breakdown_revision`): "Need
  captured", "Need edited: title", "Team changed", "Analysis confirmed", "Epic generated",
  "Features generated (2)", "Submitted for review", "Final approval recorded" and so on. The
  builder therefore takes both histories; the use case loads them.
- **5. Actors and scenarios**: the approved Stories grouped by actor, with Feature and goal.
- **15. Risks**: the backlog review's risks, moved out of the functional requirements section.

Actors, scenarios and risks are review and backlog content that nobody has approved before the
formal final approval, so both sections appear under the same gate as functional requirements and
say so before it. Sections are numbered 1–18. `SPECIFICATION_SCHEMA_VERSION` is `1.1`;
`RequirementSpecification.versions` is the one contract addition.

**Not added: business journeys affected.** `ArchitectureImpact.journey_steps` is reviewer advice
from the optional architecture-mapping job (ADR-0097), never confirmed or approved data, so it stays
out of a document whose rule is to print only what a person confirmed or approved. The neutral XLSX
export still carries it for machine consumers.

## Amendment 2 — schema 1.2: the scope statement (2026-10-30)

A standard BRD states what is in scope, what is out of scope, and the current and proposed way of
working. The Requirement gains three optional intake fields, `current_state`, `proposed_state` and
`out_of_scope`, modelled on `customer_context` and `channels` (same limits, same codec, stored in the
JSON payload, no migration). They flow to the Source step, the source editor, the History diff, the
knowledge chunks and the analysis prompt (`analysis-v27-intake-scope-context`); generation prompts
pick them up with the next prompt change. Section 3 of the document renders In scope, Out of scope,
Current state and Proposed state. `SPECIFICATION_SCHEMA_VERSION` is `1.2`.

Two invariants keep existing work valid: the fields are written to payloads only when present, and
the generation context token drops them while empty (`_requirement_state`), so stored rows, the
characterisation goldens and tokens minted before the fields existed are unchanged.
