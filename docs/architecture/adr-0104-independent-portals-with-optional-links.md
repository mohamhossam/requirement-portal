# ADR 0104 — Independent portals with optional links

## Status

Accepted 2026-10-09 by the repository owner ("optional links"). It amends:
- ADR-0098, where this repository deploys the whole platform: the knowledge portal's services,
  its Keycloak client and roles, and its place behind this repository's edge;
- ADR-0099, where each service requires the other in production.

The rest of ADR-0098, ADR-0099 and ADR-0100 stands: separate repositories, separate databases,
the ports and contracts between the services, and the kernel.

The work is sequenced in `docs/slices/enhancement-independent-portals.md`. The gaps it closes
were found by an audit on 2026-10-09 and are numbered there (C1–C4, H1–H7, M1–M8, L1–L4).

## Context

ADR-0098 and ADR-0099 split the knowledge portal out as its own service with its own database,
but kept the two portals tied together at run time and at deployment:
- this repository's `deploy/compose.production.yaml` runs the knowledge portal's API, worker,
  web app, database, migrations and import;
- this repository's Keycloak realm holds the knowledge portal's client, audience and roles;
- this repository's nginx is the only way to reach the knowledge portal, under `/knowledge/`;
- each service refuses `APP_ENV=production` without the other's address.

So neither portal can be deployed, signed into or started on its own. The repository owner wants
the two to be independent applications that still work together when both are present.

## Decision

**Each portal deploys, signs in and starts on its own. The links between them are optional.**

- **Startup.** Neither service requires the other, in development or in production. With no
  peer configured, each answers as an unconnected peer would. Here that means no library, one
  empty catalogue version, nothing for the read-only viewers, and no links to the knowledge
  portal (`VITE_KNOWLEDGE_PORTAL_URL` empty). With a peer configured, the ports, contracts and
  event feeds of ADR-0099 apply unchanged.
- **Deployment.** The knowledge portal's production deployment lives in knowledge-portal. This
  repository's `deploy/` deploys requirement work only.
- **Sign-in.** The knowledge portal's Keycloak client, audience and roles are defined in
  knowledge-portal. This repository checks only roles it owns. The two may still share one
  Keycloak server.
- **Edge.** Each portal has its own web image and hostname. Links between them are absolute URLs
  from configuration, never same-origin paths.
- **Data.** Neither service holds the other's database credentials once the knowledge import is
  retired.

## Consequences

- **Either portal can ship and run alone.** A deployment without the knowledge portal is a
  supported configuration, not a development shortcut.
- **An unconnected portal must say so.** Screens that depend on the peer show that it is not
  connected rather than failing. An empty catalogue reports "No architecture catalogue is
  connected" as its uncertainty.
- **A two-host platform costs a little more.** Two hostnames, two CSPs, and a second set of
  Keycloak redirect URIs. Moving the knowledge portal signs its users in again once.
- **Cutover is coordinated once.** The knowledge portal's own deployment must be live before this
  repository removes its copy. `docs/slices/enhancement-independent-portals.md` gives the order.

## Alternatives Considered

- **Cut every runtime link.** Rejected by the repository owner: requirement work would lose
  architecture mapping, library grounding and historic prior art, and the knowledge portal its
  Requirement knowledge screens.
- **Keep the platform deployment here and only relax the startup check.** Rejected: the knowledge
  portal still could not be deployed or signed into without this repository.

## Amendment — An unreachable portal degrades, it does not fail (2026-10-09)

Slice `production-hardening` (PR 8). The text above stays as accepted; where it differs, this
amendment governs.

An optional link can be down as well as absent. Until now a connected knowledge portal that could
not be reached failed every analysis after its model call had been paid for, and failed unified
search outright.

- **Analysis keeps its primary result.** Reference grounding catches `ServiceUnavailableError`
  (including a failed client-credentials grant) and returns the primary analysis without reference
  proposals. The analysis records its *reference grounding*: `grounded`, `no_evidence`,
  `not_connected` (no portal configured) or `unavailable`. The review UI says references were not
  checked only for `unavailable`; with no portal connected there was nothing to check.
- **The reference port says whether a portal stands behind it** (`is_connected()`), so "nothing is
  published" and "nothing is connected" are not confused.
- **Unified search keeps its local half.** With the library unreachable it answers with
  Requirement hits only and sets `X-Reference-Library: unavailable`; the body keeps its shape.
- **Recorded only when known.** Analyses from before this amendment, and re-analysis rounds that do
  not consult the library, carry no grounding; their stored payloads and generation-context tokens
  are unchanged.

## Amendment — Mapping needs membership, not a reader role (2026-10-09)

Slice `production-hardening` (PR 4a, decided by the repository owner). The text above and the
earlier amendment stay as accepted; where they differ, this amendment governs.

The browser moved from the synchronous `POST /architecture-mapping` route to the durable mapping
jobs. The synchronous route checked only membership of the Requirement; the job routes also
required `architecture_reader`. The owner chose membership as the one rule:

- **Starting a mapping** needs membership of the Requirement, checked when it is queued and again
  when it runs. No role is required.
- **Reading mapping jobs** follows workspace-wide read access (ADR-0075).
- **Cancelling or retrying another person's job** still needs `architecture_maintainer`.
- **`architecture_reader` is retired.** Nothing checks it, so it and the `architecture-readers`
  group leave the realm and the offline personas.
