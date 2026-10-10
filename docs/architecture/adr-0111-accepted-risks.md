# ADR 0111 — Accepted risks

## Status

Accepted 2026-10-10 (production hardening PR 16). It records four risks the second
production-readiness review raised and the owner decided to accept rather than fix now.
Workspace-wide read access remains for the product owner to confirm for each deployment
(see 3).

## Context

The review's findings were either fixed (production hardening PRs 1–15) or accepted. An
accepted risk that is written down nowhere looks like an oversight to the next reviewer, and
can be widened by accident. Each one below says what the risk is, why it is accepted, what
limits it, and what would make it worth revisiting.

## Decision

### 1. Sign-in tokens are kept in `sessionStorage`

- **What.**
  - oidc-client-ts keeps the signed-in user in `sessionStorage`
    (`frontend/src/auth/AuthProvider.tsx`, `userStore`).
  - That user holds the access token and the refresh token, so script running in the page
    can read them.
- **Why accepted.**
  - A token-holding backend (a BFF with an HTTP-only session cookie) would remove this, but
    it is a new service with its own session store, CSRF defence and deployment.
  - The single-page app calling the API with a bearer token is the architecture today.
- **What limits it.**
  - **No injected script.** The Content-Security-Policy allows only the app's own scripts
    (`script-src 'self'` plus hashes), and React escapes rendered text.
  - **Short-lived access tokens.** They last 5 minutes (`docs/operations/identity-provider.md`).
  - **Per tab.** `sessionStorage` belongs to one tab and is cleared when the tab closes,
    unlike `localStorage`.
  - **Not in the logs.** Operational logs record a request's method, route and status, never its
    headers.
- **Revisit when:** a cross-site scripting finding, a requirement to keep sessions across
  tabs, or a deployment whose identity policy forbids tokens in browser storage.

### 2. The silent-renewal iframe

- **What.**
  - When the app has no refresh token, oidc-client-ts renews with a hidden iframe to the
    identity provider (`/auth/silent-callback`, `prompt=none`).
  - For that, the policy's `frame-src` allows the identity provider's origin.
- **Why accepted.**
  - With refresh tokens on for `requirement-spa`, the documented setting, the iframe is only
    the fallback.
  - Removing it would sign people out whenever the refresh token is missing.
- **What limits it.**
  - **Narrow allowance.** `frame-src` allows only the configured issuer origins
    (`CSP_IDENTITY_ORIGINS`), and the app itself sends `frame-ancestors 'none'`.
  - **Fails safe.** Where third-party cookies are blocked, the fallback fails and the person
    is asked to sign in again. No session is weakened to make it work.
- **Revisit when:** the identity provider stops issuing refresh tokens to the app, or
  browsers drop support for the `prompt=none` frame.

### 3. Every signed-in person can read the whole workspace (ADR-0075)

- **What.** Any signed-in user can read every submitted Requirement, its analysis, backlog,
  history and attachments, and find it in search. Only owners and reviewers can change it, and
  drafts stay private to their author.
- **Why accepted.** The product is one shared workspace with one worklist (ADR-0075).
- **What limits it.**
  - **Authentication.** The identity provider decides who signs in at all.
  - **Fixed rules, under test.** Write access and draft privacy are enforced and tested
    (`tests/unit/test_read_visibility.py`).
- **For the product owner to confirm for each deployment.** A deployment that holds
  Requirements some signed-in people must not read needs per-Requirement read access. That is
  a product change, not a setting.
- **Revisit when:** a deployment brings in people who should see only part of the workspace.

### 4. English only

- **What.**
  - The interface, its messages, error texts and generated content are in English.
  - The page declares `lang="en"`.
  - There is no translation layer.
- **Why accepted.** The pilot's users work in English. A translation layer touches every
  screen, and the UI redesign (CLAUDE.md) is still under way.
- **What limits it.** Requirement text in another language is stored and shown as written.
- **Revisit when:** a deployment's users need another language, ideally after the redesign
  settles the screens.

## Consequences

- **Kept up to date.** A reviewer can find each accepted risk and its limits in one place.
  `SECURITY.md` points here.
- **Changed by amendment.** Narrowing any of these risks (a BFF, per-Requirement read
  access, a translation layer) is a decision of its own. It amends this ADR rather than
  quietly removing an entry.
- **Still open: the licence.** The owner left the repository without a LICENSE file for now.
  Without one, the code is not licensed for reuse.

## Alternatives Considered

- **Fix all four before the pilot.** Rejected: each is a project of its own, and the limits
  above keep the pilot's exposure small.
- **Leave them in the review findings only.** Rejected: findings are a snapshot; this record
  is where the next reviewer looks.
