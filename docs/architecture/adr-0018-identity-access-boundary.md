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
