# Requirement Portal

> **Part of a three-repository platform** (ADR-0098): `requirement-portal` (this repository),
> [`knowledge-portal`](https://github.com/mohamhossam/knowledge-portal) and
> [`platform-kernel`](https://github.com/mohamhossam/platform-kernel). Imported fresh from
> [`smb-ai-requirement-agent@d5cfb57`](https://github.com/mohamhossam/smb-ai-requirement-agent/commit/d5cfb57),
> which stays maintained in parallel; see `UPSTREAM.md`. The split is in progress: until it
> completes, this repository still contains the library and catalogue code it inherited.

> Production-readiness remediation is merged into `main`; target-environment release qualification
> is still open (see `ROADMAP.md`). Follow `docs/slices/production-readiness-remediation.md` and
> `docs/operations/production-readiness-maintenance.md` before operating migrations `013`–`015`.

An AI-assisted Requirement Engineering and backlog-decomposition application
for a Telecom SMB value stream. It turns raw business requirements into
reviewable, traceable delivery artifacts while keeping uncertainty explicit and
human approval separate from AI generation.

The target workflow is:

`Requirement → Analysis → Epic → Features → User Stories → Acceptance Criteria → Quality/Architecture Review → Human Approval → Export → Azure DevOps`

New to the project? Follow the standalone [Application Start Guide](START_GUIDE.md)
for a first run on Windows, macOS or Linux: in Docker with nothing else
installed, as a Docker deployment on a server, or from source with the
launchers. It covers the expected output, provider setup, shutdown, and startup
troubleshooting.

## Current status

`ROADMAP.md` holds the verified status ledger. Slices 0–11 (including 4A, 5A–5D, 8A–8C
and 10A), Slice 14 (architecture knowledge administration), the listed enhancements,
the reviewed document library, and production-readiness remediation are implemented and
merged into `main`. The review UI has been redesigned in phases 0–6 (`docs/ux-plan.md`,
`docs/design-system.md`, `DESIGN.md`). Target-environment release qualification remains
open. The running application currently supports:

- a Requirements worklist with workflow counters, search, sort, saved views and a
  **Needs attention** entry point, plus Activity and operational Reports pages;
- Requirement intake from a written business need and/or attached PDF, DOCX, XLSX
  and TXT files, with resumable drafts;
- analysis of known facts, constraints, business rules, assumptions, open
  questions, ambiguities and potential dependencies, with cited sources;
- an iterative answer → re-analysis loop with assignable questions, grounded
  answer suggestions and Requirement-change proposals, ending in explicit
  Requirement Owner confirmation only after all unresolved items are cleared;
- Requirement Knowledge screening for possible duplicates and contradictions;
- generating, editing, regenerating and approving an Epic, its Features, and User
  Stories with structured Given/When/Then acceptance criteria;
- INVEST quality review, Story split/merge proposals and architecture mapping;
- ownership, reviewer assignment, provenance and downstream staleness;
- submission, per-Story review decisions and final approval;
- immutable revision history with comparison, and deterministic JSON and Excel
  export of exactly the approved revision;
- a governed shared knowledge library and architecture-knowledge releases feeding
  unified, cited search;
- durable model-backed background jobs, notifications and activity history;
- deterministic offline operation through the fake LLM adapter, plus OpenAI,
  OpenRouter, local OpenAI-compatible servers and YAML model profiles (Gemini by
  default);
- in-memory or durable PostgreSQL + pgvector storage, and fake or OIDC
  (Keycloak/Entra) identity.

Azure DevOps publication and external work-item mapping (Slices 12–13) remain planned.
Generated content is always a review candidate; it is never automatically published.

## Prerequisites

- Python 3.12 or newer
- Node.js 22 with npm
- one of the launcher shells: PowerShell 5.1/7 (`start.ps1`), Command Prompt
  (`start.cmd`), or Bash with `curl` on macOS, Linux or WSL (`start.sh`)
- an OpenAI, OpenRouter or Gemini API key only when using that provider
- an OpenAI-compatible local model server only when using the local provider
- Docker Desktop (or Docker Engine) only when using durable PostgreSQL mode or
  running the whole stack in containers
- ClamAV only when uploading to the shared knowledge library

The application needs no database, provider account or `.env` file in the
default memory/fake mode. Set `PERSISTENCE_PROVIDER=postgres` for durable state.

## Quick start

From the repository root, run the launcher for your shell once with the setup
option:

```powershell
# PowerShell
.\start.ps1 -Setup
```

```bat
:: Command Prompt
start.cmd -Setup
```

```bash
# macOS, Linux or WSL
./start.sh --setup
```

This command:

1. creates `.venv` when it does not exist;
2. installs the backend, development, and locked frontend dependencies;
3. validates the model configuration without making paid requests;
4. checks that ports `8000` and `5173` are free;
5. for PostgreSQL mode, starts the local Compose database if needed and applies
   pending migrations;
6. starts FastAPI on `http://127.0.0.1:8000` and waits for its health check;
7. starts the Vite review UI on `http://127.0.0.1:5173`;
8. monitors both processes and stops both when you press `Ctrl+C`
   (`start.cmd` instead runs each server in its own window).

Open these addresses after startup:

| Address | Purpose |
|---|---|
| `http://127.0.0.1:5173` | Review UI |
| `http://127.0.0.1:8000/docs` | Interactive OpenAPI documentation |
| `http://127.0.0.1:8000/health` | API health check |

After the initial setup, start without the setup option: `.\start.ps1`,
`start.cmd` or `./start.sh`.

The default provider is `fake`, so the complete implemented workflow works
without credentials or network calls.

To run everything in Docker instead (no local Python or Node.js), copy
`deploy/demo.env.example` to `deploy/production.env` and set
`OPENROUTER_API_KEY` in it (the Docker demo uses OpenRouter and PostgreSQL),
put `POSTGRES_PASSWORD=<your password>` in `deploy/.env` (both are
git-ignored), then:

```bash
docker compose -f deploy/compose.production.yaml build
docker compose -f deploy/compose.production.yaml run --rm maintenance
docker compose -f deploy/compose.production.yaml up -d
```

Open `http://localhost:8080`. The [Application Start Guide](START_GUIDE.md)
sections "Run with Docker" and "Deploy to a server with Docker" cover everyday
commands, real providers, server deployment and Docker troubleshooting.

### Startup script options

| Purpose | PowerShell / Command Prompt | Bash |
|---|---|---|
| Install or refresh all dependencies, then start | `-Setup` | `--setup` |
| Check prerequisites, configuration and database readiness only | `-CheckOnly` | `--check-only` |
| Choose the provider: `fake` (default), `local`, `openai`, `openrouter` | `-Provider openai` | `--provider openai` |
| Write one detailed backend/LLM debug trace to `logs/debug.log` | `-DebugTrace` | `--debug-trace` |

```powershell
.\start.ps1 -Setup -Provider openai
.\start.ps1 -Provider openrouter
.\start.ps1 -Provider local -DebugTrace

# One-time Ollama setup for the deterministic 16K vision model alias
.\scripts\setup-local-ollama-model.cmd
```

```bash
./start.sh --provider local --debug-trace
```

The three launchers are independent implementations of the same sequence:
`start.ps1` for PowerShell, `start.sh` for Bash, and `start.cmd`, which calls
the standalone Command Prompt script `start.bat`. `start.ps1` and `start.sh`
write timestamped logs under `logs/`; `start.cmd` shows server output in its
two windows.

`-Provider openai` requires `OPENAI_API_KEY` in the process environment or the
root `.env` file. `-Provider openrouter` requires `OPENROUTER_API_KEY` and uses
`google/gemma-4-31b-it:free` by default. `-Provider local` requires
`LOCAL_LLM_MODEL` and `LOCAL_EMBEDDING_MODEL`; it defaults to the LM Studio API
at `http://127.0.0.1:1234/v1`. Configuration is validated before either server
starts.

To use the YAML model profiles in `config/llm.yaml` (Google Gemini by default),
set `LLM_CONFIG_PATH=config/llm.yaml` and the referenced credential such as
`GEMINI_API_KEY` in `.env`, then start **without** a provider option; the
launchers reject a provider option while a profile path is selected. See
`docs/llm-configuration.md`.

OpenRouter's free-model limits are intentionally suitable only for development
and demos; there is no paid chat-model fallback. Knowledge embeddings use
`openai/text-embedding-3-small` at 768 dimensions and may incur OpenRouter
charges. See the [model details](https://openrouter.ai/google/gemma-4-31b-it%3Afree/pricing)
and [free-tier limits](https://openrouter.ai/docs/faq).

The launchers intentionally use fixed ports `8000` and `5173`, matching the
Vite proxy configuration, and stop before startup when either port is taken.
They run the API without auto-reload so they can reliably stop both processes.
Use the manual development commands below when backend reload is preferred.

## Manual setup and startup

### PowerShell

Create the backend environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Install the frontend in the repository's `frontend` directory:

```powershell
Set-Location frontend
npm ci
Set-Location ..
```

Start the backend in terminal one:

```powershell
$env:LLM_PROVIDER = "fake"
.\.venv\Scripts\python.exe -m uvicorn smb_requirement_agent.interfaces.api.main:app --reload
```

Start the frontend in terminal two:

```powershell
Set-Location frontend
npm run dev
```

### Bash, WSL, Linux, or macOS

Create the backend environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

Install the frontend:

```bash
cd frontend
npm ci
cd ..
```

Start the backend in terminal one:

```bash
source .venv/bin/activate
LLM_PROVIDER=fake python -m uvicorn smb_requirement_agent.interfaces.api.main:app --reload
```

Start the frontend in terminal two:

```bash
cd frontend
npm run dev
```

The Vite development server proxies `/api` to
`http://127.0.0.1:8000` and removes the `/api` prefix before forwarding the
request. Local development therefore does not require browser CORS changes.

## Environment configuration

Copy the example configuration before adding local settings:

```powershell
Copy-Item .env.example .env
```

On Bash:

```bash
cp .env.example .env
```

`.env` is ignored by Git and must never be committed.

| Variable | Required | Description |
|---|---:|---|
| `LLM_PROVIDER` | No | `fake`, `local`, `openrouter`, or `openai`. The launchers set it from their provider option (default `fake`), overriding `.env`; without a launcher it defaults to `openai`. |
| `LLM_CONFIG_PATH` | No | Selects YAML model profiles (for example `config/llm.yaml`) instead of `LLM_PROVIDER`. Start the launcher without a provider option. See `docs/llm-configuration.md`. |
| `GEMINI_API_KEY`, `COMPATIBLE_API_KEY` | Profiles only | Credentials referenced by the selected profiles' `api_key_env`. |
| `OPENAI_API_KEY` | OpenAI only | Provider credential. Startup fails immediately when OpenAI is selected without it. |
| `OPENAI_MODEL` | No | OpenAI model name. Defaults to `gpt-4o`. |
| `OPENAI_EMBEDDING_MODEL` | No | OpenAI embedding model used for Requirement knowledge. Defaults to `text-embedding-3-small`; the adapter requires 768 output dimensions. |
| `OPENROUTER_API_KEY` | OpenRouter only | Bearer credential. Startup fails immediately when OpenRouter is selected without it; it is redacted from debug traces. |
| `OPENROUTER_MODEL` | No | OpenRouter chat model. Defaults to the development/demo model `google/gemma-4-31b-it:free`. |
| `OPENROUTER_EMBEDDING_MODEL` | No | OpenRouter knowledge embedding model. Defaults to `openai/text-embedding-3-small` with 768 requested dimensions; embeddings can be billed separately. |
| `OPENROUTER_BASE_URL` | No | HTTPS OpenRouter API root. Defaults to `https://openrouter.ai/api/v1`. |
| `OPENROUTER_TIMEOUT_SECONDS` | No | Positive request timeout. Defaults to `120`. |
| `OPENROUTER_MAX_OUTPUT_TOKENS` | No | Positive chat output limit. Defaults to `8192`. |
| `OPENROUTER_DATA_COLLECTION` | No | Provider-routing privacy policy. Defaults to and should remain `deny`. |
| `LOCAL_LLM_MODEL` | Local only | Model identifier loaded by the local server. For Ollama, run `scripts\setup-local-ollama-model.cmd` and use `smb-qwen3-vl:8b-16k`. |
| `DEBUG_TRACE_ENABLED` | No | `true` writes an opt-in, sensitive JSONL diagnostic trace. Defaults to `false`. |
| `DEBUG_TRACE_PATH` | Debug trace only | Single trace file. Defaults to `logs/debug.log`. |
| `LOCAL_EMBEDDING_MODEL` | Local only | Embedding model exposed by the local server. It must produce 768 dimensions. |
| `LOCAL_LLM_BASE_URL` | No | OpenAI-compatible API root. Defaults to `http://127.0.0.1:1234/v1`; use `http://127.0.0.1:11434/v1` for Ollama. |
| `LOCAL_LLM_TIMEOUT_SECONDS` | No | Local generation timeout. Defaults to `120`; use `300` for the supported Qwen vision alias and structured BRDs. |
| `LOCAL_LLM_REASONING_EFFORT` | No | Optional local thinking control: `none`, `low`, `medium`, or `high`. Use `none` for structured extraction with thinking models such as Qwen. |
| `LOCAL_LLM_CONTEXT_WINDOW_TOKENS`, `LOCAL_LLM_MAX_OUTPUT_TOKENS` | No | Context budget for the local model; the output reserve must be smaller than the window. |
| `LOCAL_LLM_VISION_ENABLED` | No | `true` only when the local model accepts image input. Defaults to `false`. |
| `PERSISTENCE_PROVIDER` | No | `memory` (default; data is lost on API restart) or `postgres`. |
| `DATABASE_URL` | PostgreSQL only | Connection URL. A `localhost`/`127.0.0.1` URL lets the launchers start and migrate the Compose database. |
| `IDENTITY_PROVIDER` | No | `fake` (default; switchable development personas) or `oidc` with the `OIDC_*` variables. See `docs/operations/keycloak-login.md`. |
| `LIBRARY_SCAN_MODE` | No | `clamav` (default) scans shared-library uploads at `LIBRARY_SCANNER_HOST`:`LIBRARY_SCANNER_PORT`. `offline` is a development-only adapter allowed only with memory persistence and fake identity. |
| `API_BACKGROUND_WORKERS` | No | `true` (default) runs background AI jobs inside the API. `false` requires PostgreSQL and a separate `python -m smb_requirement_agent.interfaces.worker`. |
| `APP_ENV` | No | `development` (default), `test`, or `production`. Production requires PostgreSQL and refuses fake identity and fake knowledge. |
| `VITE_API_BASE` | No | Browser API prefix. Defaults to `/api`; change it only for a different deployment topology. An absolute URL's origin is added to the built app's Content-Security-Policy `connect-src`. |
| `CSP_IDENTITY_ORIGINS` | OIDC builds only | Build-time, space-separated OIDC issuer origins (for example `https://login.example.com`). The built app's Content-Security-Policy admits them for token calls, silent-renewal frames and sign-in forms. Leave unset for fake identity. |

`.env.example` documents the remaining settings: document extraction limits,
the PostgreSQL pool, background-job timing, provider rate limiting, knowledge
embeddings, logging and metrics. Azure DevOps variables remain future
placeholders until their roadmap slice.

Environment variables are resolved centrally by
`infrastructure/config/settings.py`. Domain objects, use cases, routes, and
provider adapters do not read the environment directly.

## Using the review workflow

The UI opens on **Requirements**, the worklist; the top bar also links to
**Documents**, **Activity** and **Reports**. With fake identity, the
**Development persona** selector in the top bar switches between test users such
as the owner and a reviewer. Each Requirement moves through six steps in the
workflow rail: **Source → Clarify → Knowledge → Confirm → Backlog → Review &
approve**.

1. From the worklist, use the workflow counters, search, sort or the **Needs
   attention** entry point to resume work, or select **New requirement**.
2. **Source:** enter a **Requirement title** and the **Business need**, attach
   files that describe it, or both, then select **Save and analyse** (or
   **Save draft and exit** to finish later). A failed analysis never deletes the
   saved Requirement and can be retried.
3. **Clarify:** answer open questions in **Your answer**, optionally starting
   from a suggestion grounded in trusted Requirement evidence, then select
   **Send N answers and re-analyse**. You can submit a partial set; unanswered
   items remain open and saved answers appear as human-provided clarifications.
   Questions can be assigned to reviewers. Accept or edit each proposed
   Requirement change.
4. **Knowledge:** resolve possible duplicates and contradictions with other
   Requirements.
5. **Confirm:** once every finding and clarification is resolved, select
   **Confirm this analysis**. The Backlog remains locked until this explicit
   human confirmation is recorded.
6. **Backlog:** select **Generate Epic**, edit it if necessary, and approve it.
   Select **Decompose into Features**, then review, edit and approve each Feature
   independently. Select **Generate Stories** to produce Stories with
   Given/When/Then acceptance criteria and an INVEST quality review; split,
   merge, regenerate or map architecture where needed.
7. **Review & approve:** resolve the listed concerns, select **Submit for
   review**, record a decision on each Story, then grant **Final approval**.
   Download the approved revision as JSON or Excel from the revisions view.
8. If the Requirement changes, re-analyse it and reconcile or regenerate the
   stale downstream items before approving them again.

Re-analysis and regeneration use confirmation dialogs where existing AI or
human-reviewed content could be replaced. Initial Feature decomposition is
available; whole Feature-set regeneration is intentionally not exposed in the
current UI.

## Data lifetime

`PERSISTENCE_PROVIDER=memory` is the offline default and resets on API restart.
`PERSISTENCE_PROVIDER=postgres` uses the delivered PostgreSQL adapter and
explicit migrations for durable Requirements, analyses, backlog items, proposals,
private saved views, requirement-knowledge screens and suggestions, and revision
history. PostgreSQL mode requires the pgvector extension; the supplied Compose
service uses `pgvector/pgvector:pg17`. The UI stores only the last Requirement ID as a navigation
convenience; the server remains the source of truth.

For deployments, apply migrations explicitly before starting the API:

```powershell
docker compose up -d postgres
.\.venv\Scripts\python.exe -m smb_requirement_agent.infrastructure.persistence.migrate
```

```bash
docker compose up -d postgres
.venv/bin/python -m smb_requirement_agent.infrastructure.persistence.migrate
```

The API process never applies schema changes during its own startup. The
combined local launchers automate the surrounding development sequence: when a
local PostgreSQL URL is configured, they start the Compose service if needed,
wait for it, invoke the explicit migration command, and then start the API and
UI. External database URLs are checked but never cause a local container to be
started. The migration command reads only `PERSISTENCE_PROVIDER` and
`DATABASE_URL`, so it does not require LLM credentials.

## API overview

The HTTP surface is grouped by resource:

| Area | Paths |
|---|---|
| Health | `GET /health`, `GET /ready` |
| Identity | `/identity/config`, `/identity/me`, `/identity/actors` |
| Requirements and drafts | `/requirements`, `/requirements/{id}`, `/requirements/drafts/...`, ownership, assignments and reviewers |
| Attachments | `/requirements/{id}/attachments/...`, `/requirement-drafts/{draft_id}/attachments/...`, `/documents/...` |
| Analysis and clarification | `/requirements/{id}/analysis`, `.../analysis/rounds`, `.../analysis/questions/...`, `.../analysis/proposals/{proposal_id}`, `.../analysis/confirmation` |
| Requirement knowledge | `/requirements/{id}/knowledge-review`, `.../knowledge-findings/...`, `.../knowledge-index`, `/knowledge/search`, `/knowledge/search/unified` |
| Backlog | `/requirements/{id}/epic`, `.../features/...`, `.../features/{feature_id}/stories/...` (quality, split, merge, change proposals, regeneration) |
| Architecture | `/requirements/{id}/architecture-mapping`, `/architecture-knowledge/...` |
| Review and approval | `/requirements/{id}/breakdown-review/...`, `.../review-submission`, `.../approval-workflow`, `.../breakdown-approval`, `.../impact-preview` |
| Revisions and export | `/requirements/{id}/revisions`, `.../revisions/compare`, `.../revisions/{revision_number}/export` |
| Shared knowledge library | `/library/ingestions`, `/library/documents/...`, `/library/source-impact/...` |
| Background jobs | `/jobs/{job_id}`, `/requirements/{id}/ai-jobs/...` |
| Portfolio | `/activity`, `/reports/operational`, `/saved-views`, `/notifications` |

Use `http://127.0.0.1:8000/docs` for request schemas and interactive calls, or
the committed contract in `frontend/openapi.json`. Application and domain errors
are translated centrally to stable HTTP responses; route handlers do not contain
business rules.

## Architecture

The code follows inward Clean Architecture dependency direction:

```text
Interfaces / Infrastructure → Application → Domain
```

- `domain/` contains entities, value objects, invariants, and deterministic
  business behavior without frameworks or external systems.
- `application/` contains use cases, orchestration, and outbound ports.
- `infrastructure/` contains configuration and concrete provider/repository
  adapters.
- `interfaces/api/` contains FastAPI delivery schemas, routes, dependency
  providers, centralized error translation, and the composition root.
- `frontend/` consumes the stable HTTP/OpenAPI contract and never calls an LLM
  provider directly.

The complete object graph is created only in
`interfaces/api/container.py` during FastAPI startup. The fake, local,
OpenRouter, OpenAI and profile-configured adapters implement the same application ports, so the
provider can be changed without changing use cases, routes, or the browser.

## Repository map

```text
.
├── start.ps1                  # PowerShell setup/startup launcher
├── start.cmd                  # Command Prompt entry point; calls start.bat
├── start.bat                  # Standalone Command Prompt launcher
├── start.sh                   # Bash launcher for macOS, Linux and WSL
├── START_GUIDE.md             # First-run guide
├── compose.yaml               # Local PostgreSQL + pgvector service
├── .env.example               # Every configuration variable, documented
├── config/llm.yaml            # Optional YAML model profiles
├── src/smb_requirement_agent/
│   ├── domain/                # Business model and invariants
│   ├── application/           # Use cases and ports
│   ├── infrastructure/        # Configuration, persistence and provider adapters
│   └── interfaces/            # FastAPI API, CLI, worker and maintenance entry points
├── frontend/
│   ├── src/api/               # Typed API client and generated contract
│   ├── src/app/               # Routes, pages and the Requirement workspace
│   ├── src/features/          # Requirement, analysis, backlog and review UI
│   ├── src/components/        # App shell and shared UI components
│   └── tests/                 # Playwright browser smoke tests
├── tests/                     # Backend unit, API, and architecture tests
├── scripts/                   # OpenAPI dump, launcher helpers, Ollama setup, evaluations
├── deploy/                    # Images, Compose reference deployment and monitoring add-on
├── docs/architecture/         # Accepted architecture decisions
├── docs/slices/               # Slice specs and validation evidence
├── docs/operations/           # Deployment and operations runbooks
├── docs/ux-plan.md            # UI redesign plan
├── docs/design-system.md      # UI design system
├── AGENTS.md                  # Engineering constitution
├── PRODUCT.md, DESIGN.md      # Product context and shipped design system
├── ROADMAP.md                 # Delivery status and approved sequence
└── WORKSPACE.md               # Detailed developer workflow
```

## Validation and quality gates

Activate `.venv`, then run the five mandatory backend gates from the repository
root:

```bash
pytest
ruff check .
ruff format --check .
mypy src tests
lint-imports
```

Run frontend gates from `frontend/`:

```bash
npm run api:check
npm run lint
npm run typecheck
npm run test
npm run build
npm run test:smoke
```

The Playwright smoke test starts a fake-provider API and the built Vite preview
server, then exercises the complete review and staleness journey in Chromium.
Install the browser once if Playwright requests it:

```bash
npx playwright install chromium
```

The GitHub Actions workflow runs backend gates, frontend gates, and browser
smoke testing on pushes and pull requests.

## OpenAPI and frontend type synchronization

`frontend/openapi.json` is the committed backend contract and
`frontend/src/api/schema.d.ts` contains generated TypeScript types.

When an API schema changes:

```bash
python scripts/dump_openapi.py
cd frontend
npm run api:generate
npm run api:check
```

`npm run api:check` regenerates types in a temporary directory and fails when
the committed TypeScript contract has drifted. Backend snapshot tests also
protect closed enum values and the OpenAPI document.

## Troubleshooting

### `.venv` or frontend dependencies are missing

Run the launcher's setup option: `.\start.ps1 -Setup`, `start.cmd -Setup` or
`./start.sh --setup`.

### PowerShell will not execute the script

Use a trusted local checkout and follow your organization’s script-execution
policy. In managed WDAC/AppLocker environments, see the specialized virtual
environment instructions in `WORKSPACE.md`; do not weaken organization-wide
security policy for this repository.

### A provider reports a missing key

Either switch to the offline adapter with `-Provider fake` / `--provider fake`,
or put a valid key (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, or the credential a
selected model profile names) in `.env`. Placeholder credentials are
intentionally rejected.

### "LLM_CONFIG_PATH conflicts with an explicit launcher provider option"

`LLM_CONFIG_PATH` selects model profiles, so the launcher must not also choose
a provider. Start without `-Provider` / `--provider`, or remove
`LLM_CONFIG_PATH` from `.env`.

### Local LLM startup reports a missing model

Set a chat model and a 768-dimension embedding model already served by your
local server, then start in local mode:

```dotenv
LLM_PROVIDER=local
LOCAL_LLM_MODEL=smb-qwen3-vl:8b-16k
LOCAL_EMBEDDING_MODEL=your-768-dimension-embedding-model-id
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_TIMEOUT_SECONDS=300
LOCAL_LLM_REASONING_EFFORT=none
LOCAL_LLM_CONTEXT_WINDOW_TOKENS=16384
LOCAL_LLM_MAX_OUTPUT_TOKENS=8192
LOCAL_LLM_VISION_ENABLED=true
```

For Ollama, create or refresh that project alias first with
`.\scripts\setup-local-ollama-model.cmd`. It pins a 16K context, deterministic
generation settings, verifies vision support, and confirms the live allocation.

```powershell
.\start.ps1 -Provider local
```

The server must implement OpenAI-compatible `POST /v1/chat/completions` with
JSON-schema structured output. LM Studio documents this contract in its
[structured-output guide](https://lmstudio.ai/docs/developer/openai-compat/structured-output).

### PostgreSQL is not ready

Before starting either server, the launcher verifies persistence readiness.
PostgreSQL mode performs a bounded authenticated query and exits with a clear
message when the configured database is unavailable; memory mode needs no
external service. During normal local startup, a missing local PostgreSQL
service is started through `docker compose`, then the standalone migration
command is run. `-CheckOnly` / `--check-only` remains read-only and never starts
or migrates a database. Start Docker, correct `DATABASE_URL`, or set
`PERSISTENCE_PROVIDER=memory`.

### Library uploads fail with "Malware scanner unavailable"

Shared knowledge library uploads are scanned by ClamAV at
`LIBRARY_SCANNER_HOST`:`LIBRARY_SCANNER_PORT` (default `127.0.0.1:3310`) and fail
closed when it is unreachable. Run ClamAV, for example
`docker run -d -p 127.0.0.1:3310:3310 clamav/clamav:1.5`, or, for an offline
trial with memory persistence and fake identity only, set
`LIBRARY_SCAN_MODE=offline`. Requirement attachments are not affected. See
`docs/operations/document-knowledge.md`.

### View application and Ollama logs

`start.ps1` and `start.sh` write timestamped logs under the ignored `logs/`
directory, print their exact paths at startup, and show the last lines of each
when a server fails to start. `start.cmd` shows server output in its two
windows. Follow the newest API error log with:

```powershell
Get-Content (Get-ChildItem .\logs\api-error-*.log |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName -Wait
```

```bash
tail -f "$(ls -t logs/api-error-*.log | head -n 1)"
```

Follow Ollama's server log in another terminal:

```powershell
Get-Content "$env:LOCALAPPDATA\Ollama\server.log" -Tail 100 -Wait
```

The API logs mapped 5xx provider failures with their exception chain, method,
and path. Requirement text and provider payloads are not deliberately logged in
normal mode.

For a single detailed backend trace, restart with:

```powershell
.\start.ps1 -Provider local -DebugTrace
Get-Content .\logs\debug.log -Wait
```

`debug.log` is JSON Lines and records HTTP lifecycle events, the local LLM request
with image data removed, the raw provider response, the parsed schema, normalized
analysis candidates, exact expected/returned/missing citation keys, and mapped
exception chains. It contains requirement and document text. Credentials, binary
content, image data URLs, and hidden reasoning are always redacted. Delete it after
debugging and review it before sharing.

### Port 8000 or 5173 is already in use

Stop the process using the port, including any manually started Uvicorn or Vite
instance, then rerun the launcher. The current Vite proxy assumes the API is on
port 8000. Every launcher checks both fixed ports before applying migrations or
starting either server; `start.ps1` also reports the listening PID when Windows
exposes it.

### The UI says the remembered Requirement does not exist

The backend was restarted and its in-memory repositories were cleared. Return
to **Requirements** and create a new Requirement.

### The browser cannot reach the API

Confirm `http://127.0.0.1:8000/health` returns `{"status":"ok"}` and that the
UI is accessed through the Vite address on port 5173. Directly opening built
HTML files does not provide the `/api` proxy.

### OpenAPI types are reported as stale

Regenerate both artifacts using the commands in **OpenAPI and frontend type
synchronization**, review the contract change, and commit the backend snapshot,
OpenAPI document, and TypeScript definitions together.

## Deployment

`deploy/compose.production.yaml` is the reference production deployment:

- one backend image running the API, worker, migrate and maintenance
  processes;
- an nginx image serving the built app and proxying `/api`;
- PostgreSQL and ClamAV.

With `deploy/demo.env.example` copied to `deploy/production.env`, the same stack
runs as a local demo with OpenRouter AI output and no sign-in (see
**Quick start**). The optional
`deploy/compose.monitoring.yaml` overlay adds Prometheus and a provisioned
Grafana dashboard for the API and worker metrics.

Outside development, start the API with
`python -m smb_requirement_agent.interfaces.api.serve`, which configures
`LOG_LEVEL` and `LOG_FORMAT` before serving. First install, upgrades,
health probes, JSON logs, Prometheus metrics and the provider rate limit
are covered in `docs/operations/deployment.md`.

## Project documentation

Read these documents before changing implementation behavior:

1. `AGENTS.md` — engineering and architecture rules
2. `ROADMAP.md` — approved slice scope and sequence
3. `WORKSPACE.md` — development commands and package boundaries
4. `docs/architecture/` — accepted architecture decisions
5. `docs/slices/` — active and delivered slice specifications
6. `docs/source/` — original business decomposition reference
7. `docs/ux-plan.md` and `docs/design-system.md` — the governing UI redesign documents
8. `docs/llm-configuration.md` and `docs/operations/` — model configuration and operations runbooks

Never commit `.env`, API keys, provider payloads containing sensitive business
data, or Azure DevOps credentials.
