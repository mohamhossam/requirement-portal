# Slice 8A — Identity, Ownership, and Reviewer Assignment

> Status: **complete locally; CI pending push**. Every roadmap field is
> implemented and validated below.

## Objective

Add authenticated provider-neutral actors, Requirement ownership, reviewer
assignments, owner-scoped drafts, and truthful attribution without coupling the
core application to OIDC.

## User Outcome

Signed-in users can see who owns and reviews a Requirement, find work assigned
to them, and understand which actions they may take. Owners can transfer
ownership and manage reviewers; private drafts remain isolated.

## In Scope

- Opaque actors and immutable actor snapshots.
- Requirement owner/reviewer access with attributed change history.
- Owner-only analysis confirmation and assignment management.
- Creator ownership for Requirements/drafts and owner preservation on promotion.
- Explicit self-claim for legacy unowned Requirements and drafts.
- Fake identities plus generic OIDC discovery/JWKS bearer validation.
- Actor directory, current profile, access, draft ownership, revision, worklist,
  API, React, OpenAPI, and PostgreSQL persistence changes.

## Out of Scope

- Per-answer actor attribution and immutable analysis rounds (Slice 8B).
- Async jobs or identity notifications (Slice 8C).
- Story/full-backlog approval governance and comments (Slice 9).
- Provider directories, invitations, administrator roles, and multi-issuer federation.
- Reviewer collaboration on drafts or draft ownership transfer.

## Domain

- `ActorId`, `ActorProfile`, `ActorSnapshot`, `AssignmentRole`,
  `RequirementAssignment`, `AccessChange`, `RequirementAccess`, and
  `DraftOwnership` are provider-neutral.
- An access aggregate permits at most one owner, unique reviewers, and never the
  same actor in both roles.
- Transfer removes the recipient from reviewers and does not retain the prior
  owner automatically.
- `RequirementId` now rejects blank identity values.
- Analysis confirmations and breakdown decisions carry optional immutable actor
  snapshots so pre-identity records remain readable.

## Application Use Cases

- `ResolveCurrentActor` records the authenticated current profile in the known
  actor directory.
- `SearchKnownActors` returns bounded signed-in profiles.
- `RequirementAccessService` reads capabilities, claims legacy records,
  transfers ownership, and idempotently manages reviewers.
- Identity-aware Requirement/draft façades assign creators, isolate drafts, and
  preserve ownership during atomic promotion.
- Worklist policy supports owner and current-actor assignment scoping for both
  normal results and attention rows.

## Ports

- `IdentityProviderPort`
- `ActorDirectoryPort`
- `AccessRepositoryPort`
- Existing Requirement, draft, transaction, revision, and worklist ports are reused.

## Adapters

- `FakeIdentityProvider` supplies deterministic owner, reviewer, and observer personas.
- `OidcIdentityProvider` validates discovery/JWKS signatures, issuer, audience,
  expiry, subject, and an explicit asymmetric algorithm allowlist; unknown keys
  trigger one refresh.
- In-memory and PostgreSQL adapters store current actor profiles, Requirement
  access, and draft ownership. PostgreSQL migration `006_identity_access.sql`
  leaves existing records unowned.
- Access writes use optimistic history checks and Requirement-row locks;
  PostgreSQL transactions capture one final immutable revision.
- Snapshot readers accept historical Requirement/analysis/review payloads with
  no access or actor fields.

## API

- Public: `GET /health`, `GET /identity/config`.
- Authenticated identity: `GET /identity/me`, `GET /identity/actors`.
- Assignments: `GET /requirements/{id}/assignments`, ownership claim/transfer,
  and idempotent reviewer `PUT`/`DELETE` routes.
- Draft legacy claim: `POST /requirements/drafts/{id}/ownership/claim`.
- `GET /requirements` accepts `owner_id` and `assigned_to_me` and returns owner
  summaries/facets.
- Draft listing defaults to current-owner rows and supports an explicit unowned
  legacy view.
- Central translation returns `401` plus `WWW-Authenticate`, `403`, `404`,
  `409`, `422`, or `503` according to fault.

## UI

- Authentication gate with OIDC Authorization Code + PKCE callback, session
  storage, automatic renewal, bearer injection, return-path preservation, and logout.
- Fake mode displays an explicit persona selector; the header shows the actor.
- Worklist owner filter, owner/reviewer columns, and “Assigned to me.”
- Requirement access panel shows owner, reviewers, capabilities, access history,
  known-actor assignment, transfer, legacy claim, and explanatory denied states.
- Analysis confirmation is disabled for non-owners with the owner named.
- Confirmation and review-decision attribution show actor snapshots or the exact
  “actor unavailable for pre-identity record” legacy label.
- Draft resume/autosave/promotion are owner-only, and the dashboard exposes an
  explicit legacy-draft claim action. Mutation errors retain local form state.
- Protected PDFs are fetched with authorization before browser preview.

## Business Rules

- All business/data endpoints require an actor; only health and identity config are public.
- Existing source/backlog/review actions remain available to authenticated actors.
- Only the owner confirms analysis, transfers ownership, or changes reviewers.
- Assignments accept only known signed-in actors.
- `assigned_to_me` means owner or reviewer and scopes attention identically.
- A new actor profile/last-seen update never creates a Requirement revision.
- Generated content remains candidate content; identity does not imply approval.

## Tests

- Domain/application invariants, transfer/idempotency/denial, blank Requirement
  identity, draft isolation, legacy conflict, worklist assignment, and attribution.
- Fake identities and mocked OIDC discovery/JWKS covering valid, missing,
  expired, issuer/audience/signature/algorithm, rotation, and availability cases.
- API identity/assignment routes, owner capabilities, filters, protected routes,
  error mappings, and OpenAPI drift.
- UI auth/persona, bearer/401 handling, owner/assignment filters, assignment
  management, denied confirmation, legacy labels, and draft claim behavior.
- Existing PostgreSQL integration suite validates migrations and durable JSONB
  state when `TEST_DATABASE_URL` is configured.

## Acceptance Criteria

- [x] New Requirements and drafts are owned by their authenticated creator.
- [x] Legacy records are visibly unowned and explicitly, atomically claimable.
- [x] Owners can transfer ownership and idempotently manage known reviewers.
- [x] Non-owners cannot confirm analysis or manage assignments.
- [x] Worklist ownership, owner facets, and Assigned to me are actor-scoped.
- [x] Draft list/read/autosave/attachments/promotion are owner-only.
- [x] OIDC validation is provider-neutral and fake mode remains account-free.
- [x] Actor attribution and pre-identity fallback labels are visible.
- [x] OpenAPI and TypeScript contracts include every Slice 8A route/schema.

## Validation Evidence

- `.venv\Scripts\pytest.exe` — PASS: 452 passed, 7 skipped in 4.82s. The
  skipped cases are the opt-in PostgreSQL integration suite because
  `TEST_DATABASE_URL` is not configured; no local Docker daemon was available.
- `.venv\Scripts\ruff.exe check .` — PASS: all checks passed.
- `.venv\Scripts\ruff.exe format --check .` — PASS: 279 files
  already formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: no issues in 231
  source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 178 files and 815 dependencies
  analysed; 2 contracts kept, 0 broken.
- `npm.cmd run api:check` — PASS: generated OpenAPI TypeScript output has no
  drift. The existing Node `DEP0190` warning from the check script was emitted.
- `npm.cmd run lint` — PASS: ESLint clean.
- `npm.cmd run typecheck` — PASS.
- `npm.cmd run test` — PASS: 18 files, 78 tests in 6.67s.
- `npm.cmd run build` — PASS: 1,916 modules transformed; built in 308ms.
- `$env:SMOKE_API_PORT='8023'; $env:SMOKE_UI_PORT='4193'; npm.cmd run test:smoke`
  — PASS: 6 tests across desktop and responsive Chromium in 11.3s, including
  owner/reviewer assignment, denial, transfer, Assigned to me, and draft isolation.
- CI — NOT RUN for these uncommitted working-tree changes; pending push.

## Deferred

- Collaborative question history and answer attribution — Slice 8B.
- Async jobs and notifications — Slice 8C.
- Story and full-backlog approval governance — Slice 9.
