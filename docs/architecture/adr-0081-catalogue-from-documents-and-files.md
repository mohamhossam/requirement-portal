# ADR 0081 — Building the architecture catalogue from documents and catalogue files

## Status

Accepted. Pulls Knowledge Center sub-slice F forward and widens it to PDF and images. ADR 0086 adds XLSX, CSV and TSV to the accepted files, and ADR 0090 adds Markdown.

## Context

Maintainers had two ways to fill a draft release: type every system into forms, or paste YAML into
a text box. The source of truth is usually an architecture document (Word, PDF) or a diagram, or
a spreadsheet kept by an architect. Slice 14 forbids AI evidence from creating catalogue systems
on its own.

## Decision

**A draft can be filled three ways.** All three end in the same review, build and publish steps.

1. **Documents → AI suggestions.**
   - **Accepted files.** Architecture uploads accept DOCX, PDF, TXT, PNG and JPEG. The allowlist is
     passed to `validate_document_upload`; other uploads keep PDF, DOCX and TXT.
   - **Extraction job.** A maintainer starts an `EXTRACTION` architecture job per document. The
     job fingerprint is the document version plus `model:prompt_version`, so asking again reuses
     the job.
   - **Reading.** `ProposeCatalogueChanges` reads located text through `LocatedDocumentExtractor`
     in size-bounded batches. Images are read as one segment through the vision model. The index
     build skips images.
   - **Proposals.** `CatalogueExtractorPort` proposes systems, capabilities, constraints and
     relationships, each citing segment numbers and a quote. The structured adapter follows the
     reference-proposal pattern: untrusted-data framing, no invention, no people or squads.
   - **Citation checks.** The adapter drops items whose cited numbers are out of range, or whose
     quote is not in the cited text. Image readings are exempt from the quote match. If every
     item is dropped, the run fails with a provider error (502).
   - **Storage.** Suggestions are stored as `CatalogueCandidate`s with model, prompt version,
     citations and status `proposed`. Suggestions already in the draft are left out, with a
     warning.
2. **Catalogue file.**
   - `CatalogueFilePort` reads and writes Excel, YAML and JSON, which all map to the same content.
   - The Excel workbook has Systems, Capabilities, Constraints and Relationships sheets, plus an
     Instructions sheet in the downloadable template. Each parse error names its sheet and row,
     or its entry.
   - Imports are **preview-first**. `preview_file_import` returns the diff, and
     `apply_file_import` replaces the draft's systems and relationships under the draft revision
     check. Documents stay.
   - Workbooks are checked against the office archive limits before openpyxl opens them.
   - The previous JSON-string YAML endpoints are removed.
3. **Manual edits**, as before.

**Maintainers decide every suggestion.**
- `DecideCatalogueCandidate` accepts (optionally with edits), rejects, or accepts all.
- Accepting merges the change through the pure domain functions `classify` and `apply_candidate`.
  Merging never drops existing aliases, triggers or constraints.
- A capability, constraint or relationship whose system is not in the draft is refused with a
  409 (`catalogue_suggestion_dependency`). "Accept all" applies suggestions in dependency order,
  and reports how many still wait.
- The decision is stored first, then the draft is saved under its revision. A failed draft save
  reopens the decision.

**Review before publishing.** `diff_releases` compares a draft with the active release. It
reports systems, capabilities, relationships and documents as added, changed (with the fields
that changed) or removed. The UI requires this changes view before publishing. Publishing is
still one maintainer with a rationale; there is no second approver.

**LLM wiring.** A `catalogue` profile task, falling back to the default, selects the model.
Image support follows the profile's `images` flag, or `LOCAL_LLM_VISION_ENABLED` for the local
provider. The extraction route uses the provider rate limit.

## Consequences

- Architects can bootstrap a catalogue from the documents they already have. Every AI-originated
  item stays traceable to a passage and a model.
- Prompt injection in uploaded documents cannot change the catalogue by itself: nothing applies
  without a maintainer. Readers of the review list still see the raw quotes.
- Large PDFs cost several model calls. Reading is capped at 600 passages, and a warning is
  recorded when the cap is reached.
- Scanned PDFs and diagrams embedded in Word are not sent to the vision model yet. That is left
  for a later increment, which needs its own evidence-indexing decision.

## Alternatives Considered

- **Let the AI write straight into the draft.** Rejected by the user, and it contradicts the
  Slice 14 rule and AGENTS.md §8.
- **OCR for images.** Rejected: it reads text but not the boxes and arrows that carry
  dependencies. A vision model is used instead.
- **Import files without a preview.** Rejected: replacing a draft is destructive, and the diff
  is cheap.
