"""Typed compatibility names for focused repository integration fixtures."""

from __future__ import annotations

from smb_kernel.persistence.connector import (
    DirectPostgresConnector,
)

from smb_requirement_agent.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_worklist import (
    CurrentWorklistProjectionPort,
    RequirementWorklistSnapshot,
)
from smb_requirement_agent.domain.analysis.entities import (
    AnalysisRound,
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.value_objects import AnalysisId, QuestionId
from smb_requirement_agent.domain.document.entities import SourceDocument
from smb_requirement_agent.domain.document.value_objects import DocumentId
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.value_objects import EpicId
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.identity.entities import (
    DraftOwnership,
    RequirementAccess,
)
from smb_requirement_agent.domain.requirement.entities import Requirement, RequirementDraft
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.revision.entities import (
    BreakdownRevision,
    RequirementRevision,
    RevisionNumber,
)
from smb_requirement_agent.domain.shared.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.domain.shared.identifiers import RequirementId
from smb_requirement_agent.domain.story.entities import StoryChangeProposal, UserStory
from smb_requirement_agent.domain.story.value_objects import StoryId, StoryProposalId
from smb_requirement_agent.infrastructure.persistence.postgres_activity_reader import (
    ActivityInputDelta,
)
from smb_requirement_agent.infrastructure.persistence.postgres_activity_sources import (
    PostgresActivitySources,
)
from smb_requirement_agent.infrastructure.persistence.postgres_document_metadata import (
    PostgresDocumentRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_repositories import (
    PostgresAccessRepository,
    PostgresActorDirectory,
    PostgresAnalysisAuditRepository,
    PostgresAnalysisRepository,
    PostgresBreakdownReviewRepository,
    PostgresEpicRepository,
    PostgresFeatureRepository,
    PostgresRequirementDraftRepository,
    PostgresRequirementRepository,
    PostgresStoryChangeProposalRepository,
    PostgresStoryRepository,
)
from smb_requirement_agent.infrastructure.persistence.postgres_revisions import (
    PostgresRevisionRepository,
    PostgresRevisionWriter,
)
from smb_requirement_agent.infrastructure.persistence.postgres_snapshots import (
    PostgresSnapshotReader,
)
from smb_requirement_agent.infrastructure.persistence.postgres_store import PostgresStore
from smb_requirement_agent.infrastructure.persistence.postgres_values import DbConnection


class FixturePostgresStore(PostgresStore, RequirementRepositoryPort):
    """Repository-test convenience facade; production uses the individual adapters."""

    def __init__(self, database_url: str, projection: CurrentWorklistProjectionPort) -> None:
        def refresh(connection: DbConnection, requirement_ids: tuple[RequirementId, ...]) -> None:
            for requirement_id in requirement_ids:
                projection.refresh(requirement_id)

        super().__init__(
            DirectPostgresConnector(database_url), PostgresRevisionWriter().capture, refresh
        )

    def add(self, requirement: Requirement) -> None:
        return PostgresRequirementRepository(self).add(requirement=requirement)

    def get(self, requirement_id: RequirementId) -> Requirement | None:
        return PostgresRequirementRepository(self).get(requirement_id=requirement_id)

    def list_all(self) -> list[Requirement]:
        return PostgresRequirementRepository(self).list_all()

    def save(self, requirement: Requirement) -> None:
        return PostgresRequirementRepository(self).save(requirement=requirement)

    def add_draft(self, draft: RequirementDraft) -> None:
        return PostgresRequirementDraftRepository(self).add(draft=draft)

    def get_draft(self, draft_id: RequirementId) -> RequirementDraft | None:
        return PostgresRequirementDraftRepository(self).get(draft_id=draft_id)

    def list_drafts(self) -> list[RequirementDraft]:
        return PostgresRequirementDraftRepository(self).list_all()

    def save_draft(self, draft: RequirementDraft) -> None:
        return PostgresRequirementDraftRepository(self).save(draft=draft)

    def delete_draft(self, draft_id: RequirementId) -> None:
        return PostgresRequirementDraftRepository(self).delete(draft_id=draft_id)

    def get_requirement(self, requirement_id: RequirementId) -> RequirementAccess | None:
        return PostgresAccessRepository(self).get_requirement(requirement_id=requirement_id)

    def save_requirement(self, access: RequirementAccess) -> None:
        return PostgresAccessRepository(self).save_requirement(access=access)

    def get_draft_ownership(self, draft_id: RequirementId) -> DraftOwnership | None:
        return PostgresAccessRepository(self).get_draft_ownership(draft_id=draft_id)

    def save_draft_ownership(self, ownership: DraftOwnership) -> None:
        return PostgresAccessRepository(self).save_draft_ownership(ownership=ownership)

    def delete_draft_ownership(self, draft_id: RequirementId) -> None:
        return PostgresAccessRepository(self).delete_draft_ownership(draft_id=draft_id)

    def save_analysis(self, analysis: RequirementAnalysis) -> None:
        return PostgresAnalysisRepository(self).save(analysis=analysis)

    def get_analysis(self, requirement_id: RequirementId) -> RequirementAnalysis | None:
        return PostgresAnalysisRepository(self).get_by_requirement_id(requirement_id=requirement_id)

    def delete_analysis(self, requirement_id: RequirementId) -> None:
        return PostgresAnalysisRepository(self).delete_by_requirement_id(
            requirement_id=requirement_id
        )

    def append_analysis_round(self, round_: AnalysisRound) -> None:
        return PostgresAnalysisAuditRepository(self).append_round(round_=round_)

    def list_analysis_rounds(self, requirement_id: RequirementId) -> list[AnalysisRound]:
        return PostgresAnalysisAuditRepository(self).list_rounds(requirement_id=requirement_id)

    def get_analysis_round(
        self, requirement_id: RequirementId, analysis_id: AnalysisId
    ) -> AnalysisRound | None:
        return PostgresAnalysisAuditRepository(self).get_round(
            requirement_id=requirement_id, analysis_id=analysis_id
        )

    def add_analysis_question(self, question: ClarificationQuestion) -> None:
        return PostgresAnalysisAuditRepository(self).add_question(question=question)

    def save_analysis_question(self, question: ClarificationQuestion) -> None:
        return PostgresAnalysisAuditRepository(self).save_question(question=question)

    def get_analysis_question(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> ClarificationQuestion | None:
        return PostgresAnalysisAuditRepository(self).get_question(
            requirement_id=requirement_id, question_id=question_id
        )

    def list_analysis_questions(self, requirement_id: RequirementId) -> list[ClarificationQuestion]:
        return PostgresAnalysisAuditRepository(self).list_questions(requirement_id=requirement_id)

    def save_epic(self, epic: Epic) -> None:
        return PostgresEpicRepository(self).save(epic=epic)

    def get_epic(self, requirement_id: RequirementId) -> Epic | None:
        return PostgresEpicRepository(self).get_by_requirement_id(requirement_id=requirement_id)

    def delete_epic(self, requirement_id: RequirementId) -> None:
        return PostgresEpicRepository(self).delete_by_requirement_id(requirement_id=requirement_id)

    def feature_set_version(self, epic_id: EpicId) -> int:
        return PostgresFeatureRepository(self).set_version(epic_id=epic_id)

    def replace_features(
        self, epic_id: EpicId, features: list[Feature], expected_set_version: int
    ) -> int:
        return PostgresFeatureRepository(self).replace_for_epic(
            epic_id=epic_id, features=features, expected_set_version=expected_set_version
        )

    def get_features(self, epic_id: EpicId) -> list[Feature]:
        return PostgresFeatureRepository(self).get_by_epic_id(epic_id=epic_id)

    def get_feature(self, epic_id: EpicId, feature_id: FeatureId) -> Feature | None:
        return PostgresFeatureRepository(self).get(epic_id=epic_id, feature_id=feature_id)

    def save_feature(self, feature: Feature) -> None:
        return PostgresFeatureRepository(self).save(feature=feature)

    def delete_features(self, epic_id: EpicId) -> None:
        return PostgresFeatureRepository(self).delete_by_epic_id(epic_id=epic_id)

    def story_set_version(self, feature_id: FeatureId) -> int:
        return PostgresStoryRepository(self).set_version(feature_id=feature_id)

    def replace_stories(
        self, feature_id: FeatureId, stories: list[UserStory], expected_set_version: int
    ) -> int:
        return PostgresStoryRepository(self).replace_for_feature(
            feature_id=feature_id, stories=stories, expected_set_version=expected_set_version
        )

    def get_stories(self, feature_id: FeatureId) -> list[UserStory]:
        return PostgresStoryRepository(self).get_by_feature_id(feature_id=feature_id)

    def get_story(self, feature_id: FeatureId, story_id: StoryId) -> UserStory | None:
        return PostgresStoryRepository(self).get(feature_id=feature_id, story_id=story_id)

    def save_story(self, story: UserStory) -> None:
        return PostgresStoryRepository(self).save(story=story)

    def save_story_proposal(self, proposal: StoryChangeProposal) -> None:
        return PostgresStoryChangeProposalRepository(self).save(proposal=proposal)

    def get_story_proposal(
        self, feature_id: FeatureId, proposal_id: StoryProposalId
    ) -> StoryChangeProposal | None:
        return PostgresStoryChangeProposalRepository(self).get(
            feature_id=feature_id, proposal_id=proposal_id
        )

    def list_story_proposals(self, feature_id: FeatureId) -> list[StoryChangeProposal]:
        return PostgresStoryChangeProposalRepository(self).list_for_feature(feature_id=feature_id)

    def delete_story_proposal(self, feature_id: FeatureId, proposal_id: StoryProposalId) -> None:
        return PostgresStoryChangeProposalRepository(self).delete(
            feature_id=feature_id, proposal_id=proposal_id
        )

    def delete_story_proposals_for_feature(self, feature_id: FeatureId) -> None:
        return PostgresStoryChangeProposalRepository(self).delete_for_feature(feature_id=feature_id)

    def save_breakdown_review(self, review: BreakdownReview) -> None:
        return PostgresBreakdownReviewRepository(self).save(review=review)

    def get_breakdown_review(self, requirement_id: RequirementId) -> BreakdownReview | None:
        return PostgresBreakdownReviewRepository(self).get(requirement_id=requirement_id)

    def record_actor(self, actor: ActorProfile) -> None:
        return PostgresActorDirectory(self).record(actor=actor)

    def get_actor(self, actor_id: ActorId) -> ActorProfile | None:
        return PostgresActorDirectory(self).get(actor_id=actor_id)

    def search_actors(self, query: str | None, limit: int) -> list[ActorProfile]:
        return PostgresActorDirectory(self).search(query=query, limit=limit)

    def list_snapshots(
        self, requirement_ids: tuple[str, ...] | None = None
    ) -> list[RequirementWorklistSnapshot]:
        return PostgresSnapshotReader(self).list_snapshots(requirement_ids=requirement_ids)

    def list_requirement_revisions(
        self, requirement_id: RequirementId, *, after: int = 0
    ) -> list[RequirementRevision]:
        return PostgresRevisionRepository(self).list_requirement_revisions(
            requirement_id=requirement_id, after=after
        )

    def list_breakdown_revisions(
        self, requirement_id: RequirementId, *, after: int = 0
    ) -> list[BreakdownRevision]:
        return PostgresRevisionRepository(self).list_breakdown_revisions(
            requirement_id=requirement_id, after=after
        )

    def load_activity_history(
        self,
    ) -> tuple[
        dict[str, list[RequirementRevision]],
        dict[str, list[BreakdownRevision]],
        dict[str, list[AnalysisRound]],
        dict[str, list[ClarificationQuestion]],
    ]:
        return PostgresRevisionRepository(self).load_activity_history()

    def get_breakdown_revision(
        self, requirement_id: RequirementId, number: RevisionNumber
    ) -> BreakdownRevision | None:
        return PostgresRevisionRepository(self).get_breakdown_revision(
            requirement_id=requirement_id, number=number
        )

    def add_document(self, document: SourceDocument) -> None:
        return PostgresDocumentRepository(self).add(document=document)

    def get_document(self, document_id: DocumentId) -> SourceDocument | None:
        return PostgresDocumentRepository(self).get(document_id=document_id)

    def save_document(self, document: SourceDocument) -> None:
        return PostgresDocumentRepository(self).save(document=document)

    def list_documents(
        self,
        *,
        requirement_id: RequirementId | None = None,
        draft_id: RequirementId | None = None,
    ) -> list[SourceDocument]:
        return PostgresDocumentRepository(self).list_documents(
            requirement_id=requirement_id, draft_id=draft_id
        )

    def create_current_revisions(self, requirement_id: RequirementId) -> None:
        PostgresRevisionRepository(self).create_current_revisions(requirement_id)

    def activity_inputs(
        self, requirement_id: RequirementId, active_round_ids: tuple[str, ...], access_version: int
    ) -> ActivityInputDelta:
        return PostgresActivitySources(
            self, PostgresSnapshotReader(self), PostgresRevisionRepository(self)
        ).activity_inputs(requirement_id, active_round_ids, access_version)
