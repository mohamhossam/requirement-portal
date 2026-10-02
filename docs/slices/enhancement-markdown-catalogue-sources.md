# Enhancement — Markdown catalogue sources

Requested 2026-10-01 by the product owner. Architecture catalogue → Add content → From documents
should accept Markdown files. This is feature work outside the UI redesign's presentation-only
rule. On the UI side, only the accepted-file constants and the help text change.

## Objective

Let maintainers add `.md` and `.markdown` files as catalogue source documents, read for AI
suggestions and indexed as evidence (ADR-0090).

## User outcome

- Maintainers can pick or drop a Markdown file in "From documents".
- The help text lists Markdown among the accepted formats.
- Suggestions from a Markdown file cite `lines A-B`, and the passage dialog opens those lines.

## In scope

- The architecture upload allowlist.
- The MIME fallback for untyped `.md` uploads.
- Located passages for `text/markdown`.
- The file picker's `accept` list, type correction and help text.

## Out of scope

- Rendering Markdown.
- Heading-aware passages.
- Other upload surfaces, which already accept `.md`.

## Application

- `ARCHITECTURE_EXTENSIONS` gains `"text/markdown": ".md,.markdown"`.
- `UploadKnowledgeDocument` treats a `.md` or `.markdown` file sent as an empty type,
  `application/octet-stream`, `text/plain` or `text/x-markdown` as `text/markdown`.

## Adapters

- `LocatedDocumentExtractor` reads `text/markdown` in the same 40-line windows as `text/plain`.

## UI

- `DocumentSources`:
  - `ACCEPT` adds `.md,.markdown`;
  - `MIME` maps both extensions to `text/markdown`;
  - `FORMATS` names Markdown.

## Tests

- `test_architecture_p1.py`:
  - Markdown line windows;
  - NUL bytes and invalid UTF-8 are refused.
- `test_architecture_knowledge.py`:
  - `.md` and `.markdown` uploads under each browser type are stored as `text/markdown`;
  - `.md` declared as PDF is refused.
- `ArchitectureCataloguePage.test.tsx`: the `accept` list, and an untyped `landscape.md` is sent
  as `text/markdown`.

**Evidence.**
- Backend: `pytest` (full suite) passes. `ruff check`, `ruff format --check`, `mypy src tests`
  and `lint-imports` (7 contracts) are clean.
- Frontend: `vitest run src/features/catalogue` (46 passed) and `npm run build` are green.
- Browser, against the fake API:
  - a draft's "From documents" lists Markdown and accepts `.md,.markdown`;
  - an untyped `landscape.md` uploads and reading finishes;
  - the suggestion cites `landscape · lines 1-6`, and "Show in document" opens those lines with
    the quote highlighted.
- Not run:
  - the impeccable critique, since the only visible change is one word of help text;
  - a live-model check.
