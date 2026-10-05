# Application Start Guide

This guide gets the SMB AI Requirement Breakdown Agent running: the FastAPI
backend, its background worker and the React review UI. There are two ways to
run it:

- **Docker.** One set of commands builds and starts the whole application in
  containers. You need only Docker; Python and Node.js are not required. Use it
  to try the application and to deploy it to a server.
- **Launchers.** `start.ps1`, `start.cmd` and `start.sh` run the API and the UI
  directly on your machine from source. Use them to develop the application.

The Docker demo uses OpenRouter for AI output and needs an OpenRouter API key.
The launchers start with the built-in fake AI provider, which needs no API key
and no external account: every screen works offline with deterministic sample
content. Either path can switch to the other provider.

## 1. Choose how to run it

| You want to | Use | Section |
|---|---|---|
| Try the application with nothing but Docker and an OpenRouter key | Docker demo | 2 |
| Deploy it to a server for other people | Docker deployment | 3 |
| Change the code, with fast reloads | Launchers | 4 |

The Docker stack and the launchers keep separate data and use different ports
(`8080` versus `5173` and `8000`), so you can run both on one machine.

## 2. Run with Docker

`deploy/compose.production.yaml` starts the whole platform, every process in
its own container: requirement work, built from this repository, and the
knowledge service, from the image knowledge-portal publishes.

| Container | Purpose |
|---|---|
| `postgres` | PostgreSQL 17 with pgvector for requirement work; a named volume keeps the data |
| `clamav` | Malware scanner for uploads to either service |
| `migrate` | Applies requirement work's migrations, then exits |
| `api` | The FastAPI backend (HTTP only) |
| `worker` | Background AI jobs, indexing, attachment ingestion and the knowledge event feed |
| `knowledge-postgres` | The knowledge service's own database |
| `knowledge-migrate` | Applies the knowledge service's migrations, then exits |
| `knowledge-api` | The knowledge service: shared library, architecture and squad catalogues |
| `knowledge-worker` | Library ingestion and catalogue jobs |
| `knowledge-web` | The knowledge portal's browser app, served under `/knowledge/` |
| `web` | nginx serving the review UI on port `8080`, forwarding `/api` to the API and `/knowledge-api` to the knowledge service |

The Compose project is `requirement-platform`, so it can run beside an earlier
`requirement-ai` stack; set `WEB_PORT` in `deploy/.env` to publish it on a port
other than `8080`.

`deploy/demo.env.example` configures a local demo:

- OpenRouter for AI output (a free, rate-limited chat model) and for
  requirement-knowledge embeddings (a model billed to your OpenRouter account);
- PostgreSQL storage in the stack's `postgres` container;
- the development personas instead of a sign-in;
- ClamAV scanning, and the knowledge service's initial architecture catalogue.

The same file works for the knowledge service, as `deploy/knowledge.env`.

### Prerequisites

- Docker Desktop on Windows or macOS, or Docker Engine with the Compose v2
  plugin on Linux. Confirm with `docker compose version`.
- About 4 GB of memory available to Docker. ClamAV uses most of it while it
  loads its signatures. On Docker Desktop, check **Settings → Resources**.
- About 5 GB of free disk space for the images and volumes.
- Port `8080` free on your machine.
- An OpenRouter API key, from <https://openrouter.ai/keys>. Embedding calls
  are billed, so the account needs a small credit balance.

Run every command from the repository root, the folder that contains
`README.md`, `pyproject.toml` and `deploy/`.

### Step 1: create the settings files

The stack reads three files, all ignored by Git:

- `deploy/production.env` holds requirement work's settings.
- `deploy/knowledge.env` holds the knowledge service's settings.
- `deploy/.env` holds the values Docker Compose itself needs: the two database
  passwords and the two tokens the services use to call each other (each 32
  characters or more). Compose reads it automatically for every command that
  uses `-f deploy/compose.production.yaml`. A `.env` file in the repository
  root is **not** read by these commands.

```powershell
# Windows PowerShell
Copy-Item deploy/demo.env.example deploy/production.env
Copy-Item deploy/demo.env.example deploy/knowledge.env
Set-Content deploy/.env @(
  "POSTGRES_PASSWORD=choose-a-password",
  "KNOWLEDGE_POSTGRES_PASSWORD=choose-another-password",
  "REQUIREMENT_SERVICE_TOKEN=$([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))",
  "KNOWLEDGE_SERVICE_TOKEN=$([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))"
)
```

```bash
# macOS/Linux
cp deploy/demo.env.example deploy/production.env
cp deploy/demo.env.example deploy/knowledge.env
cat > deploy/.env <<EOF
POSTGRES_PASSWORD=choose-a-password
KNOWLEDGE_POSTGRES_PASSWORD=choose-another-password
REQUIREMENT_SERVICE_TOKEN=$(openssl rand -hex 32)
KNOWLEDGE_SERVICE_TOKEN=$(openssl rand -hex 32)
EOF
```

The knowledge service's images are public on ghcr.io, so Docker pulls them
without signing in.

Open `deploy/production.env` and `deploy/knowledge.env` and set your OpenRouter key in both:

```dotenv
OPENROUTER_API_KEY=your-real-key
```

The API and worker refuse to start while it is blank. To run the demo offline
with sample output instead, set `LLM_PROVIDER=fake` in the same file.

Choose your own password. Keep it unchanged once the stack has started: the
database volume keeps the password it was created with.

You can instead set `POSTGRES_PASSWORD` in the shell (`export
POSTGRES_PASSWORD=...` or `$env:POSTGRES_PASSWORD = "..."`), but then you must
set it in every new terminal before running any `docker compose` command.

### Step 2: build and start

```bash
docker compose -f deploy/compose.production.yaml pull knowledge-api knowledge-web
docker compose -f deploy/compose.production.yaml build
docker compose -f deploy/compose.production.yaml run --rm maintenance
docker compose -f deploy/compose.production.yaml up -d
```

- `pull` fetches the knowledge service's pinned release (`KNOWLEDGE_IMAGE_TAG`), its API and its browser app.
- `build` creates the `requirement-platform/api` and `requirement-platform/web` images. It
  takes several minutes the first time.
- `run --rm maintenance` starts PostgreSQL, applies the migrations and records
  the marker the API needs before it reports ready. Run it once on a new
  database, before the first `up`. Without it, the API never becomes healthy
  and the `web` container does not start.
- `up -d` starts everything in the background.

### Step 3: confirm it is running

```bash
docker compose -f deploy/compose.production.yaml ps
```

After up to a minute, `api` and `knowledge-api` show `(healthy)`, and `web`,
`worker`, `knowledge-worker`, both PostgreSQL containers and `clamav` are `Up`.
`migrate` and `knowledge-migrate` have exited, which is expected.

| Address | Purpose |
|---|---|
| `http://localhost:8080` | Review UI |
| `http://localhost:8080/api/health` | The API is serving; returns `{"status":"ok"}` |
| `http://localhost:8080/api/ready` | The API is ready: database migrated and maintenance recorded |
| `http://localhost:8080/knowledge-api/ready` | The knowledge service is ready |
| `http://localhost:8080/knowledge/` | The knowledge portal, for knowledge admins (Amina Owner and Ravi Reviewer in the demo) |

Port `8080` is the only one the stack publishes. The API, worker, database and
scanner are reachable only from inside the stack. Continue with section 5 to
walk through a first Requirement.

The port is published on all network interfaces. The demo lets anyone who can
reach it act as any development persona, so keep it on your own machine or
behind a firewall that blocks port `8080` from other computers.

### Everyday commands

```bash
docker compose -f deploy/compose.production.yaml ps            # container status
docker compose -f deploy/compose.production.yaml logs -f api   # follow API logs (also: worker, web, clamav)
docker compose -f deploy/compose.production.yaml stop          # stop; data is kept
docker compose -f deploy/compose.production.yaml up -d         # start again
docker compose -f deploy/compose.production.yaml down          # stop and remove the containers; data is kept
docker compose -f deploy/compose.production.yaml down -v       # stop and delete all data
```

The containers restart automatically with Docker unless you stopped them. After
`down -v`, repeat the full first start, including `maintenance`.

### Update to new code

```bash
git pull
docker compose -f deploy/compose.production.yaml build
docker compose -f deploy/compose.production.yaml up -d
```

`up` reapplies any new migrations before it restarts the API and worker. Data
is kept.

### Another AI provider in Docker

The demo uses OpenRouter. To switch, edit `deploy/production.env`, set the
provider and its key, then run
`docker compose -f deploy/compose.production.yaml up -d` again:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your-real-key
```

The other providers use the variables from section 7. Changing the embedding
model makes existing requirement-knowledge indexes stale; see
`docs/llm-configuration.md` for the index rebuild. A model server running on
your own machine is not `127.0.0.1` from inside a container. On Docker Desktop
use `http://host.docker.internal:11434/v1` (Ollama) or
`http://host.docker.internal:1234/v1` (LM Studio) as `LOCAL_LLM_BASE_URL`. On
Linux, use the host's network address, and make sure the model server listens
on it and not only on `127.0.0.1`.

To use model profiles (section 7), the stack already mounts the repository's
`config/` folder read-only at `/app/config`. Set the in-container path in
`deploy/production.env`, with the profiles' keys:

```dotenv
LLM_CONFIG_PATH=/app/config/llm.yaml
GEMINI_API_KEY=your-real-key
```

To keep your profiles file somewhere else, add `LLM_CONFIG_DIR` with that
folder's absolute path to `deploy/.env`.

### Monitoring with Grafana (optional)

`deploy/compose.monitoring.yaml` adds Prometheus and Grafana with a ready-made
dashboard of API traffic, AI provider calls and token use, and background
jobs. Add a Grafana password to `deploy/.env`, then pass both files:

```dotenv
GRAFANA_ADMIN_PASSWORD=choose-another-password
```

```bash
docker compose -f deploy/compose.production.yaml -f deploy/compose.monitoring.yaml up -d
```

Open `http://localhost:3000` and sign in as `admin` with that password. The
**Requirement AI — overview** dashboard opens first. Its provider and token
panels fill as the demo calls OpenRouter; they stay empty with
`LLM_PROVIDER=fake`, which makes no provider calls. Use both
`-f` files for `ps`, `logs` and `down` while monitoring runs. Details and
alert rules are in `docs/operations/deployment.md` ("Metrics").

### Good to know

- ClamAV loads its signatures for a few minutes after its first start.
  Shared-library uploads wait for it; the rest of the application does not.
- The API does not auto-reload in containers. Use the launchers (section 4) or
  section 8 for day-to-day development.
- The Docker stack keeps its own database volume and does not publish port
  `5432`, so it neither shares data nor conflicts with a launcher's PostgreSQL.

## 3. Deploy to a server with Docker

A real deployment uses the same manifest and commands as section 2, with
production settings. `docs/operations/deployment.md` is the full operations
reference: process model, health probes, logs, metrics, rate limits and image
updates.

### What changes from the demo

| Demo | Deployment |
|---|---|
| `deploy/demo.env.example`, twice | `deploy/production.env.example` and `deploy/knowledge.env.example`, with every blank filled in |
| `APP_ENV=development` | `APP_ENV=production` |
| Development personas, no sign-in | OIDC sign-in (`IDENTITY_PROVIDER=oidc`) |
| OpenRouter's free chat model, also used for architecture mapping | A production `LLM_PROVIDER` or model profiles, used for architecture mapping too |
| No knowledge evaluation | `KNOWLEDGE_EVALUATION_APPROVED=true` in `deploy/knowledge.env`, set only after the models pass the English/Arabic evaluation |
| Plain HTTP on port `8080` | A TLS reverse proxy in front of port `8080` |

With `APP_ENV=production`, the API and worker refuse to start on the fake
personas or an unapproved architecture evaluation, and the error names the
setting. A half-converted demo file fails fast instead of
running insecurely.

Architecture mapping uses the same models as the rest of the application
(`LLM_PROVIDER` or the model profiles); it needs no separate model server or
tokenizer file.

### Server prerequisites

- A Linux host with Docker Engine and the Compose v2 plugin, at least 4 GB of
  memory and room for the database to grow.
- An OIDC identity provider. `deploy/keycloak/` and
  `docs/operations/keycloak-login.md` describe the Keycloak setup the
  application is built against.
- A domain name with a TLS certificate, served by a reverse proxy or load
  balancer (for example nginx, Caddy, Traefik or a cloud load balancer).
- The model provider you configure (a local model server or a hosted API),
  reachable from the host.

### First install

On the server, from a clone of the repository:

```bash
cp deploy/production.env.example deploy/production.env
cp deploy/knowledge.env.example deploy/knowledge.env
```

Fill in every blank in both files; `.env.example` documents each variable. Then
create `deploy/.env` with the values Compose needs:

```dotenv
POSTGRES_PASSWORD=a-long-random-password
KNOWLEDGE_POSTGRES_PASSWORD=another-long-random-password
# The services' tokens for each other's internal API: 32+ random characters each.
REQUIREMENT_SERVICE_TOKEN=...
KNOWLEDGE_SERVICE_TOKEN=...
# A knowledge-portal release.
KNOWLEDGE_IMAGE_TAG=v0.1.0
# The OIDC issuer origin. It is built into the page's Content-Security-Policy;
# without it the browser blocks sign-in.
CSP_IDENTITY_ORIGINS=https://login.example.com
```

Restrict the three files to the deployment account, for example
`chmod 600 deploy/.env deploy/production.env deploy/knowledge.env`. The knowledge
service's images are public on ghcr.io. Then fetch, build, prepare the database and start:

```bash
docker compose -f deploy/compose.production.yaml pull knowledge-api knowledge-web
docker compose -f deploy/compose.production.yaml build
docker compose -f deploy/compose.production.yaml run --rm maintenance
docker compose -f deploy/compose.production.yaml up -d
```

Point the reverse proxy at `http://127.0.0.1:8080` and firewall port `8080` so
it is reachable only from the proxy. Once `https://<your-domain>/api/ready`
answers, open `https://<your-domain>` and sign in.

`CSP_IDENTITY_ORIGINS` is baked into the web image when it is built. When the
issuer changes, update `deploy/.env` and run `build` and `up -d` again.

### Operate the deployment

- **Upgrades.** `git pull`, then `build` and `up -d` as in section 2. `up`
  applies new migrations before the API and worker restart. Run `maintenance`
  again only when a release's notes require it, with the API and every worker
  stopped (`docs/operations/production-readiness-maintenance.md`).
- **Scaling.** Background jobs are leased in PostgreSQL, so more workers are
  safe: `docker compose -f deploy/compose.production.yaml up -d --scale worker=2`.
- **Retention.** Schedule the notification clean-up once a day, for example
  with cron:

  ```bash
  docker compose -f deploy/compose.production.yaml run --rm retention
  ```

- **Backups.** Back up the database regularly and keep copies off the server:

  ```bash
  docker compose -f deploy/compose.production.yaml exec -T postgres \
    pg_dump -U smb -d smb_requirements -Fc > smb_requirements-$(date +%F).dump
  ```

  Or use a managed PostgreSQL and point `DATABASE_URL` at it.
- **Logs.** The API and worker write one JSON object per line to
  `docker compose ... logs`. Ship them to your log platform as needed.

## 4. Run with the launchers (development)

### Prerequisites

Install:

- Python 3.12 or newer
- Node.js 22 with npm
- Windows: PowerShell 5.1 or PowerShell 7 (for `start.ps1`) or Command Prompt
  (for `start.cmd`)
- macOS/Linux: Bash and `curl` (for `start.sh`)

Optional, only for the features that need them:

- Docker Desktop (or Docker Engine) for durable PostgreSQL storage
- ClamAV for scanning Requirement attachments (see section 6)
- an API key or a local OpenAI-compatible model server for real AI output

Confirm the tools are available:

```powershell
# Windows
py -3.12 --version
node --version
npm --version
```

```bash
# macOS/Linux
python3.12 --version
node --version
npm --version
```

### Pick your launcher

Run every command from the repository root.

| Shell | Launcher | Notes |
|---|---|---|
| PowerShell | `.\start.ps1` | Runs both servers hidden, writes logs under `logs/`, stops both on `Ctrl+C`. |
| Command Prompt | `start.cmd` | Calls `start.bat`, a standalone CMD implementation. Opens the API and UI in two titled windows. |
| Bash (macOS, Linux, WSL) | `./start.sh` | Same behaviour as `start.ps1`, including `logs/`. |

All three perform the same steps and accept the same options:

| Purpose | PowerShell | Command Prompt | Bash |
|---|---|---|---|
| First run: install, then start | `.\start.ps1 -Setup` | `start.cmd -Setup` | `./start.sh --setup` |
| Start again later | `.\start.ps1` | `start.cmd` | `./start.sh` |
| Validate without starting | `.\start.ps1 -CheckOnly` | `start.cmd -CheckOnly` | `./start.sh --check-only` |
| Choose the AI provider | `-Provider openai` | `-Provider openai` | `--provider openai` |
| Write a debug trace | `-DebugTrace` | `-DebugTrace` | `--debug-trace` |

Providers are `fake` (the default), `local`, `openai` and `openrouter`.

### First startup

```powershell
.\start.ps1 -Setup
```

```bat
start.cmd -Setup
```

```bash
./start.sh --setup
```

`-Setup` / `--setup` prepares the workspace and then starts the application:

1. creates the Python `.venv` if it does not exist;
2. installs the backend with its development dependencies (`pip install -e ".[dev]"`);
3. installs the exact frontend versions from `package-lock.json` (`npm ci`);
4. validates the model configuration without making any paid request;
5. checks that ports `8000` and `5173` are free;
6. when PostgreSQL is configured, starts the local Compose database if needed
   and applies pending migrations;
7. starts the API and waits for its health check;
8. starts the review UI and waits for it to answer.

Dependency installation takes a few minutes on the first run. No `.env` file is
needed for the fake provider.

#### If PowerShell blocks local scripts

Follow your organization's script-execution policy. If process-scoped bypasses
are permitted, this affects only the new PowerShell process and does not change
the machine-wide policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start.ps1 -Setup
```

If WDAC or AppLocker still blocks Python extension modules or the script, do
not weaken the managed policy. Follow the WDAC/AppLocker environment setup in
`WORKSPACE.md` or contact the machine administrator.

### Confirm the application is ready

A successful start prints output similar to:

```text
[startup] Validating model configuration...
{
  "provider": "fake",
  "mode": "legacy environment configuration"
}
Configuration is valid; no paid model requests were made.
[startup] Checking local API and UI ports...
[startup] Starting API on http://127.0.0.1:8000...
[startup] Starting review UI on http://127.0.0.1:5173...

Application ready
  Review UI:  http://127.0.0.1:5173
  API docs:   http://127.0.0.1:8000/docs
  Health:     http://127.0.0.1:8000/health
  Provider:   fake
  API log:    ...\logs\api-<timestamp>.log
  ...
```

The JSON block names the model configuration actually in use. When
`LLM_CONFIG_PATH` selects model profiles, it lists each task's provider and
model instead.

Open:

| Address | Purpose |
|---|---|
| `http://127.0.0.1:5173` | Review UI |
| `http://127.0.0.1:8000/docs` | Interactive API documentation |
| `http://127.0.0.1:8000/health` | Health check; returns `{"status":"ok"}` |

Keep the launcher window open while using the application. With `start.cmd`,
keep both server windows open as well.

### Stop the application

- `start.ps1` / `start.sh`: press `Ctrl+C` in the launcher window. Both servers
  stop.
- `start.cmd`: close both server windows, or press `Ctrl+C` in each.

With the default `PERSISTENCE_PROVIDER=memory`, stopping the API discards all
data. With PostgreSQL (section 6), Requirements, answers, generated artifacts
and revisions survive restarts.

### Start it again later

Dependencies do not need reinstalling on every run:

```powershell
.\start.ps1
```

```bat
start.cmd
```

```bash
./start.sh
```

Run the setup option again only after `pyproject.toml` or
`frontend/package-lock.json` changes, or after `.venv` or
`frontend/node_modules` is removed.

To verify prerequisites, configuration and database readiness without
starting servers, use `-CheckOnly` / `--check-only`. It never starts or
migrates a database.

### Run with the knowledge service (development)

On its own, the launcher runs requirement work with offline stand-ins for the
knowledge service: library search finds nothing, architecture mapping covers
only the systems a Requirement declares, and the read-only passage and evidence
views have nothing to show.
To work against the real knowledge service, run
[knowledge-portal](https://github.com/mohamhossam/knowledge-portal) beside it.
Clone it next to this repository and follow its README; its API listens on
`8100` and its browser app on `5174`.

The two services call each other's internal API with two shared tokens, each
32 or more characters. Use the same two values on both sides:

| Setting | requirement work (`.env` here) | knowledge-portal (its `.env`) |
|---|---|---|
| Where the other service is | `KNOWLEDGE_API_BASE_URL=http://127.0.0.1:8100` | `REQUIREMENT_API_BASE_URL=http://127.0.0.1:8000` |
| The token requirement work presents | `REQUIREMENT_SERVICE_TOKEN=<token A>` | `REQUIREMENT_SERVICE_TOKEN=<token A>` |
| The token the knowledge service presents | `KNOWLEDGE_SERVICE_TOKEN=<token B>` | `KNOWLEDGE_SERVICE_TOKEN=<token B>` |

Start knowledge-portal's API first, then this launcher. The launcher's ready
banner names the knowledge service it is connected to. Each side keeps working
if the other is stopped, and reports the other as unavailable where it needs it.

With fake sign-in on both sides, Amina Owner and Ravi Reviewer are knowledge
admins in both portals. In development the review UI's **Open knowledge
portal** link points at `/knowledge/` on its own server, which does not serve
the portal: open `http://localhost:5174/knowledge/` directly. The Docker stack
(section 2) serves both under one address, so the link works there.

## 5. Walk through the first requirement

Open the review UI: `http://localhost:8080` with Docker, or
`http://127.0.0.1:5173` with a launcher.

The UI opens on **Requirements**, the worklist. The top bar holds the
navigation (**Requirements**, **Documents**, **Activity**, **Reports**) and the
**New requirement** button. In development identity mode, a **Development
persona** selector in the top bar switches between the test users, for example
the owner (`fake-owner`) and a reviewer (`fake-reviewer`).

Each Requirement moves through six steps, shown in the workflow rail on the
left: **Source → Clarify → Knowledge → Confirm → Backlog → Review & approve**.

1. **Source.** Select **New requirement**. Enter a **Requirement title** and
   the **Business need**, or attach files that describe it. Open
   **Add detail if you know it (optional)** for systems, channels, rules and
   constraints. Select **Save and analyse**, or **Save draft and exit** to
   finish later.
2. **Clarify.** Read the known facts, assumptions and open questions. Answer
   what you can in **Your answer**, then select **Send N answers and
   re-analyse**. Unanswered questions stay open. Accept or edit each proposed
   change to the Requirement (**Accept as written**).
3. **Knowledge.** Resolve any possible duplicates or contradictions with other
   Requirements.
4. **Confirm.** When nothing is left open, select **Confirm this analysis**.
   The Backlog stays locked until this explicit human confirmation.
5. **Backlog.** Select **Generate Epic**, edit it if needed, and **Approve** it.
   Select **Decompose into Features**, then edit and approve each Feature.
   Select **Generate Stories** to get User Stories with Given/When/Then
   acceptance criteria and an INVEST quality review.
6. **Review & approve.** Resolve the listed concerns and select **Submit for
   review**. Record an **Approve** or **Reject** decision on each Story (switch
   the **Development persona** to act as a reviewer), then select **Final
   approval**. The approved revision can be downloaded as JSON or Excel from
   the Requirement's revisions view.

Generated content is always a review candidate. Nothing is published
automatically.

## 6. Optional configuration (launchers)

The Docker stack reads its settings from `deploy/production.env` (section 2).
The launchers read the process environment and a root `.env` file. Start from
the template:

```powershell
Copy-Item .env.example .env
```

```bash
cp .env.example .env
```

Never commit `.env` or share its contents. `.env.example` documents every
variable.

### Durable PostgreSQL storage

Set in `.env`:

```dotenv
PERSISTENCE_PROVIDER=postgres
DATABASE_URL=postgresql://smb:smb_dev@127.0.0.1:5432/smb_requirements
```

Then start as usual. When `DATABASE_URL` points at `localhost` or `127.0.0.1`,
the launcher starts the `postgres` service from `compose.yaml` if it is not
already running, waits for it, and applies pending migrations before starting
the API. The image is PostgreSQL 17 with pgvector, and a Docker named volume
keeps the data across restarts. A non-local `DATABASE_URL` is checked but never
started by the launcher.

To run the same steps by hand:

```powershell
docker compose up -d postgres
.\.venv\Scripts\python.exe -m smb_requirement_agent.infrastructure.persistence.migrate
```

```bash
docker compose up -d postgres
.venv/bin/python -m smb_requirement_agent.infrastructure.persistence.migrate
```

The API never changes the schema during its own startup.

### Scanning Requirement attachments

Files attached to a Requirement are scanned for malware before they are read,
and stay at "Malware scanner unavailable" until a scanner is reachable. The
Docker stack includes one. With a launcher, choose one:

- **Offline trial only:** set `LIBRARY_SCAN_MODE=offline` in `.env`. This is a
  deterministic development adapter, not malware protection, and startup
  rejects it with PostgreSQL or OIDC identity.
- **Real scanning:** run ClamAV on `127.0.0.1:3310` (the defaults for
  `LIBRARY_SCANNER_HOST` and `LIBRARY_SCANNER_PORT`), for example:

  ```bash
  docker run -d --name smb-clamav -p 127.0.0.1:3310:3310 clamav/clamav:1.5
  ```

  ClamAV needs a few minutes to load its signatures after starting.

The shared knowledge library and the architecture and squad catalogues are not
in this application any more: they belong to the knowledge portal (section 4,
"Run with the knowledge service"), which scans its own uploads.

## 7. Use a real AI provider

Offline fake mode is recommended for the first run. Each launcher validates the
provider settings before starting either server and stops with a clear message
when a key or model is missing. Placeholder keys are rejected.

The variables below go in `.env` for the launchers, or in
`deploy/production.env` for Docker (with `LLM_PROVIDER` set to the provider
name; see section 2).

### OpenAI

```dotenv
OPENAI_API_KEY=your-real-key
OPENAI_MODEL=gpt-4o
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

Start with `.\start.ps1 -Provider openai`, `start.cmd -Provider openai` or
`./start.sh --provider openai`.

### OpenRouter (development/demo)

```dotenv
OPENROUTER_API_KEY=your-real-key
OPENROUTER_MODEL=google/gemma-4-31b-it:free
OPENROUTER_EMBEDDING_MODEL=openai/text-embedding-3-small
OPENROUTER_DATA_COLLECTION=deny
```

Start with `-Provider openrouter` / `--provider openrouter`. The free chat
model has low daily limits and is unsuitable for production. The application
never falls back to a paid chat model. Knowledge embeddings use the configured
embedding model and may be billed.

### Local model server (LM Studio or Ollama)

Start an OpenAI-compatible server and load a chat model that supports
JSON-schema structured output plus a 768-dimension embedding model. Then:

```dotenv
LOCAL_LLM_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_LLM_MODEL=smb-qwen3-vl:8b-16k
LOCAL_EMBEDDING_MODEL=your-768-dimension-embedding-model-id
LOCAL_LLM_TIMEOUT_SECONDS=300
LOCAL_LLM_REASONING_EFFORT=none
LOCAL_LLM_CONTEXT_WINDOW_TOKENS=16384
LOCAL_LLM_MAX_OUTPUT_TOKENS=8192
LOCAL_LLM_VISION_ENABLED=true
```

`LOCAL_LLM_MODEL` and `LOCAL_EMBEDDING_MODEL` are both required. The base URL
above is Ollama's; omit it to use LM Studio's default,
`http://127.0.0.1:1234/v1`. In Docker, replace `127.0.0.1` as described in
section 2. For Ollama on Windows, create the deterministic project model alias
once:

```powershell
.\scripts\setup-local-ollama-model.cmd
```

Then start with `-Provider local` / `--provider local`. For Qwen thinking
models, `LOCAL_LLM_REASONING_EFFORT=none` stops internal reasoning from using
up the generation timeout.

### Model profiles (Gemini and per-task models)

`config/llm.yaml` defines named model profiles and can assign a different
model to each task. The supplied file selects Google Gemini and needs
`GEMINI_API_KEY`. To use it with a launcher, set in `.env`:

```dotenv
LLM_CONFIG_PATH=config/llm.yaml
GEMINI_API_KEY=your-real-key
```

Start the launcher **without** a provider option. A provider option is rejected
while `LLM_CONFIG_PATH` is set. See `docs/llm-configuration.md` for the
`check`, `smoke` and index `rebuild` commands to run before switching.

## 8. Manual startup (backend auto-reload)

The launchers run the API without auto-reload so they can stop it reliably. For
backend development with reload, use two terminals.

PowerShell:

```powershell
# Terminal 1 — API
$env:LLM_PROVIDER = "fake"
.\.venv\Scripts\python.exe -m uvicorn smb_requirement_agent.interfaces.api.main:app --reload

# Terminal 2 — review UI
Set-Location frontend
npm run dev
```

Bash:

```bash
# Terminal 1 — API
LLM_PROVIDER=fake .venv/bin/python -m uvicorn smb_requirement_agent.interfaces.api.main:app --reload

# Terminal 2 — review UI
cd frontend
npm run dev
```

The UI proxies `/api` requests to the API on port `8000`. With PostgreSQL, run
the migration command from section 6 first.

## 9. Logs and debug trace

### Docker

Every container writes to Docker's log. Follow one or more services:

```bash
docker compose -f deploy/compose.production.yaml logs -f api worker
docker compose -f deploy/compose.production.yaml logs --tail 100 web
```

The API and worker log one JSON object per line. `docs/operations/deployment.md`
("Logs") describes the fields.

### Launchers

`start.ps1` and `start.sh` write timestamped API and UI logs under `logs/` and
print their exact paths at startup. When startup fails, they print the last
lines of each log. `start.cmd` shows server output in its two windows.

Follow the newest API error log:

```powershell
Get-Content (Get-ChildItem .\logs\api-error-*.log |
  Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName -Wait
```

```bash
tail -f "$(ls -t logs/api-error-*.log | head -n 1)"
```

`-DebugTrace` / `--debug-trace` also writes `logs/debug.log`, a JSON Lines
trace that includes requirement text, prompts and model completions. Delete it
after debugging and review it before sharing.

## 10. Common startup problems

### Docker

#### "required variable POSTGRES_PASSWORD is missing a value"

Compose could not find the password. Create `deploy/.env` as in section 2, or
set `POSTGRES_PASSWORD` in the current terminal. A root `.env` file is not read
by `docker compose -f deploy/compose.production.yaml`.

#### "env file ... deploy/production.env not found"

Copy `deploy/demo.env.example` (demo) or `deploy/production.env.example`
(deployment) to `deploy/production.env`.

#### `web` never starts and `api` stays unhealthy

Usually the one-time `maintenance` step was skipped. Run
`docker compose -f deploy/compose.production.yaml run --rm maintenance`, then
`up -d` again. Otherwise read
`docker compose -f deploy/compose.production.yaml logs api`; a configuration
error names the setting to fix.

#### 'password authentication failed for user "smb"'

`POSTGRES_PASSWORD` differs from the one the database volume was created with.
Restore the original value. For a demo whose data you do not need, `down -v`
deletes the volume so the next first start uses the new password.

#### Port 8080 is already in use

Stop the other program using it, or change the published port in
`deploy/compose.production.yaml` (`"8081:8080"` publishes it on `8081`).

#### Shared-library uploads say the scanner is unavailable

ClamAV is still loading its signatures. Wait a few minutes and check
`docker compose -f deploy/compose.production.yaml logs clamav`. If the
container keeps restarting, give Docker more memory.

#### The build fails while downloading

The build downloads base images and packages from Docker Hub, the GitHub
container registry, PyPI and npm. Check your network or corporate proxy
settings in Docker Desktop, then run `build` again.

### Launchers

#### `.venv` or frontend dependencies are missing

Run the setup option: `.\start.ps1 -Setup`, `start.cmd -Setup` or
`./start.sh --setup`.

#### Node.js cannot be found

Install Node.js 22, then close and reopen the terminal so `PATH` refreshes.
Confirm `node --version` and `npm --version` work.

#### A provider reports a missing key or model

Return to offline mode with `-Provider fake` / `--provider fake`, or correct
the value in `.env`. `LLM_PROVIDER=local` needs both `LOCAL_LLM_MODEL` and
`LOCAL_EMBEDDING_MODEL`.

#### "LLM_CONFIG_PATH conflicts with an explicit launcher provider option"

Model profiles are selected in `.env`. Start without `-Provider` /
`--provider`, or remove `LLM_CONFIG_PATH` to use a single provider.

#### Port 8000 or 5173 is already in use

Every launcher checks both ports before touching the database or starting a
server. Stop the previous Uvicorn, Vite or launcher process and run again. The
ports are fixed because the UI proxy expects the API on `8000`.
`start.ps1` also reports the listening PID when Windows exposes it.

#### PostgreSQL is not ready

Start Docker Desktop, or check `DATABASE_URL`. To run without a database, set
`PERSISTENCE_PROVIDER=memory`.

#### The browser remembers a Requirement that is not found

The API restarted in memory mode and its data was cleared. Return to
**Requirements** and create a new one.

#### The UI opens but cannot call the API

Check that `http://127.0.0.1:8000/health` returns `{"status":"ok"}`, then read
the API error log. Open the UI at `http://127.0.0.1:5173`; opening built HTML
files directly does not provide the `/api` proxy.

## More information

- `README.md` — project overview, architecture, configuration and quality gates
- `WORKSPACE.md` — development environment and workflow details
- `docs/llm-configuration.md` — model profiles and provider switching
- `docs/operations/deployment.md` — production deployment and operations
- `docs/operations/keycloak-login.md` — sign-in with Keycloak
- `ROADMAP.md` — delivery status and planned slices
- `AGENTS.md` — mandatory engineering rules
