# Enhancement 8A.1 — Branded Keycloak login

> Status: **implemented locally; CI and real-provider staging acceptance pending**.

## Objective

Turn the generic Slice 8A OIDC redirect into an accessible branded login flow
with administrator-created Keycloak password accounts and explicitly linked
Microsoft Entra SSO identities.

## User Outcome

Signed-out users understand what workspace they are entering, can select their
authorized sign-in method, recover a password, and return to the exact internal
page they originally requested.

## In Scope

- Public responsive `/login` experience with Microsoft, password, failure,
  session-expiry, and fake-development states.
- Safe deep-link preservation and choice-specific OIDC authorization parameters.
- Keycloak realm bootstrap, durable local database, HTTPS, SMTP recovery,
  Microsoft broker, and matching login theme.
- Configuration, API contract, deployment documentation, ADR, and tests.

## Out of Scope

- Public registration, invitations, application-owned credentials, social
  identity providers, multi-issuer federation, or production credentials.
- Changing ownership policy, actor identifiers, application ports, or database schemas.

## Domain

- No change. Existing provider-neutral actor, ownership, reviewer, and authorization rules apply.

## Application Use Cases

- No change. `ResolveCurrentActor` continues resolving the authenticated bearer subject.

## Ports

- No change. `IdentityProviderPort` remains the only authentication boundary.

## Adapters

- The existing generic OIDC adapter validates Keycloak discovery/JWKS tokens.
- Optional Keycloak deployment owns local credentials, recovery, throttling,
  Microsoft brokering, and explicit account linking.

## API

- `GET /identity/config` additively returns ordered login choices with an ID,
  label, and bounded authorization-parameter map.
- Environment settings enable company SSO/password choices and configure the
  Keycloak broker alias.

## UI

- `/login` provides a branded split layout and a compact mobile layout.
- Protected deep links redirect through login and are restored only when the
  return value is same-origin and not an authentication route.
- Buttons announce redirect progress, reject repeat submission, and expose
  recoverable configuration, callback, provider, and session-expiry errors.
- Fake mode remains automatic for protected pages and provides a labelled test
  persona entry when `/login` is visited directly.

## Business Rules

- Accounts are administrator-provisioned. Keycloak self-registration and
  direct password grants are disabled.
- Microsoft access requires an explicit administrator-created identity link;
  email equality never links accounts automatically.
- Passwords and reset tokens never pass through or persist in this application.
- A deployed issuer/subject change requires an actor-mapping audit and explicit migration.

## Tests

- Settings and identity config contract coverage for both choices and invalid configuration.
- React tests for choice parameters, deep links, unsafe returns, duplicate submission,
  errors, fake personas, callbacks, logout/session renewal, and actor-state clearing.
- Deterministic browser coverage at desktop and responsive widths.
- JSON/Compose validation for Keycloak bootstrap; real Entra and SMTP flows are staged checks.

## Acceptance Criteria

- [x] Signed-out protected routes reach the branded page and preserve safe internal destinations.
- [x] Microsoft and password choices start PKCE redirects with the intended parameters.
- [x] Keycloak supplies branded credential, recovery, required-action, and error pages.
- [x] Public registration and automatic email linking are disabled.
- [x] Fake identity remains account-free and visibly labelled on `/login`.
- [x] All local backend and frontend quality gates are green.
- [ ] CI is green for the committed change.
- [ ] Staging Entra and SMTP acceptance is complete.

## Validation Evidence

### Review corrections — 2026-09-09

- Corrected the Compose bootstrap-admin variable names to `KC_BOOTSTRAP_ADMIN_*`.
- Enabled broker login and attached a required denial-only first-login flow so
  pre-linked Microsoft users can authenticate while unlinked identities cannot
  create users or link matching email addresses.
- Added regression checks for the Compose variable mapping and the broker's
  complete denial flow; documented how to update an already-persisted realm.
- This repairs the deployment implementation of ADR-0040. Domain, application,
  ports, API, and UI contracts are unchanged; no roadmap field is dropped.
- `.venv/Scripts/python.exe -m pytest tests/unit/test_keycloak_login_config.py` —
  PASS: `4 passed, 1 warning in 0.03s`.
- `.venv/Scripts/python.exe -m pytest` — PASS:
  `740 passed, 21 skipped, 1 warning in 49.84s`.
- `.venv/Scripts/ruff.exe check .` — PASS: `All checks passed!`.
- `.venv/Scripts/ruff.exe format --check .` — PASS: `429 files already formatted`.
  The initial check found one formatting issue in the new test; corrected before
  the final full gate run.
- `.venv/Scripts/mypy.exe src tests` — PASS:
  `Success: no issues found in 339 source files`.
- `.venv/Scripts/lint-imports.exe` — PASS: `Contracts: 6 kept, 0 broken.`
- `docker compose --env-file <temporary-validation-env> -f deploy/keycloak/compose.yaml config --quiet`
  — PASS: exit 0 with temporary non-secret values; temporary file removed.
  Docker emitted a warning that the user's Docker config file was not readable.
- Live Keycloak validation — NOT RUN: `docker info --format '{{.ServerVersion}}'`
  could not connect because the Docker engine named pipe was absent. Real Entra
  and SMTP acceptance still requires the staging services and credentials.
- CI — NOT RUN: fixes remain local and uncommitted.

### Original implementation evidence

- `.venv\Scripts\pytest.exe` — PASS: 738 passed, 21 skipped in 80.12s. Skips are
  opt-in external/PostgreSQL cases; one existing Starlette deprecation warning remains.
- `.venv\Scripts\ruff.exe check .` — PASS.
- `.venv\Scripts\ruff.exe format --check .` — PASS: 429 files formatted.
- `.venv\Scripts\mypy.exe src tests` — PASS: 339 source files.
- `.venv\Scripts\lint-imports.exe` — PASS: 6 contracts kept, 0 broken.
- `npm run api:check` — PASS; the existing Node `DEP0190` warning was emitted.
- `npm run lint` — PASS.
- `npm run typecheck` — PASS.
- `npm run test` — PASS: 24 files, 129 tests.
- `npm run build` — PASS: 1,928 modules transformed; Vite reported the existing
  advisory for a JavaScript chunk over 500 kB.
- `npm run test:smoke` with isolated API/UI ports — PASS: 18 desktop and responsive
  Chromium tests in 2.3 minutes, including the new login route in both layouts.
- `docker compose -f compose.yaml config --quiet` — PASS for the application stack.
- `docker compose --env-file validation.env -f compose.yaml config --quiet` from
  `deploy/keycloak` — PASS with temporary non-secret validation values; the file was removed.
- CI — NOT RUN for the uncommitted local change.
- Entra login and SMTP reset delivery — NOT RUN; require staging credentials and services.

## Deferred

- Production activation and real-provider acceptance require deployment secrets,
  a trusted hostname/certificate, Entra registration, and SMTP service.
