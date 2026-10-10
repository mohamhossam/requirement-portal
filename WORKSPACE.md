# WORKSPACE.md — Developer and Coding-Agent Workspace Setup

## 1. Workspace Goal

This repository is intentionally prepared for both human developers and autonomous coding agents.

The workspace must make it easy to:
- understand the active roadmap slice,
- preserve Clean Architecture,
- run all quality checks locally,
- replace external adapters,
- develop without live LLM/ADO dependencies,
- review changes incrementally.

---

## 2. Repository Layout

This repository is one of three that make up the platform (ADR-0098):

| Repository | Holds |
|---|---|
| `requirement-portal` (this one) | Requirement work: intake, clarification, review, backlog, attachments, architecture mapping of Requirements, and the reference deployment in `deploy/` that runs the whole platform |
| [`knowledge-portal`](https://github.com/mohamhossam/knowledge-portal) | The knowledge service: the shared library, the architecture and squad catalogues, its own database and its own browser app under `/knowledge/` (ADR-0099) |
| [`platform-kernel`](https://github.com/mohamhossam/platform-kernel) | `smb_kernel`: shared mechanisms only, such as identity, document extraction, model transports and internal HTTP (ADR-0100) |

Each runs alone in development with offline stand-ins for the other; START_GUIDE.md section 4,
"Run with the knowledge service", connects the two.

Initial structure:

```text
.
├── AGENTS.md
├── ROADMAP.md
├── WORKSPACE.md
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── .importlinter
├── .agents/
│   ├── agents/
│   │   └── smb-requirement-engineer/
│   │       └── agent.md
│   └── workflows/
│       └── implement-slice.md
├── .github/
│   └── workflows/
│       └── ci.yml
├── docs/
│   ├── source/
│   │   └── SMB_AI_Story_Breakdown_Prompt_Template_requirement_1.md
│   ├── architecture/
│   │   ├── README.md
│   │   ├── adr-template.md
│   │   └── adr-NNNN-*.md
│   └── slices/
├── src/
│   └── smb_requirement_agent/
│       ├── shared_kernel/        # pure domain shared by every context (ADR-0103)
│       ├── identity/ jobs/ requirements/ references/ analysis/
│       ├── knowledge/ breakdown/ governance/
│       │   └── {domain, application/{ports, use_cases, errors.py}, infrastructure}/
│       ├── reporting/            # application and infrastructure only
│       ├── workflows/            # cross-context orchestration; the public error catalogue
│       ├── application/          # shared technical: base errors, events, technical ports
│       ├── infrastructure/       # shared technical: config, persistence, LLM transport, text
│       │   ├── config/
│       │   ├── llm/
│       │   └── persistence/
│       └── interfaces/
│           └── api/
│               ├── container.py      # composition root
│               ├── dependencies.py
│               ├── error_handlers.py # error -> status map
│               ├── routes/
│               └── schemas/
└── tests/
    ├── conftest.py
    ├── architecture/
    └── unit/
```

Do not create folders for every future concept before the slice requires them.

---

## 3. Prerequisites

Recommended:
- Python 3.12+
- Git
- a Python virtual environment
- Node.js only when the frontend slice begins

Optional external systems are not required for early slices:
- no live LLM required for unit tests,
- no PostgreSQL until persistence slice,
- no ADO until ADO slices.

---

## 4. Python Setup

### Bash / WSL / macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### PowerShell (standard)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### PowerShell — Windows Application Control (WDAC/AppLocker) environments

If your machine enforces an Application Control policy that blocks newly downloaded
`.pyd` extension modules in project directories, create the venv with
`--system-site-packages` so that compiled packages (e.g. `pydantic_core`) are
loaded from the trusted system Python location instead of being re-downloaded:

```powershell
py -3.12 -m venv --system-site-packages .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
# force-reinstall any packages whose CLI scripts were not created by pip
python -m pip install ruff "import-linter" --force-reinstall --quiet
```

After activation, all standard quality gate commands (`pytest`, `ruff`, `mypy`,
`lint-imports`) resolve through `.venv\Scripts\` as normal.

### The platform kernel

`smb-platform-kernel` (ADR-0100) is a git dependency, pinned by tag in
`pyproject.toml`. The repository is public, so pip and uv fetch it without credentials.

To work on the kernel and this application together, install your local checkout over
the pinned one. Never commit that change:

```bash
pip install -e ../platform-kernel
```

Upgrading means changing the tag in `pyproject.toml`, then running `uv lock`.

---

## 5. Environment Configuration

Copy:

```bash
cp .env.example .env
```

Do not commit `.env`. It is loaded at startup by `Settings.from_env()`.

`LLM_PROVIDER` selects the adapters used for analysis, Epic, Feature, and Story
generation:

| Value | Behaviour |
|---|---|
| `openai` (default) | Real provider calls. Requires `OPENAI_API_KEY`. |
| `openrouter` | Authenticated OpenRouter calls. Requires `OPENROUTER_API_KEY`; defaults to the development/demo Gemma free model. |
| `local` | OpenAI-compatible local server. Requires `LOCAL_LLM_MODEL`; no credential. |
| `fake` | Deterministic canned analysis. No account needed. |

Startup fails immediately with a `ConfigurationError` if `LLM_PROVIDER=openai`
and no key is present, rather than returning a provider error on the first
analysis request. The same fail-fast rule applies to `LLM_PROVIDER=openrouter`
and `OPENROUTER_API_KEY`. Set `LLM_PROVIDER=fake` to run the whole application without
provider credentials.

Optional: `OPENAI_MODEL` (defaults to `gpt-4o`),
`OPENAI_MAX_OUTPUT_TOKENS` (each reply's cap, defaults to `8192`) and
`OPENAI_EMBEDDING_MODEL` (defaults to `text-embedding-3-small`). Knowledge
embeddings are normalized to the application's 768-dimensional contract;
dimension mismatches fail the provider operation explicitly.

OpenRouter mode defaults to `google/gemma-4-31b-it:free` for chat and
`openai/text-embedding-3-small` for 768-dimensional Requirement-knowledge
embeddings. Chat uses JSON mode plus strict application-side schema validation,
because the free endpoint does not enforce JSON Schema. Requests require
eligible endpoints to honor parameters and deny provider data collection;
privacy is never weakened to recover availability. Free models have low daily
limits and are suitable for development/demo use, not production. There is no
automatic paid chat-model fallback, while the configured embedding model may
incur OpenRouter charges.

Local mode defaults to LM Studio's API root at
`http://127.0.0.1:1234/v1`. Set `LOCAL_LLM_BASE_URL` to another compatible
server, such as `http://127.0.0.1:11434/v1` for Ollama, and set
`LOCAL_LLM_MODEL` to the model identifier loaded by that server.
For the supported local vision setup, run `scripts\setup-local-ollama-model.cmd`
and select `smb-qwen3-vl:8b-16k`. The tracked Modelfile pins the 16K context and
deterministic sampling, while the setup probe verifies vision and live allocation.
Local mode also requires `LOCAL_EMBEDDING_MODEL`, naming an embedding model
served by the same OpenAI-compatible API and producing 768 dimensions.
`LOCAL_LLM_TIMEOUT_SECONDS` defaults to `120`; the supported Qwen vision alias uses `300`
for image-bearing structured BRD packets on laptop-class GPUs.
`LOCAL_LLM_CONTEXT_WINDOW_TOKENS` defaults to `8192`, and
`LOCAL_LLM_MAX_OUTPUT_TOKENS` defaults to `4096`. The adapter counts the focused
prompt plus JSON schema and fails before a call that would require truncating
the human requirement or clarification answers. If a provider still stops at
the output limit, the failure explicitly names both settings rather than
reporting a generic schema mismatch.
Local Requirement-knowledge screening and clarification-suggestion operations reserve at most
2,048 output tokens because their schemas cap results at ten findings and three suggestions. This
leaves the remainder of the configured context for retrieved evidence without reducing the larger
output allowance used by analysis and backlog generation.
Set `LOCAL_LLM_VISION_ENABLED=true` only when `LOCAL_LLM_MODEL` accepts
OpenAI-compatible image content. Structured analysis blocks image-bearing BRDs
when this declaration is false. For the supplied 14-page BRD, the temporary
legacy-path settings are a 16,384-token Ollama/application context and a 4,096-token
output allowance; restart both processes after changing them. Enhancement 5D.2
normally avoids that workaround by planning section packets within the configured
budget.
Set `LOCAL_LLM_REASONING_EFFORT=none` for thinking models when structured
extraction should skip internal reasoning. Other accepted values are `low`,
`medium`, and `high`; leaving it empty omits the provider parameter.

`DEBUG_TRACE_ENABLED=true` opts into a single sensitive JSONL trace at
`DEBUG_TRACE_PATH` (default `logs/debug.log`). The trace records backend request
lifecycle, local structured-output prompts and final completions, parsed models,
normalized analysis candidates, citation-set comparisons, and mapped exception
chains. Credentials, binary/image content, and hidden reasoning are redacted.
Normal operation performs no trace file I/O. Keep the persistent setting disabled
and use `start.ps1 -DebugTrace` for the local launcher; the launcher restores the
prior process environment when it exits so later tests do not inherit tracing.
Delete the file after diagnosis, and inspect it before sharing.

`PERSISTENCE_PROVIDER=memory` keeps offline/test state in process. Set
`PERSISTENCE_PROVIDER=postgres` and `DATABASE_URL` for durable storage; packaged
migrations are applied explicitly before API startup with
`python -m smb_requirement_agent.infrastructure.persistence.migrate`. Azure DevOps
publication (Slice 12) is off until `ADO_PUBLISHER` is set; its `ADO_*` variables are
documented in `.env.example`.

For local development, `start.ps1` and `start.cmd` orchestrate that explicit
step: they start the Compose PostgreSQL service only for a local database URL,
wait for readiness, run the migration command, and then launch the API/UI.
`-CheckOnly` performs no startup or migration side effects.
The development image is PostgreSQL 17 with pgvector. Migration `010` enables
the `vector` extension and creates the full-text and HNSW knowledge indexes.

New migrations are named by UTC creation time, `YYYYMMDDHHMM_description.sql`
(for example `202609241530_add_rate_limits.sql`). Sequential numbering stopped
at `026`: two branches each taking "the next number" collided (`018`), and a
timestamp sorts after every legacy number, so the runner's lexical order is
still creation order. Never rename an applied migration — the runner would
apply it again. `tests/unit/test_migration_catalogue.py` enforces both rules.

**Migrations: expand, then contract (ADR-0108).**
- **Expanding is the default.** A release migrates before its new processes start. The previous
  release may still be serving at that moment, and a rollback redeploys it onto the migrated
  database. So a migration adds: new tables, nullable or defaulted columns, indexes, relaxed
  constraints.
- **Contracting is a separate, later step.** Dropping, renaming or retyping a table or column,
  or emptying a table, removes what the previous release reads. It ships only once no deployed
  release needs the old shape, usually one release after the code stopped using it.
  - The file starts with a `-- contract-step: <why it is safe now>` line.
  - The release's `CHANGELOG.md` section names it, because rolling back past it means restoring
    a backup.
- **Enforced.** `tests/architecture/test_migration_expand_contract.py` refuses any contracting
  statement without the marker, including one built inside `EXECUTE`. Migrations up to
  `202610091200` predate the rule.

Source-document defaults are `DOCUMENT_MAX_FILE_BYTES=10485760` and
`DOCUMENT_CONTEXT_MAX_CHARACTERS=60000`. Memory persistence keeps metadata and
blobs in process. PostgreSQL persistence stores immutable bytes in the database,
separate from revision JSON. Extraction defaults to two active child processes,
four waiting requests, 30 seconds, 512 MiB per child, 200 PDF pages, 1,000,000
characters, 250,000 XML nodes, 20 million decoded-image pixels, and 1,000,000
visited spreadsheet cells.

Production-readiness migrations `013`–`015` require the coordinated maintenance
window in `docs/operations/production-readiness-maintenance.md`. Blob import and
worklist projection backfill are explicit, resumable administrative steps; API
startup never runs them. Preserve legacy document files until separately approved.

Configuration is read only in `infrastructure/config/settings.py`. Do not
expose these values to the domain, and do not read `os.environ` from a use
case.

`IDENTITY_PROVIDER=fake` is the offline default. It exposes three clearly
labelled development personas in the UI (owner, reviewer, observer), defaults
to the owner, and accepts `X-Fake-Actor-Id` only in fake mode. For production,
set `IDENTITY_PROVIDER=oidc` plus `OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, and
`OIDC_CLIENT_ID`. `OIDC_SCOPES` defaults to `openid profile email`, and
`OIDC_ALLOWED_ALGORITHMS` defaults to the asymmetric allowlist `RS256,ES256`.
Only access tokens are accepted, issued to `OIDC_CLIENT_ID` or a client listed in
`OIDC_AUTHORIZED_PARTIES`, with `OIDC_LEEWAY_SECONDS` (60) of clock difference
allowed (ADR-0018, amendment 2026-10-09).
OIDC settings are validated when the application starts; raw tokens and claims
are never persisted.

AI operations run through bounded background workers. Defaults are
`AI_JOB_WORKER_CONCURRENCY=1`, `AI_JOB_POLL_INTERVAL_SECONDS=1`,
`AI_JOB_LEASE_SECONDS=90`, and `AI_JOB_HEARTBEAT_SECONDS=20`. Heartbeats must be
less than half the lease duration. `AI_JOB_MAX_ATTEMPTS=3` (minimum 1) caps how many
attempts one job may start: a job whose worker keeps dying, so its lease keeps
expiring and it keeps being reclaimed, fails as `attempts_exhausted` (retryable)
instead of looping forever, and its creator is notified. A job whose model provider was
rate limited or unavailable, or whose platform service could not be reached, is not failed
at once: it waits `AI_JOB_RETRY_FIRST_SECONDS=30`, doubling per attempt up to
`AI_JOB_RETRY_MAX_SECONDS=300`, and runs again within the same cap. Its Requirement's other
jobs wait behind it, so their order holds. With PostgreSQL, jobs and notifications
survive API restarts; memory mode retains the same behavior for offline work but
loses process-local state on restart. Model-backed work runs only as a job: the
synchronous generation endpoints are retired (ADR-0105), the browser starts `/ai-jobs`
and polls durable status, and a start that can only fail (re-analysis or an Epic over
human work without `force`, Features before the Epic is approved, Stories that exist)
is refused at once with 409 or 422.

API restart starts only the durable worker: it never scans the Requirement portfolio or creates
knowledge-screening jobs. Genuine Requirement/evidence changes still schedule automatically.
Knowledge and Confirm lazily call the team-authorized knowledge-screen ensure endpoint when review
is required or stale. An equivalent failed, cancelled, or anomalously completed attempt returns
`manual_retry_required`; only an explicit human Retry creates a user-priority linked job.

Before rolling out Enhancement 11A.1, stop API/workers and apply migration `012` with the normal
explicit migration command. It marks only queued automatic knowledge-screen jobs cancelled.
Running jobs remain lease-recoverable and Requirements, screens, findings, suggestions, user jobs,
and terminal history are preserved.

---

## 6. Run the API

Development:

```bash
LLM_PROVIDER=fake uvicorn smb_requirement_agent.interfaces.api.main:app --reload
```

Health:

```text
GET http://127.0.0.1:8000/health
```

## 6.1 Run the Review UI

Keep the API running with `LLM_PROVIDER=fake`, then use a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

`package-lock.json` resolves every package from `registry.npmjs.org`. On a
network that only reaches an internal npm proxy, point your own npm config
at it once; the repository carries no registry setting:

```bash
npm config set registry https://<internal-npm-proxy>/repository/npm-proxy/
```

Open `http://127.0.0.1:5173`. The UI keeps the current requirement id in the
route (`/requirements/:id`) and remembers the last id in browser storage only
as a convenience. In memory mode, restarting the API makes a remembered id
return a deliberate “Requirement not found” state. PostgreSQL mode keeps it.

The root route is the Slice 5B desktop worklist: server-backed search, repeated
workflow-status filters, sorting, pagination, status facets, and a ranked
attention band. Intake supports save-only or save-and-analyse, and the review
route uses Capture → Analyse → Clarify → Confirm → Breakdown. Breakdown is
unavailable until a human-confirmed analysis exists. Archivo Narrow and Lucide are
installed locally in `frontend/`; there is no runtime font or Claude export
dependency.

Slice 8A adds actor-aware ownership. The SPA loads `/identity/config` before
entering the workspace. OIDC mode uses Authorization Code + PKCE, session
storage, automatic token renewal, bearer injection, callback return-path
restoration, and provider logout. Requirement creation and draft creation bind
the current actor as owner; only owners can confirm analysis or manage
reviewers. The worklist can filter by owner or “Assigned to me,” and resumable
drafts are visible only to their owner. Existing durable rows with no identity
metadata remain visibly unowned and require an explicit self-claim.

Enhancement 8A.1 adds a public `/login` entry for OIDC deployments. It offers
configured Microsoft and administrator-provisioned password choices, preserves
safe internal return paths, and keeps fake mode account-free. Keycloak remains
outside the application boundary and owns credentials, recovery, throttling,
and Entra brokering. See `docs/operations/keycloak-login.md` for local and
staging setup.

Slice 8B makes clarification collaborative and auditable. Every new analysis
has an identity, provider-reported provenance, source Requirement version, and
an immutable round. Active questions have stable IDs, optimistic versions,
severity/blocker classification, team assignment, attributed drafts, and
attributed final answers. Resolving an answer (a `resolve_clarification_question`
job, ADR-0105) creates the next round; explicit re-analysis requires `force=true`. The Clarify view exposes
question cards, Ask someone, draft and resolve actions, conflict-safe local
text, and a complete round-history drill-down. PostgreSQL migration `007`
backfills pre-8B analyses without inventing unavailable actors or provenance.

Enhancement 8B.1 lets analysis start from only a title and business need.
Desired outcome is optional source evidence; when it is absent, `analysis-v3`
may propose one observable outcome plus clearly labelled rule or constraint
candidates. Only the Requirement Owner can accept, edit, or reject those
proposals. Confirmation requires every proposal to be decided, every blocker
question resolved, and one effective outcome. Downstream generation receives
only source-backed findings and accepted/edited intent. Proposal state and its
append-only decisions live in the existing versioned analysis JSON payload, so
this enhancement requires no relational database migration.

Enhancement 8B.2 batches stable clarification answers. Each question card keeps
its provider-free Save draft action, while one section action submits every
nonblank visible answer through a single durable
`resolve_clarification_questions` job. The application validates the complete
batch, calls the analyzer once, rechecks every optimistic version, and commits
all resolutions with one immutable analysis round. Unanswered questions remain
active, and existing blocker and authorization rules are unchanged. The review
workspace groups extracted evidence into Known facts, Business rules, and
Constraints, and active confirmation items into Assumptions, Open questions,
Ambiguities, and Potential dependencies.

Enhancement 8B.3 replaces exact-text question matching with explicit
`analysis-v4` reconciliation. Every remaining active AI question must be
retained, retired, or replaced, while human-authored questions are protected.
Replacements receive application-owned IDs and link to superseded predecessors;
classification and assignment carry forward but drafts remain archived on the
old question. Immutable rounds retain decision rationales and links, and the
application rechecks the complete active-question snapshot before committing
the analysis and question lifecycle changes atomically.

Workspace reads are scoped to their views: Epic/Features on Breakdown, question
suggestions and analysis rounds on Clarify/Confirm, and history on Revisions.
One requirement-scoped provider owns AI-job polling and transition refreshes;
historical completions do not replay artifact refreshes. Missing optional content
can still return an initial 404, while unrelated and hidden resources are not
fetched. See `docs/slices/fix-workspace-request-loading.md` for maintenance details
and validation evidence.

Source Documents are available from intake/capture and at `/documents`.
The standalone reviewed reference library is linked from that page at `/documents/library`.
It has independent upload/review/publication governance and document-only shared search; it is
integrated with owner-reviewed Requirement analysis applicability proposals. Exact search children
retain bounded owner-approved same-section context for interpretation without widening citations. See
`docs/slices/enhancement-document-knowledge.md` for delivered and outstanding scope and
`docs/operations/document-knowledge.md` for scanner/OCR provisioning and release requirements.
The library also offers an opt-in table-aware preview → approve/build → activate path. Completed
builds wait for their owner's activation; activation replaces the current publication and requires
reconciliation of prior citations. Legacy publications remain readable/searchable under their
original chunk policy. See ADR-0054 and `enhancement-table-corpus-builds.md`.
New PowerPoint library uploads expose each table row separately, with R/C cell positions and
explicit empty/merged-cell markers. Compare those markers and RTL reading order with the original;
they do not infer headers or business meaning. Excluded row wording is not copied to slide context.
Stored extractions remain unchanged; see ADR-0055 and `enhancement-presentation-tables.md`.
New DOCX uploads use `structured-docx-sections-v2` (retaining the ADR-0056 table behavior) for both library and Requirement attachments.
Rows show grid positions, spans and merge markers; nested tables are separate review blocks.
Headers/merged anchors are no longer copied into later rows. Older extracted text requires a new
upload and review to gain this behavior; rebuilding it alone retains its old text. See ADR-0056
and `enhancement-word-tables.md`.

New library CSV/TSV uploads use `structured-delimited-rows-v1`: every nonblank record, including
the first, is reviewable with positional R/C fields. No header wording is copied into other rows.
Quoted line breaks remain within logical records and formula-like strings are inert text. Existing
publications require a new upload/review to adopt it; see ADR-0057 and `enhancement-delimited-rows.md`.

New XLSX uploads use `structured-xlsx-sections-v2` (retaining ADR-0058 merges) in library and Requirement attachments. Merged
anchors/continuations show their range and anchor coordinate without repeating anchor wording.
Review against the original; malformed/overlapping/oversized merges fail explicitly. Existing
extractions remain unchanged; new upload/review is required. See ADR-0058 and
`enhancement-spreadsheet-merges.md`.

Supported uploads are PDF, DOCX, XLSX, and UTF-8 TXT. DOCX and XLSX versions
retain ordered evidence blocks, extraction warnings, and protected raster assets;
legacy PDF/TXT versions remain plain text. Hidden worksheets require explicit
selection. Inclusion in analysis is explicit; replacing an included version or
changing worksheet inclusion clears generated-artifact currency and requires
analysis reconciliation. Structured analysis plans context-safe packets, validates
every item citation, caches successful packet fragments, and performs bounded
hierarchical consolidation before persisting one failure-atomic analysis round.

Architecture impact is populated during Feature and Story generation using the packaged
`smb-source-reference-v1` catalogue. The explicit Map/Refresh architecture action remains
available for legacy or manually edited content and refuses stale inputs. The initial
source has no verified squad roster, so ownership is shown as Unassigned rather than inferred.

The Breakdown workspace links to `/requirements/:id/review`. Generation automatically saves
analysis uncertainty, architecture dependencies, cross-system warnings, staleness, and final
INVEST quality into one durable Remaining concerns review. Explicit Generate/Refresh remains
available for older or manually changed content and reuses current assessments. Flags
retain evidence type and source links; eligible warnings can be resolved with a recorded
decision, open questions reuse the clarification loop, and source-action flags cannot be
dismissed. A saved review remains readable but read-only when its evidence fingerprint
is stale.

Slice 11 adds neutral export to Revision History. The current Requirement Owner or an
assigned reviewer can download any exact, formally approved immutable revision as
deterministic JSON or Excel. The package preserves the Epic, Features, Stories,
Given/When/Then criteria, provenance, architecture tags, and final-approval manifest;
export never regenerates content, stores a copy, or publishes to Azure DevOps.

`VITE_API_BASE` defaults to `/api`. Both the Vite development and preview
servers proxy that prefix to `http://127.0.0.1:8000` and strip it before the
request reaches FastAPI. Override the variable only when another deployment
topology supplies a different API base URL.

Browser smoke tests default to API port `8000` and UI port `4173`. When either
port is already in use, set `SMOKE_API_PORT` and `SMOKE_UI_PORT`; Playwright and
the Vite proxy use the same API-port override so the run remains isolated.

The combined PowerShell startup writes timestamped API/UI stdout and stderr to
the ignored `logs/` directory. Mapped 5xx errors are logged with their exception
chain at the API boundary without deliberately logging requirement content.
The explicit `-DebugTrace` switch additionally creates the single sensitive
`logs/debug.log` trace described above; it does not replace process stdout/stderr.

Frontend validation:

```bash
cd frontend
npm run api:check
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:smoke
```

The smoke test starts the fake-provider API and the built preview server. Run
`npm run build` before `npm run test:smoke`; the CI smoke job does this in its
own workspace because CI jobs do not share build output.

---

## 7. Quality Commands

Run before finishing a coding task:

```bash
pytest
ruff check .
ruff format --check .
mypy src tests
lint-imports
```

To apply formatting:

```bash
ruff format .
```

The coding agent must never claim a gate passed unless it ran the command successfully.

All five gates also run in CI on every push and pull request
(`.github/workflows/ci.yml`). A slice is not done while any of them is red.

---

## 8. Test Strategy

### Domain tests
Pure, fast, no I/O.

### Application tests
Use:
- fakes,
- in-memory repositories,
- deterministic clocks/IDs when needed,
- fake LLM ports.

### Infrastructure tests
Test adapter behavior/contracts separately.

### API tests
Exercise transport mapping and status/error behavior.

### Live external tests
Keep opt-in and excluded from normal unit test runs.

---

## 9. Slice Execution Workflow

For each new slice:

1. Read `AGENTS.md`.
2. Read the slice in `ROADMAP.md`, **field by field**. Domain, Application,
   Ports, Adapters, API, UI and Tests are all scope. Anything you plan to leave
   out goes to the user before you start, per `AGENTS.md` §15.1 — never by
   writing "None." in the spec.
3. Record an ADR in `docs/architecture/` if the slice makes a structural
   decision (see that directory's README for when one is required).
4. Create/update `docs/slices/slice-XX-<name>.md` with:
   - objective,
   - in scope,
   - out of scope,
   - domain changes,
   - use cases,
   - ports/adapters,
   - API/UI changes,
   - tests,
   - acceptance criteria.
5. Inspect existing implementation.
6. Implement the smallest end-to-end path.
7. Run quality gates locally, then confirm CI is green.
8. Mark the slice spec with completion evidence.
9. Do not implement the next slice in the same task unless explicitly requested.

Suggested branch naming:

```text
slice/01-requirement-intake
slice/02-requirement-analysis
fix/<short-description>
refactor/<short-description>
```

---

## 10. Active Slice Spec Template

Create files like `docs/slices/slice-01-requirement-intake.md`.

Template:

```markdown
# Slice XX — Name

## Objective
...

## User Outcome
...

## In Scope
- ...

## Out of Scope
- ...

## Domain
- ...

## Application Use Cases
- ...

## Ports
- ...

## Adapters
- ...

## API
- ...

## UI
- ...
<!-- Not optional. If the ROADMAP entry for this slice names a UI, it is scope.
     "None." is only valid here when the roadmap entry itself names no UI, or
     when an omission was agreed with the user in advance and is recorded under
     a "Dropped from this slice" heading below and in AGENTS.md section 19. -->

## Business Rules
- ...

## Tests
- ...

## Acceptance Criteria
- [ ] ...

## Validation Evidence
- `pytest` —
- `ruff check .` —
- `ruff format --check .` —
- `mypy src tests` —
- `lint-imports` —

## Dropped from this slice
<!-- Anything in the ROADMAP entry not delivered, why, who agreed, and where it
     is carried to. Omit this heading only when nothing was dropped. -->
- ...

## Deferred
- ...
```

---

## 11. Clean Architecture Boundary Map

```text
┌────────────────────────────────────┐
│ Interfaces                         │
│ FastAPI / future Web UI boundary   │
└─────────────────┬──────────────────┘
                  │
                  ▼
┌────────────────────────────────────┐
│ Application                        │
│ Use cases / ports / orchestration  │
└─────────────────┬──────────────────┘
                  │
                  ▼
┌────────────────────────────────────┐
│ Domain                             │
│ Entities / VOs / invariants        │
└────────────────────────────────────┘

Infrastructure adapters depend inward on
Application/Domain ports and models.
```

This layering holds inside each bounded context (ADR-0103). Between contexts, a context imports
only the contexts upstream of it:

```text
workflows → reporting → governance → breakdown → knowledge → analysis
  → references → requirements → {jobs | identity} → shared_kernel
```

`lint-imports` enforces the order (`contexts_layered` and one "depends only upstream" contract per
context). An upstream context that needs a downstream effect publishes a domain event or calls a
port it owns. `docs/architecture/context-map.md` places every module.

The object graph is wired in exactly one place,
`interfaces/api/container.py`, from `Settings`. Nothing is constructed at
import time: `main.py` builds the container during startup, and tests build
their own per test. Route handlers receive use cases through
`interfaces/api/dependencies.py` and never name a concrete adapter.

Domain and application errors are mapped to HTTP status codes once, in
`interfaces/api/error_handlers.py`. Routes do not translate errors.

Forbidden examples:

```text
domain -> fastapi
domain -> sqlalchemy
application -> openai SDK
application -> azure devops SDK
route -> SQL query containing business rules
React component -> provider-specific LLM payload
```

---

## 12. Suggested API Evolution

Do not implement all endpoints now. Add them only with their slice.

Likely evolution:

```text
GET    /health

POST   /requirements
GET    /requirements/{id}
PUT    /requirements/{id}

POST   /requirements/{id}/ai-jobs          (analysis, clarification, generation, review: ADR-0105)
GET    /requirements/{id}/ai-jobs/{job_id}

GET    /requirements/{id}/analysis

GET    /requirements/{id}/epic
PUT    /requirements/{id}/epic
POST   /requirements/{id}/epic/approval

GET    /requirements/{id}/features
PUT    /requirements/{id}/features/{feature_id}
POST   /requirements/{id}/features/{feature_id}/approval
...

POST   /breakdowns/{id}/submit-review
POST   /breakdowns/{id}/approve

GET    /activity
GET    /reports/operational
GET    /saved-views
POST   /saved-views
PUT    /saved-views/{view_id}
DELETE /saved-views/{view_id}

POST   /breakdowns/{id}/export

POST   /breakdowns/{id}/publish/ado
```

Endpoint naming may evolve as the resource model becomes clearer.

---

## 13. Frontend Workspace

Introduce frontend code when a slice's `ROADMAP.md` entry names a UI.

> This section previously read "when the roadmap reaches UI work that justifies
> it", which was read as *some future UI slice* while `ROADMAP.md` names a UI
> in almost every slice. Slices 01–04 each shipped without one on the strength
> of that reading. A slice's UI line is scope; see `AGENTS.md` §15.1 for the
> only route to not building it.

Structure:

```text
frontend/
├── package.json
├── src/
│   ├── app/
│   ├── features/
│   │   ├── requirements/
│   │   ├── analysis/
│   │   ├── backlog/
│   │   └── review/
│   ├── components/
│   └── api/
└── tests/
```

Preferred baseline:
- TypeScript,
- React,
- Vite.

UI principles:
- hierarchy tree for Epic/Feature/Story,
- detail editor,
- visible AI assumptions/open questions,
- visible approval state,
- preserve user edits,
- regenerate only selected scope,
- no direct LLM calls from browser,
- no ADO secrets in browser.

---

## 14. LLM Adapter Workspace

When Slice 2 begins, create an adapter structure only then, for example:

```text
infrastructure/
└── llm/
    ├── prompts/
    ├── schemas/
    └── <provider>_requirement_analyzer.py
```

Keep provider-independent interfaces in Application.

Prompts should be versionable and testable.

Test fixtures should cover:
- valid structured output,
- missing fields,
- malformed output,
- unsupported assumptions,
- timeout/provider errors.

---

## 15. Architecture Mapping and the Knowledge Service

The architecture catalogue, its drafts, documents and published releases moved to
[knowledge-portal](https://github.com/mohamhossam/knowledge-portal) with the platform split
(ADR-0099); curate them there. Requirement work keeps:

- **Mapping.** Features and Stories are mapped against the catalogue release in service, which
  the knowledge service matches (`POST /internal/architecture/match`). Mapping jobs run in this
  repository's `requirement_mapping_jobs` queue. The worker leases them, heartbeats during model
  calls and records failure categories; failed jobs need an explicit retry. Publishing a new
  release does not remap existing Features or Stories: reviewers refresh their mapping and review.
- **The read-only views.** Cited library passages and architecture evidence open read-only here,
  fetched from the knowledge service. Curation stays in the knowledge portal, open to
  `knowledge_admin` only.
- **The roles.** Any member of a Requirement may map its architecture. Assign
  `architecture_maintainer` to let someone cancel and retry other people's mapping jobs
  (ADR-0104 and its 2026-10-09 amendment).

Mapping uses the configured models (`LLM_PROVIDER` or the model profiles: the `knowledge` task and
the embedding), as ADR-0082 records. `LLM_PROVIDER=fake` and memory persistence remain the
offline path. Production requires PostgreSQL persistence; fake identity is rejected at startup.

By default the API process also runs every background worker (AI jobs, attachment ingestion,
requirement indexing, the knowledge event feed and, with any provider but `fake`, architecture
mapping jobs). To scale HTTP and workers independently, run API replicas with
`API_BACKGROUND_WORKERS=false` (PostgreSQL required) and one or more worker processes:

```bash
python -m smb_requirement_agent.interfaces.worker
```

The worker process exits non-zero if a worker becomes unhealthy, so run it under
a supervisor that restarts it. Size `DATABASE_POOL_MAX_SIZE` per process for its
concurrent requests plus workers; every API and worker process has its own pool.
Pooled sessions run under `DATABASE_STATEMENT_TIMEOUT_SECONDS` (30),
`DATABASE_LOCK_TIMEOUT_SECONDS` (5) and `DATABASE_IDLE_TRANSACTION_TIMEOUT_SECONDS` (60).
A statement or lock wait past its limit answers 503 `database_busy`. Size PostgreSQL's
`POSTGRES_MAX_CONNECTIONS` for every pool (`docs/operations/deployment.md`, "Database
connections and limits").

Production identity uses `APP_ENV=production`, `IDENTITY_PROVIDER=oidc`,
`OIDC_ISSUER_URL`, `OIDC_AUDIENCE`, `OIDC_CLIENT_ID`, and `OIDC_ROLES_CLAIM`.
Register `${origin}/auth/callback` as the browser redirect URI and configure
the delegated API scope with `OIDC_SCOPES`; the browser reads public identity
configuration from `/identity/config` at runtime. All application data endpoints
require a validated bearer token in OIDC mode. Health stays public.

The knowledge service's own build, retrieval evaluation and release qualification are
documented in knowledge-portal.

---

## 16. Persistence Workspace

Before Slice 10:
- prefer in-memory adapters unless durable state is truly required.

At Slice 10:
- introduce PostgreSQL and migration tooling behind repository adapters.
- preserve domain/application tests that do not require the database.

### Clarification suggestion scheduling

Analysis persistence and human-authored question creation enqueue durable answer-suggestion jobs
inside the same transaction. Workers generate later so provider latency and failures never block
the saved analysis round. Current analysis facts, rules, and constraints are passed separately from
trusted cross-Requirement knowledge; they are not added to the trusted index. The browser polls the
existing AI-job feed, progressively refreshes current suggestion sets, and retains manual refresh
for retry or changed evidence.

---

## 17. ADO Workspace

Do not add ADO dependencies before Slice 12.

Expected location later:

```text
infrastructure/
└── azure_devops/
    ├── client.py
    ├── mapper.py
    ├── publisher.py
    └── config.py
```

Application sees only the publication port and neutral result models.

ADO writes must support explicit preview/approval flow.

---

## 18. Coding Agent Usage

### Codex
Keep `AGENTS.md` at repository root. Give Codex tasks scoped like a good issue:
- exact slice,
- objective,
- relevant files,
- acceptance criteria,
- commands to run.

Example:

```text
Implement Slice 1 — Requirement Intake only.

Read AGENTS.md, ROADMAP.md, and WORKSPACE.md first.
Create the active slice spec.
Do not add AI, database, ADO, or Feature/Story models.
Run all quality gates and report results.
```

### Antigravity
The repository contains a workspace custom agent:

```text
.agents/agents/smb-requirement-engineer/agent.md
```

Use it for implementation/review work so Antigravity receives the same project constraints.

The root `AGENTS.md` remains the shared engineering constitution.

---

## 19. Recommended First Coding Task

Start with:

```text
Slice 0 — Clean Architecture Workspace
```

Then:

```text
Slice 1 — Requirement Intake
```

Do not start directly with the big AI prompt or ADO integration.

The product becomes safer and easier to evolve when the core requirement/backlog model is proven before external integrations are added.

### Generation-time quality and risks

Story assessment includes source facts, confirmed decisions and unresolved evidence. Its cache
is bound to those inputs as well as Story content. Existing assessments made without that context
are stale and require explicit reassessment. Feature/Story prompts are `feature-v5` / `story-v5`;
the grounded semantic rubric is `story-quality-v3`. Correction tasks distinguish a failed AI draft
from source requirements, request discovery when Estimable fails, and reject a refused split for
a sole oversized candidate when the operation allows multiple Stories. Provider schemas require
at least one complete acceptance criterion per Story.

Feature and Story generation now prepare architecture/uncertainty guidance, assess unsaved candidates,
and refine once when needed before saving the final draft and its evidence. Single regeneration and
merge preserve their cardinality. The Remaining concerns review reuses current quality snapshots;
opening the review or Story list never launches evaluation. Edited or legacy Stories without current
quality offer explicit reassessment. Checked split/merge previews retain their mappings and assessments,
and changed generation evidence requires a new preview. See ADR-0041 and the generation-quality spec.


### Configured model integration

`LLM_CONFIG_PATH=config/llm.yaml` selects named task profiles at backend startup. Credentials stay
in environment variables such as `GEMINI_API_KEY`. Direct Gemini and compatible service examples,
local check/live smoke/rebuild/rollback commands and the worker-drain switch procedure are documented
in `docs/llm-configuration.md` (ADR-0043). Without the path, existing provider settings remain available.
Profile search uses isolated embedding generations; unidentified legacy vectors are preserved and
never compared against the configured generation. Changing supported models requires YAML/env changes
and restart; different protocols require a transport adapter in the existing composition root.

New TXT/Markdown uploads use `structured-text-sections-v1`: headings retain their wording only in
their own review block; section paths use neutral heading line positions. Existing line review,
warnings, publication and exact citations expose this behavior. New upload/review is required for
existing documents; see ADR-0059 and `enhancement-text-sections.md`.

New DOCX uploads now use `structured-docx-sections-v2`, retaining ADR-0056 table extraction while
giving body prose neutral paragraph locations and heading paths. Correcting prose or excluding
a heading no longer retains original wording in metadata. Existing image-readiness decisions remain
unchanged. See ADR-0060 and `enhancement-word-prose.md`; existing publications need new upload/review.

New XLSX uploads use `structured-xlsx-sections-v2`, retaining ADR-0058 merge behavior. Worksheet
names are independently reviewable headings; row/image/chart paths use neutral workbook tab
positions. New hidden-sheet selection uses `Worksheet N`; legacy selections stay unchanged.
See ADR-0061 and `enhancement-worksheet-names.md`. New upload/review is required for adoption.


### Dedicated Requirement indexing (ADR-0062)

The API lifespan starts an independent Requirement index worker. Screening and suggestion jobs wait
in their durable queue until the configured Requirement corpus is current; unrelated jobs continue.
The Knowledge page shows preparation progress and member retry. Apply additive migration 023 through
the normal migration runner. Existing clean Requirement indexes adopt bounded field children on a
source change or explicit configured-generation rebuild; no bulk source rewrite is automatic.

Live, opt-in synthetic qualification commands (never part of pytest):

```powershell
.venv/Scripts/python.exe -m tests.chunk_token_fixtures  # Requirement samples; library samples are knowledge-portal's
.venv/Scripts/python.exe -m smb_requirement_agent.interfaces.cli.llm qualify-tokens --config config/llm.yaml --samples docs/evaluation/chunk-token-fixtures.json --input-limit 2048
```

The first command is offline. The latter two use configured credentials and live embedding endpoints;
only synthetic fixtures are sent. Token measurements remain separate from runtime UTF-8 budget units.
The model-rollout harness uses isolated memory storage and never changes saved application settings.
See `docs/slices/enhancement-chunking-indexing.md` for actual local evidence and production limits.

### Library ownership and dependencies (ADR-0063)

Moved to knowledge-portal with the platform split (ADR-0099): ownership handover and the
dependencies view are its Ownership and Who cites it pages. Requirement work answers the
dependents query over its internal API (`/internal/references/{id}/dependents`). The record of
the original design follows.

The document workspace exposes Manage ownership and View dependencies to the current owner.
Handover selects a known user, records a rationale and requires acknowledgement of losing private
access. The new owner receives every private file/review/publication control; original upload and
approval actors remain unchanged. Historical handovers stay available to the current owner.
Submission keys remain scoped to the original uploader, and replaying an old upload after handover
cannot recover private access. No migration is required for existing library JSON.

Dependencies list recorded reference proposals in current analyses and immutable earlier rounds,
including rejected proposals and withdrawn/replaced publications. Only the document owner's
Requirement memberships appear, so an empty view is not evidence of zero workspace dependencies.
The existing source-reconciliation gates still govern generation and approval; this view performs
no rewrite or external publication. See `docs/slices/enhancement-library-governance.md`.

### Search and AI grounding (ADR-0064)

Unified search combines published library documents, which it asks the knowledge service for,
with Requirements the current actor owns/reviews. `POST /knowledge/search/unified` returns labelled,
bounded, source-balanced evidence; the original document-only endpoint remains compatible.
Unified search waits for the dedicated Requirement index to be current and explains retry through
the existing mapped index error. No vector distances are compared across index generations.

Clarification suggestions can cite exact published passages. They retain model/prompt provenance
and publication identities; withdrawal/replacement prevents saving or selecting stale suggestions.
Submitting an answer remains an attributed human decision, and applicability proposals retain
their separate owner rationale workflow. Suggestion-derived answers are excluded from the shared
independent corpus, while remaining available as the subject's own screening context.
Pending reference conflicts appear in Knowledge review with a route back to owner decisions;
outdated applicability citations remain visible and guard confirmation/generation.

Run `.venv/Scripts/python.exe scripts/evaluate_grounding.py docs/evaluation/grounding-synthetic.json`
for a synthetic arithmetic check. Use actual human judgments following
`docs/evaluation/grounding-rubric.md` for semantic qualification; no provider quality claim follows
from the synthetic fixture. See `docs/slices/enhancement-search-ai-grounding.md` for validation.

### Document ingestion completion (ADR-0065)

Requirement and draft browser attachments now submit durable 202 ingestion records, poll status,
and offer retry/cancel. The document worker scans/extracts then atomically attaches the result;
existing synchronous upload endpoints remain supported. In knowledge-portal, library owners can
compare source raster previews and resolve only block-scoped warnings through saved exclusions
with reasons.

`DOCUMENT_OFFICE_PREVIEW_EXECUTABLE` optionally names an installed local LibreOffice executable.
When unset, slide previews explain their unavailability and suggest a PDF export; PDF pages and
image regions use the existing bounded raster renderer. Configured Office previews reject external
links and active/embedded objects, use a private profile and 45-second conversion deadline, and
never send source files to a remote service. Qualify the installed renderer before production.

See `docs/slices/enhancement-ingestion-completion.md` for checks and deployment limits.

### Source lineage and impact review (ADR-0066)

Apply migration 024 and run `python -m smb_requirement_agent.interfaces.maintenance` in a coordinated
maintenance window before starting the upgraded API. Readiness requires migration and backfill;
startup never scans/rebuilds histories. Review source impact in a document or Requirement workspace.
The Requirement owner records retain/revise decisions for exact content and publication state.

Recorded document-derived chunks preserve origins for search/dependency inspection, but screening
and suggestions do not treat them as independent Requirement corroboration. Legacy unrecorded
origins remain unknown. See `docs/slices/enhancement-source-lineage.md` for validation and scope.
