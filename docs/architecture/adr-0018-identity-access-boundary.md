# ADR 0018 — Provider-neutral identity and Requirement access boundary

## Status

Accepted

## Context

Requirement confirmation and review decisions were human-labelled without a
real actor, and resumable drafts or portfolio work could not be scoped to a
person. The application must support enterprise authentication without making
OIDC claims, access tokens, or a provider SDK part of the domain. It must also
remain fully usable offline and preserve pre-identity durable records.

## Decision

- Represent people in the domain with opaque `ActorId`, mutable current
  `ActorProfile`, and immutable `ActorSnapshot` values. Derive OIDC actor IDs
  deterministically from issuer plus subject; persist neither tokens nor raw
  claims.
- Model owner/reviewer state in a Requirement-scoped `RequirementAccess`
  aggregate. It owns the one-owner/no-owner-as-reviewer invariants and appends
  attributed access changes. Draft ownership is separate and fixed until
  promotion.
- Put authentication, known-actor lookup, and access persistence behind narrow
  application ports. Select fake or OIDC adapters only in
  `interfaces/api/container.py`.
- Validate OIDC bearer signatures with discovery/JWKS, issuer, audience,
  expiry, subject, and an explicit asymmetric algorithm allowlist. Refresh
  JWKS once when a key ID is unknown.
- Require authentication at router boundaries. Owner-only policy is enforced
  by application/domain collaborators for analysis confirmation, ownership
  transfer, reviewer management, and draft access—not by React controls.
- Preserve existing rows as unowned. Ownership is obtained only by an explicit
  atomic claim, and access changes are included in immutable Requirement
  revisions. Historical payloads without access or actor fields remain valid.
- Use Authorization Code + PKCE through `oidc-client-ts` in the SPA, retaining
  access tokens only in session storage. Fake mode uses a clearly labelled
  deterministic persona selector.

## Consequences

Identity providers can be replaced without changing the domain, offline
development needs no account, authorization remains testable and deterministic,
and reviewers can audit who confirmed or decided. Current profiles may change
while historical snapshots stay stable.

The service now depends on OIDC discovery/JWKS availability and needs key
rotation handling. Access is stored separately from Requirement content, so
multi-record creation, claim, promotion, and revision capture must share a
transaction. The known-actor directory intentionally contains only actors who
have signed in; invitations, administrators, provider directories, and
multi-issuer federation require later explicit decisions.

## Alternatives Considered

- Persist provider subjects or complete claims: rejected because it couples
  durable business state to one provider and retains unnecessary identity data.
- Put owner IDs directly on Requirement and draft entities: rejected because
  access history and reviewer roles have a separate lifecycle and would pollute
  the core requirement model.
- Enforce permissions only in routes or the SPA: rejected because other
  delivery mechanisms could bypass business authorization.
- Require OIDC in every environment: rejected because deterministic account-free
  local development and tests are a permanent project constraint.

## Amendment — Access tokens only, from this app's client, with clock leeway (2026-10-09)

Accepted with production hardening Phase 0 (`docs/slices/production-hardening.md`) and
platform-kernel v1.2.0. The default for authorized clients was chosen by the repository owner on
2026-10-09.

- **Access tokens only.** A token whose `typ` claim names another kind, such as Keycloak's ID or
  refresh tokens, is refused. A token with no `typ` claim is judged by the other checks.
- **Issued to this app's client.** A person's token must name `OIDC_CLIENT_ID` as its authorized
  party (`azp`), or a client the deployment lists in `OIDC_AUTHORIZED_PARTIES`.
  - The audience alone admitted any client in the realm that a mapper gives the API's audience.
    That includes a service's client-credentials token, which names no person.
  - A token for a command-line tool needs its client listed.
- **Clock leeway.** Expiry and issue times allow `OIDC_LEEWAY_SECONDS` (60) of clock difference
  with the issuer. This also applies to the knowledge service's granted tokens on `/internal`.
- **Keys keep being served.**
  - The signing keys are reloaded by one request at a time, outside the cache's lock. Other
    requests are checked against the keys already held.
  - A reload that fails keeps the last good keys and is tried again after 30 seconds, so a
    brief issuer outage no longer fails sign-ins.
  - A token signed with a key the cache lacks, while the issuer is unreachable, is still
    answered as "identity unavailable" (503), not as an invalid token.
