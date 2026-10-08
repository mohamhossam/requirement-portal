"""Durable AI split/merge proposals a reviewer applies or discards."""

from __future__ import annotations

import uuid
from dataclasses import replace

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.breakdown.application.errors import (
    StoryGenerationError,
    StoryProposalNotFoundError,
)
from smb_requirement_agent.breakdown.application.ports.breakdown_context import BreakdownContextPort
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.generation_guidance import GenerationGuidance
from smb_requirement_agent.breakdown.application.ports.story_generator import (
    StoryGeneratorPort,
)
from smb_requirement_agent.breakdown.application.ports.story_repository import (
    StoryChangeProposalRepositoryPort,
    StoryRepositoryPort,
)
from smb_requirement_agent.breakdown.application.use_cases.generation_checks import GenerationChecks
from smb_requirement_agent.breakdown.application.use_cases.story_quality import (
    story_set_fingerprint,
)
from smb_requirement_agent.breakdown.application.use_cases.story_workflow import (
    StoryWorkflow,
    atomic_story_change,
    generated_story,
    ordered_source_stories,
    replace_source_stories,
    source_stories_fingerprint,
    story_context_lineage,
    story_from_candidate,
    story_state_fingerprint,
)
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.entities import (
    StoryChangeOperation,
    StoryChangeProposal,
    StoryDraft,
    UserStory,
)
from smb_requirement_agent.breakdown.domain.story.errors import (
    InvalidStoryContentError,
    StoryProposalConflictError,
)
from smb_requirement_agent.breakdown.domain.story.events import StoriesChanged
from smb_requirement_agent.breakdown.domain.story.quality import (
    FeatureQualitySnapshot,
    StoryQualityEvidence,
)
from smb_requirement_agent.breakdown.domain.story.value_objects import (
    StoryId,
    StoryProposalId,
)
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
    RequirementPermission,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import merge_lineage


class StoryChangeProposals(StoryWorkflow):
    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        analysis_repository: RequirementAnalysisRepositoryPort,
        epic_repository: EpicRepositoryPort,
        feature_repository: FeatureRepositoryPort,
        story_repository: StoryRepositoryPort,
        transaction_manager: TransactionManagerPort,
        events: DomainEventPublisher,
        *,
        authorization: RequirementAccessPort,
        contexts: BreakdownContextPort,
        checks: GenerationChecks,
        proposals: StoryChangeProposalRepositoryPort,
        generator: StoryGeneratorPort,
        clock: ClockPort,
    ) -> None:
        self._checks = checks
        self._contexts = contexts
        super().__init__(
            requirement_repository,
            analysis_repository,
            epic_repository,
            feature_repository,
            story_repository,
            transaction_manager,
            events,
            authorization=authorization,
        )
        self._proposals = proposals
        self._generator = generator
        self._clock = clock

    def create(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        operation: StoryChangeOperation,
        source_story_ids: tuple[StoryId, ...],
    ) -> StoryChangeProposal:
        with (
            self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER),
            self._contexts.guard(
                lambda: self._contexts.stories(requirement_id, feature_id),
                references_for=requirement_id,
                reference_targets=(
                    *self._contexts.input_artifact_ids(requirement_id, feature_id),
                    *(item.value for item in source_story_ids),
                ),
            ),
        ):
            return self._create(
                requirement_id=requirement_id,
                feature_id=feature_id,
                operation=operation,
                source_story_ids=source_story_ids,
            )

    def _create(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        operation: StoryChangeOperation,
        source_story_ids: tuple[StoryId, ...],
    ) -> StoryChangeProposal:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        all_stories = self._stories.get_by_feature_id(feature_id)
        expected_set_version = self._stories.set_version(feature_id)
        sources = ordered_source_stories(all_stories, source_story_ids)
        if operation is StoryChangeOperation.SPLIT and len(sources) != 1:
            raise InvalidStoryContentError("AI split requires exactly one source Story.")
        if operation is StoryChangeOperation.MERGE and len(sources) < 2:
            raise InvalidStoryContentError("AI merge requires at least two source Stories.")

        def generate(guidance: GenerationGuidance) -> list[UserStory]:
            if operation is StoryChangeOperation.SPLIT:
                candidates = self._generator.propose_split(
                    context.requirement,
                    context.analysis,
                    context.epic,
                    context.feature,
                    sources[0],
                    guidance=guidance,
                )
                if len(candidates) < 2:
                    raise StoryGenerationError("Provider returned fewer than two split candidates.")
            else:
                candidates = [
                    self._generator.propose_merge(
                        context.requirement,
                        context.analysis,
                        context.epic,
                        context.feature,
                        sources,
                        guidance=guidance,
                    )
                ]
            return [
                replace(
                    story_from_candidate(
                        feature_id,
                        item,
                        self._clock,
                        story_id=sources[0].id if index == 0 else None,
                        lineage=story_context_lineage(context, sources),
                    ),
                    version=sources[0].version + 1 if index == 0 else 1,
                )
                for index, item in enumerate(candidates)
            ]

        source_ids = {item.id for item in sources}
        survivor_ids = {item.id for item in all_stories} - source_ids
        with self._transactions.external_call():
            prepared = self._checks.stories(
                context.requirement,
                context.analysis,
                context.feature,
                generate,
                lambda candidates: replace_source_stories(all_stories, source_ids, candidates),
                allow_split=operation is StoryChangeOperation.SPLIT,
            )
        replacements = tuple(item for item in prepared.stories if item.id not in survivor_ids)
        proposal = StoryChangeProposal(
            id=StoryProposalId(str(uuid.uuid4())),
            feature_id=feature_id,
            operation=operation,
            source_story_ids=tuple(item.id for item in sources),
            source_fingerprint=source_stories_fingerprint(sources),
            candidates=tuple(
                StoryDraft(
                    item.role, item.action, item.value, item.acceptance_criteria, item.provenance
                )
                for item in replacements
            ),
            prepared_candidates=replacements,
            quality_assessments=prepared.snapshot.assessments,
            source_set_fingerprint=story_state_fingerprint(all_stories),
            generation_context=story_state_fingerprint(context),
        )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_generation_snapshot(
                requirement_id,
                feature_id,
                context,
                all_stories,
                expected_set_version,
            )
            self._proposals.save(proposal)
        return proposal

    def list_proposals(
        self, requirement_id: RequirementId, feature_id: FeatureId
    ) -> list[StoryChangeProposal]:
        self._tree(requirement_id, feature_id)
        return self._proposals.list_for_feature(feature_id)

    def apply(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        proposal_id: StoryProposalId,
        expected_version: int,
        expected_set_version: int,
    ) -> list[UserStory]:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._apply(
                requirement_id=requirement_id,
                feature_id=feature_id,
                proposal_id=proposal_id,
                expected_version=expected_version,
                expected_set_version=expected_set_version,
            )

    @atomic_story_change
    def _apply(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        proposal_id: StoryProposalId,
        expected_version: int,
        expected_set_version: int,
    ) -> list[UserStory]:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        proposal = self._proposals.get(feature_id, proposal_id)
        if proposal is None:
            raise StoryProposalNotFoundError(f"Story proposal {proposal_id.value!r} not found.")
        if proposal.version != expected_version:
            raise ArtifactVersionConflictError(
                "The Story proposal changed. Reload it before applying."
            )
        current = self._stories.get_by_feature_id(feature_id)
        if self._stories.set_version(feature_id) != expected_set_version:
            raise ArtifactVersionConflictError(
                "The Story set changed. Reload it before applying this proposal."
            )
        sources = ordered_source_stories(current, proposal.source_story_ids)
        if source_stories_fingerprint(sources) != proposal.source_fingerprint:
            raise StoryProposalConflictError(
                "The source Stories changed after this preview was created. Create a new preview."
            )
        replacements = [
            replace(
                generated_story(
                    feature_id,
                    sources[0].id if index == 0 else StoryId(str(uuid.uuid4())),
                    draft,
                ),
                version=sources[0].version + 1 if index == 0 else 1,
                source_lineage=merge_lineage(
                    *(
                        tuple(
                            origin.through(f"story:{source.id.value}:v{source.version}")
                            for origin in source.source_lineage
                        )
                        for source in sources
                    )
                ),
            )
            for index, draft in enumerate(proposal.candidates)
        ]
        if proposal.prepared_candidates:
            if proposal.source_set_fingerprint != story_state_fingerprint(
                current
            ) or proposal.generation_context != story_state_fingerprint(context):
                raise StoryProposalConflictError(
                    "The generation evidence changed after this preview. Create a new preview."
                )
            replacements = list(proposal.prepared_candidates)
        updated = replace_source_stories(current, {item.id for item in sources}, replacements)
        self._stories.replace_for_feature(feature_id, updated, expected_set_version)
        self._proposals.delete(feature_id, proposal_id)
        self._events.publish(StoriesChanged(requirement_id=requirement_id, feature_id=feature_id))
        self._checks.save(
            requirement_id,
            FeatureQualitySnapshot(
                feature_id,
                story_set_fingerprint(
                    tuple(updated),
                    StoryQualityEvidence.from_context(
                        context.requirement, context.analysis, context.feature
                    ),
                ),
                proposal.quality_assessments,
                self._clock.now(),
            )
            if proposal.prepared_candidates
            else None,
        )
        return updated

    def discard(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        proposal_id: StoryProposalId,
        expected_version: int,
        expected_set_version: int,
    ) -> None:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._discard(
                requirement_id=requirement_id,
                feature_id=feature_id,
                proposal_id=proposal_id,
                expected_version=expected_version,
                expected_set_version=expected_set_version,
            )

    @atomic_story_change
    def _discard(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        proposal_id: StoryProposalId,
        expected_version: int,
        expected_set_version: int,
    ) -> None:
        self._tree(requirement_id, feature_id)
        proposal = self._proposals.get(feature_id, proposal_id)
        if proposal is None:
            raise StoryProposalNotFoundError(f"Story proposal {proposal_id.value!r} not found.")
        if (
            proposal.version != expected_version
            or self._stories.set_version(feature_id) != expected_set_version
        ):
            raise ArtifactVersionConflictError(
                "The proposal or Story set changed. Reload it before discarding."
            )
        self._proposals.delete(feature_id, proposal_id)
