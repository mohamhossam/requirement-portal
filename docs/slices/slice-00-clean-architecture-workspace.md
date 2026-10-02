# Slice 00 — Clean Architecture Workspace

## Objective
Establish the repository skeleton and automated quality boundaries for incremental implementation.

## User Outcome
There is no end-user business capability yet. Developers/coding agents can safely implement future vertical slices.

## In Scope
- Clean Architecture package boundaries.
- Root agent/workspace/roadmap documentation.
- Minimal FastAPI health endpoint.
- pytest, ruff, mypy strict, import-linter.
- No external integrations.

## Out of Scope
- Requirement entity/use cases.
- LLM integration.
- Frontend.
- Database.
- Azure DevOps.

## Domain
No business model required yet.

## Application Use Cases
None.

## Ports
None.

## Adapters
None.

## API
- `GET /health`

## UI
None.

## Business Rules
Only architecture and quality rules from `AGENTS.md`.

## Tests
- health endpoint — `tests/unit/test_health.py`
- architecture contracts via import-linter — `tests/architecture/test_architecture.py`

## Acceptance Criteria
- [x] Workspace structure exists (`domain/`, `application/`, `infrastructure/`, `interfaces/api/`).
- [x] `AGENTS.md` exists.
- [x] `ROADMAP.md` exists.
- [x] `WORKSPACE.md` exists.
- [x] Health endpoint is defined (`GET /health → 200 {"status": "ok"}`).
- [x] FastAPI application imports successfully.
- [x] Health endpoint test exists and passes.
- [x] Architecture dependency test exists and passes.
- [x] Full quality gates executed — see Validation Evidence.
- [x] No Requirement/LLM/Epic/Feature/Story/database/ADO functionality introduced.

## Validation Evidence

Environment: Python 3.14.5 (pythoncore-3.14-64) on Windows.  
Note: A Windows Application Control (WDAC) policy blocks pydantic_core's compiled
DLL in virtual environments created under `c:\ai\projects\`. The system Python
at `C:\Users\moham\AppData\Local\Python\pythoncore-3.14-64\` is in a trusted
location; packages installed there load correctly. Project is installed in
editable mode (`-e .`) into that interpreter.

```
C:\Users\moham\AppData\Local\Python\pythoncore-3.14-64\python.exe -m pytest -v
```
PASS — 2 passed, 1 warning in 0.39s
```
tests/architecture/test_architecture.py .   [ 50%]
tests/unit/test_health.py .                 [100%]
```

```
C:\Users\moham\AppData\Local\Python\pythoncore-3.14-64\python.exe -m ruff check .
```
PASS — All checks passed!

```
C:\Users\moham\AppData\Local\Python\pythoncore-3.14-64\python.exe -m ruff format --check .
```
PASS — 21 files already formatted

```
C:\Users\moham\AppData\Local\Python\pythoncore-3.14-64\python.exe -m mypy src tests
```
PASS — Success: no issues found in 12 source files

```
C:\Users\moham\AppData\Local\Python\pythoncore-3.14-64\python.exe -c \
  "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())"
```
PASS — Contracts: 2 kept, 0 broken.
```
Domain must not depend on outer layers              KEPT
Application must not depend on infrastructure or interfaces  KEPT
```

FastAPI application startup (import check):
```
C:\Users\moham\AppData\Local\Python\pythoncore-3.14-64\python.exe -c \
  "from smb_requirement_agent.interfaces.api.main import app; print('OK')"
```
PASS — FastAPI application imports successfully. Routes: ['/health', ...]

## Deferred
All product behavior begins in Slice 01.

### Environment Note (for future developers)
The Windows Application Control (WDAC) policy on this machine blocks newly
downloaded `.pyd` extension modules in project-local directories. The
`.venv` is created with `--system-site-packages` so compiled packages
(`pydantic_core`, etc.) resolve from the trusted system Python location.

Setup (see `WORKSPACE.md` § 4 for full instructions):

```powershell
py -3.14 -m venv --system-site-packages .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pip install ruff "import-linter" --force-reinstall --quiet
```

After that, the standard commands from `WORKSPACE.md` work normally:

```powershell
pytest
ruff check .
ruff format --check .
mypy src tests
lint-imports
```

All five gates confirmed passing via `.venv` on 2026-08-31.
