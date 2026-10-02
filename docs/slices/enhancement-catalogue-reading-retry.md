# Enhancement — Retry and explain catalogue reading failures

Requested 2026-10-01 by the product owner, after `SMB_Architecture_AI_Reference_v2209.md` failed
with "no part of the document could be read by the AI model". The document fits in one call. The
model (`google/gemini-3.1-flash-lite` via OpenRouter) gave one unusable answer about two seconds
after the job started, so the whole document failed. Four replays of the same document and
catalogue each succeeded, with 9 to 45 suggestions. On the UI side, only failure wording changes.

## Objective

A single rejected answer no longer fails a document, and a document that still cannot be read
says why.

## User outcome

- Each part of a document is asked for once more when its answer is rejected.
- A failed reading names the cause instead of the generic message. The cause is one of:
  - an empty, refused or cut-off answer;
  - a timeout;
  - a rate limit;
  - provider credentials, configuration or credits;
  - suggestions whose quotes could not be checked against the document.

## In scope

- One retry per part, in `StructuredCatalogueExtractor`.
- Specific error types and public codes for a total failure.
- Job-failure wording for the new codes.

## Out of scope

- More than one retry, or backoff.
- Changing the model, prompt or citation check.
- Splitting a one-call document into smaller calls.

## Application

- `CatalogueAnswerUnusableError` and `CatalogueCitationError` subclass `CatalogueExtractionError`.
- Public codes:

  | Code | Raised when |
  |---|---|
  | `catalogue_extraction_unusable` | Every part's last answer was malformed, empty or refused. |
  | `catalogue_extraction_uncited` | Every part's last answer cited nothing checkable. |

- `CatalogueAnswerUnusableError` is raised from the provider's last failure. A classified
  provider failure therefore surfaces as its own code, such as `model_invalid_output`,
  `model_timeout` or `model_rate_limit`.

## Adapters

- `StructuredCatalogueExtractor` asks for a rejected part once more. A part's reason is the reason
  its last attempt failed.
- Authentication, configuration and payment failures are not retried, since asking again cannot
  fix them.
- The checkpoint runs before the retry, so a document that left the draft stops reading.
- The failure message carries the last part's warning, for the worker log.

## UI

- `labels.ts` `JOB_ERROR` gains wording for both new codes and for the `model_*` codes.
- `labels.test.ts` covers the wording.

## Tests

- `test_catalogue_reading.py`:
  - a malformed or uncited first answer is asked for again, and the second answer is kept;
  - an authentication failure is not retried;
  - each total failure maps to its error type and public code;
  - a part's reason follows its last attempt.
- `test_error_handlers.py`: both new errors map to 502.

**Evidence.**
- Backend: `pytest` (full suite) passes. `ruff check`, `ruff format --check`, `mypy src tests`
  and `lint-imports` (7 contracts) are clean.
- Frontend: `vitest run src/features/catalogue` (47 passed) and `npm run build` are green.
- Not run:
  - a browser check, since the only visible change is failure wording, covered by
    `labels.test.ts`;
  - a live-model check of the retry, because the running containers were not rebuilt.
