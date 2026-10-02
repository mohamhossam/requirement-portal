"""In-memory worklist snapshot adapter."""

from __future__ import annotations

from smb_requirement_agent.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.application.ports.ai_jobs import AiJobRepositoryPort
from smb_requirement_agent.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.application.ports.breakdown_repository import BreakdownRepositoryPort
from smb_requirement_agent.application.ports.breakdown_review_repository import (
    BreakdownReviewRepositoryPort,
)
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.ports.requirement_worklist import (
    CurrentWorklistProjectionPort,
    RequirementWorklistSnapshot,
)
from smb_requirement_agent.application.ports.story_repository import StoryRepositoryPort
from smb_requirement_agent.domain.requirement.value_objects import RequirementId


class InMemoryCurrentWorklistProjection(CurrentWorklistProjectionPort):
    """Memory mode computes its small worklist on read and needs no stored row."""

    def refresh(self, requirement_id: RequirementId) -> None:
        return None


class InMemoryRequirementWorklistSnapshotAdapter:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        analyses: RequirementAnalysisRepositoryPort,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
        revisions: BreakdownRepositoryPort,
        access: AccessRepositoryPort,
        audits: AnalysisAuditRepositoryPort,
        jobs: AiJobRepositoryPort,
        reviews: BreakdownReviewRepositoryPort,
    ) -> None:
        self._requirements = requirements
        self._analyses = analyses
        self._epics = epics
        self._features = features
        self._stories = stories
        self._revisions = revisions
        self._access = access
        self._audits = audits
        self._jobs = jobs
        self._reviews = reviews

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]:
        snapshots: list[RequirementWorklistSnapshot] = []
        for requirement in self._requirements.list_all():
            if requirement_ids is not None and requirement.id.value not in requirement_ids:
                continue
            analysis = self._analyses.get_by_requirement_id(requirement.id)
            epic = self._epics.get_by_requirement_id(requirement.id)
            features = tuple(self._features.get_by_epic_id(epic.id)) if epic is not None else ()
            stories = tuple(
                story
                for feature in features
                for story in self._stories.get_by_feature_id(feature.id)
            )
            timestamps = [
                revision.created_at
                for revision in self._revisions.list_requirement_revisions(requirement.id)
            ]
            timestamps.extend(
                revision.created_at
                for revision in self._revisions.list_breakdown_revisions(requirement.id)
            )
            if not timestamps:  # pragma: no cover - tracking repository invariant
                continue
            snapshots.append(
                RequirementWorklistSnapshot(
                    requirement=requirement,
                    analysis=analysis,
                    epic=epic,
                    features=features,
                    stories=stories,
                    updated_at=max(timestamps),
                    access=self._access.get_requirement(requirement.id),
                    questions=tuple(self._audits.list_questions(requirement.id)),
                    active_ai_operation=(
                        active[0].job.operation
                        if (
                            active := self._jobs.list_for_requirement(
                                requirement.id, active_only=True
                            )
                        )
                        else None
                    ),
                    review=self._reviews.get(requirement.id),
                )
            )
        return snapshots
