# Enhancement — Centralized logging in Graylog

> Status: **planned; not started.** Decisions recorded 2026-09-26. Implementation
> must not begin until this spec is scheduled in `ROADMAP.md`.

## Objective

Every container's logs reach Graylog as structured, searchable records. An
operator can follow one request from the edge to the API, investigate errors
and sign-in problems, and **retrieve every log line related to one Requirement
by its ID**, in development and in production.

## User Outcome

An operator opens Graylog and:
- pastes a Requirement ID to see, in time order, every request, background
  job, AI provider call, error and warning that touched it, including the
  draft it started as;
- pastes a request ID from an error message to see that request's nginx and
  API lines together;
- watches a security stream of failed sign-ins, lockouts, 401s and 403s.

## Recorded decisions

| # | Question | Decision |
|---|---|---|
| 1 | Graylog server | The project ships Graylog for development **and** production |
| 2 | Transport | Fluent Bit reads Docker's log files and forwards GELF to Graylog. The application never talks to Graylog |
| 3 | Which containers | All of them |
| 4 | User in request logs | The opaque actor ID only; never names or emails |
| 5 | Retention | 30 days operational, 365 days security and sign-in, both configurable |
| 6 | Production runtime | Docker Compose on a server |
| 7 | Requirement lookup | Every log line related to a Requirement carries its ID, and Graylog offers a Requirement timeline search |

## Current state (as found)

- **API and worker:** JSON lines on stdout (`LOG_FORMAT=json`) with timestamp,
  level, logger, message and `correlation_id`. The request line has method,
  route template, status and `duration_ms`; the AI-job line has job ID,
  operation and status.
  - No `service`, `environment` or actor field.
  - **No Requirement ID anywhere.** The request line logs the route template
    by design, so identifiers are dropped.
- **Correlation:** only the AI-job worker sets a correlation scope. The
  requirement index, architecture job and document ingestion workers log
  without one.
- **One-off commands:** `migrate`, `maintenance` and `retention` use `print()`,
  so their output is not JSON.
- **nginx (`web`):** default text access log. It carries no `request_id`,
  although nginx already forwards `$request_id` to the API as `X-Request-ID`.
  It also **logs query strings**, which can hold search text; the application
  deliberately never logs them.
- **Keycloak:** realm events are enabled but stored only in its database, not
  logged.
- **Docker:** the Compose services use Docker's default `json-file` driver with
  no size cap, so container logs grow without limit.
- **Nothing** leaves the host.

## In Scope

### 1. Structured fields on every application log line

- Add a **log context** alongside the existing correlation context in
  `infrastructure/observability/`, read by `JsonLogFormatter`. It holds:
  - `requirement_id`, `draft_id`, `job_id` and `actor_id` for the current unit
    of work;
  - `service` (`api`, `worker`, `migrate`, `maintenance`, `retention`), from a
    new `SERVICE_NAME` setting that the Compose manifests set per service;
  - `environment` (`APP_ENV`) and `release` (image tag, when set).
- **HTTP.** When a route is matched, set the context from its path parameters,
  before the handler runs, so every line written while serving the request
  carries it:
  - `requirement_id` from `requirement_id`, or from `source_id` when
    `scope=requirements`;
  - `draft_id` from `draft_id`, or from `source_id` when
    `scope=requirement-drafts`;
  - `job_id` from `job_id`.

  The request line keeps the route template and never logs the concrete path
  or query. The authenticated `actor_id` is added once the actor is resolved.
- **Workers.** Each claimed unit of work runs inside a correlation scope and a
  log context:
  - AI jobs: `requirement_id` from the job;
  - requirement index work: its Requirement;
  - architecture mapping jobs: their Requirement;
  - release-scoped architecture builds: `release_id` only;
  - document ingestion: `requirement_id` or `draft_id` from its source, or
    `library_document_id` for the shared library.

  Every provider call, warning and error inside that work inherits the IDs.
- **Draft promotion.** Log one explicit `requirement.draft_promoted` line
  carrying both `draft_id` and `requirement_id`, so a Requirement's timeline
  can include the draft it started as.
- **One-off commands.** `migrate`, `maintenance` and `retention` use
  `configure_logging`. Their messages become log records, and the exit codes
  are unchanged.
- **Privacy is unchanged:**
  - no Requirement text, prompts, provider payloads, names, emails, tokens or
    query strings;
  - IDs are opaque UUIDs;
  - the debug trace (`logs/debug.log`) is a file, never shipped.

### 2. Edge, identity and container logs

- **nginx:** a JSON `log_format` with:
  - time, `request_id`, method;
  - **path without query string** (`$uri`);
  - status, bytes, request time, upstream time;
  - client address as seen by nginx.

  The API sees the same `request_id` as `correlation_id`.
- **Keycloak** (`deploy/keycloak/compose.yaml`):
  - JSON console logs;
  - the `jboss-logging` event listener, logging login, failed login, logout,
    lockout and admin events at INFO;
  - never credentials or tokens.

  This complements Enhancement 8A.2 (AD sign-in).
- **Every Compose service** (application, Keycloak, monitoring and logging
  stacks) uses a shared `x-logging` anchor:
  - `json-file` with `max-size` and `max-file`, capping disk use;
  - `labels`/`tag` options, so each line records its Compose service name.

### 3. Log shipper (Fluent Bit)

- A `fluent-bit` service (image pinned by digest) in
  `deploy/compose.logging.yaml`:
  - reads the Docker container log files (host path mounted read-only);
  - takes the service name from the `json-file` attributes, so no Docker
    socket is needed.
- Processing:
  - parse application and nginx JSON into fields; other containers' lines stay
    as `message`;
  - add `service` and `environment` where a container did not provide them;
  - set the GELF `level` from the record's level.
- Output: GELF over TCP to Graylog. TLS is configurable via `GRAYLOG_GELF_TLS`
  and required when Graylog is on another host.
- **Filesystem buffering** with a size cap (`FLUENT_BIT_BUFFER_MAX`):
  - a Graylog outage never blocks or fails an application container;
  - logs are delivered when Graylog returns;
  - the oldest are dropped only after the cap is reached.
- Fluent Bit's own health endpoint is used as the Compose healthcheck. Its
  metrics are scraped by the monitoring add-on when both run.

### 4. Graylog stack (development and production)

- Services in `deploy/compose.graylog.yaml`, each image pinned by digest:
  - `graylog` (server and web UI);
  - `mongodb` (Graylog configuration);
  - `graylog-datanode` (OpenSearch managed by Graylog, holding the log data).
- **Development:**
  - runs on the same host;
  - web UI on `127.0.0.1:9000`;
  - modest heap settings (about 3–4 GB of RAM in total).
- **Production:** the same manifest, with:
  - secrets (`GRAYLOG_PASSWORD_SECRET`, `GRAYLOG_ROOT_PASSWORD_SHA2`) from the
    deployment secret store;
  - persistent volumes;
  - the web UI behind the site's TLS reverse proxy;
  - the GELF input reachable only on the private network;
  - documented sizing for heap, disk per day and data-node memory.
- **Idempotent provisioning.** A one-shot `graylog-provision` service configures
  Graylog through its REST API, so a fresh or rebuilt Graylog converges to the
  same setup.
  - **Input:** GELF TCP.
  - **Index sets:**
    - `smb-operational`: rotated daily, deleted after `GRAYLOG_RETENTION_OPERATIONAL_DAYS` (default 30);
    - `smb-security`: rotated daily, deleted after `GRAYLOG_RETENTION_SECURITY_DAYS` (default 365).
  - **Streams:**
    - Application (api, worker, one-off commands);
    - Edge (nginx);
    - Identity (Keycloak);
    - Infrastructure (PostgreSQL, ClamAV, monitoring, Fluent Bit);
    - Errors (level ERROR and above, all services);
    - Security, stored in `smb-security`: API 401 and 403, Keycloak failed
      logins, lockouts and admin events.
  - **Pipeline rule:** extract `requirement_id` and `draft_id` from nginx paths
    (`/api/requirements/<uuid>/…`, `/api/requirement-drafts/<uuid>/…`), so edge
    lines join the Requirement timeline too.
  - **Saved searches:**
    - **Requirement timeline**, parameterised by Requirement ID:
      `requirement_id:<id>`, plus the draft IDs recorded by its
      `requirement.draft_promoted` line, across all streams, oldest first;
    - **Request trace:** `correlation_id` or `request_id`;
    - failed AI jobs;
    - 5xx by route;
    - failed sign-ins by user.
  - **Dashboard:** errors over time by service, slowest routes, job failures,
    sign-in failures, and log volume per service.
  - **Event definitions** (Graylog alerts):
    - repeated failed sign-ins for one user;
    - a burst of 403s;
    - error-rate spike per service.

    Metric alerts stay in Prometheus to avoid duplicates.
- The provisioning definitions live in `deploy/graylog/` and are the reviewed
  source of truth. Changes made in the UI are not persisted back.

### 5. Documentation

- A "Logs" section in `docs/operations/deployment.md` covering:
  - the architecture;
  - bringing up the Graylog and logging overlays;
  - the field reference, including all ID fields;
  - how to search by Requirement ID or request ID;
  - retention settings;
  - privacy rules;
  - sizing and backup (MongoDB for configuration; log data is retention-bound);
  - behaviour during a Graylog outage.
- A new ADR recording the choice: Fluent Bit tailing json-file logs, GELF to a
  project-shipped Graylog, and log context for identifiers. It amends ADR-0074's
  logging section.
- `START_GUIDE.md` (Docker section), `README.md`, and the env templates
  (`deploy/production.env.example`, `deploy/demo.env.example`) list the new
  variables.

## Out of Scope

- Shipping the launcher-based local runs (`start.ps1`/`start.sh` write to
  `logs/`); Graylog covers the Docker stack. Tailing `logs/` can be added later.
- A link or panel inside the application UI that opens Graylog for a
  Requirement.
- Replacing the in-app Activity feed, which remains the business audit trail;
  Graylog holds technical logs.
- Graylog clustering and high availability beyond one server node.
- Kubernetes manifests (decision 6).
- Shipping the debug trace, request bodies or provider payloads.

## Domain

- No change.

## Application Use Cases

- Draft promotion writes the `requirement.draft_promoted` log line with both
  IDs. No behaviour, port or return value changes.

## Ports

- No change. Log context is an infrastructure/interface concern, set by the
  HTTP layer and the workers; the application layer keeps using standard
  logging.

## Adapters

- `infrastructure/observability`: log context, and formatter fields for
  context, service, environment and release.
- The four background workers set a correlation scope and a log context per
  unit of work.

## API

- No contract change. Request log lines gain `requirement_id`, `draft_id`,
  `job_id` and `actor_id` fields when present.
- New settings: `SERVICE_NAME` and an optional `RELEASE` (image tag).

## UI

- No change.

## Business Rules

- Logs never contain Requirement text, prompts, provider payloads, names,
  emails, tokens, passwords or query strings. Identifiers are opaque.
- Logging never affects application availability. Containers write only to
  stdout; shipping failures are absorbed by Fluent Bit's bounded buffer.
- Security and sign-in records are kept longer (default 365 days) than
  operational records (default 30 days). Both are configurable.
- All Requirement-scoped logs are retrievable by `requirement_id`. Pre-promotion
  draft activity is reachable through the recorded draft-to-Requirement link.

## Tests

- **Unit, observability:**
  - the formatter emits service, environment, release and log-context fields;
  - context is isolated between concurrent requests and jobs, and reset after
    each;
  - absent IDs are omitted rather than logged as empty.
- **Unit, HTTP:** for Requirement, draft, `source_id` (both scopes) and job
  routes, every line logged during the request, including an error line,
  carries the right IDs. The request line still logs the route template and no
  path or query.
- **Unit, workers:** an AI job, an index run, a mapping job and an ingestion
  each log with `correlation_id` and the right Requirement or draft ID.
- **Unit, promotion:** the `requirement.draft_promoted` line carries both IDs.
- **Unit, commands:** `migrate`, `maintenance` and `retention` emit JSON under
  `LOG_FORMAT=json`, with unchanged exit codes.
- **Configuration:**
  - the nginx template's log format contains `request_id` and `$uri`, and never
    `$request_uri` or `$args`;
  - every Compose service uses the shared logging anchor;
  - new images are pinned (`test_image_pins.py` extended);
  - `fluent-bit --dry-run` validates the shipper config.
- **CI end-to-end:**
  - start the reference stack with Fluent Bit pointed at a small stand-in GELF
    receiver (not a full Graylog);
  - create a Requirement through nginx;
  - assert that parsed nginx and API records with the same `correlation_id`
    arrive, and that API and worker records carry the Requirement's ID.
- **Local acceptance with the real Graylog stack:**
  - provisioning is idempotent (it runs twice with no drift);
  - the Requirement timeline search returns the request, job and edge lines for
    a Requirement created from a draft;
  - retention settings are applied to both index sets.

## Acceptance Criteria

- [ ] Logs from every container reach Graylog; application and nginx records arrive as structured fields.
- [ ] Searching a Requirement ID returns its requests, background jobs, provider-call warnings and errors, edge lines, and its pre-promotion draft activity, in time order.
- [ ] A request ID returns the matching nginx and API lines.
- [ ] Failed sign-ins, lockouts, 401s and 403s appear in the Security stream, kept for the configured security retention.
- [ ] Operational and security retention are configurable and applied.
- [ ] Stopping Graylog does not affect the application; logs written during the outage arrive afterwards, up to the buffer cap.
- [ ] No log record contains Requirement text, prompts, payloads, names, emails, tokens or query strings.
- [ ] Container log files on the host are size-capped.
- [ ] Graylog provisioning is idempotent and reproducible from `deploy/graylog/`.
- [ ] All backend and frontend quality gates, configuration tests and the CI end-to-end check are green.

## Files expected to change

- `src/smb_requirement_agent/infrastructure/observability/` (log context, formatter)
- `src/smb_requirement_agent/infrastructure/config/settings.py` (`SERVICE_NAME`, `RELEASE`)
- `src/smb_requirement_agent/interfaces/api/main.py` (route-matched context, actor field)
- `src/smb_requirement_agent/infrastructure/jobs/*.py`, `infrastructure/documents/library_worker.py`
- the draft-promotion use case (one log line)
- `src/smb_requirement_agent/interfaces/maintenance.py`, `interfaces/retention.py`,
  `infrastructure/persistence/migrate.py`
- `deploy/web/default.conf.template` (JSON access log)
- `deploy/compose.production.yaml`, `deploy/compose.monitoring.yaml`,
  `deploy/keycloak/compose.yaml` (logging anchor, `SERVICE_NAME`, Keycloak JSON and events)
- new: `deploy/compose.logging.yaml`, `deploy/compose.graylog.yaml`,
  `deploy/fluent-bit/`, `deploy/graylog/` (provisioning definitions and script)
- `tests/unit/…` (observability, HTTP, workers, commands), `tests/architecture/test_image_pins.py`,
  new configuration tests
- `.github/workflows/ci.yml` (end-to-end log shipping check)
- `docs/operations/deployment.md`, new ADR, `START_GUIDE.md`, `README.md`, env templates

## Validation Evidence

None yet; not started.
