# Reviewed document knowledge: operating and release checklist

Implementation status is in `docs/slices/enhancement-document-knowledge.md`. Do not interpret
this runbook or an enabled endpoint as production qualification.

## Provisioning

- Apply packaged migration `022_document_library.sql` with the existing migration command while
  API/workers are stopped. It creates new tables and does not publish existing attachments.
- Originals remain in `document_blobs`; back up that table together with library metadata,
  submissions, approvals and extraction revisions. Derived chunk/cache tables are rebuildable.
- Run ClamAV locally, maintain signature updates, restrict its unauthenticated socket to trusted
  loopback/private infrastructure, and configure `StreamMaxLength` and scan limits above the
  application's upload limits. Set `ATTACHMENT_SCAN_MODE=clamav`, `ATTACHMENT_SCANNER_HOST` and
  `ATTACHMENT_SCANNER_PORT`. An outage fails ingestion closed; it never supplies a clean verdict.
- `ATTACHMENT_SCAN_MODE=offline` is ONLY a deterministic development adapter. Startup rejects it
  with durable persistence or OIDC identity. It is not malware protection.
- Install the `document-ocr` optional extra, Tesseract, and its `eng` and `ara` trained data. Package
  Docling model assets beforehand and set `ATTACHMENT_OCR_ARTIFACTS_PATH`. Do not rely on first-upload
  downloads. Pin the qualified runtime/model bundle in the deployment image and record its hashes.
- Document extraction uses independent single-worker capacity, a 4 GiB process cap and a 600-second
  deadline. Ingestion leases last 660 seconds. Validate those defaults with representative files.

## Governance and recovery

Uploads are private until an owner saves a selection/correction revision and approves it.
Approval is not automatic publication: search activation waits for every selected chunk.
Replacing a file preserves old publication; withdrawal removes all current publication eligibility.
Original downloads are owner-only because excluded material can remain in the file. Shared viewers
receive only approved selected passages. Never grant access by disclosing a version URL alone.

Cancelled or expired attempts cannot commit. Expired ingestion is reclaimable, with a three-attempt
ceiling. Failed/cancelled work has an explicit owner Retry; quarantined uploads do not. Indexing has
a separate three-attempt ceiling and an explicit owner retry. Monitor terminal state and provider
availability before retrying. A full embedding-generation migration and recovery qualification
remain necessary before switching live models; no mixed-identity vector comparison is allowed.

## Table-aware corpus builds

The active corpus consists of one publication generation per published document. Owners govern
those members independently. The new `table-fields-512-768-v2` policy is opt-in; deployment never
rewrites a legacy `structure-512-768-v1` publication. Rendered table fields are packing hints,
including literal delimiters in cells; this does not certify a reconstructed table schema.

1. In the library, save the complete extraction review. Preview the table-aware version and inspect
   exact excerpts, offsets and context. Corrections or exclusions require another saved revision.
2. **Approve and build search version** pins the source fingerprint, chunk policy and configured
   embedding/counter/normalizer identity. The background worker stages bounded batches. Old search
   results remain eligible. Ready state records chunk count, sorted-ID/content-hash manifest and time.
3. Inspect the ready build. **Activate built version** explicitly replaces the current publication.
   The activation checks stored chunks against the manifest and rechecks owner/version/current
   source. Requirements citing the old publication now need reference reconciliation; their
   historical decisions and evidence are retained. Do not treat a rebuild as citation-neutral.
4. **Discard pending build** preserves the active publication. It fences an in-flight worker and
   keeps staged chunks and approval history for audit. It does not delete original bytes.
5. Provider failure backs off, preserving completed batches. After three attempts use **Retry
   indexing**. Restore the pinned model configuration before retrying, or discard and start a new
   preview/build. A changed source or incomplete manifest requires discard/rebuild before activation.

API equivalents are GET `/library/documents/{id}/builds/preview`, POST to `/builds` with the returned
document version/fingerprint/index identity, then POST `/builds/{build_id}/activation` with current
document version and completed manifest. POST `/builds/{build_id}/discard` cancels only that pending
build. A repeat or stale mutation returns 409; fetch state before retrying. Do not auto-activate from
an operations script. Metadata uses compatible defaults in existing JSON; no new SQL migration.

For recovery, back up publication payloads with the originals/revisions. Derived chunks/cache can
be rebuilt, but a new approved build has new identity and needs explicit activation. Never mark a
build ready by editing database JSON. No nonempty restore rehearsal is claimed here.

The two child policies can coexist under the same configured embedding identity. An incompatible
active model identity still fails search explicitly. Model migration therefore needs a planned
search maintenance window and affected owners' rebuild/activation decisions. Restore the previous
configuration before any activation to abandon a rollout safely; after partial activation, coordinate
the remaining owners or use a separately approved recovery plan. Cross-owner atomic cutover,
zero-downtime multi-model serving and production rollback qualification are not delivered here.

## Required release evidence

### Presentation tables and historical tokenizer status (ADR-0055)

The no-live-probe status below describes ADR-0055. ADR-0062, documented later in this runbook,
supersedes it with actual selected-model fixture measurements; a matching local tokenizer is
still not substituted for the explicit UTF-8 runtime budget counter.

New PPTX extractions use `structured-pptx-tables-v1`. Review rows independently in the existing
library editor. R1C1 means physical row 1, cell 1; bracketed empty/span/continuation text is an
extraction annotation, not original wording. No header meaning or merged-cell content is inferred.
Verify source XML order against the visual slide, especially RTL and merged layouts. Exclude
private rows and notes separately before previewing/building. Neither is copied into shared labels.
Existing extraction revisions/publications are preserved; a new upload/review is required to use
the improved extraction. Synthetic fixtures and browser coverage are not production format QA.

The checked-in profile selects `gemini-embedding-001`. Its documented input limit does not supply
a matching local tokenizer, and the SDK's [counting support issue](https://github.com/googleapis/python-genai/issues/1541)
remains open at this checkpoint. No live capability probe was performed. Keep model-tokenizer
qualification open: do not substitute a chat-model counter or report UTF-8 units as measured
embedding tokens. No provider/model configuration has been changed for this checkpoint.

### Word table review and existing publications

New DOCX uploads use `structured-docx-sections-v2` (retaining the ADR-0056 table behavior) through both library and Requirement attachment
paths. Review table rows and nested tables independently. R/C positions follow declared spans and
row omissions; bracketed markers represent extraction structure. Compare merged/RTL layout with
the original file. Missing/different grids produce warnings; malformed metadata fails ingestion.
Limits are eight nesting levels, 1,000 grid columns per row and the configured visited-cell budget
across all tables. The budget includes spanned/omitted positions without copying their contents.

Prior DOCX extractions may already contain copied header or merged-anchor text in other rows.
They remain immutable. Owners should inspect affected publications and withdraw any containing
unintended wording, then upload a new version, review and publish it. Rebuilding the old extracted
text alone does not apply the new extractor. No existing publication was withdrawn automatically.

### CSV/TSV first-record review and existing publications

New CSV/TSV uploads use `structured-delimited-rows-v1`. Every nonblank record, including the first,
is independently reviewable. R/C labels count logical records/fields, not physical file lines:
quoted line breaks stay within a record. Headers are not inferred or copied; compare the original
file to interpret relationships. Empty fields use `[empty cell]`; formulas remain inert strings.
Blank records retain numbering but add no content. The first record with fields establishes width;
ragged/malformed rows fail ingestion visibly. Limits include 100,000 records, 1,000 fields per row,
the configured cumulative cell and rendered character budgets, and the CSV parser field limit.

Prior CSV/TSV extraction may have copied first-record wording into every data row. Inspect affected
publications and withdraw unintended wording, then upload/review/publish a new version. Rebuilding
old extracted text does not run the new extractor. Historical publications are never rewritten.
Both formats use existing Library review, table-aware preview/build and explicit activation controls.

### XLSX merged-range review

New library and Requirement attachment uploads use `structured-xlsx-sections-v2` (retaining ADR-0058 merges). A cell marked
`[merged A2:A3 continuation; anchor A2]` refers to a position, not copied anchor text. Empty merged
anchors and continuation-only rows are explicit. Compare the original to interpret the layout;
exclude private anchors, headings and hidden-sheet passages independently in library review.
Formula text/cached-value annotations remain evidence, not executed calculations. Existing hidden
worksheet selection for Requirement analysis is unchanged.

Malformed, single-cell, reversed, overlapping/duplicate or out-of-bounds merged ranges fail ingestion;
a non-anchor continuation containing its own value also fails and requires correcting/unmerging the
source workbook. Limits remain 100,000 rows and 1,000 columns per sheet plus configured cumulative
visited cells. Merge areas are bounded before expansion; traversal includes empty merge tails and
blank positions. These are safety limits, not representative extraction/performance qualification.

Existing XLSX revisions/publications are not rewritten. Upload a new immutable version, review and
publish it to adopt merge annotations; rebuilding old extracted text alone cannot add them.

### Release gates

1. At least 200 human-labelled queries including 50 cross-language cases. Keep the original
   language, relevance grades, expected sources, contradictions and support annotations.
2. Compare child and parent-context configurations with the actual embedding tokenizer. The current
   768-unit child and 1,536-unit context ceilings use a deliberately conservative UTF-8 byte budget
   and must not be reported as model-token benchmark winners.
3. Verify zero draft/unapproved/withdrawn leakage, exact citations and human semantic support.
4. On a recorded environment, measure 1 million chunks and 25 users, database retrieval p95 <1s
   and end-to-end p95 <3s; report query embedding separately and concurrent ingestion starvation.
5. Rehearse nonempty migration, backup restore, worker crash/cancellation and provider outage.
   Verify original checksums and approval manifests after recovery, before enabling search.
6. Run all backend/frontend gates and PostgreSQL/pgvector CI. A skipped database test is not a pass.

No human-labelled dataset, measured scale result, or restore rehearsal is supplied by the current
implementation request. Do not fabricate those records.

The 2026-09-23 qualification checkpoint adds a **synthetic nonempty** restore rehearsal and a
small-corpus HTTP concurrency measurement. It supersedes the absence of any restore example,
not the production gates above. Commands, scope and actual evidence are in
`docs/slices/production-readiness-qualification.md` and `docs/operations/release-qualification.md`.

## Evaluation command

`python scripts/evaluate_document_knowledge.py judgments.json results.json` prints metrics and
exits nonzero unless all implemented quality gates pass. Input JSON arrays use these shapes:

```json
[{"id":"query-001","human_reviewer":"actual reviewer identity","cross_language":true,
  "judgments":[{"source_id":"document-or-requirement-id","relevance":3}]}]
```

```json
[{"query_id":"query-001","sources":[{"source_id":"document-or-requirement-id",
  "eligible":true,"citation_valid":true}]}]
```

These are schema examples, not human-labelled benchmark evidence. Relevance grades are 0–3.
Record every returned distinct source's judgment; missing judgments fail dataset completeness.
Eligibility/citation flags must be produced by validating actual retrieved results against the
publication store, not guessed or defaulted true. A no-hit query still needs an explicit empty
result. The calculator deduplicates sources for rank metrics but checks every returned citation
for leakage/invalidity. It reports both standard fractional Recall@20 and hit rate (the plan's
"at least one relevant source appears" wording), and graded nDCG@10. Human semantic-support and
contradictory-evidence review remain separate required evidence. A reviewer-name string cannot
prove a human performed the review; retain the actual review records with the dataset.

The chosen extraction approach should be verified against [Docling's local model configuration](https://docling-project.github.io/docling/usage/advanced_options/)
and the remaining table/token work against [Docling's chunking documentation](https://docling-project.github.io/docling/concepts/chunking/).
The present library chunker is not Docling's HybridChunker and does not claim its full table behavior.

### TXT/Markdown heading review

New uploads use `structured-text-sections-v1`. Section paths identify heading line positions,
not copied wording. Review/exclude/correct heading passages independently. Included corrected
headings can supply approved same-section context. Physical line numbering includes blank lines.
Hash-heading recognition is a navigation hint in both formats, not full Markdown rendering;
fences, links, HTML, tables and other syntax remain literal reviewable lines.

Prior TXT/Markdown revisions may carry original heading wording in descendant metadata even if
the heading was excluded or corrected. Inspect affected publications, withdraw unintended wording,
and upload/review/publish a new version. A corpus rebuild alone retains old extracted paths.
Do not silently rewrite historical citations. Other format heading metadata remains separate work.

### Word prose review

New DOCX uploads use `structured-docx-sections-v2`. Headings, paragraphs and list items have
`Paragraph N` labels; paths use neutral heading paragraph positions. Numbering includes direct
body blank/contents paragraphs but not table-internal paragraphs, whose row locations remain
separate. Review original and corrected prose independently. Included corrected headings can
supply approved section context; excluded headings supply no wording. Body image readiness and
table extraction behavior are unchanged.

Legacy Word extractions can retain original prose labels and copied heading paths even after
review corrections/exclusions. Inspect affected shared publications, withdraw unintended wording,
and upload/review/publish a new version. Rebuilding old extracted text alone cannot fix metadata.
Historical citations are not rewritten. This does not qualify full Word layout or the legacy
decorative-image heuristic; broader extraction/operations qualification remains open.

### Worksheet name review

New XLSX uploads use `structured-xlsx-sections-v2`. Review names in their own heading passages.
Locations use `Worksheet N` in workbook tab order, counting empty/hidden/chart tabs. Hidden-sheet
checkboxes use that same position; original names remain in the private extraction headings.
Formula references/chart text can contain names as explicit source evidence: review those passages
separately. Merge/formula/image behavior remains as before. Legacy revisions/selections are intact.

Inspect affected legacy publications for copied names in row labels/paths; withdraw unintended
wording and upload/review/publish a new version. Rebuilding stored extraction cannot remove copied
metadata. This does not qualify general workbook layout or actual embedding token counts.


## Requirement indexing and measured qualification (ADR-0062)

Migration 023 adds derived progress storage only. The independent Requirement worker processes up
to 16 distinct texts per batch; source-change compare-and-swap activates only a complete source.
Progress and cached vectors survive restart. A worker that died while holding a lease can be
replaced after its 15-minute lease expires. Three provider failures pause that source (30/60/120-second
backoff); a member uses Knowledge → Retry knowledge preparation. A source edit also resets failures.
Other sources continue through fair pagination. Screening/suggestion jobs wait without consuming
provider attempts while the corpus is pending. Check `/ready`'s `requirement_index_worker` field.
A missing/incompatible configured generation needs the existing explicit `llm rebuild` operator flow.

Existing clean indexes are not rewritten during migration. Schedule the explicit configured-generation
rebuild to adopt bounded children across historical long fields. Restore the previous configured
identity and activate a complete, current generation for Requirement rollback; a stale generation
must first be rebuilt. Historical evidence stays immutable and stale citations still need review.

For shared documents, coordinate a maintenance window with **every owner**. Record the current
configuration and publication/build manifests, stage a build of each owner's current reviewed source,
verify completeness, then let each owner activate their build. Mixed identities intentionally block
search. If reverting, restore the old configuration and have every owner build/activate the current
reviewed content under it. Reconcile superseded citations; do not repoint historical approvals or
assume a ready build is approval to activate. Never grant an operator cross-owner approval authority.

On 2026-09-22, actual `gemini-embedding-001:countTokens` measured 64 synthetic reviewed table/prose
and Requirement samples at 18–528 tokens, all below 2,048 and accepted for embedding. Runtime counters
still expose UTF-8 **budget units**, not measured tokens. A dated sample qualification cannot guarantee
all future content or provider revisions; rerun on model/endpoint/chunk-policy changes. Unsupported or
malformed count responses fail explicitly and never fall back to a chat model. See the checkpoint
spec for the fixture generator and `llm qualify-tokens` commands and the saved JSON evidence.

The opt-in `python -m tests.live_model_rollout --config config/llm.yaml --target-model gemini-embedding-2`
exercise completed 001→2→001 with two synthetic owners, actual providers and isolated memory storage.
The same authority/isolation/rollback contract passes against PostgreSQL with deterministic vectors.
These are local qualification evidence. A deployed maintenance rehearsal, representative customer
corpus, operational telemetry/load/restore checks and CI remain release requirements.

## Ownership handover and dependency inspection

Before replacing or withdrawing a policy, open **View dependencies** in its library workspace.
Entries distinguish current analysis from immutable historical rounds, recorded proposal decisions,
and whether the cited publication remains current. The view shows only Requirements you own or
review; it does not expose other teams' private Requirement names or dependency counts. Historical
round statuses describe the saved generation snapshot; later decisions remain in Requirement history.

Use **Manage ownership** to select a known workspace user and record a handover reason. Confirm
loss of private access and transfer. The new owner gains private originals, extraction review and
publication controls immediately. Upload/approval attribution and current publication identity do
not change. The former owner can read only still-published selected passages, like any other reader.
An old upload retry cannot retrieve a private document after transfer. If the form reports a version
conflict, reload and inspect the current owner/version before retrying. Handover history is available
to the current owner. There are no invitations, administrator recovery or delegated document reviewers
in this checkpoint.

## Source preview and ingestion completion

Set `DOCUMENT_OFFICE_PREVIEW_EXECUTABLE` only after installing and qualifying a local LibreOffice
renderer. Previews reject external relationships and active/embedded objects; use a self-contained
PDF export for those files. Missing renderer, OCR assets or scanner availability is explicit in
the browser. Empty OCR configuration uses safe native image/PDF extraction without claiming OCR.

Block-scoped warnings resolve only when that exact block is excluded in a saved review with a
rationale. Document-wide/legacy blockers still require corrected source uploads. Re-inclusion
restores a blocker. Never rewrite old extraction metadata to infer warning scopes.

Legacy Docling OCR heading paths can retain excluded wording. Inspect and withdraw affected
publications, then re-upload, review and publish a fresh version. Rebuilding stored text cannot
apply the new positional heading safeguards.

Async attachment status is stored with the document queue and restored by the Requirement/draft
page. Failed/quarantined uploads never attach. Completion rechecks access and the expected
replacement version. If the source changed, upload a new version after reviewing current state.

## Source lineage migration and reconciliation (ADR-0066)

1. Back up the database and stop application writers/workers for coordinated maintenance.
2. Run `python -m smb_requirement_agent.infrastructure.persistence.migrate` through migration 024.
3. Run `python -m smb_requirement_agent.interfaces.maintenance`. It backfills recorded current and
   immutable historical dependency rows, preserving impact decisions. Re-running is safe.
4. Verify readiness before restarting traffic. Inspect a known reused document and Requirement,
   checking exact source version/range, direct/indirect paths and membership filtering.

The Library **Review source impact** view shows only Requirements the owner can access. An empty
page does not imply zero organization dependencies. Open a Requirement's source impact review to
record an owner decision. **Retain historical evidence** needs a rationale for this exact content.
**Revise affected content** leaves review unresolved: start a fresh analysis if confirmed, reject
an outdated proposal, re-analyse without that input and regenerate descendants. Source lineage
remains attached to manually edited content; editing wording alone does not prove independence.
New generated artifacts may need their own historical-source review. Earlier decisions and approvals
remain in history. A document version or publication change invalidates earlier retained reviews.

For answer-derived evidence that still applies, retain the historical source explicitly; replacing
the current inputs must preserve earlier answered-round history. Never backfill origins by matching
text. Legacy objects without recorded lineage stay unattributed. Rebuild the configured Requirement
knowledge generation after upgrading; citation fingerprint checks prevent stale chunks from silently
becoming independent evidence.

`SMOKE_LINEAGE_POSTGRES=1` selects a test-only browser entry point, requiring a database whose name
contains `test`, fake providers and synthetic scanner results. Use disposable test data only. CI runs
this separately from memory browser coverage; production scanner rules are unchanged. Integration
tests also exercise real concurrent decisions, rollback, nonempty rebuild and restart.
