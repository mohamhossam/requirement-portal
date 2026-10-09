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
