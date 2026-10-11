# ADR 0112 — Azure DevOps publication through a REST adapter behind a publisher port

## Status

Accepted 2026-10-10 with Slice 12 (`docs/slices/slice-12-ado-publication.md`). The ADO edition
was the open question ROADMAP.md recorded for Slices 12 and 13; this records the default chosen.

## Context

Slice 12 publishes a formally approved backlog to Azure DevOps. AGENTS.md §9 keeps every ADO
concept (organization, project, area and iteration paths, field names, work-item ids) out of the
domain, and §8 allows publication only from an explicitly approved revision, never automatically.
Which ADO edition the organization runs was not known, and publication must also run with no ADO
account at all (§4.5).

## Decision

- **Port.** `governance/application/ports/backlog_publisher.py` (`BacklogPublisherPort`) has two
  operations: `target()`, describing where items go for the preview, and `create(item, parent)`,
  which creates one work item linked under its parent. The application builds a neutral
  `PublicationPlan` (`governance/application/publication.py`) from the same approved-revision
  document export renders, so publication sends exactly what export would.
- **Adapter.** `governance/infrastructure/publication/azure_devops.py` calls REST API **7.1**,
  `POST {organization}/{project}/_apis/wit/workitems/${type}`, one JSON Patch document per item,
  with the parent link (`System.LinkTypes.Hierarchy-Reverse`) in the same request. 7.1 is served
  by Azure DevOps Services and by Azure DevOps Server 2022 and later, so `ADO_ORGANIZATION_URL`
  may name either. It authenticates with a personal access token (basic auth).
- **No retries on create.** A lost answer may hide a created item, so a create is sent once. A
  refusal or transport failure stops the publication; created items are reported, and nothing
  under the failed item is sent. Safe re-publication is Slice 13's.
- **Configuration** is in `AdoPublicationSettings` (`infrastructure/config/settings.py`), read
  from `ADO_*` variables: the publisher (`none`, `fake`, `azure_devops`), organization URL,
  project, token, default area path, iteration path, the three work-item type names, the
  description and acceptance-criteria field names, tags, and `ADO_SQUAD_AREA_PATHS`.
- **Squad boards.** A Feature whose impacted systems all belong to one squad carries that squad's
  id in the plan; the adapter maps it to the squad's area path, and its Stories follow it. A
  Feature with no squad, or several, goes to the default area path, because choosing one would be
  a guess.
- **Offline.** `ADO_PUBLISHER=none` (the default) answers the preview with
  `publication_unavailable` (503); `fake` keeps items in memory so the flow runs end to end.
- **Authorization.** Any member may preview; only the Requirement's owner may publish, and the
  request must carry the final approval's fingerprint from the preview.

## Consequences

- An organization on Azure DevOps Server 2020 or older needs `api-version=6.0`; that is a
  one-constant change in the adapter, not a design change.
- A personal access token belongs to a person. A service principal or managed identity would need
  another credential source in the adapter; nothing outside it changes.
- One request per item is slow for very large backlogs and has no transaction. The `$batch`
  endpoint was rejected for the same reason: it is not atomic either, and it hides which item
  failed.
- Slice 12 alone does not remember what it published; a second publish of the same revision
  creates new items. Slice 13 adds the mapping that prevents it.

## Alternatives Considered

- **The `azure-devops` Python SDK.** It pins old dependencies, adds a large surface for one
  endpoint, and still leaves validation of responses to us.
- **A durable outbox, like the knowledge handoff (ADR-0101).** Publication is an explicit,
  owner-confirmed action whose result the owner needs to see at once; a background queue would
  turn a refusal (such as a wrong area path) into a notification hours later. Slice 13 revisits
  this for retries.
- **Choosing a squad when several own a Feature's systems.** Any rule (first, most systems)
  invents an ownership decision people have not made.
