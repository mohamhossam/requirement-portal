# Enhancement 11B — Grounded Clarification-Answer Suggestions

> Status: **complete locally; CI pending push**.

## Objective

Let a reviewer request concise answers for an active clarification question from current trusted
Requirement evidence while retaining the existing deliberate human resolve/re-analyse action.

## Roadmap Scope Check

| Roadmap field | Delivery |
|---|---|
| Domain | Immutable suggestion sets, cited evidence fingerprints, optional human-answer origin. |
| Application | On-demand grounded generation, citation validation, staleness, selection provenance validation. |
| Ports | Provider-neutral suggester and suggestion validator; reused hybrid index/embedding boundaries. |
| Adapters | Fake/OpenAI/local suggestion generation and memory/PostgreSQL persistence. |
| API | Durable suggestion job, current-set GET, additive `source_suggestion_id`. |
| UI | Suggest action, zero-result message, selectable rationale/evidence cards, editable free text. |
| Tests | Grounding, zero-to-three cardinality, malformed output, staleness, selection/edit/manual flow, API/UI/persistence. |

Nothing in the Enhancement 11B roadmap entry is dropped.

## Behavior

- Only an active question and accessible current trusted knowledge are searched. The unresolved
  Requirement itself is excluded from candidates.
- A result contains zero to three distinct suggestions. Zero reliable evidence is a successful
  empty result; blank answers/rationales, duplicate answers, unknown/missing citations, or partial
  provider output are explicit provider failures.
- Every immutable set records the question-content fingerprint, evidence chunk IDs and content
  fingerprints, generation time, model, and prompt version.
- Replaced/resolved questions or changed/removed cited knowledge hide the prior set. A provider
  failure does not mutate the question draft or overwrite a prior valid set.
- Selection only fills the free-text answer. The reviewer can edit it and must invoke the existing
  resolve/re-analyse action. The optional suggestion ID is validated as current and retained on the
  explicitly human-confirmed clarification.

## Validation Evidence

- `TEST_DATABASE_URL=postgresql://smb:smb_dev@127.0.0.1:5432/smb_requirements pytest` — PASS, 604 tests; includes durable suggestion-set persistence.
- `ruff check .` — PASS.
- `ruff format --check .` — PASS, 363 files formatted.
- `mypy src tests` — PASS, 296 source files.
- `lint-imports` — PASS, 2 contracts kept and 0 broken.
- `npm test -- --run` — PASS, 23 files and 112 tests.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run build` — PASS (non-blocking bundle-size advisory only).
- `npm run api:check` — PASS.
- `npm run test:smoke` on isolated ports — PASS, 14 Playwright cases across desktop and responsive Chromium; the main journey requests, selects, edits, and submits a grounded suggestion.
- CI — pending push; local success is not CI authority.

## Architecture Impact

ADR-0027 governs the shared trusted-evidence and provider-validation decisions. Suggestion content
never becomes business truth without the existing attributed human resolution workflow.

## Deferred / Open

- No automatic answer submission, external knowledge sources, or separate confidentiality model.
