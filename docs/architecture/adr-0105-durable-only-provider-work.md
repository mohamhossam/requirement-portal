# ADR 0105 — Model-backed work runs only as a durable job

## Status

Accepted 2026-10-08 by the repository owner ("move the synchronous AI routes to the job queue
now"), and implemented 2026-10-09 in production hardening PR 4a and PR 4b
(`docs/slices/production-hardening.md`). It amends ADR-0020, which kept the synchronous
endpoints "during migration".

## Context

ADR-0020 made every model-backed action an `AiJob` and moved the browser onto the job routes,
but kept the synchronous routes that did the same work inside the HTTP request. By 2026-10-08
the browser used them for one thing only, architecture mapping. Everything else used them only
from tests. They still cost the deployment:
- a request held an API worker thread and an open connection for as long as the model took,
  so the edge allowed 600 seconds for every `/api/` call;
- the same command had two paths with different failure, retry and progress behaviour, and
  only the job path had retry with backoff (ADR-0020 amendment), cancellation and an audit
  trail;
- each route needed its own rate limit and its own context-token check, and the rate-limit
  architecture test had to list them all.

## Decision

**No request waits on a model. Model-backed work runs only as a durable job:** an AI job
(`POST /requirements/{id}/ai-jobs`) or an architecture mapping job
(`POST /requirements/{id}/architecture-mapping/jobs`).

- **Removed** (PR 4b):
  - analysis, clarification and question resolution:
    - `POST /requirements/{id}/analysis`;
    - `…/analysis/clarifications`;
    - `…/analysis/question-resolutions`;
    - `…/analysis/questions/{question_id}/resolution`;
  - generation:
    - `POST …/epic`;
    - `POST …/features`;
    - `POST …/features/{feature_id}/stories`;
  - Story regeneration and proposals:
    - `…/stories/regeneration`;
    - `…/stories/{story_id}/regeneration`;
    - `…/stories/change-proposals`;
  - quality reads that ran the evaluator:
    - `GET …/stories/quality`;
    - `…/stories/{story_id}/quality`;
    - `…/quality/split-recommendations`;
  - review:
    - `POST …/breakdown-review`;
    - `…/breakdown-review/open-questions/{flag_id}/resolution`;
  - mapping: `POST …/architecture-mapping`.

  The browser already started the job equivalents. Feature quality is read from its stored
  snapshot (`…/stories/quality-assessment`).
- **Kept:**
  - routes for human decisions that only *queue* model work, such as asking a clarification
    question or deciding an intent proposal (they stay rate-limited as automatic triggers);
  - unified knowledge search, a bounded call to the knowledge service.
- **Refused at start.** A job that can only fail is refused when it is started, with the status
  the synchronous route used to return:
  - re-analysis without `force`;
  - a Requirement missing fields;
  - an Epic over human work without `force`, or from an unconfirmed analysis;
  - Features before the Epic is approved, or over human work without `force`;
  - first Stories that already exist, or for a Feature that is not ready.

  The breakdown use cases expose `require_can_generate` for this, beside
  `AnalysisCollaboration.require_can_generate`, and `AiJobs` calls them before enqueueing.
  Other conflicts appear only while the work runs, and they end as a failed job with a public
  error code. Examples are a concurrent edit, Story regeneration over human work, and a
  mapping refusal.
- **Edge.** nginx gives `/api/` a 60-second read and send timeout, down from 600 seconds.
- **Tests** drive model-backed work the way the browser and worker do. `tests/job_driver.py`
  starts a job through the public route, then runs the container's queue and executor until the
  job is terminal.

## Consequences

- **Bounded requests.**
  - A slow or hung model no longer holds an API thread, a database connection or a browser
    request.
  - Retry with backoff, cancellation, progress and failure notifications apply to all model
    work.
  - The edge timeout bounds a stuck upstream.
- **One path per command.** Context-token checks happen when the job starts and again before
  it commits. `RequirementCommands` no longer takes an expected context.
- **What callers lose.**
  - The `201`/`200` "created or replaced" distinction is gone. A caller reads the resource after
    the job succeeds.
  - A conflict found only at run time becomes a failed job rather than a `409`. Mapping jobs
    report only an error category.
  - There are no external API consumers. Any script that called the removed routes must start
    jobs instead.
- **Tests run the worker.** Tests that need model output now start a job and run it, which
  exercises the production path at the cost of a few extra queries per test.

## Alternatives Considered

- **Keep the synchronous routes behind a setting.** This keeps two paths and their differences
  alive, and a long edge timeout is still needed whenever the setting is on.
- **Answer the old paths with `202` and a job.** Same-path compatibility would hide a changed
  contract behind familiar URLs. No consumer needs it, because the browser already uses the job
  routes.
- **Keep the routes and only shorten the edge timeout.** A slow model would then fail requests
  at the edge while the work went on behind it, with no record and nothing to retry.
