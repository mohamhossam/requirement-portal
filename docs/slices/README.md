# Slice specifications

One file per slice, enhancement, remediation phase or fix, written before the
work and kept afterwards as its record. A spec here is **not** a status claim:

- **`ROADMAP.md` is the status ledger.** Its delivery table and "Recommended
  Delivery Order" say what is delivered, scheduled, specified-but-unscheduled,
  or still open. Read it before starting anything in this directory (§9 of
  `WORKSPACE.md`: unscheduled work must not begin).
- **Validation evidence lives inside each spec** ("Validation Evidence"), filled
  in when the slice lands. Specs written before that convention, and some
  redesign phase records, do not carry one; their evidence is the merged PR and
  CI run named in `ROADMAP.md`.
- **Some specs describe work now owned by `knowledge-portal`.** The shared
  library, catalogue and document-knowledge extraction moved there with the
  repository split (ADR-0104); their specs remain here as history. When a spec's
  paths no longer exist in `src/`, check the knowledge portal before concluding
  the work was dropped.
- **`redesign-phase-*.md` (0–7) are shipped**, as are redesign phases 8–10,
  which have commit records in `ROADMAP.md` rather than specs. ADR-0117 records
  the shell they produced.

The spec template is `WORKSPACE.md` §10.
