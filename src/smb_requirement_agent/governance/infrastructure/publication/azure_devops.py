"""Publish work items through the Azure DevOps REST API (Slice 12, ADR-0112).

One `POST …/_apis/wit/workitems/${type}` per item, as a JSON Patch document that sets the
title, description, area and iteration, and links the item under its parent in the same
request. API version 7.1 is served by Azure DevOps Services and by Azure DevOps Server
2022 and later, so the organization URL may name either (`https://dev.azure.com/org` or a
Server collection).

A create is never retried: an answer lost on the way back may hide a created item, and
sending it again would duplicate it. Every refusal or transport failure becomes
`PublicationTargetError`, and a response with no usable work-item id is one too.
"""

from __future__ import annotations

import base64
import html
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from smb_requirement_agent.governance.application.errors import PublicationTargetError
from smb_requirement_agent.governance.application.publication import (
    PlannedWorkItem,
    PublicationTarget,
    PublishedWorkItem,
    SquadLocation,
    WorkItemKind,
)

API_VERSION = "7.1"
PARENT_LINK = "System.LinkTypes.Hierarchy-Reverse"
# Enough of a refusal for a person to act on, without echoing a whole error page.
MESSAGE_LIMIT = 300


@dataclass(frozen=True)
class AzureDevOpsConfiguration:
    organization_url: str
    project: str
    personal_access_token: str
    area_path: str
    iteration_path: str | None
    work_item_types: Mapping[WorkItemKind, str]
    description_field: str
    acceptance_criteria_field: str
    tags: tuple[str, ...]
    # Squad id to the area path of that squad's board.
    squad_area_paths: Mapping[str, str]
    timeout_seconds: float


class AzureDevOpsWorkItemPublisher:
    def __init__(self, configuration: AzureDevOpsConfiguration, http: httpx.Client) -> None:
        self._config = configuration
        self._organization = configuration.organization_url.rstrip("/")
        self._http = http
        token = base64.b64encode(f":{configuration.personal_access_token}".encode()).decode()
        self._authorization = f"Basic {token}"
        self._target = PublicationTarget(
            system="Azure DevOps",
            project=configuration.project,
            default_location=configuration.area_path,
            details=(
                ("Organization", self._organization),
                ("Iteration", configuration.iteration_path or "The project's default"),
                (
                    "Work item types",
                    ", ".join(configuration.work_item_types[kind] for kind in WorkItemKind),
                ),
            ),
            squad_locations=tuple(
                SquadLocation(squad_id, path)
                for squad_id, path in sorted(configuration.squad_area_paths.items())
            ),
        )

    def target(self) -> PublicationTarget:
        return self._target

    def create(self, item: PlannedWorkItem, parent: PublishedWorkItem | None) -> PublishedWorkItem:
        kind = self._config.work_item_types[item.kind]
        url = (
            f"{self._organization}/{quote(self._config.project, safe='')}"
            f"/_apis/wit/workitems/${quote(kind, safe='')}"
        )
        try:
            response = self._http.post(
                url,
                params={"api-version": API_VERSION},
                content=json.dumps(self._document(item, parent)).encode(),
                headers={
                    "Authorization": self._authorization,
                    "Content-Type": "application/json-patch+json",
                    "Accept": "application/json",
                },
                timeout=self._config.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise PublicationTargetError(
                f"Azure DevOps could not be reached ({type(exc).__name__})."
            ) from exc
        if response.status_code >= 400:
            raise PublicationTargetError(_refusal(response))
        return self._published(item, response)

    def _document(
        self, item: PlannedWorkItem, parent: PublishedWorkItem | None
    ) -> list[dict[str, Any]]:
        config = self._config
        fields: list[tuple[str, str]] = [
            ("System.Title", item.title),
            (config.description_field, _description(item)),
            ("System.AreaPath", self._target.location_for(item.owning_squad_id)),
        ]
        if config.iteration_path:
            fields.append(("System.IterationPath", config.iteration_path))
        if item.acceptance_criteria:
            fields.append((config.acceptance_criteria_field, _acceptance_criteria(item)))
        if config.tags:
            fields.append(("System.Tags", "; ".join(config.tags)))
        operations: list[dict[str, Any]] = [
            {"op": "add", "path": f"/fields/{name}", "value": value} for name, value in fields
        ]
        if parent is not None:
            operations.append(
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {
                        "rel": PARENT_LINK,
                        "url": f"{self._organization}/_apis/wit/workItems/{parent.external_id}",
                    },
                }
            )
        return operations

    def _published(self, item: PlannedWorkItem, response: httpx.Response) -> PublishedWorkItem:
        try:
            body = response.json()
        except ValueError as exc:
            raise PublicationTargetError(
                "Azure DevOps answered with something other than JSON."
            ) from exc
        identifier = body.get("id") if isinstance(body, dict) else None
        if not isinstance(identifier, int) or isinstance(identifier, bool) or identifier < 1:
            raise PublicationTargetError("Azure DevOps answered without a work item id.")
        links = body.get("_links")
        html_link = links.get("html") if isinstance(links, dict) else None
        href = html_link.get("href") if isinstance(html_link, dict) else None
        if not isinstance(href, str) or not href.startswith(("https://", "http://")):
            project = quote(self._config.project, safe="")
            href = f"{self._organization}/{project}/_workitems/edit/{identifier}"
        return PublishedWorkItem(key=item.key, external_id=str(identifier), url=href)


def _refusal(response: httpx.Response) -> str:
    detail = ""
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and isinstance(body.get("message"), str):
        detail = " ".join(body["message"].split())[:MESSAGE_LIMIT]
    if response.status_code in (401, 403):
        prefix = f"Azure DevOps refused the credentials ({response.status_code})."
    else:
        prefix = f"Azure DevOps refused the item ({response.status_code})."
    return f"{prefix} {detail}".strip()


def _description(item: PlannedWorkItem) -> str:
    return "".join(
        f"<p><strong>{html.escape(label)}</strong><br>{html.escape(text)}</p>"
        for label, text in item.description
        if text.strip()
    )


def _acceptance_criteria(item: PlannedWorkItem) -> str:
    rows = "".join(
        "<li>"
        f"<strong>Given</strong> {html.escape(criterion.given)}<br>"
        f"<strong>When</strong> {html.escape(criterion.when)}<br>"
        f"<strong>Then</strong> {html.escape(criterion.then)}"
        "</li>"
        for criterion in item.acceptance_criteria
    )
    return f"<ol>{rows}</ol>"
