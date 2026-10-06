# Enhancement — Knowledge Center B1: attachments in the requirement corpus

> **Status:** delivered on `feat/knowledge-attachment-sources` (2026-10-06).
> **Parent:** the Knowledge Center re-plan, sub-slice B1
> ([enhancement-knowledge-center.md](enhancement-knowledge-center.md)). ADR-0099 Amendment 1
> records that attachment content joins the requirement corpus.

## Objective

A Requirement written mostly or wholly as an attached document should be screened, found and
cited as well as one written as typed text. Until now `RequirementKnowledgeCorpus.chunks()`
indexed only the typed fields, the analysis and agreed resolutions. A document-only
Requirement was screened from its title alone, and its attachment never reached knowledge search
or answer suggestions.

## User outcome

- Two Requirements supplied as the same BRD under different titles are flagged as possible
  duplicates. The finding quotes the attachment passage and links to the document.
- Knowledge search finds a passage that exists only in an attachment.
- A clarification answer can be suggested from another Requirement's attachment.
- Excluding an attachment, replacing it with a new version, choosing hidden worksheets or removing
  it changes what is indexed, the same way editing a typed field does.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | Attachment passages reach **the same places as typed text**: screening, knowledge search and answer suggestions. | Agreed in session (2026-10-06). An attachment is the author's own source, not a copy of someone else's. |
| 2 | **What an attachment contributes is the analysis rule.** `SourceDocument.included_blocks` is the included version's blocks, without the hidden worksheets nobody included. Analysis (`AssembleAnalysisDocuments`) and the corpus both read through it. | One rule, so the corpus never knows something analysis was told to ignore, and the other way round. |
| 3 | **One passage per block**, of kind `attachment`. Its `field` is `attachment:<document_id>:<block_id>`, and its `evidence_path` is `/documents/<document_id>`. A legacy plain-text extraction is one passage, `attachment:<document_id>:text`. Image-only blocks have no text and are skipped. | The field is unique per block, so two equal passages stay two citations and are never deduplicated together. The path opens the document reader, which already exists. |
| 4 | **No lineage.** The passages carry no `source_lineage`. | Lineage marks copies of library passages, which screening and suggestions exclude. An attachment is the Requirement's own source, like a typed field. |
| 5 | **Change tracking follows the document row.** <ul><li>**PostgreSQL:** a trigger on `source_documents` calls the existing `mark_knowledge_source_changed()` (migration `202610061000`). Inclusion, the included version, hidden worksheets and removal all live in that row.</li><li>**Memory mode:** `InMemoryDocumentRepository` takes the same callback.</li><li>**Existing data:** the migration marks every Requirement that already has an included attachment, so it is indexed once more.</li></ul> | No use case has to remember the index. A draft's document has no Requirement and marks nothing until promotion sets one. |
| 6 | **Labels only on the frontend.** `attachment` reads "Attachment passage" in the Knowledge step and in Clarify's suggestion evidence. | The frontend is presentation-only (CLAUDE.md). The existing panels already show the excerpt and link to `evidence_path`. |

## Scope

**Changed**

- **Domain:**
  - `KnowledgeSourceKind.ATTACHMENT`;
  - `SourceDocument.included_blocks`.
- **Application:**
  - `RequirementKnowledgeCorpus` takes the document repository and adds attachment values;
  - `AssembleAnalysisDocuments` uses `included_blocks`, with no change in behaviour.
- **Adapters:**
  - the migration `202610061000_knowledge_attachment_sources.sql`;
  - the `source_changed` callback on `InMemoryDocumentRepository`;
  - the composition passes the document repository to both corpus constructions (request graph
    and commit-time projections).
- **Frontend:** `PREFIX_LABEL.attachment` and `evidenceFieldLabel`.

**Not changed**

- The API.
- The screening, search and suggestion use cases.
- The index schema.
- The provider prompts.

## Known limits

- The screening query embeds the first 768 UTF-8 units of the subject text, which starts with the
  typed fields. For a document-only Requirement that includes the start of its attachment.
- The lexical side of screening uses `websearch_to_tsquery` on the whole subject. A long subject
  matches lexically only rarely, so screening of long attachments leans on the vector side. This
  was already true of long typed text.
- The judge's prompt carries the whole subject text, attachments included. Analysis already sends
  the same text to its provider.

## Tests

**Unit tests:** `tests/unit/test_knowledge_attachment_sources.py`

- Two document-only Requirements with different titles are screened as possible duplicates. The
  evidence cites `attachment:<document>:<block>` and `/documents/<document>`.
- Each included block with text is one passage, with no lineage.
- Excluding an attachment marks the Requirement for re-indexing. Its passages leave the index, and
  an earlier finding's citation is no longer current.
- A new version replaces the old passages, and removal takes them out.
- A hidden worksheet is indexed only once it is included.
- Knowledge search returns an attachment passage.
- An answer suggestion can cite an attachment passage.
- The memory repository marks the Requirement on every write, and a draft's document marks nothing.

**Integration tests (PostgreSQL):** `tests/integration/test_knowledge_attachment_sources_postgres.py`

- An upload, an exclusion, a re-inclusion and a removal each advance `knowledge_source_changes`
  and reach the index.
  - Without the trigger, this test fails (`assert (2 > 2)`).
- A draft attachment is indexed for the Requirement once the draft is promoted.

**Frontend tests:** `KnowledgeReviewPanel.test.tsx` covers both labels.

## Validation evidence

Recorded on 2026-10-06, locally, with PostgreSQL 16:

- `ruff format --check src tests` and `ruff check src tests`: clean.
- `mypy src tests`: clean.
- `lint-imports`: all contracts kept.
- `pytest`, unit, architecture and integration with `TEST_DATABASE_URL`: green. This includes the
  two new Postgres tests.
- **Frontend:**
  - `npm run build` and `npm run lint`: green;
  - `KnowledgeReviewPanel.test.tsx`: 14 passed.
