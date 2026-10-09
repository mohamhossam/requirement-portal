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
- **Not yet.** KP's writes recorded against the service, and per-direction service credentials
  in place of the two shared tokens; both need platform-kernel.
