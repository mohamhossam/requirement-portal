# Enhancement — Knowledge Center B3: retire, reinstate and bulk reindex (requirement-portal half)

> **Status:** delivered on `feat/knowledge-corpus-actions` (2026-10-07).
> **Parent:** the Knowledge Center re-plan, sub-slice B3
> ([enhancement-knowledge-center.md](enhancement-knowledge-center.md)). knowledge-portal adds
> the actions to its Requirements page in its own slice.

## Objective

B2 shows a knowledge admin the corpus and its findings. B3 lets them act on it: retire an
obsolete or cancelled Requirement so it stops producing duplicate warnings, return it, and retry
or reindex the corpus in bulk. The rules and data stay here (ADR-0099 Amendment 1); knowledge-portal
calls three service-token routes, naming the admin.

## API

All three are added to `contracts/requirement-internal.openapi.json` and need the service token.

- **`POST /internal/knowledge/requirements/{id}/retirement`**, body
  `{actor_id, actor_name, reason}` (reason 1–500 characters), answers a `MembershipResult`
  (`requirement_id`, `state`, `changed_at`, `closed_findings`, `notified`). 404 for an unknown
  Requirement; 409 when it is already retired or closed as a duplicate.
- **`POST /internal/knowledge/requirements/{id}/reinstatement`**, the same body; 409 unless it
  is retired.
- **`POST /internal/knowledge/reindex`**, body `{actor_id, actor_name, scope, requirement_ids?,
  reason?}`: `scope: "failed"` retries every Requirement that stopped indexing;
  `scope: "requirements"` indexes up to 500 chosen Requirements again. Answers
  `{requirements}`, how many were retried or marked. 409 while the model change waits for a
  rebuild.
- **Reads:** `GET /internal/knowledge/corpus` gains `retired_only`, and each row a `retired`
  mark (`at`, `by`, `reason`); the summary gains `retired`.

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | **Retired means fully out**, as a closed duplicate is: no passages in the index, never a candidate, not screened itself, and citations to it are no longer current, so search and suggestions drop it at once. | Agreed in session (2026-10-07). A retired Requirement must stop producing warnings on both sides. |
| 2 | **Membership is its own record**, not a Requirement state: no version bump, so generated backlog, staleness and history are untouched. One row per Requirement ever retired, its `state` active or retired; its trigger marks the Requirement for indexing. | "Stays fully readable and keeps its history" (spec B3). |
| 3 | **Every actionable finding citing it closes as `source_retired`**, either side, recording the admin and the reason; a closed finding cannot be re-proposed. A screen after reinstatement may raise the pair afresh: a source-retired finding never blocks a new one. | Agreed in session (2026-10-07). |
| 4 | **A retired Requirement's knowledge review reads as current and ready**, with the retirement on the response; its Knowledge step shows who retired it, when and why, and no screen is scheduled for it. | Confirmation must not wait on a screen that will never run. |
| 5 | **Reinstating folds the membership's change into the screening fingerprint**, so the earlier screen reads as stale and the next time the Knowledge step opens, it is screened again. The owner's notification links there. | Re-screening is provider work; internal routes never reach the scheduler (`test_provider_rate_limit.py`). |
| 6 | **The owner is notified** on retirement and reinstatement, with the reason (`knowledge_corpus_retired`, `knowledge_corpus_reinstated`). | Agreed in session (2026-10-07). |
| 7 | **Bulk retry resets only sources that stopped on their current change; bulk reindex bumps only the chosen sources.** Vectors are cached by text, so unchanged passages are not embedded again. | The worker does the provider work at its own pace. |
| 8 | **Every action is recorded** in `knowledge_corpus_actions`. | The audit trail stays with the data. |

## Changes

- **Domain:** `knowledge/membership.py` (`CorpusMembership`, `CorpusState`, `CorpusAction`,
  `CorpusActionKind`); `KnowledgeFindingStatus` and `KnowledgeDecisionKind` gain
  `source_retired`; `KnowledgeFinding.close_source_retired`; `propose_resolution` only on an
  actionable finding; `RequirementRetiredError` and `CorpusMembershipConflictError` (409);
  `NotificationKind` gains two kinds; `ActivityAction.FINDING_SOURCE_RETIRED`.
- **Migration** `202610070900_knowledge_corpus_actions.sql`: `requirement_corpus_membership`
  with its source-change trigger, and `knowledge_corpus_actions`.
- **Ports and adapters:** `CorpusMembershipPort`, `CorpusActionsPort`, `SourceChangesPort`, in
  PostgreSQL and in memory (enrolled in memory transactions).
- **Exclusion:** `RequirementKnowledgeCorpus.in_corpus` feeds `index_source`, both citation
  checks and the fingerprint; screening, the screen scheduler and choosing a canonical
  Requirement refuse a retired one.
- **Application:** `RetireFromCorpus`, `ReinstateToCorpus`, `BulkReindexRequirements`;
  `IndexBacklogReader.retry_failed`; retired counts and rows in the B2 reads.
- **Interface:** the routes, the contract and its path test; `KnowledgeReviewResponse` gains
  `corpus_retirement`.
- **Frontend (feature work, decision 4):** the Knowledge step's retirement notice; labels for the
  new finding status, decision, activity and notification kinds.

## Tests

**Unit:** `tests/unit/test_corpus_actions.py`
- retiring closes the findings that cite it, records the admin and reason, notifies the owner,
  records the action, and leaves the Requirement untouched;
- a retired Requirement leaves the index, is not a candidate, is not screened, and search drops it;
- reinstating notifies, re-indexes, and a fresh screen raises the pair anew;
- a reinstated Requirement's earlier screen is stale;
- a source-retired finding cannot be closed again or re-proposed;
- blank reasons, retiring twice, reinstating an active one and retiring a duplicate are refused;
- a retired Requirement cannot be chosen as canonical;
- reindex marks only the chosen Requirements; retry resets only stopped sources;
- retired Requirements are counted and filtered;
- the routes need the token, and pass 404, 409 and 422 through.

**PostgreSQL:** `tests/integration/test_corpus_actions_postgres.py`: the trigger, the membership
and action rows, the closed finding's payload, the reads, reinstatement and bulk reindex.

## Validation evidence

Recorded on 2026-10-07, locally, with PostgreSQL 16:

- `ruff format --check src tests` and `ruff check src tests`: clean.
- `mypy src tests`: clean.
- `lint-imports`: contracts kept.
- Full `pytest` with `TEST_DATABASE_URL`: green.
- Frontend `lint`, `typecheck`, `api:check` and `build`: green.
