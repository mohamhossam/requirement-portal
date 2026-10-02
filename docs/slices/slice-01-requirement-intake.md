# Slice 01 — Requirement Intake

## Objective

Introduce the first business capability: a Business Owner can create, retrieve,
and update a requirement draft without any AI involvement.

## User Outcome

A Business Owner can:

1. Submit a raw business requirement text (title + description).
2. Retrieve the saved requirement by its ID.
3. Update the title or description of an existing requirement.

The requirement remains a **draft business input** — it is not yet analysed,
decomposed into Epics, or decomposed into Features or Stories.

## In Scope

- `Requirement` domain aggregate with `RequirementId`, `RequirementTitle`,
  `RequirementDescription`, `RequirementStatus`.
- Domain validation: non-empty, non-blank title and description; whitespace
  normalisation on construction.
- `RequirementStatus.DRAFT` only.
- `CreateRequirement`, `GetRequirement`, `UpdateRequirement` use cases.
- `RequirementRepositoryPort` outbound port.
- `InMemoryRequirementRepository` adapter.
- `POST /requirements`, `GET /requirements/{id}`, `PUT /requirements/{id}` endpoints.
- Domain, application, repository, and API tests.
- Slice documentation.

## Out of Scope

- RequirementAnalysis, KnownFact, Assumption, OpenQuestion (Slice 02).
- Epic, Feature, UserStory, AcceptanceCriterion (Slices 03–06).
- SMB architecture mapping (Slice 07).
- Review / Approval workflow (Slice 09).
- Versioning / Revision history (Slice 10).
- JSON/Excel export (Slice 11).
- Azure DevOps integration (Slices 12–13).
- Any LLM/AI integration.
- Database / PostgreSQL.
- Frontend / React UI.
- Timestamps (`created_at` / `updated_at`).
- Delete or list-all operations.

## Domain

### `RequirementId`
- Frozen dataclass wrapping a `str`.
- Generated as `str(uuid.uuid4())` at the application boundary in `CreateRequirement`.

### `RequirementTitle`
- Frozen dataclass.
- Strips surrounding whitespace on construction.
- Raises `InvalidRequirementTitleError` if empty or blank after stripping.

### `RequirementDescription`
- Frozen dataclass.
- Strips surrounding whitespace on construction.
- Raises `InvalidRequirementDescriptionError` if empty or blank after stripping.

### `RequirementStatus`
- Enum with single value `DRAFT = "draft"`.

### `Requirement`
- Frozen dataclass (aggregate root).
- Fields: `id`, `title`, `description`, `status`.
- `update(title, description) -> Requirement` — returns a new immutable instance.
  ID and status are preserved. Value objects enforce invariants.

### Domain Errors
| Class | When raised |
|---|---|
| `InvalidRequirementTitleError` | Empty or blank title |
| `InvalidRequirementDescriptionError` | Empty or blank description |
| `RequirementNotFoundError` | ID not present in repository |
| `DuplicateRequirementError` | `add()` called with an existing ID |

## Application Use Cases

### `CreateRequirement`
- Input: `CreateRequirementInput(title: str, description: str)`
- Constructs domain value objects (validation fires here).
- Generates `RequirementId(str(uuid.uuid4()))`.
- Calls `repository.add()`.
- Returns the created `Requirement`.

### `GetRequirement`
- Input: `RequirementId`
- Calls `repository.get()`.
- Raises `RequirementNotFoundError` when the result is `None`.

### `UpdateRequirement`
- Input: `RequirementId`, `UpdateRequirementInput(title: str, description: str)`
- Loads existing requirement; raises `RequirementNotFoundError` if absent.
- Calls `Requirement.update(title, description)` — domain validates.
- Calls `repository.save()`.
- Returns updated `Requirement`.

## Ports

### `RequirementRepositoryPort`
Located at `application/ports/requirement_repository.py`.

```
add(requirement: Requirement) -> None
get(requirement_id: RequirementId) -> Requirement | None
save(requirement: Requirement) -> None
```

## Adapters

### `InMemoryRequirementRepository`
Located at `infrastructure/persistence/in_memory_requirement_repository.py`.

- Implements `RequirementRepositoryPort`.
- Backed by a private `dict[str, Requirement]`.
- `add()` raises `DuplicateRequirementError` on collision.
- `save()` overwrites the existing entry.
- A single instance is shared across requests within one process (module-level
  singleton in `interfaces/api/dependencies.py`).

## API

| Method | Path | Success | Error |
|---|---|---|---|
| `POST` | `/requirements` | `201 Created` | `422` on invalid title/description |
| `GET` | `/requirements/{id}` | `200 OK` | `404` if not found |
| `PUT` | `/requirements/{id}` | `200 OK` | `404` if not found; `422` on invalid update |

### Request/Response shapes

**POST body / PUT body**
```json
{
  "title": "High Speed Business Pro XGPON",
  "description": "The new bundles created with High Speed Internet..."
}
```

**Response**
```json
{
  "id": "<uuid>",
  "title": "High Speed Business Pro XGPON",
  "description": "The new bundles created with High Speed Internet...",
  "status": "draft"
}
```

## UI

**Not delivered.** `ROADMAP.md` specifies a UI for this slice; it was not
built, and at the time that was recorded only as "None" rather than raised as a
decision. Carried into Slice 4A, and tracked in the `AGENTS.md` §19 register.
`AGENTS.md` §15.1 now forbids this route.

Originally recorded as:
> None. FastAPI endpoints are the delivery mechanism for Slice 01.

## Business Rules

1. A requirement title must not be empty or consist only of whitespace.
2. A requirement description must not be empty or consist only of whitespace.
3. A new requirement always starts with status `DRAFT`.
4. Updating a requirement does not change its ID or status.
5. AI must not be called during requirement intake.
6. The stored description preserves the raw business text (only surrounding
   whitespace is trimmed; sentence content is never modified).

## Tests

| Test file | Coverage |
|---|---|
| `tests/unit/test_requirement_domain.py` | Value-object validation, aggregate creation, `update()` behaviour |
| `tests/unit/test_requirement_use_cases.py` | Create/Get/Update happy paths, not-found, invalid input |
| `tests/unit/test_in_memory_requirement_repository.py` | add/get, save/get, unknown-ID, duplicate-add |
| `tests/unit/test_requirements_api.py` | Full HTTP flow: 201, 200, 404, 422; health regression |
| `tests/architecture/test_architecture.py` | Import-linter contracts (unchanged from Slice 00) |

## Acceptance Criteria

- [x] Requirement domain model exists.
- [x] Requirement has a domain-specific ID.
- [x] Empty/blank title is rejected with a domain error.
- [x] Empty/blank description is rejected with a domain error.
- [x] Requirement starts as DRAFT.
- [x] Requirement can be updated while preserving invariants.
- [x] Domain contains no framework/infrastructure dependencies.
- [x] `CreateRequirement` use case exists.
- [x] `GetRequirement` use case exists.
- [x] `UpdateRequirement` use case exists.
- [x] Application uses `RequirementRepositoryPort`.
- [x] Application does not depend on concrete repository implementation.
- [x] `InMemoryRequirementRepository` exists and implements the port.
- [x] `POST /requirements` returns 201 Created.
- [x] `GET /requirements/{id}` returns 200 or 404.
- [x] `PUT /requirements/{id}` returns 200 or 404 or 422.
- [x] Unknown requirement returns 404.
- [x] Invalid input produces 422.
- [x] API schemas do not leak into Domain.
- [x] Domain dependency contracts still pass.
- [x] Application dependency contracts still pass.
- [x] No later-slice dependencies introduced.
- [x] `pytest` passes.
- [x] `ruff check .` passes.
- [x] `ruff format --check .` passes.
- [x] `mypy src tests` passes.
- [x] `lint-imports` passes.

## Validation Evidence

Environment: Python 3.14.5 (pythoncore-3.14-64) on Windows.

```
pytest -v
```
PASS — 44 passed, 1 warning in 0.65 s
```
tests/architecture/test_architecture.py        .  [  2%]
tests/unit/test_health.py                      .  [  4%]
tests/unit/test_in_memory_requirement_repository.py  ......  [ 18%]
tests/unit/test_requirement_domain.py          ..............  [ 50%]
tests/unit/test_requirement_use_cases.py       ..........  [ 72%]
tests/unit/test_requirements_api.py            ............  [100%]
```

```
ruff check .
```
PASS — All checks passed!

```
ruff format --check .
```
PASS — 42 files already formatted

```
mypy src tests
```
PASS — Success: no issues found in 33 source files

```
lint-imports
```
PASS — Contracts: 2 kept, 0 broken.
```
Domain must not depend on outer layers              KEPT
Application must not depend on infrastructure or interfaces  KEPT
```

Application import check:
```
python -c "from smb_requirement_agent.interfaces.api.main import app; print('OK')"
```
PASS — OK

## Deferred

- Timestamps (`created_at`, `updated_at`) — not needed by Slice 01.
- Requirement list / search / delete — not needed by Slice 01.
- Approval workflow — Slice 09.
- Requirement versioning — Slice 10.
- Durable persistence (PostgreSQL) — Slice 10.
- Frontend UI — later slice when UI is introduced.
- LLM integration — Slice 02 onwards.
- ADO publication — Slices 12–13.
