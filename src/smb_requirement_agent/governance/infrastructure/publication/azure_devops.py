"""Publish work items through the Azure DevOps REST API (Slice 12, ADR-0112).

One `POST …/_apis/wit/workitems/${type}` per item, as a JSON Patch document that sets the
title, description, area and iteration, tags the item with its marker, and links it under its
parent in the same request. An update (`PATCH …/workitems/{id}`) replaces only the title,
description and acceptance criteria; a WIQL query finds an item by its marker tag (Slice 13).
API version 7.1 is served by Azure DevOps Services and by Azure DevOps Server
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
import re
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
MARKER = re.compile(r"smb-rp-[0-9a-f]{20}")


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
        self._project_path = f"{self._organization}/{quote(configuration.project, safe='')}"
        self._target = PublicationTarget(
            key=f"azure-devops:{self._organization.lower()}/{configuration.project.lower()}",
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
        response = self._send(
            "POST",
            f"{self._project_path}/_apis/wit/workitems/${quote(kind, safe='')}",
            self._document(item, parent),
            "application/json-patch+json",
        )
        return self._published(item, response)

    def update(self, external_id: str, item: PlannedWorkItem) -> PublishedWorkItem:
        operations = [
            {"op": "add", "path": f"/fields/{name}", "value": value}
            for name, value in self._content(item)
        ]
        response = self._send(
            "PATCH",
            f"{self._project_path}/_apis/wit/workitems/{quote(external_id, safe='')}",
            operations,
            "application/json-patch+json",
        )
        return self._published(item, response)

    def find(self, item: PlannedWorkItem) -> PublishedWorkItem | None:
        if not MARKER.fullmatch(item.marker):
            raise PublicationTargetError("The item has no marker to look it up by.")
        # Checked above: `smb-rp-` and hex digits, nothing WIQL would read as syntax.
        query = (
            "SELECT [System.Id] FROM WorkItems WHERE [System.TeamProject] = @project "  # noqa: S608
            f"AND [System.Tags] CONTAINS '{item.marker}'"
        )
        response = self._send(
            "POST", f"{self._project_path}/_apis/wit/wiql", {"query": query}, "application/json"
        )
        try:
            body = response.json()
        except ValueError as exc:
            raise PublicationTargetError(
                "Azure DevOps answered with something other than JSON."
            ) from exc
        found = body.get("workItems") if isinstance(body, dict) else None
        if not isinstance(found, list):
            raise PublicationTargetError("Azure DevOps answered a query without work items.")
        if not found:
            return None
        if len(found) > 1:
            raise PublicationTargetError(
                f"Several Azure DevOps items carry the tag {item.marker}; remove the duplicates."
            )
        identifier = found[0].get("id") if isinstance(found[0], dict) else None
        if not _usable_id(identifier):
            raise PublicationTargetError("Azure DevOps answered without a work item id.")
        return PublishedWorkItem(item.key, str(identifier), self._edit_url(str(identifier)))

    def _send(self, method: str, url: str, body: Any, content_type: str) -> httpx.Response:
        try:
            response = self._http.request(
                method,
                url,
                params={"api-version": API_VERSION},
                content=json.dumps(body).encode(),
                headers={
                    "Authorization": self._authorization,
                    "Content-Type": content_type,
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
        return response

    def _edit_url(self, external_id: str) -> str:
        return f"{self._project_path}/_workitems/edit/{external_id}"

    def _content(self, item: PlannedWorkItem) -> list[tuple[str, str]]:
        """The fields a person reads, which an update replaces."""
        fields = [
            ("System.Title", item.title),
            (self._config.description_field, _description(item)),
        ]
        if item.acceptance_criteria:
            fields.append((self._config.acceptance_criteria_field, _acceptance_criteria(item)))
        return fields

    def _document(
        self, item: PlannedWorkItem, parent: PublishedWorkItem | None
    ) -> list[dict[str, Any]]:
        config = self._config
        fields = [
            *self._content(item),
            ("System.AreaPath", self._target.location_for(item.owning_squad_id)),
        ]
        if config.iteration_path:
            fields.append(("System.IterationPath", config.iteration_path))
        tags = (*config.tags, item.marker) if item.marker else config.tags
        if tags:
            fields.append(("System.Tags", "; ".join(tags)))
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
        if not _usable_id(identifier):
            raise PublicationTargetError("Azure DevOps answered without a work item id.")
        links = body.get("_links")
        html_link = links.get("html") if isinstance(links, dict) else None
        href = html_link.get("href") if isinstance(html_link, dict) else None
        if not isinstance(href, str) or not href.startswith(("https://", "http://")):
            href = self._edit_url(str(identifier))
        return PublishedWorkItem(key=item.key, external_id=str(identifier), url=href)


def _usable_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


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
