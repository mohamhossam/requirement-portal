"""The Azure DevOps work-item adapter against a recorded HTTP transport (Slice 12)."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import replace

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
    story_points_field="Microsoft.VSTS.Scheduling.StoryPoints",
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


def _fields(request: httpx.Request) -> dict[str, object]:
    return {
        op["path"]: op["value"]
        for op in json.loads(request.content)
        if op["path"].startswith("/fields/")
    }


def test_a_confirmed_size_is_sent_and_an_unsized_story_sends_none() -> None:
    publisher, requests = _publisher(lambda _: httpx.Response(200, json={"id": 42}))

    publisher.create(replace(STORY, story_points=5), PARENT)
    publisher.create(STORY, PARENT)

    assert _fields(requests[0])["/fields/Microsoft.VSTS.Scheduling.StoryPoints"] == 5
    assert "/fields/Microsoft.VSTS.Scheduling.StoryPoints" not in _fields(requests[1])


def test_a_blank_story_points_field_leaves_sizes_out() -> None:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": 42})

    publisher = AzureDevOpsWorkItemPublisher(
        replace(CONFIGURATION, story_points_field=""),
        httpx.Client(transport=httpx.MockTransport(record)),
    )
    publisher.create(replace(STORY, story_points=5), PARENT)

    assert not [path for path in _fields(requests[0]) if "StoryPoints" in path]


def test_a_changed_size_changes_what_republish_compares() -> None:
    assert replace(STORY, story_points=None).content_fingerprint() == STORY.content_fingerprint()
    assert replace(STORY, story_points=3).content_fingerprint() != STORY.content_fingerprint()
    assert (
        replace(STORY, story_points=3).content_fingerprint()
        != replace(STORY, story_points=5).content_fingerprint()
    )


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


# Reading states (ontology plan Phase 7) ---------------------------------------------------


def test_states_are_read_in_one_request_leaving_out_a_deleted_item() -> None:
    publisher, requests = _publisher(
        lambda _: httpx.Response(
            200,
            json={
                "count": 3,
                "value": [
                    {"id": 4712, "fields": {"System.State": "Closed"}},
                    None,
                    {"id": 4714, "fields": {"System.State": " Removed "}},
                    {"id": 4715, "fields": {}},
                ],
            },
        )
    )

    states = publisher.states(("4712", "4713", "4714", "4715"))

    assert states == {"4712": "Closed", "4714": "Removed"}
    (request,) = requests
    assert request.method == "GET"
    assert request.url.raw_path.split(b"?")[0] == b"/contoso/SMB%20Delivery/_apis/wit/workitems"
    assert dict(request.url.params) == {
        "ids": "4712,4713,4714,4715",
        "fields": "System.State",
        "errorPolicy": "omit",
        "api-version": "7.1",
    }
    assert request.headers["Authorization"].startswith("Basic ")


def test_states_are_read_two_hundred_at_a_time_and_none_asks_nothing() -> None:
    publisher, requests = _publisher(lambda _: httpx.Response(200, json={"value": []}))

    assert publisher.states(()) == {}
    assert requests == []
    publisher.states(tuple(str(number) for number in range(1, 402)))
    assert [len(request.url.params["ids"].split(",")) for request in requests] == [200, 200, 1]


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(401, json={"message": "Not authorised."}),
        httpx.Response(200, text="<html>sign in</html>"),
        httpx.Response(200, json={"items": []}),
    ],
)
def test_an_unusable_state_answer_is_a_target_error(answer: httpx.Response) -> None:
    publisher, _ = _publisher(lambda _: answer)

    with pytest.raises(PublicationTargetError):
        publisher.states(("4712",))


def test_a_state_read_refuses_an_id_that_is_not_a_number() -> None:
    publisher, requests = _publisher(lambda _: httpx.Response(200, json={"value": []}))

    with pytest.raises(PublicationTargetError):
        publisher.states(("4712&ids=1",))
    assert requests == []
