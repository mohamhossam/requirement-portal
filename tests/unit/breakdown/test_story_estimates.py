"""Story point suggestions and confirmed sizes (ADR-0121)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.breakdown.application.errors import StoryEstimationError
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.errors import InvalidStoryContentError
from smb_requirement_agent.breakdown.domain.story.estimate import (
    EstimateBasis,
    EstimateSuggestion,
    FeatureEstimateSuggestions,
    StoryEstimate,
    StoryPoints,
    estimate_total,
)
from smb_requirement_agent.breakdown.domain.story.value_objects import StoryId
from smb_requirement_agent.breakdown.infrastructure.backlog_payloads import (
    story_from_payload,
    story_to_payload,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.story_estimate_schema import (
    StoryEstimatesSchema,
    StorySizeSchema,
)
from smb_requirement_agent.breakdown.infrastructure.llm.story_estimate_mapping import (
    LabelledStories,
    request_complete_estimates,
)
from smb_requirement_agent.governance.domain.review.fingerprints import artifact_fingerprint
from smb_requirement_agent.interfaces.api.container import build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.shared_kernel.actors import ActorId, ActorSnapshot
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, Provenance
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.job_driver import run_job
from tests.unit.workflow_helpers import generate_story_tree

NOW = datetime(2026, 10, 30, tzinfo=UTC)
ACTOR = ActorSnapshot(ActorId("ba-1"), "Business Analyst")


def _estimate(points: int, basis: EstimateBasis = EstimateBasis.TEAM_ENTERED) -> StoryEstimate:
    return StoryEstimate(StoryPoints(points), basis, ACTOR, NOW)


def _story(client: TestClient) -> Any:
    """A real generated Story, decoded into the domain."""
    requirement_id, feature_id, stories = generate_story_tree(client)
    container = client.app.state.container  # type: ignore[attr-defined]
    return container.story_repository.get(FeatureId(feature_id), StoryId(str(stories[0]["id"])))


# --- domain ------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 4, 21, True])
def test_story_points_accept_only_the_relative_scale(value: int) -> None:
    with pytest.raises(InvalidStoryContentError, match="one of 1, 2, 3, 5, 8, 13"):
        StoryPoints(value)


def test_a_suggestion_must_explain_itself_even_without_a_size() -> None:
    assert EstimateSuggestion(StoryId("s"), None, "  Split it first. ").rationale == (
        "Split it first."
    )
    with pytest.raises(InvalidStoryContentError, match="explain"):
        EstimateSuggestion(StoryId("s"), StoryPoints(3), "  ")


def test_suggestions_need_one_entry_per_story() -> None:
    provenance = Provenance(NOW, "fake", "v1")
    one = EstimateSuggestion(StoryId("s"), StoryPoints(3), "Small.")
    with pytest.raises(InvalidStoryContentError, match="exactly one"):
        FeatureEstimateSuggestions(FeatureId("f"), "fp", (one, one), provenance)
    with pytest.raises(InvalidStoryContentError, match="exactly one"):
        FeatureEstimateSuggestions(FeatureId("f"), "fp", (), provenance)


def test_totals_count_only_confirmed_sizes() -> None:
    total = estimate_total((_estimate(5), None, _estimate(3)))
    assert (total.points, total.sized, total.stories, total.unsized) == (8, 2, 3, 1)


def test_sizing_revokes_approval_and_replaying_it_does_not(client: TestClient) -> None:
    story = replace(_story(client), status=GenerationStatus.APPROVED)

    sized = story.sized(_estimate(5))
    assert sized.status is GenerationStatus.EDITED
    assert sized.version == story.version + 1
    assert sized.architecture == story.architecture
    # The same size again, even recorded differently, is not a new decision.
    assert sized.sized(_estimate(5, EstimateBasis.ACCEPTED_SUGGESTION)) is sized
    assert story.sized(None) is story


def test_fingerprint_covers_a_size_but_not_its_absence(client: TestClient) -> None:
    story = _story(client)
    unsized = artifact_fingerprint(story)

    assert artifact_fingerprint(replace(story, estimate=None)) == unsized
    assert artifact_fingerprint(replace(story, estimate=_estimate(5))) != unsized
    # Who decided, and how, is not what approval attests to.
    assert artifact_fingerprint(replace(story, estimate=_estimate(5))) == artifact_fingerprint(
        replace(story, estimate=_estimate(5, EstimateBasis.ACCEPTED_SUGGESTION))
    )


def test_payload_leaves_an_unsized_story_unchanged_and_round_trips_a_size(
    client: TestClient,
) -> None:
    story = _story(client)
    assert "estimate" not in story_to_payload(story)

    sized = replace(story, estimate=_estimate(8, EstimateBasis.ACCEPTED_SUGGESTION))
    assert story_from_payload(story_to_payload(sized)) == sized


# --- adapter mapping -------------------------------------------------------------------------


def _reply(*sizes: tuple[str, int | None, str]) -> StoryEstimatesSchema:
    return StoryEstimatesSchema(
        sizes=[
            StorySizeSchema.model_validate({"story": label, "points": points, "rationale": why})
            for label, points, why in sizes
        ]
    )


def test_mapper_returns_one_suggestion_per_story_in_order(client: TestClient) -> None:
    first = _story(client)
    second = replace(first, id=StoryId("second"))

    result = request_complete_estimates(
        lambda labelled: _reply(("S2", None, "Needs a refund rule."), ("S1", 3, " Smallest. ")),
        (first, second),
    )

    assert [(item.story_id, item.points, item.rationale) for item in result] == [
        (first.id, StoryPoints(3), "Smallest."),
        (second.id, None, "Needs a refund rule."),
    ]


def test_mapper_asks_again_only_for_stories_left_out_or_unexplained(client: TestClient) -> None:
    first = _story(client)
    second = replace(first, id=StoryId("second"))
    asked: list[list[str]] = []

    def request(labelled: LabelledStories) -> StoryEstimatesSchema:
        asked.append([label for label, _ in labelled])
        if len(asked) == 1:
            return _reply(("S1", 2, "Small."), ("S2", 5, "   "))
        return _reply(("S2", 5, "Twice the first."))

    result = request_complete_estimates(request, (first, second))

    assert asked == [["S1", "S2"], ["S2"]]
    assert [item.points for item in result] == [StoryPoints(2), StoryPoints(5)]


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (_reply(("S9", 3, "Unknown.")), "unknown Story"),
        (_reply(("S1", 3, "Once."), ("S1", 5, "Twice.")), "twice"),
        (_reply(), "without a usable size"),
    ],
)
def test_mapper_rejects_unusable_replies(
    client: TestClient, reply: StoryEstimatesSchema, message: str
) -> None:
    story = _story(client)
    with pytest.raises(StoryEstimationError, match=message):
        request_complete_estimates(lambda labelled: reply, (story,))


# --- API ---------------------------------------------------------------------------------------


def _suggest(client: TestClient, requirement_id: str, feature_id: str) -> dict[str, Any]:
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    run = run_job(
        client,
        requirement_id,
        "suggest_story_estimates",
        context_token=client.get(base).json()["generation_context_token"],
        feature_id=feature_id,
    )
    assert run.succeeded, run.job
    response = client.get(f"{base}/estimate-suggestions")
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


def test_suggest_accept_and_total_sizes_through_the_api(client: TestClient) -> None:
    requirement_id, feature_id, stories = generate_story_tree(client)
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    assert client.get(base).json()["estimate_total"] == {
        "points": 0,
        "sized": 0,
        "stories": len(stories),
    }

    suggestions = _suggest(client, requirement_id, feature_id)
    assert suggestions["fresh"] is True
    assert suggestions["provenance"]["model"] == "fake"
    assert {item["story_id"] for item in suggestions["suggestions"]} == {
        item["id"] for item in stories
    }

    story = stories[0]
    suggested = next(item for item in suggestions["suggestions"] if item["story_id"] == story["id"])
    accepted = client.put(
        f"{base}/{story['id']}/estimate",
        json={
            "points": suggested["points"],
            "basis": "accepted_suggestion",
            "expected_version": story["version"],
        },
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["estimate"]["points"] == suggested["points"]
    assert body["estimate"]["basis"] == "accepted_suggestion"
    assert body["estimate"]["decided_by"]["id"]
    assert body["status"] == "edited"
    assert body["content_fingerprint"] != story["content_fingerprint"]

    total = client.get(base).json()["estimate_total"]
    assert total == {"points": suggested["points"], "sized": 1, "stories": len(stories)}
    # A size does not change what the AI read, so the suggestions stay current.
    assert client.get(f"{base}/estimate-suggestions").json()["fresh"] is True

    cleared = client.put(
        f"{base}/{story['id']}/estimate",
        json={"points": None, "expected_version": body["version"]},
    )
    assert cleared.status_code == 200
    assert cleared.json()["estimate"] is None


def test_an_accepted_size_must_be_the_current_suggestion(client: TestClient) -> None:
    requirement_id, feature_id, stories = generate_story_tree(client)
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    story = stories[0]

    # No suggestion yet: claiming one is refused, entering a size is not.
    refused = client.put(
        f"{base}/{story['id']}/estimate",
        json={"points": 5, "basis": "accepted_suggestion", "expected_version": story["version"]},
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "story_estimate_suggestions_conflict"

    suggestions = _suggest(client, requirement_id, feature_id)
    suggested = next(item for item in suggestions["suggestions"] if item["story_id"] == story["id"])
    other = next(value for value in (1, 2, 3, 5, 8, 13) if value != suggested["points"])
    mismatched = client.put(
        f"{base}/{story['id']}/estimate",
        json={
            "points": other,
            "basis": "accepted_suggestion",
            "expected_version": story["version"],
        },
    )
    assert mismatched.status_code == 409

    entered = client.put(
        f"{base}/{story['id']}/estimate",
        json={"points": other, "expected_version": story["version"]},
    )
    assert entered.status_code == 200
    assert entered.json()["estimate"]["basis"] == "team_entered"


def test_suggestions_go_out_of_date_when_story_content_changes(client: TestClient) -> None:
    requirement_id, feature_id, stories = generate_story_tree(client)
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    _suggest(client, requirement_id, feature_id)
    story = stories[0]

    edited = client.put(
        f"{base}/{story['id']}",
        json={
            "role": story["role"],
            "action": f"{story['action']} and export it",
            "value": story["value"],
            "acceptance_criteria": story["acceptance_criteria"],
            "kind": story["kind"],
            "expected_version": story["version"],
        },
    )
    assert edited.status_code == 200, edited.text

    assert client.get(f"{base}/estimate-suggestions").json()["fresh"] is False


def test_size_errors_map_to_their_status_codes(client: TestClient) -> None:
    requirement_id, feature_id, stories = generate_story_tree(client)
    base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
    story = stories[0]

    missing = client.get(f"{base}/estimate-suggestions")
    assert missing.status_code == 404
    assert missing.json()["code"] == "story_estimate_suggestions_not_found"

    off_scale = client.put(
        f"{base}/{story['id']}/estimate", json={"points": 4, "expected_version": story["version"]}
    )
    assert off_scale.status_code == 422
    assert off_scale.json()["code"] == "invalid_story_content"

    stale_version = client.put(
        f"{base}/{story['id']}/estimate",
        json={"points": 3, "expected_version": int(str(story["version"])) + 5},
    )
    assert stale_version.status_code == 409


class _FailingEstimator:
    model = "broken"
    prompt_version = "broken-v1"

    def suggest(self, stories: object, *, evidence: object) -> tuple[EstimateSuggestion, ...]:
        raise StoryEstimationError("The provider returned no usable sizes.")


def test_a_failed_sizing_pass_fails_the_job_as_a_provider_error() -> None:
    container = build_container(FAKE_PROVIDER_SETTINGS, story_estimator=_FailingEstimator())
    with TestClient(create_app(lambda: container)) as client:
        requirement_id, feature_id, _ = generate_story_tree(client)
        base = f"/requirements/{requirement_id}/features/{feature_id}/stories"
        run = run_job(
            client,
            requirement_id,
            "suggest_story_estimates",
            context_token=client.get(base).json()["generation_context_token"],
            feature_id=feature_id,
        )
        assert run.job is not None
        assert run.job["status"] == "failed"
        assert run.job["failure"]["code"] == "story_estimation"
        assert client.get(f"{base}/estimate-suggestions").status_code == 404
