# Enhancement — Independent portals with optional links

Decision: ADR-0104. Plan: the
[portal separation fix plan](https://claude.ai/code/artifact/c9024453-b5a8-4c0d-9811-4f60abd78861).
Audit: the [gap report](https://claude.ai/code/artifact/7f2d0739-0bac-4f6f-9285-754176c5854f)
(2026-10-09), whose gap ids are used below.

## Goal

requirement-portal and knowledge-portal each deploy, sign in and start on their own. When both
are present and configured, they keep working together through the ADR-0099 ports.

## Phases

| Phase | Closes | Here | In knowledge-portal |
|---|---|---|---|
| 1. Record the decision | none | ADR-0104 | Copy of ADR-0098 to 0104 |
| 2. Peer optional at startup | C3, link half of M5 | No production check; link from `VITE_KNOWLEDGE_PORTAL_URL` | The same in reverse |
| 3. Knowledge portal deploys alone | C1, H7, M6, M7 | none | Own production compose, env and `config/llm.yaml` |
| 4. Knowledge portal owns sign-in | C2, H2, H3, M2 | RP-owned roles; KP writes attributed to the service; per-direction credentials | Own Keycloak client, audience and roles |
| 5. Own edge and hostname | C4, rest of M5 | none until cutover | Configurable base path and API prefix |
| Cutover | C1–C4 in production | Remove the knowledge services, realm entities and nginx locations | Goes live on its own host |
| 6. Retire the migration bridge | H4, H5, M8 | Drop the knowledge tables (PR #51 does this for empty ones) and the drop tool | Remove the import |
| 7. CI, contracts and cleanup | H6, M1, M3, M4, M7, L1, L2, L4 | Contract stub in CI; env renames; import-linter | Contract releases; import-linter |

## Phase 2 here (delivered with Phase 1)

- **Config.** `settings_validation.py` no longer requires `KNOWLEDGE_API_BASE_URL` in production.
  The URL and `REQUIREMENT_SERVICE_TOKEN` are still set together or not at all.
- **Composition.** Unchanged: with no knowledge portal configured, the existing stand-ins answer
  (`references/infrastructure/knowledge_client.py`). The empty catalogue reports "No architecture
  catalogue is connected".
- **UI.** `KNOWLEDGE_PORTAL_URL` comes from `VITE_KNOWLEDGE_PORTAL_URL`. Unset, it is the
  platform path `/knowledge/`, so today's deployment is unchanged. Empty, every link to the
  knowledge portal is hidden. `deploy/web/Dockerfile` passes it as a build argument. The
  repository owner allowed this non-presentation frontend change on 2026-10-09, as an exception
  to `CLAUDE.md`'s redesign rule.
- **Not in this phase.** A link-health endpoint apart from `/ready`, and the knowledge portal's
  side, which ships in knowledge-portal.

## Phase 4 here

Decided 2026-10-09 by the repository owner: one realm shared by both portals, and requirement
work's own roles in place of the knowledge portal's, with no transition.

- **Roles.** Architecture mapping checks `architecture_reader` and `architecture_maintainer`
  (`identity/application/ports/identity.py`), granted by the groups `architecture-readers` and
  `architecture-maintainers` in `deploy/keycloak/realm-requirement-ai.json`. `knowledge_reader`
  and `knowledge_maintainer` grant nothing here any more. People who map architecture must be
  in the new groups before this ships.
- **Links.** Who sees the links to the knowledge portal comes from `VITE_KNOWLEDGE_PORTAL_ROLE`.
  Unset, it is the portal's `knowledge_admin`, as before. Empty, everyone signed in sees them and
  the portal decides who gets in.
- **Realm.** The knowledge portal's client, audience, roles and groups stay in this realm file
  until the cutover; knowledge-portal now defines them itself (`deploy/keycloak/`).
- **Service credentials.** Each service can hold only its own client secret (platform-kernel
  1.1.0): this service's `requirement-service` client gets its tokens to the knowledge service,
  and `/internal` admits tokens granted to the knowledge service's client for the audience
  `requirement-internal`. Shared tokens keep working beside them. `docs/operations/deployment.md`,
  "Service credentials".
- **Writes by the knowledge portal.** Nudges, retirements, reinstatements and reindexing it asks
  for are recorded against the calling service (`service:knowledge`), keeping the admin's name as
  display text only (`interfaces/api/routes/internal.py`). The `actor_id` those requests carry is
  still accepted, so the internal contract is unchanged, but it is not recorded.

## Cutover here

Requirement work's manifest stops running the knowledge portal. It merges once the knowledge
portal runs from its own repository (`v0.2.0` or later), with its database restored there.

- **Manifest.** `deploy/compose.production.yaml` has no `knowledge-*` services, volume or
  settings file (`deploy/knowledge.env.example` is gone). `KNOWLEDGE_API_BASE_URL` and the
  service tokens move to `production.env`, optional. `drop-knowledge-tables` takes the
  knowledge database's address as an argument. `knowledge-import` stays with the last release
  that bundled the portal.
- **Peer network.** `deploy/compose.peer.yaml` joins `api` and `worker` to the external
  network `platform-internal`, where `api` is `requirement-api`; knowledge-portal's overlay of
  the same name joins it as `knowledge-api`.
- **Edge.** `/knowledge-api/` answers 404. `/knowledge/` redirects to `KNOWLEDGE_PORTAL_URL`
  with the rest of the path for one release, and answers 404 when it is unset. The web image
  refuses a value that is not an http(s) URL ending in `/`, since the path is appended. The
  same setting is built in for the links; the image's default is now empty, hiding them.
- **Realm.** `knowledge-spa`, the `knowledge_*` roles and the `knowledge-*` groups leave
  `deploy/keycloak/realm-requirement-ai.json`. A realm that already holds them keeps them.
- **Monitoring.** Prometheus scrapes requirement work's exporters only.
- **CI.** The deployment job checks out knowledge-portal at its pinned release, starts it from
  that repository's manifest and peer overlay, and runs the cross-portal checks through both
  edges (decided 2026-10-09 by the repository owner).
- **Not in this change.** Retiring the old knowledge volume, which waits on a quiet period
  and a backup, and Phase 6.

## Phase 7 here

Chosen 2026-10-09 by the repository owner to come before Phase 6, which waits on confirming
the production knowledge import.

- **Import boundary.** `.importlinter` forbids `knowledge_portal` anywhere in requirement work;
  the two meet only over HTTP.
- **Setting names.** Attachment scanning is configured as `ATTACHMENT_SCAN_MODE`,
  `ATTACHMENT_SCANNER_HOST`, `ATTACHMENT_SCANNER_PORT` and `ATTACHMENT_OCR_ARTIFACTS_PATH`.
  The former `LIBRARY_*` names are still read for one release; set both and they must agree.
- **Contracts.** knowledge-portal attaches its internal contract to each release. The CI
  deployment job checks that `contracts/knowledge-internal.openapi.json` is the one the pinned
  release (`KNOWLEDGE_IMAGE_TAG`) ships, so moving the pin means copying its contract too.
- **CI.** The deployment job runs the knowledge portal from its own repository (see
  "Cutover here"), so the planned contract stub is not needed.
