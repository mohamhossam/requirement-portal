# ADR 0042 — Business need attachments as prompt sources

## Status
Accepted — implements the user-approved attachment-input plan.

## Context
Business need previously required typed text. Supporting documents were separate,
excluded initially, and draft attachments could not be selected or removed. Authors
need to submit Word, Markdown, images and Figma exports directly as source input.

## Decision
Keep the title mandatory and permit an empty typed description only through
application paths that validate an included, ready source attachment. Direct create
without attachment sources retains strict description validation. Persist the empty
string without inventing business text. Requirement source eligibility is computed
in the Application layer from the source record and current document selections.
Removing or excluding the last usable source blocks subsequent analysis.

Reuse immutable document versions, authenticated asset previews, existing storage
ports, citation validation and bounded multimodal evidence packets. Add Markdown
as UTF-8 source text and sanitize standalone PNG/JPEG into bounded image evidence.
Rasterize PDF page content with pypdfium2 inside the existing bounded subprocess;
keep page text and visual blocks in source order. Blank pages are not evidence.
Legacy extraction versions and snapshots remain readable.

Uploads accept an optional include_in_analysis form flag, false by default. The
Business need uploader explicitly enables it. Failed or blocked intended uploads
remain excluded and carry a persisted requires_attention flag. Explicit exclusion,
removal or successful replacement clears the blocker. A replacement changes the
document aggregate version once per atomic write and retains prior immutable bytes.

Draft inclusion and removal check ownership, document scope and optimistic versions
inside the same locked transaction. Promotion transfers source selections atomically.
Serializing frontend draft writes prevents competing create/autosave/upload paths.

Typed business need and file evidence remain separately labelled prompt inputs.
Embedded file instructions cannot override application rules. Conflicting business
statements are surfaced for review. Models without image support fail explicitly.

## Consequences
File-only capture works without copied extraction text or placeholder descriptions.
Current attachment selections determine readiness, while historic analysis citations
still identify the exact file version and checksum. PDF rendering adds a dependency
and multimodal processing cost, bounded by existing page, pixel, process and packet
limits. Document metadata adds an optional JSON field; no SQL migration is needed.

## Alternatives considered
- Copy extraction into description: rejected because it loses input provenance and
  misrepresents machine-extracted text as the user's typed instructions.
- Accept native Figma files or live links: excluded by the user's chosen export workflow.
- Silently ignore images or failed intended uploads: rejected because analysis would
  use incomplete source material without the author's decision.
