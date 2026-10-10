"""The Azure DevOps work-item adapter against a recorded HTTP transport (Slice 12)."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable

import httpx
import pytest

from smb_requirement_agent.governance.application.errors import PublicationTargetError
from smb_requirement_agent.governance.application.publication import (
    AcceptanceCriterionText,
    PlannedWorkItem,
    PublishedWorkItem,
    WorkItemKind,
)
from smb_requirement_agent.governance.infrastructure.publication.azure_devops import (
    AzureDevOpsConfiguration,
    AzureDevOpsWorkItemPublisher,
)

CONFIGURATION = AzureDevOpsConfiguration(
    organization_url="https://dev.azure.com/contoso/",
    project="SMB Delivery",
    personal_access_token="pat-secret",
    area_path="SMB Delivery",
    iteration_path="SMB Delivery\\PI 7",
    work_item_types={
        WorkItemKind.EPIC: "Epic",
        WorkItemKind.FEATURE: "Feature",
        WorkItemKind.STORY: "User Story",
    },
    description_field="System.Description",
    acceptance_criteria_field="Microsoft.VSTS.Common.AcceptanceCriteria",
    tags=("smb-requirement-portal",),
    squad_area_paths={"billing": "SMB Delivery\\Billing"},
    timeout_seconds=5.0,
)

STORY = PlannedWorkItem(
    key="story-1",
    kind=WorkItemKind.STORY,
    label="Story 1.1",
    title="As a customer, I want <b>bold</b> orders",
    description=(("Story", "As a customer & partner, I want <x>."), ("Empty", "  ")),
    acceptance_criteria=(AcceptanceCriterionText("a cart", "I pay", "the order <is> placed"),),
    parent_key="feature-1",
    owning_squad_id="billing",
    owning_squad_name="Billing",
)
PARENT = PublishedWorkItem("feature-1", "41", "https://dev.azure.com/contoso/x/41")


def _publisher(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[AzureDevOpsWorkItemPublisher, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    client = httpx.Client(transport=httpx.MockTransport(record))
    return AzureDevOpsWorkItemPublisher(CONFIGURATION, client), requests


def test_a_story_is_created_under_its_parent_on_its_squads_board() -> None:
    publisher, requests = _publisher(
        lambda _: httpx.Response(
            200,
            json={
                "id": 42,
                "_links": {"html": {"href": "https://dev.azure.com/contoso/web/42"}},
            },
        )
    )

    created = publisher.create(STORY, PARENT)

    assert created == PublishedWorkItem("story-1", "42", "https://dev.azure.com/contoso/web/42")
    (request,) = requests
    assert request.method == "POST"
    assert str(request.url) == (
        "https://dev.azure.com/contoso/SMB%20Delivery/_apis/wit/workitems/$User%20Story"
        "?api-version=7.1"
    )
    assert request.headers["Content-Type"] == "application/json-patch+json"
    expected = base64.b64encode(b":pat-secret").decode()
    assert request.headers["Authorization"] == f"Basic {expected}"
    operations = json.loads(request.content)
    fields = {op["path"]: op["value"] for op in operations if op["path"].startswith("/fields/")}
    assert fields["/fields/System.Title"] == "As a customer, I want <b>bold</b> orders"
    assert fields["/fields/System.Description"] == (
        "<p><strong>Story</strong><br>As a customer &amp; partner, I want &lt;x&gt;.</p>"
    )
    assert fields["/fields/System.AreaPath"] == "SMB Delivery\\Billing"
    assert fields["/fields/System.IterationPath"] == "SMB Delivery\\PI 7"
    assert fields["/fields/System.Tags"] == "smb-requirement-portal"
    assert fields["/fields/Microsoft.VSTS.Common.AcceptanceCriteria"] == (
        "<ol><li><strong>Given</strong> a cart<br><strong>When</strong> I pay<br>"
        "<strong>Then</strong> the order &lt;is&gt; placed</li></ol>"
    )
    (relation,) = [op for op in operations if op["path"] == "/relations/-"]
    assert relation["value"] == {
        "rel": "System.LinkTypes.Hierarchy-Reverse",
        "url": "https://dev.azure.com/contoso/_apis/wit/workItems/41",
    }


def test_an_epic_has_no_parent_link_and_lands_on_the_default_area() -> None:
    publisher, requests = _publisher(lambda _: httpx.Response(200, json={"id": 7}))
    epic = PlannedWorkItem(
        "epic-1",
        WorkItemKind.EPIC,
        "Epic",
        "Online",
        (("Outcome", "Faster"),),
        (),
        None,
        None,
        None,
    )

    created = publisher.create(epic, None)

    assert created.url == "https://dev.azure.com/contoso/SMB%20Delivery/_workitems/edit/7"
    operations = json.loads(requests[0].content)
    assert not [op for op in operations if op["path"] == "/relations/-"]
    paths = {op["path"]: op["value"] for op in operations}
    assert paths["/fields/System.AreaPath"] == "SMB Delivery"
    assert "/fields/Microsoft.VSTS.Common.AcceptanceCriteria" not in paths
    assert "/workitems/$Epic" in str(requests[0].url)


def test_the_target_describes_where_items_go() -> None:
    publisher, _ = _publisher(lambda _: httpx.Response(500))

    target = publisher.target()

    assert target.system == "Azure DevOps"
    assert target.project == "SMB Delivery"
    assert dict(target.details)["Organization"] == "https://dev.azure.com/contoso"
    assert target.location_for("billing") == "SMB Delivery\\Billing"
    assert "pat-secret" not in repr(target)


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (
            httpx.Response(401, text="<html>sign in</html>"),
            "Azure DevOps refused the credentials (401).",
        ),
        (
            httpx.Response(400, json={"message": "TF401320: Rule Error for field Area Path."}),
            "Azure DevOps refused the item (400). TF401320: Rule Error for field Area Path.",
        ),
        (
            httpx.Response(200, text="not json"),
            "Azure DevOps answered with something other than JSON.",
        ),
        (httpx.Response(200, json={"fields": {}}), "Azure DevOps answered without a work item id."),
        (httpx.Response(200, json={"id": True}), "Azure DevOps answered without a work item id."),
        (httpx.Response(200, json={"id": 0}), "Azure DevOps answered without a work item id."),
        (httpx.Response(200, json=[{"id": 3}]), "Azure DevOps answered without a work item id."),
    ],
)
def test_refusals_and_unusable_answers_are_publication_failures(
    response: httpx.Response, message: str
) -> None:
    publisher, _ = _publisher(lambda _: response)

    with pytest.raises(PublicationTargetError) as raised:
        publisher.create(STORY, PARENT)

    assert str(raised.value) == message


def test_an_unreachable_service_is_a_publication_failure_and_is_not_retried() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    publisher, requests = _publisher(refuse)

    with pytest.raises(PublicationTargetError, match="could not be reached"):
        publisher.create(STORY, PARENT)
    assert len(requests) == 1


def test_a_long_refusal_message_is_cut() -> None:
    publisher, _ = _publisher(lambda _: httpx.Response(400, json={"message": "x" * 1000}))

    with pytest.raises(PublicationTargetError) as raised:
        publisher.create(STORY, PARENT)

    assert len(str(raised.value)) < 400


MARKED = PlannedWorkItem(
    key=STORY.key,
    kind=STORY.kind,
    label=STORY.label,
    title=STORY.title,
    description=STORY.description,
    acceptance_criteria=STORY.acceptance_criteria,
    parent_key=STORY.parent_key,
    owning_squad_id=STORY.owning_squad_id,
    owning_squad_name=STORY.owning_squad_name,
    marker="smb-rp-0123456789abcdef0123",
)


def test_a_created_item_is_tagged_with_its_marker() -> None:
    publisher, requests = _publisher(lambda _: httpx.Response(200, json={"id": 42}))

    publisher.create(MARKED, PARENT)

    fields = {op["path"]: op["value"] for op in json.loads(requests[0].content)}
    assert fields["/fields/System.Tags"] == "smb-requirement-portal; smb-rp-0123456789abcdef0123"


def test_an_update_replaces_only_what_a_person_reads() -> None:
    publisher, requests = _publisher(lambda _: httpx.Response(200, json={"id": 42}))

    updated = publisher.update("42", MARKED)

    assert updated == PublishedWorkItem(
        "story-1", "42", "https://dev.azure.com/contoso/SMB%20Delivery/_workitems/edit/42"
    )
    (request,) = requests
    assert request.method == "PATCH"
    assert str(request.url) == (
        "https://dev.azure.com/contoso/SMB%20Delivery/_apis/wit/workitems/42?api-version=7.1"
    )
    assert request.headers["Content-Type"] == "application/json-patch+json"
    paths = [op["path"] for op in json.loads(request.content)]
    # Area, iteration, tags and the parent link stay as people left them in the tracker.
    assert paths == [
        "/fields/System.Title",
        "/fields/System.Description",
        "/fields/Microsoft.VSTS.Common.AcceptanceCriteria",
    ]


def test_find_looks_the_item_up_by_its_marker() -> None:
    publisher, requests = _publisher(
        lambda _: httpx.Response(200, json={"workItems": [{"id": 42, "url": "x"}]})
    )

    found = publisher.find(MARKED)

    assert found == PublishedWorkItem(
        "story-1", "42", "https://dev.azure.com/contoso/SMB%20Delivery/_workitems/edit/42"
    )
    (request,) = requests
    assert request.method == "POST"
    assert str(request.url) == (
        "https://dev.azure.com/contoso/SMB%20Delivery/_apis/wit/wiql?api-version=7.1"
    )
    query = json.loads(request.content)["query"]
    assert "[System.TeamProject] = @project" in query
    assert "[System.Tags] CONTAINS 'smb-rp-0123456789abcdef0123'" in query


def test_find_answers_none_when_no_item_carries_the_marker() -> None:
    publisher, _ = _publisher(lambda _: httpx.Response(200, json={"workItems": []}))

    assert publisher.find(MARKED) is None


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"workItems": [{"id": 1}, {"id": 2}]}, "Several Azure DevOps items"),
        ({"workItems": [{"id": "1"}]}, "without a work item id"),
        ({"value": []}, "without work items"),
    ],
)
def test_find_refuses_an_ambiguous_or_unusable_answer(
    body: dict[str, object], message: str
) -> None:
    publisher, _ = _publisher(lambda _: httpx.Response(200, json=body))

    with pytest.raises(PublicationTargetError, match=message):
        publisher.find(MARKED)


def test_find_never_sends_a_marker_it_did_not_make() -> None:
    publisher, requests = _publisher(lambda _: httpx.Response(200, json={"workItems": []}))
    tampered = PlannedWorkItem(
        key=STORY.key,
        kind=STORY.kind,
        label=STORY.label,
        title=STORY.title,
        description=STORY.description,
        acceptance_criteria=(),
        parent_key=None,
        owning_squad_id=None,
        owning_squad_name=None,
        marker="smb-rp-x' OR 1=1 --",
    )

    with pytest.raises(PublicationTargetError, match="no marker"):
        publisher.find(tampered)
    assert requests == []
