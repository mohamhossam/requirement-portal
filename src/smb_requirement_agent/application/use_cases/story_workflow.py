"""Feature-scoped User Story generation and review workflows."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from functools import wraps
from typing import Concatenate, cast

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
    EpicNotFoundError,
    FeatureNotFoundError,
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
    StoryGenerationError,
    StoryNotFoundError,
)
from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.ports.story_generator import (
    StoryCandidate,
    StoryGeneratorPort,
)
from smb_requirement_agent.application.ports.story_quality_evaluator import StoryQualityEvidence
from smb_requirement_agent.application.ports.story_repository import (
    StoryChangeProposalRepositoryPort,
    StoryRepositoryPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.generation_checks import GenerationChecks
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.application.use_cases.source_lineage import generation_lineage
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.story.entities import (
    StoryDraft,
    UserStory,
)
from smb_requirement_agent.domain.story.errors import (
    FeatureNotReadyForStoriesError,
    InvalidStoryContentError,
    StoriesAlreadyExistError,
    StoryRegenerationConflictError,
)
from smb_requirement_agent.domain.story.events import StoriesChanged
from smb_requirement_agent.domain.story.value_objects import (
    AcceptanceCriterion,
    BusinessValue,
    DesiredAction,
    StoryId,
    UserRole,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import (
    SourceLineage,
    merge_lineage,
)


@dataclass(frozen=True)
class AcceptanceCriterionInput:
    given: str
    when: str
    then: str


@dataclass(frozen=True)
class StoryInput:
    role: str
    action: str
    value: str
    acceptance_criteria: tuple[AcceptanceCriterionInput, ...]
    source_reconciled: bool = False
    expected_version: int = 1


@dataclass(frozen=True)
class _StoryTree:
    requirement: Requirement
    epic: Epic
    feature: Feature


@dataclass(frozen=True)
class _StoryContext(_StoryTree):
    analysis: RequirementAnalysis


class StoryWorkflow:
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
        authorization: RequirementAccessService,
    ) -> None:
        self._requirements = requirement_repository
        self._analyses = analysis_repository
        self._epics = epic_repository
        self._features = feature_repository
        self._stories = story_repository
        self._transactions = transaction_manager
        self._authorization = authorization
        self._events = events

    def _tree(self, requirement_id: RequirementId, feature_id: FeatureId) -> _StoryTree:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None:
            raise EpicNotFoundError(f"No Epic exists for requirement {requirement_id.value!r}.")
        feature = self._features.get(epic.id, feature_id)
        if feature is None:
            raise FeatureNotFoundError(
                f"No Feature {feature_id.value!r} under requirement {requirement_id.value!r}."
            )
        requirement.require_active()
        return _StoryTree(requirement, epic, feature)

    def _context(self, requirement_id: RequirementId, feature_id: FeatureId) -> _StoryContext:
        tree = self._tree(requirement_id, feature_id)
        analysis = self._analyses.get_by_requirement_id(requirement_id)
        if analysis is None:
            raise RequirementAnalysisNotFoundError(
                f"Requirement {requirement_id.value!r} has no current analysis."
            )
        return _StoryContext(tree.requirement, tree.epic, tree.feature, analysis)

    @staticmethod
    def _ensure_ready(feature: Feature) -> None:
        availability = feature.story_availability()
        if not availability.allowed:
            raise FeatureNotReadyForStoriesError(availability.reason)

    def _story(self, feature_id: FeatureId, story_id: StoryId) -> UserStory:
        story = self._stories.get(feature_id, story_id)
        if story is None:
            raise StoryNotFoundError(
                f"No Story {story_id.value!r} under Feature {feature_id.value!r}."
            )
        return story

    def _require_generation_snapshot(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        expected: _StoryContext,
        expected_stories: list[UserStory],
        expected_set_version: int,
    ) -> None:
        if (
            self._context(requirement_id, feature_id) != expected
            or self._stories.get_by_feature_id(feature_id) != expected_stories
            or self._stories.set_version(feature_id) != expected_set_version
        ):
            raise ArtifactVersionConflictError(
                "Requirement, analysis, Feature, or Story set changed while generation was "
                "running. Reload it."
            )


def atomic_story_change[Workflow: StoryWorkflow, **Params, Result](
    method: Callable[Concatenate[Workflow, Params], Result],
) -> Callable[Concatenate[Workflow, Params], Result]:
    """Run a Story mutation and its revision checkpoint in one transaction."""

    @wraps(method)
    def wrapped(self: Workflow, *args: Params.args, **kwargs: Params.kwargs) -> Result:
        with self._transactions.transaction():
            requirement_id = cast(
                RequirementId,
                kwargs.get("requirement_id", args[0] if args else None),
            )
            self._transactions.lock_requirement(requirement_id)
            return method(self, *args, **kwargs)

    return cast(Callable[Concatenate[Workflow, Params], Result], wrapped)


class GetStories(StoryWorkflow):
    def quality_evidence(
        self, requirement_id: RequirementId, feature_id: FeatureId
    ) -> StoryQualityEvidence:
        context = self._context(requirement_id, feature_id)
        return StoryQualityEvidence.from_context(
            context.requirement, context.analysis, context.feature
        )

    def execute(self, requirement_id: RequirementId, feature_id: FeatureId) -> list[UserStory]:
        self._tree(requirement_id, feature_id)
        return self._stories.get_by_feature_id(feature_id)


class GenerateStories(StoryWorkflow):
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
        authorization: RequirementAccessService,
        contexts: GenerationContextTokens,
        checks: GenerationChecks,
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
        self._generator = generator
        self._clock = clock

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, feature_id: FeatureId
    ) -> list[UserStory]:
        with (
            self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER),
            self._contexts.guard(
                lambda: self._contexts.stories(requirement_id, feature_id),
                references_for=requirement_id,
                reference_targets=self._contexts.input_artifact_ids(requirement_id, feature_id),
            ),
        ):
            return self._execute(requirement_id=requirement_id, feature_id=feature_id)

    def _execute(self, requirement_id: RequirementId, feature_id: FeatureId) -> list[UserStory]:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        existing = self._stories.get_by_feature_id(feature_id)
        if existing:
            raise StoriesAlreadyExistError(
                "Stories already exist; use whole-Feature regeneration to replace them."
            )
        expected_set_version = self._stories.set_version(feature_id)
        with self._transactions.external_call():
            prepared = self._checks.stories(
                context.requirement,
                context.analysis,
                context.feature,
                lambda guidance: [
                    story_from_candidate(
                        feature_id, candidate, self._clock, lineage=story_context_lineage(context)
                    )
                    for candidate in self._generator.generate(
                        context.requirement,
                        context.analysis,
                        context.epic,
                        context.feature,
                        guidance=guidance,
                    )
                ],
                lambda candidates: candidates,
                allow_split=True,
            )
        stories = list(prepared.stories)
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_generation_snapshot(
                requirement_id, feature_id, context, existing, expected_set_version
            )
            self._stories.replace_for_feature(feature_id, stories, expected_set_version)
            self._events.publish(
                StoriesChanged(requirement_id=requirement_id, feature_id=feature_id)
            )
            self._checks.save(requirement_id, prepared.snapshot)
        return stories


class EditStory(StoryWorkflow):
    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        data: StoryInput,
    ) -> UserStory:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(
                requirement_id=requirement_id, feature_id=feature_id, story_id=story_id, data=data
            )

    @atomic_story_change
    def _execute(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        data: StoryInput,
    ) -> UserStory:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        story = self._story(feature_id, story_id)
        if story.version != data.expected_version:
            raise ArtifactVersionConflictError(
                f"Story changed from version {data.expected_version} to {story.version}. Reload it."
            )
        draft = _draft_from_input(data)
        edited = story.edit(
            draft.role,
            draft.action,
            draft.value,
            draft.acceptance_criteria,
            source_reconciled=data.source_reconciled,
        )
        self._stories.save(edited)
        self._events.publish(StoriesChanged(requirement_id=requirement_id, feature_id=feature_id))
        return edited


class SplitStory(StoryWorkflow):
    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        replacements: tuple[StoryInput, ...],
        expected_set_version: int,
    ) -> list[UserStory]:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(
                requirement_id=requirement_id,
                feature_id=feature_id,
                story_id=story_id,
                replacements=replacements,
                expected_set_version=expected_set_version,
            )

    @atomic_story_change
    def _execute(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        replacements: tuple[StoryInput, ...],
        expected_set_version: int,
    ) -> list[UserStory]:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        if len(replacements) < 2:
            raise InvalidStoryContentError("A split needs at least two replacement Stories.")
        source = self._story(feature_id, story_id)
        if self._stories.set_version(feature_id) != expected_set_version:
            raise ArtifactVersionConflictError("The Story set changed. Reload it before splitting.")
        replacement_stories = [
            _manual_story(
                feature_id,
                source.id if index == 0 else StoryId(str(uuid.uuid4())),
                _draft_from_input(item),
                source.provenance,
                lineage=tuple(
                    item.through(f"story:{source.id.value}:v{source.version}")
                    for item in source.source_lineage
                ),
            )
            for index, item in enumerate(replacements)
        ]
        updated = replace_source_stories(
            self._stories.get_by_feature_id(feature_id), {source.id}, replacement_stories
        )
        self._stories.replace_for_feature(feature_id, updated, expected_set_version)
        self._events.publish(StoriesChanged(requirement_id=requirement_id, feature_id=feature_id))
        return updated


class MergeStories(StoryWorkflow):
    def execute(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_ids: tuple[StoryId, ...],
        replacement: StoryInput,
        expected_set_version: int,
    ) -> list[UserStory]:
        with self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER):
            return self._execute(
                requirement_id=requirement_id,
                feature_id=feature_id,
                story_ids=story_ids,
                replacement=replacement,
                expected_set_version=expected_set_version,
            )

    @atomic_story_change
    def _execute(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_ids: tuple[StoryId, ...],
        replacement: StoryInput,
        expected_set_version: int,
    ) -> list[UserStory]:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        sources = ordered_source_stories(self._stories.get_by_feature_id(feature_id), story_ids)
        if self._stories.set_version(feature_id) != expected_set_version:
            raise ArtifactVersionConflictError("The Story set changed. Reload it before merging.")
        merged = _manual_story(
            feature_id,
            sources[0].id,
            _draft_from_input(replacement),
            sources[0].provenance,
            lineage=merge_lineage(
                *(
                    tuple(
                        item.through(f"story:{source.id.value}:v{source.version}")
                        for item in source.source_lineage
                    )
                    for source in sources
                )
            ),
        )
        updated = replace_source_stories(
            self._stories.get_by_feature_id(feature_id), {item.id for item in sources}, [merged]
        )
        self._stories.replace_for_feature(feature_id, updated, expected_set_version)
        self._events.publish(StoriesChanged(requirement_id=requirement_id, feature_id=feature_id))
        return updated


class RegenerateStory(StoryWorkflow):
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
        authorization: RequirementAccessService,
        contexts: GenerationContextTokens,
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
        self._generator = generator
        self._clock = clock
        self._proposals = proposals

    def execute_one(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        *,
        force: bool = False,
    ) -> list[UserStory]:
        with (
            self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER),
            self._contexts.guard(
                lambda: self._contexts.stories(requirement_id, feature_id),
                references_for=requirement_id,
                reference_targets=(
                    *self._contexts.input_artifact_ids(requirement_id, feature_id),
                    story_id.value,
                ),
            ),
        ):
            return self._execute_one(
                requirement_id=requirement_id, feature_id=feature_id, story_id=story_id, force=force
            )

    def _execute_one(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        story_id: StoryId,
        *,
        force: bool = False,
    ) -> list[UserStory]:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        stories = self._stories.get_by_feature_id(feature_id)
        source = self._story(feature_id, story_id)
        expected_set_version = self._stories.set_version(feature_id)
        proposals_before = tuple(self._proposals.list_for_feature(feature_id))
        has_proposals = bool(proposals_before)
        if (source.is_human_owned or has_proposals) and not force:
            raise StoryRegenerationConflictError(
                "The Story or a pending change proposal contains human work; regenerate with "
                "force to authorize replacement."
            )
        with self._transactions.external_call():
            prepared = self._checks.stories(
                context.requirement,
                context.analysis,
                context.feature,
                lambda guidance: [
                    replace(
                        story_from_candidate(
                            feature_id,
                            self._generator.regenerate(
                                context.requirement,
                                context.analysis,
                                context.epic,
                                context.feature,
                                source,
                                guidance=guidance,
                            ),
                            self._clock,
                            story_id=source.id,
                            lineage=story_context_lineage(context, [source]),
                        ),
                        version=source.version + 1,
                    )
                ],
                lambda candidates: [
                    candidates[0] if item.id == source.id else item for item in stories
                ],
                allow_split=False,
            )
        updated = list(prepared.stories)
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_generation_snapshot(
                requirement_id, feature_id, context, stories, expected_set_version
            )
            self._stories.replace_for_feature(feature_id, updated, expected_set_version)
            if tuple(self._proposals.list_for_feature(feature_id)) != proposals_before:
                raise ArtifactVersionConflictError(
                    "Story proposals changed during generation. Reload them."
                )
            self._proposals.delete_for_feature(feature_id)
            self._events.publish(
                StoriesChanged(requirement_id=requirement_id, feature_id=feature_id)
            )
            self._checks.save(requirement_id, prepared.snapshot)
        return updated

    def execute_all(
        self,
        actor: ActorProfile,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        *,
        force: bool = False,
    ) -> list[UserStory]:
        with (
            self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER),
            self._contexts.guard(
                lambda: self._contexts.stories(requirement_id, feature_id),
                references_for=requirement_id,
                reference_targets=self._contexts.input_artifact_ids(requirement_id, feature_id),
            ),
        ):
            return self._execute_all(
                requirement_id=requirement_id, feature_id=feature_id, force=force
            )

    def _execute_all(
        self,
        requirement_id: RequirementId,
        feature_id: FeatureId,
        *,
        force: bool = False,
    ) -> list[UserStory]:
        context = self._context(requirement_id, feature_id)
        self._ensure_ready(context.feature)
        existing = self._stories.get_by_feature_id(feature_id)
        expected_set_version = self._stories.set_version(feature_id)
        proposals_before = tuple(self._proposals.list_for_feature(feature_id))
        has_proposals = bool(proposals_before)
        if (any(story.is_human_owned for story in existing) or has_proposals) and not force:
            raise StoryRegenerationConflictError(
                "The Story set or a pending change proposal contains human work; regenerate "
                "with force to authorize replacement."
            )
        with self._transactions.external_call():
            prepared = self._checks.stories(
                context.requirement,
                context.analysis,
                context.feature,
                lambda guidance: [
                    story_from_candidate(
                        feature_id, candidate, self._clock, lineage=story_context_lineage(context)
                    )
                    for candidate in self._generator.generate(
                        context.requirement,
                        context.analysis,
                        context.epic,
                        context.feature,
                        guidance=guidance,
                    )
                ],
                lambda candidates: candidates,
                allow_split=True,
            )
        stories = list(prepared.stories)
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            self._require_generation_snapshot(
                requirement_id, feature_id, context, existing, expected_set_version
            )
            self._stories.replace_for_feature(feature_id, stories, expected_set_version)
            if tuple(self._proposals.list_for_feature(feature_id)) != proposals_before:
                raise ArtifactVersionConflictError(
                    "Story proposals changed during generation. Reload them."
                )
            self._proposals.delete_for_feature(feature_id)
            self._events.publish(
                StoriesChanged(requirement_id=requirement_id, feature_id=feature_id)
            )
            self._checks.save(requirement_id, prepared.snapshot)
        return stories


def _criteria(values: tuple[AcceptanceCriterionInput, ...]) -> tuple[AcceptanceCriterion, ...]:
    return tuple(AcceptanceCriterion(item.given, item.when, item.then) for item in values)


def _draft_from_input(data: StoryInput) -> StoryDraft:
    return StoryDraft(
        UserRole(data.role),
        DesiredAction(data.action),
        BusinessValue(data.value),
        _criteria(data.acceptance_criteria),
    )


def _draft_from_candidate(candidate: StoryCandidate, clock: ClockPort) -> StoryDraft:
    return StoryDraft(
        UserRole(candidate["role"]),
        DesiredAction(candidate["action"]),
        BusinessValue(candidate["value"]),
        tuple(AcceptanceCriterion(**item) for item in candidate["acceptance_criteria"]),
        Provenance(clock.now(), candidate["model"], candidate["prompt_version"]),
    )


def story_from_candidate(
    feature_id: FeatureId,
    candidate: StoryCandidate,
    clock: ClockPort,
    *,
    story_id: StoryId | None = None,
    lineage: tuple[SourceLineage, ...],
) -> UserStory:
    return replace(
        generated_story(
            feature_id,
            story_id if story_id is not None else StoryId(str(uuid.uuid4())),
            _draft_from_candidate(candidate, clock),
        ),
        source_lineage=lineage,
    )


def generated_story(feature_id: FeatureId, story_id: StoryId, draft: StoryDraft) -> UserStory:
    if draft.provenance is None:
        raise StoryGenerationError("Generated Story draft has no provenance.")
    return UserStory(
        id=story_id,
        feature_id=feature_id,
        role=draft.role,
        action=draft.action,
        value=draft.value,
        acceptance_criteria=draft.acceptance_criteria,
        status=GenerationStatus.GENERATED,
        provenance=draft.provenance,
    )


def _manual_story(
    feature_id: FeatureId,
    story_id: StoryId,
    draft: StoryDraft,
    provenance: Provenance,
    *,
    lineage: tuple[SourceLineage, ...] = (),
) -> UserStory:
    return UserStory(
        id=story_id,
        feature_id=feature_id,
        role=draft.role,
        action=draft.action,
        value=draft.value,
        acceptance_criteria=draft.acceptance_criteria,
        status=GenerationStatus.EDITED,
        provenance=provenance,
        source_lineage=lineage,
    )


def ordered_source_stories(stories: list[UserStory], ids: tuple[StoryId, ...]) -> list[UserStory]:
    if len(set(ids)) != len(ids):
        raise InvalidStoryContentError("Story ids must be unique.")
    selected = [story for story in stories if story.id in set(ids)]
    if len(selected) != len(ids):
        raise StoryNotFoundError("One or more source Stories do not exist under this Feature.")
    return selected


def replace_source_stories(
    current: list[UserStory], source_ids: set[StoryId], replacements: list[UserStory]
) -> list[UserStory]:
    first = next(index for index, story in enumerate(current) if story.id in source_ids)
    survivors = [story for story in current if story.id not in source_ids]
    return survivors[:first] + replacements + survivors[first:]


def source_stories_fingerprint(stories: list[UserStory]) -> str:
    payload = [
        {
            "id": story.id.value,
            "role": story.role.value,
            "action": story.action.value,
            "value": story.value.value,
            "criteria": [criterion.__dict__ for criterion in story.acceptance_criteria],
            "status": story.status.value,
            "stale": None
            if story.staleness is None
            else [story.staleness.reason.value, story.staleness.since.isoformat()],
        }
        for story in stories
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def story_state_fingerprint(value: _StoryContext | list[UserStory]) -> str:
    payload = [asdict(item) for item in value] if isinstance(value, list) else asdict(value)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def story_context_lineage(
    context: _StoryContext, sources: list[UserStory] | None = None
) -> tuple[SourceLineage, ...]:
    inputs: list[tuple[str, Epic | Feature | UserStory]] = [
        ("epic", context.epic),
        ("feature", context.feature),
    ]
    inputs.extend(("story", source) for source in (sources or []))
    return merge_lineage(
        generation_lineage(context.analysis),
        *(
            tuple(
                origin.through(f"{kind}:{item.id.value}:v{item.version}")
                for origin in item.source_lineage
            )
            for kind, item in inputs
        ),
    )
