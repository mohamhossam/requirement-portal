# Slice 12 — ADO Publication

## Objective

Let the owner of a formally approved backlog preview it as Azure DevOps work items and publish it
there explicitly, through a publication port the application owns (ADR-0112).

This slice includes frontend feature work beyond the presentation-only rule in `CLAUDE.md`: a new
panel with its own query and mutation, like earlier feature slices during the redesign.

## User Outcome

An approved backlog can be previewed and explicitly published into Azure DevOps.

## In Scope

- A publication plan built from the approved revision's export document.
- `BacklogPublisherPort`, an Azure DevOps REST adapter, an offline fake and an "unavailable"
  publisher for deployments without ADO.
- ADO configuration outside the domain, including the squad-to-area-path mapping the
  ontology and impact implementation plan asks for.
- Preview and publish routes, and a publication panel on the Revisions page.

## Out of Scope

- Remembering what was published, duplicate prevention, update and retry: Slice 13.
- The Epic-closed hook back from ADO: the implementation plan's Phase 7.

## Domain

None new. The approval rules are the existing ones (`formal_final_approval`, a complete tree),
and AGENTS.md §9 keeps every ADO concept out of the domain. Slice 13 introduces the publication
domain model.

## Application Use Cases

- `PreviewPublication` (any member): the plan, its target and counts.
- `PublishBreakdown` (owner only): checks the confirmed approval fingerprint, creates items
  parents first, stops at the first refusal and reports each item as created, refused or not sent.

## Ports

- `BacklogPublisherPort` (`governance/application/ports/backlog_publisher.py`).

## Adapters

- `AzureDevOpsWorkItemPublisher`: REST API 7.1, one JSON Patch create per item with the parent
  link, title, HTML description, acceptance criteria, area, iteration and tags. No retry on create.
  Refusals, transport failures and responses without a usable id become `PublicationTargetError`.
- `FakeBacklogPublisher` (`ADO_PUBLISHER=fake`), `UnavailableBacklogPublisher` (the default).
- `AdoPublicationSettings`: `ADO_PUBLISHER`, `ADO_ORGANIZATION_URL`, `ADO_PROJECT`,
  `ADO_PERSONAL_ACCESS_TOKEN` (or `_FILE`), `ADO_AREA_PATH`, `ADO_ITERATION_PATH`,
  `ADO_EPIC_TYPE`, `ADO_FEATURE_TYPE`, `ADO_STORY_TYPE`, `ADO_DESCRIPTION_FIELD`,
  `ADO_ACCEPTANCE_CRITERIA_FIELD`, `ADO_TAGS`, `ADO_SQUAD_AREA_PATHS`, `ADO_TIMEOUT_SECONDS`.

## API

- `GET /requirements/{id}/revisions/{n}/publication`: target, counts and the item hierarchy, with
  where each item lands.
- `POST /requirements/{id}/revisions/{n}/publication` with `{"approval_fingerprint": …}`: the
  per-item report and outcome (`published`, `partial`, `failed`).
- Errors: `breakdown_revision_not_publishable` (409), `publication_confirmation_mismatch` (409),
  `publication_unavailable` (503), `publication_target_refused` (502, the catalogue entry for a
  refusal that ever escapes the per-item report).

## UI

`features/publication/PublicationPanel.tsx`, under the approved export on the Revisions page:
target project and facts, item counts, the hierarchy with each item's area path and owning squad,
and a Publish button for the owner that opens a confirmation dialog naming the project and item
count. After publishing, each row shows Created (with a link), Refused (with the reason) or Not
sent. Without a configured publisher the panel says publication is not set up.

## Business Rules

- Only a revision with a formal final approval and a Story under every Feature is publishable.
- Nothing is published without the owner's confirmation of that approval's fingerprint, so a
  request built from an older preview is refused.
- Parents are created before children and each child is linked to its parent.
- A Feature lands on the area path of the one squad owning all its impacted systems; with none or
  several it lands on the default area path. Stories follow their Feature.
- No automatic publication: generation and approval never call the publisher.

## Tests

- `tests/unit/governance/test_backlog_publication.py`: preview hierarchy and counts, owner
  publishes every item under its parent (fake publisher), stale confirmation and reviewer refused,
  unconfigured portal answers 503, partial and failed publication reporting, squad ownership rule,
  title cutting.
- `tests/unit/governance/test_azure_devops_publisher.py`: request URL, headers and JSON Patch
  (parent link, squad area path, HTML escaping, acceptance criteria), refusals with and without a
  message, non-JSON and id-less answers, unreachable service sent once.
- `tests/unit/test_ado_publication_settings.py`: defaults, environment parsing, token file,
  invalid settings fail the boot, adapter selection.
- `tests/unit/test_error_handlers.py`: the four new public errors and their statuses.
- `frontend/src/features/publication/PublicationPanel.test.tsx`: preview, confirmation before
  publishing, non-owner, not set up, partial report.

## Acceptance Criteria

- [x] An approved revision can be previewed with its target, counts and hierarchy.
- [x] Only the owner can publish, and only after confirming the previewed approval.
- [x] Parent and child links are created.
- [x] A partial failure is reported item by item and stops further sends.
- [x] The flow runs with no ADO account (`ADO_PUBLISHER=fake`).

## Validation Evidence

Run on 2026-10-10 against this branch:

- `pytest` — PASS (see the pull request's CI run for the authoritative result)
- `ruff check .` — PASS
- `ruff format --check .` — PASS
- `mypy src tests` — PASS
- `lint-imports` — PASS
- `cd frontend && npm run lint && npx vitest run && npm run build && npm run api:check` — PASS

## Deferred

- Slice 13: the publication record, external id mapping, duplicate prevention, update and retry.
- The ADO edition is assumed to support REST 7.1 (ADR-0112); an older Server needs the API version
  lowered.
