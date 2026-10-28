# Changelog

Each release has a `## vX.Y.Z` section, written before the tag is pushed. The release workflow
(`.github/workflows/release.yml`, ADR-0108) refuses a tag without one and publishes the section as
the GitHub release notes. The tag must match `version` in `pyproject.toml` and
`frontend/package.json`.

Under each heading, list what changed for whoever deploys, then any upgrade step. Name every
contract-step migration (WORKSPACE.md, "Migrations"), because rolling back past one means
restoring a backup.

## Unreleased

- **One bad finding no longer fails the knowledge screen.** Screening asks the model which
  other requirements may duplicate or contradict this one. A single finding with a blank field,
  a second finding for the same requirement, or a citation of a passage it was not given failed
  the whole screen ("Knowledge classifier returned incomplete findings") and lost the valid
  findings. That finding is now set aside and logged as a count; a screen with no usable finding
  at all still fails. No upgrade step (ADR-0027, amended).
- **A citation repair that names a block outside its section no longer fails the analysis.**
  Resolving a question failed with "The model could not provide valid source citations.
  Analysis was not saved." when a section's citation repair cited evidence block 173 of a
  smaller section. The one correction meant for that never ran, because other outputs in the
  same repair were marked unsupported, which used to be final. Now a malformed repair always gets
  its correction. If the corrected repair still cites a block the section does not have, that
  output is set aside, or carried if it is a question the review kept, and the rest of the
  analysis stands (ADR-0032, amended). No upgrade step.
- **A slow product assessment is no longer given up on.** Analysis waited 120 s for the
  knowledge service's assessment. A requirement with many needs took 131 s, so the analysis was
  saved with "Product impact was not assessed" (logged as "The knowledge service could not be
  reached") while the knowledge service went on to answer. It now waits 240 s. It still does not
  retry. No upgrade step.
- **Resolving a question no longer fails on a question the model kept.** With structured
  documents, the last step of an analysis combines the section findings and reviews the open AI
  questions. A question it kept that no finding repeated had nothing to cite, and the job failed
  with "The model could not provide valid source citations. Analysis was not saved." The kept
  question is now carried with its earlier support, as it already was when combining fell back
  to a merge. A reworded (replaced) question still needs support. No upgrade step (ADR-0032,
  amended).
- **One malformed model response no longer fails the analysis.** OpenRouter does not enforce
  the response format, and GPT-5.1 occasionally returns analysis JSON with fields run together
  or cut short; the job then failed with "The model returned invalid, empty, refused or
  truncated structured output" and lost every section analysed so far. Such a response is now
  asked for once more and discarded. A second malformed response, a refusal or a truncated
  response still fails. No upgrade step (ADR-0032, amended).

- **Grounded answer suggestions no longer fail on a long answer list.** The model is asked for
  at most three answers of at most five citations each, but was held to it: a fourth answer or
  a sixth citation failed the job with "The model returned invalid, empty, refused or truncated
  structured output". The best three answers and each one's first five citations are now kept.
  No upgrade step.
- **A failed product-impact assessment is asked for once.** The knowledge portal answers 502
  when its models' verdict fails a check, and requirement work retried it twice, at a minute
  or two each, before finishing the analysis without product impact. The assessment is no
  longer retried, which took about two minutes off the analysis that showed it.
  No upgrade step.
- **filelock 4.2.4, OpenTelemetry 1.45.1 and setuptools 84.2.1 (security).** filelock 4.0.8
  carries CVE-2026-112940 (high: arbitrary file overwrite), CVE-2026-112913 and CVE-2026-112907,
  fixed in 4.2.1; opentelemetry-api 1.45.0 carries CVE-2026-114603, fixed in 1.45.1; setuptools
  84.0.0 carries GHSA-xmj3-9gf7-h52w, fixed in 84.1.0. The OpenTelemetry SDK and instrumentation
  packages move with the API to their matching patch releases. No code change, no upgrade step.
- **Frontend: zod 4.6.7, undici 7.30.1 and vitest 5.0.5 (security).** zod below 4.6.6 can
  exhaust memory validating oversized constrained collections (GHSA-mrhx-c7xc-m3w5, high);
  undici 7.30.0 has three advisories (GHSA-4qv8-2p9j-2685, GHSA-f72v-6w45-q472,
  GHSA-xjj6-f33q-929c, high); vitest 5.0.2 has two moderate ones in its mock registration
  (test tooling only, never in the served image). No code change, no upgrade step.

- **Product impact is assessed for large analyses.** Requirement work sent the knowledge
  portal one text item per fact, rule, constraint and answer, and the portal accepts at most 50
  items of 10,000 characters: an analysis with about 200 findings was refused with 422 and shown
  as "Product impact was not assessed". Over 50 items, consecutive items are now joined with
  newlines into fewer, larger ones, which is how the portal reads them anyway, so it sees the
  same text. An item over 10,000 characters is split at a space; past 500,000 characters in
  all, the end is left out with a warning. No migration.

- **A repeated item no longer fails the analysis.** When the model listed the same fact,
  constraint or rule twice (even in other case or spacing), or proposed one statement as both a
  rule and a constraint, both copies shared one citation, and the citation checks rejected the
  whole response as "duplicate evidence citation records". The first copy is now kept and later
  ones dropped before any citation check; combining section findings compares them the same way.
  No migration.

- **Large analyses no longer fail at the last step.** Combining the findings from each
  document section used a fixed 60,000-character budget whatever the model, and failed when a
  round could not shrink them ("could not be consolidated within the provider context budget").
  Combining now uses the analysis model's context window, from its model profile, the local
  model's settings or the new `OPENROUTER_CONTEXT_TOKENS` (for example `400000` for
  `openai/gpt-5.1`). Section packets keep their size. If combining still cannot shrink, the
  validated section findings are merged and kept, open AI questions are retained, and the worker
  logs a warning. Upgrade step (optional): set `OPENROUTER_CONTEXT_TOKENS` in `production.env`
  to your OpenRouter model's window. No migration (ADR-0029, amended).

- **One bad item no longer fails the whole analysis.** When the model marks one of its findings
  unsupported, or proposes a figure the sources lack, that item is set aside and the rest of the
  analysis is saved; before, every valid finding was discarded with "Analysing requirement
  failed". The worker logs how many items were set aside and why, never their text. The analysis
  still fails when nothing is left, or when the unsupported item is a question kept from an
  earlier round (ADR-0032, amended; ADR-0025).
- **The requirement itself can back a finding.** When the documents are analysed section by
  section, a finding taken from the requirement's description, structured fields or decided
  intent can now cite the requirement. Before, it could cite only the section's passages or an
  answer, so such findings were unsupportable. They show no document under "Where this came
  from", as in an analysis without documents. Prompt version `analysis-v26-requirement-citations`
  re-runs cached section analyses once. No migration.

- **Analysis no longer fails when consolidation repeats a figure from a document.** With
  structured documents, the last step reads only the earlier findings' statements, so the check
  that refuses invented figures in intent proposals (ADR-0025) treated a figure the first pass
  had taken from a document, or kept in a proposal's rationale or success measures, as invented.
  The whole analysis then failed with "Analysing requirement failed". That step now also counts
  the documents' text and the earlier proposals' rationale and success measures as support. The
  model is not shown them, and the fragment cache is unchanged. No migration.

- **platform-kernel v1.3.1** (was v1.3.0): it allows Pillow 13, so only the docling family still
  needs the temporary `[tool.uv]` Pillow override. No code change, no upgrade step.

- **Pillow 13, certifi 2026.10.19 and pypdf 6.21 (security).** Every Pillow 12.x carries the
  October 2026 advisories (CVE-2026-112395 and others: denial of service and information
  disclosure in the JPEG, GIF, TIFF and PDF code), fixed only in 13.0.0; certifi 2026.7.22
  still trusted emSign roots with compromised intermediate keys (GHSA-6q48-6c7w-9gw2); pypdf
  6.19.0 has CVE-2026-113793 to 113795, fixed by 6.20.1. The image now installs the fixed
  versions. The frontend's build tool moves to vite 8.3.5: 8.3.0 to 8.3.2 bundle a
  launch-editor with three high advisories (GHSA-r825-w8mm-5pxw and two more; development
  server only, never in the served image). platform-kernel v1.3.0 and docling still ask for Pillow below 13, so a
  temporary `[tool.uv]` override allows 13 until they do. No upgrade step.

- **Starting an AI job no longer deadlocks with a finishing one.** Inserting a job locked the
  Requirement row and then its job-lease row, while a completing attempt held the lease row and
  locked the Requirement row at commit (capturing the revision) — under load PostgreSQL aborted
  one of the two (deadlock detected, seen as transient CI noise). Every transaction that takes
  both rows now takes the lease row first, so the two queue instead. No migration.
- **The requirement-analysis prompt is sectioned and assembled per request**
  (`analysis-v25-sectioned-conditional`). The question-lifecycle, evidence-citation and
  attachment rules are sent only when the request supplies active AI questions, evidence
  blocks or documents, freeing context for the evidence itself; the vague-language and
  completeness rules are aligned with ISO/IEC/IEEE 29148 (weak-word categories, domain-
  relevant completeness dimensions); extracted statements must be singular, unambiguous
  and verifiable; rule/constraint proposals state condition and behavior explicitly. The
  vague-term backstop that triggers a focused review now also reads attachment text (a
  blank description with a vague BRD previously never triggered it) and recognizes the
  standard weak words (TBD, "if necessary", "as soon as possible", …). Stored analyses
  keep their recorded provenance; reverting to `analysis-v24` is one git revert of the
  prompt commit plus a redeploy. No migration.
- **Features carry acceptance criteria, and every Feature and Story a business/enabler
  kind** (ADR-0118; prompts `feature-v8`, `story-v8`). Generation supplies feature-level
  conditions of satisfaction and types each item as business work or a SAFe enabler
  (exploration, architecture, infrastructure, compliance); both are editable, exported
  (schema 1.6 → 1.7, new XLSX columns), published to ADO as description rows and shown in
  the UI. Rows persisted and approvals recorded before this change are untouched: the new
  payload and fingerprint fields are written only at non-default values, so nothing is
  rewritten and no approval lapses. Story generation-context tokens are invalidated once;
  open clients recover by reloading the Story set. No migration.
- **Breakdown prompts align with the published SAFe guidance** (`epic-v4`, `feature-v7`,
  `story-v7`). Epic generation now receives the decided product impact and unconfirmed
  evidence (dependencies, ambiguities) the Feature/Story prompts already saw, and asks for a
  SAFe-style value statement; the Feature prompt frames the outcome as a benefit hypothesis,
  prefers customer-recognizable splits over `component_system`, orders MVP drops first, and
  its schema rejects an empty Feature set; the Story prompt adds the simple/complex and
  defer-performance splitting patterns and requires observable acceptance `then` clauses that
  cover evidence-supported failure behavior. Artifacts generated under the old prompt
  versions keep their recorded provenance; no migration.
- **Every attachment upload is malware-scanned.** The synchronous attachment routes
  (`POST …/attachments` and `…/attachments/{id}/versions`, for Requirements and drafts) now run
  the same fail-closed scan as background ingestion; previously only ingestion scanned. A flagged
  file answers 422, and an unreachable scanner refuses the upload instead of accepting it.
  `ATTACHMENT_SCAN_MODE=offline` now requires only fake identity (it previously also demanded
  memory persistence); production still refuses it through OIDC. No migration.
- **The backend image fails closed.** `deploy/api/Dockerfile` sets `APP_ENV=production`, so the
  image deployed with no environment demands production configuration (OIDC, PostgreSQL, a real
  model provider) instead of booting with the fake development identity. Development and demo
  manifests already override `APP_ENV`. In production the API now also answers 404 on
  `/openapi.json`, `/docs` and `/redoc` itself, instead of relying on the bundled edge to hide
  them. No migration.
- **Production requires a daily AI spend ceiling.** `APP_ENV=production` refuses to start with
  `PROVIDER_DAILY_TOKEN_BUDGET` unset or 0 (record-only). Upgrade step: set it in
  `deploy/production.env` to the organization's daily token budget and keep the
  `DailyTokenBudgetExceeded` alert threshold in step. No migration.
- **Test coverage for the measured gaps.** New unit tests cover the auth module
  (`safeAuthReturnPath` open-redirect refusals, the sign-in page's fake and OIDC flows, the
  knowledge-admin role check), the `TagInput` primitive (previously 0%), the in-memory reverse
  lineage index (membership, filters, retirement, citation counts, decision versioning) and the
  LLM CLI's refusal paths. The frontend coverage floors rise to 82/75/73/85 (statements/branches/
  functions/lines), re-measured 2026-10-15; the review's other suspected gaps (story workflow,
  activity projection, revision tracking) measured 85–100% covered and needed nothing. No
  migration.
- **The browser follows the server's review rules.** `frontend/src/review/rules.ts` is deleted:
  approval, generation and regeneration availability now come from the API's `actions` fields
  (ADR-0073), so the gate texts are the server's and cannot drift. The request-body types and
  the passage-citation shape are derived from the generated contract types instead of being
  hand-written (AGENTS.md §19 debt, paid as an owner-approved ADR-0109 exception). No API or
  migration change; the visible difference is slightly different wording on blocked
  Approve/Generate buttons.
- **CI robustness.** Every workflow job has a `timeout-minutes` ceiling instead of GitHub's
  6-hour default. The redundant `postgres-architecture` job (quality gates already runs
  the whole test tree against PostgreSQL) is deleted, now that the `main` branch-protection
  rule no longer requires a check by that name. The browser smoke job now runs against
  PostgreSQL with
  migrations applied — the durable mode a deployment uses — instead of the in-memory store, and
  uploads Playwright traces on failure, as does the deployment job's platform browser step; the
  backend coverage XML is kept as an artifact. Dependabot gets a `registries` entry for the
  private platform-kernel — the owner must also store `KERNEL_READ_TOKEN` as a Dependabot secret
  or uv update PRs cannot resolve. `pytest-timeout` (300s per test) guards against hangs, and the
  polling-worker tests join their threads so none outlives the run. No migration.
- **Edge and deployment hardening.** The `web` port now binds to `127.0.0.1` by default —
  upgrade step: deployments that expose the edge directly set `WEB_BIND=0.0.0.0` in `deploy/.env`
  (and a firewall or TLS proxy in front remains required). `/api/` responses carry
  `Content-Security-Policy: default-src 'none'; sandbox`, so a directly opened attachment or
  image is inert; the app reads them with fetch and is unaffected. The api, worker, migrate and
  web containers drop all Linux capabilities (`cap_drop: [ALL]`). `ADO_ORGANIZATION_URL` must be
  HTTPS — plain HTTP sent the personal access token in cleartext. The gitleaks allowlist is anchored to the exact `ci-only…` values instead
  of any line containing them. ADR-0111 Amendment 1 records the prompt-injection, spend-ceiling
  and operator-owned-infrastructure risks. No migration.
- **Documentation brought in line with the shipped code.** README, PRODUCT.md, ROADMAP.md,
  WORKSPACE.md, AGENTS.md §19 and CLAUDE.md no longer describe Azure DevOps publication, the
  repository split, the bounded-context layout or the UI redesign as pending — all are shipped.
  ADR-0117 records the redesigned application shell and formally supersedes ADRs 0045, 0047 and
  0050; the ADR index gains its missing rows and the note that ADR-0107 was skipped. SECURITY.md
  and the deployment runbook now say no release has been tagged yet. `.python-version` (3.12) and
  `frontend/.nvmrc` (24) pin local runtimes to CI's, and the launchers ask for Node.js 24. No
  migration.
- **A figure the owner gave in an answer no longer fails analysis.** The check that refuses
  numeric targets the model invents (ADR-0025) now also counts the owner's clarification answers
  and accepted or edited intent decisions as support, not only the requirement and its documents.
  Resolving a question answered with "1000 max for off-net calls" used to fail with "The service
  could not complete the request". No migration.
- **Publishing approved backlogs to Azure DevOps (Slice 12, ADR-0112).** Off by default
  (`ADO_PUBLISHER=none`). To turn it on, set `ADO_PUBLISHER=azure_devops`, `ADO_ORGANIZATION_URL`,
  `ADO_PROJECT` and `ADO_PERSONAL_ACCESS_TOKEN` (or `_FILE`), a token with Work Items read and
  write. `ADO_SQUAD_AREA_PATHS` sends each squad's Features to its board. No migration.
- **Safe republish to Azure DevOps (Slice 13, ADR-0113).** Publishing again updates the items
  already sent instead of duplicating them, and Retry continues a publication that stopped
  part-way. Migration `202610101200_backlog_publications` (expand only: a new table).

- **Product impact in analysis (ontology plan Phase 4, ADR-0115, ADR-0116).** With a knowledge
  portal linked, analysis asks it where the requirement sits (a new offering or a change to one),
  and the owner accepts, overrides or marks the verdict unknown before confirming. Breakdown
  follows the decided impact (prompts `feature-v6` and `story-v6`), review flags an undecided
  verdict, capability gaps and weak links, and publication records the verdict. Needs
  knowledge-portal v0.3.0 or later; an older one assesses nothing and blocks nothing.
  `PRODUCT_VERDICT_VALIDATED` (default `false`) stops calling the verdict a suggestion once the
  live gate has passed. No migration: the impact is stored in the analysis snapshot.
- **Decided verdicts sent back as precedents (ontology plan Phase 5).** Each accepted,
  overridden or unknown product impact is queued with the decision and delivered to the knowledge
  portal's `POST /internal/architecture/precedents`, retried until it answers. Assessments now
  carry the requirement's id, so its own decision is never its precedent. Needs knowledge-portal
  v0.4.0 or later; an older one answers 404, which is retried for about two days. Migration
  `202610111200_precedent_handoffs` (expand only: a new table).
- **What a closed Epic delivered (ontology plan Phase 7).** When an Epic this service published is
  closed or removed in Azure DevOps, its service hook
  (`POST /api/integrations/azure-devops/work-items`) queues it once per event. A worker reads its
  Features' states and sends what was delivered, what was predicted and the catalogue changes that
  implies to the knowledge portal's `POST /internal/change-requests/deliveries`, retried until it
  answers. Off until `ADO_HOOK_SECRET` (24+ characters, or `_FILE`) is set and the subscription is
  added in Azure DevOps (`docs/operations/deployment.md`, "Azure DevOps service hook"). Needs
  knowledge-portal v0.5.0 or later. Migration `202610111800_delivery_closures` (expand only: a new
  table and an index on `backlog_publications`).
- **A drafted offering for a new offering (ontology plan Phase 9).** When the knowledge portal
  suggests a new offering in a family or a new product line, it drafts the offering and its
  journey; the product impact card shows the draft, and the approved backlog sends it back
  unchanged while the decided verdict is a new offering. Export schema 1.6 adds
  `product_impact` (the decided verdict, its offering and release, and the draft) to the
  approved-backlog export and the JSON download; a knowledge portal older than v0.6.0 ignores
  it. Needs knowledge-portal v0.6.0 for the draft. No migration.
- **Production mode on one machine against the local Keycloak.** Two optional overlays,
  `deploy/keycloak/compose.local.yaml` and `deploy/compose.local-oidc.yaml`, run the Docker stack
  with `APP_ENV=production` and OIDC sign-in through `https://keycloak.localhost:8443`
  (`docs/operations/keycloak-login.md`, "Production mode on one machine"). Not for a shared
  deployment. `.gitattributes` now checks shell scripts out with LF line endings: on Windows, a
  CRLF checkout left the web container restarting with "not found". No migration.

## v0.1.0

Prepared as the first release, but its tag was never pushed, so no `v0.1.0`
images exist; the release that ships this content will be cut from a later
version. It was the pilot candidate, closing the pilot gate of
`docs/slices/production-hardening.md`, with its shared provider limits and platform-kernel 1.3.0.

- **Production configuration fails closed.**
  - The production manifest always runs `APP_ENV=production` with OIDC sign-in.
  - A fake model, the debug trace or non-JSON logs refuse to start.
  - The API documentation is not served at the edge.
- **Analysis survives a knowledge-portal outage.** It is kept and marked "references not
  checked".
- **AI jobs retry transient outages with backoff.**
  - The waits are `AI_JOB_RETRY_FIRST_SECONDS` and `AI_JOB_RETRY_MAX_SECONDS`.
  - Exhausted jobs are labelled in metrics.
- **Model-backed work runs only as a durable job (ADR-0105).**
  - The synchronous provider routes are removed.
  - The edge's `/api/` timeout is 60 seconds.
  - Architecture mapping runs through the job routes and needs Requirement membership only.
- **Probes and shutdown.**
  - `/ready` answers within 2.5 seconds on its own threads.
  - In-flight requests get 25 seconds on a stop.
  - `web` has a healthcheck.
- **The browser keeps working through a token renewal.**
  - Requests abandoned by a sign-out or identity switch are silent.
  - A crash or a redeployed page shows a way out (ADR-0109).
- **Releases, backups, upgrade and rollback (ADR-0108).**
  - Signed images, with SBOMs, are published to `ghcr.io` by tag.
  - `/health` reports the version.
  - A `backup` service is added.
  - Migrations follow an expand/contract policy.
- **Shared provider limits, a daily token budget, and edge limits (ADR-0106).**
  - The per-person provider rate limit holds across API replicas.
  - `PROVIDER_DAILY_TOKEN_BUDGET` pauses new AI work until 00:00 UTC once spent
    (`provider_budget_exhausted`, 429). Queued jobs wait.
  - nginx limits each client address (`EDGE_RATE_PER_SECOND`, `EDGE_BURST`).
  - A deployment behind a TLS proxy must set `TRUSTED_PROXY_CIDR`.
- **Platform-kernel 1.2.0.**
  - **Sign-in.** A person's token must be an access token issued to `OIDC_CLIENT_ID`. Other
    clients are accepted only when listed in `OIDC_AUTHORIZED_PARTIES`.
  - **Clock difference.** `OIDC_LEEWAY_SECONDS` (60) of clock difference is tolerated.
  - **Issuer outages.** A brief issuer outage no longer fails sign-ins: the last good signing
    keys keep being served (ADR-0018 amendment).
  - **OpenAI.** Each reply is capped at `OPENAI_MAX_OUTPUT_TOKENS` (8192).
  - **Migrations.** A migration waits at most 10 seconds for a table lock, and concurrent
    `migrate` runs take turns.
  - **Knowledge service.** Calls pause for 30 seconds after 5 failures in a row.
- **Database sessions are bounded (ADR-0074 amendment).**
  - Pooled connections run with a 30s statement timeout, a 5s lock timeout and a 60s
    idle-transaction timeout (`DATABASE_*_TIMEOUT_SECONDS`).
  - A busy database answers 503 `database_busy`, and AI jobs retry it.
  - PostgreSQL starts with `max_connections=${POSTGRES_MAX_CONNECTIONS:-200}`; size it with
    `deployment.md`.
  - Pool use is exported as `smb_db_pool_connections`.
- **Alerting, SLOs and runbooks.**
  - The monitoring overlay adds:
    - Alertmanager, sending to `ALERTMANAGER_RECEIVER` (`none`, `webhook` or `slack`) at
      `ALERTMANAGER_URL`;
    - a PostgreSQL exporter;
    - a host exporter.
  - 18 alerts, each with a runbook in `docs/operations/alerts.md` and unit tests run by CI.
  - Proposed objectives in `docs/operations/slos.md`, for the owner to confirm.
  - New metrics: `smb_build_info`, `smb_ready`, the AI job queue (`smb_ai_jobs_queued`,
    `smb_ai_job_oldest_queued_age_seconds`), `smb_provider_spend_blocked_total`, and the
    process, Python and garbage-collector series.
- **Containers and the edge are hardened.**
  - Every container rotates its logs and has memory, CPU and process limits
    (`API_MEM_LIMIT`, `WORKER_MEM_LIMIT`, `POSTGRES_MEM_LIMIT`, `CLAMAV_MEM_LIMIT`).
  - `clamav` and `worker` have healthchecks.
  - Secrets can be read from files (`NAME_FILE`; `docs/operations/secrets.md`, with rotation
    steps), including a new `DATABASE_PASSWORD`.
  - `DATABASE_URL` can name a managed PostgreSQL as a Compose variable.
  - The edge forwards the browser's scheme only from `TRUSTED_PROXY_CIDR` and sends HSTS over
    HTTPS.
  - The API trusts forwarded headers only from the deployment's fixed subnet
    (`REQUIREMENT_SUBNET`).
  - Logs carry exception types and correlation IDs, never messages.
  - A job heartbeat rides out a brief database failure while its lease lasts.
- **Supply chain.**
  - CI scans every commit for secrets (gitleaks), and CodeQL analyses the backend, the frontend
    and the workflows.
  - Every Monday, the latest release's images are scanned again for new vulnerabilities
    (`deployment.md`, "Releases and upgrades").
  - The optional Keycloak stack pins its images by digest, restarts with the host, and now pulls
    Keycloak from Docker Hub (`keycloak/keycloak`) rather than quay.io.
  - `docs/operations/identity-provider.md` describes the two clients and the token and session
    lifetimes.
- **The browser copes with a slow or failing API, and says when it fails.**
  - Requests give up after 30 seconds, or 2 minutes for uploads and downloads. A page nobody
    shows any more stops its requests.
  - Error messages and failure notices show the request's reference (its correlation ID), to
    quote to support.
  - Browsers report crashes to `POST /api/client-errors`, by kind only, counted as
    `smb_client_errors_total`. The edge limits each address to 1 report a second.
  - One `web` image serves every deployment. `CSP_IDENTITY_ORIGINS`, `KNOWLEDGE_PORTAL_URL` and
    `KNOWLEDGE_PORTAL_ROLE` are read when the container starts, which refuses to start under OIDC
    without an issuer origin.
  - The frontend declares Node 24 (`engines`, `.nvmrc`).
- **Long lists are paged, and old job inputs are cleared.**
  - `GET /documents` and `GET /requirements/drafts` answer a page (`offset`, `limit`, `total`,
    `has_more`) with search and sort, instead of a bare list. Documents also carry their
    owner's title, the counts per state and the owners to filter by. The Documents page loads
    more on request.
  - The `retention` command also clears the stored inputs of AI jobs that succeeded or were
    cancelled more than `AI_JOB_PAYLOAD_RETENTION_DAYS` (90) ago. Job rows and history stay;
    such a job can no longer be retried (`ai_job_inputs_pruned`, 409). Knowledge screens keep
    their inputs (ADR-0079 amendment).
  - Each run also reports the document blobs' count and size, and how many nothing refers to.
    It deletes none.
- **Optional tracing (ADR-0110), with platform-kernel 1.3.0.**
  - Set `OTEL_EXPORTER_OTLP_ENDPOINT` to export OpenTelemetry traces over OTLP/HTTP. Unset (the
    default), nothing is traced. Each traced unit has one trace:
    - an API request, named by its route;
    - an AI job attempt.
  - Each trace holds that unit's SQL statements and its calls to the knowledge portal, model
    providers and the identity provider.
  - No path, query string, body, SQL value or exception message is recorded.
  - Only the knowledge portal is sent `traceparent`. The edge drops one a browser sends.
  - `OTEL_TRACES_SAMPLER_ARG` keeps a share of new traces (default all).
  - JSON log lines carry `trace_id` and `span_id` inside a kept trace.
  - The monitoring overlay adds an OpenTelemetry Collector and Grafana Tempo
    (`TEMPO_RETENTION`, 72h), with a Grafana data source.
  - FastAPI's own telemetry is off, so `OTEL_*` variables can no longer stop the API starting.
- **The browser is easier to find your way in.**
  - An address that matches no page says so, with a link to the dashboard, instead of showing
    the dashboard under a wrong address.
  - A new page takes keyboard focus, so a screen reader starts at its content. Choosing an item
    that changes the address within a page leaves focus where it is.
  - Links to Azure DevOps work items are shown only for `https:` addresses.
  - Remembering the last requirement no longer fails a save in private browsing, and
    downloads keep their file long enough for Firefox and Safari.
- **Governance.**
  - `SECURITY.md`: report vulnerabilities privately through GitHub.
  - `CODEOWNERS` and a pull request template.
  - Four accepted risks recorded in ADR-0111: tokens in `sessionStorage`, the silent-renewal
    iframe, workspace-wide read access, and English only.
  - The repository has no licence yet.

Upgrade: none (first release). Contract-step migrations: none after `202610091200`.
