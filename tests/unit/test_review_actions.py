"""Action availability: the one statement of when review actions are allowed."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.value_objects import KnownFact
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.shared_kernel.actions import ActionAvailability
from smb_requirement_agent.shared_kernel.errors import InvalidGeneratedContentError
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, ReviewableGeneration
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import StaleReason
from tests.unit.breakdown.test_epic_domain import make_epic
from tests.unit.breakdown.test_feature_domain import make_feature
from tests.unit.breakdown.test_story_domain import make_story

NOW = datetime(2026, 1, 2, tzinfo=UTC)


class TestActionAvailability:
    def test_blocked_action_requires_a_reason(self) -> None:
        with pytest.raises(InvalidGeneratedContentError):
            ActionAvailability(allowed=False)

    def test_allowed_action_cannot_carry_a_reason(self) -> None:
        with pytest.raises(InvalidGeneratedContentError):
            ActionAvailability(allowed=True, reason="no")

    def test_blocked_action_cannot_ask_for_confirmation(self) -> None:
        with pytest.raises(InvalidGeneratedContentError):
            ActionAvailability(allowed=False, reason="no", confirmation="sure?")


class TestApproval:
    @pytest.mark.parametrize("make", [make_epic, make_feature, make_story])
    def test_generated_content_can_be_approved(
        self, make: Callable[[], ReviewableGeneration]
    ) -> None:
        assert make().approval_availability() == ActionAvailability.allow()

    @pytest.mark.parametrize(
        ("reason", "source"),
        [
            (StaleReason.REQUIREMENT_CHANGED, "requirement"),
            (StaleReason.EPIC_CHANGED, "Epic"),
            (StaleReason.FEATURE_CHANGED, "Feature"),
        ],
    )
    def test_stale_content_names_the_changed_source(self, reason: StaleReason, source: str) -> None:
        feature = make_feature().mark_stale(reason, NOW)

        assert feature.approval_availability() == ActionAvailability.block(
            f"Reconcile this Feature: its source {source} changed."
        )

    def test_an_approved_version_cannot_be_approved_again(self) -> None:
        epic = make_epic(GenerationStatus.APPROVED)

        availability = epic.approval_availability()

        assert not availability.allowed
        assert availability.reason == (
            "This Epic version is already approved. Edit or regenerate it before approving again."
        )


class TestRegeneration:
    def test_untouched_content_regenerates_without_confirmation(self) -> None:
        assert make_story().regeneration_availability() == ActionAvailability.allow()

    @pytest.mark.parametrize(
        ("status", "label"),
        [
            (GenerationStatus.EDITED, "edited"),
            (GenerationStatus.NEEDS_REVISION, "sent back for revision"),
            (GenerationStatus.APPROVED, "approved"),
        ],
    )
    def test_human_owned_content_must_be_confirmed(
        self, status: GenerationStatus, label: str
    ) -> None:
        availability = make_epic(status).regeneration_availability()

        assert availability.allowed
        assert availability.confirmation == (
            f"This Epic has been {label}. Regenerating replaces its content and human review state."
        )


class TestDownstreamGeneration:
    def test_only_an_approved_epic_can_be_decomposed(self) -> None:
        assert make_epic().decomposition_availability() == ActionAvailability.block(
            "Approve the Epic before decomposing it into Features."
        )
        assert make_epic(GenerationStatus.APPROVED).decomposition_availability().allowed

    def test_a_stale_approved_epic_cannot_be_decomposed(self) -> None:
        epic = make_epic(GenerationStatus.APPROVED).mark_stale(StaleReason.REQUIREMENT_CHANGED, NOW)

        assert epic.decomposition_availability() == ActionAvailability.block(
            "Reconcile the stale Epic before decomposing it into Features."
        )

    def test_stories_need_a_current_approved_feature(self) -> None:
        assert make_feature().story_availability() == ActionAvailability.block(
            "Approve the Feature before generating or changing its Stories."
        )
        approved = make_feature(GenerationStatus.APPROVED)
        assert approved.story_availability().allowed
        assert approved.mark_stale(StaleReason.EPIC_CHANGED, NOW).story_availability() == (
            ActionAvailability.block(
                "Reconcile the stale Feature before generating or changing its Stories."
            )
        )

    def test_an_epic_needs_confirmed_analysis(self) -> None:
        analysis = RequirementAnalysis(
            requirement_id=RequirementId("req-1"),
            known_facts=(KnownFact("Fact"),),
            constraints=(),
            business_rules=(),
            assumptions=(),
            open_questions=(),
            ambiguities=(),
            potential_dependencies=(),
        )

        assert analysis.epic_generation_availability() == ActionAvailability.block(
            "The analysis must be human-confirmed before an Epic can be generated."
        )
        confirmed = analysis.confirm(NOW, FAKE_ACTORS[0])
        assert confirmed.epic_generation_availability().allowed
