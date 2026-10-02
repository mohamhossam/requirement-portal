"""GenerateFeatures use case."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from enum import Enum

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
    EpicNotFoundError,
    FeatureGenerationError,
    RequirementAnalysisNotFoundError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.application.ports.feature_generator import (
    FeatureCandidate,
    FeatureGeneratorPort,
)
from smb_requirement_agent.application.ports.feature_repository import FeatureRepositoryPort
from smb_requirement_agent.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
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
from smb_requirement_agent.application.use_cases.invalidate_approval_workflow import (
    InvalidateApprovalWorkflow,
)
from smb_requirement_agent.application.use_cases.source_lineage import generation_lineage
from smb_requirement_agent.domain.document.lineage import merge_lineage
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.errors import EpicNotApprovedError
from smb_requirement_agent.domain.epic.value_objects import EpicStatus
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.errors import (
    FeatureRegenerationConflictError,
)
from smb_requirement_agent.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureName,
    FeatureOutcome,
    SplittingPattern,
    SplittingRationale,
)
from smb_requirement_agent.domain.identity.entities import ActorProfile
from smb_requirement_agent.domain.requirement.value_objects import RequirementId
from smb_requirement_agent.domain.shared.enums import supported_values, value_of
from smb_requirement_agent.domain.shared.generation import Provenance


@dataclass(frozen=True)
class GenerateFeaturesResult:
    """The generated set, and whether it replaced an existing one."""

    features: list[Feature]
    replaced_existing: bool


class GenerateFeatures:
    """Decomposes an approved Epic into Feature candidates.

    The Epic must be approved and current. Decomposing a draft Epic means
    building a backlog on text nobody has signed off, and decomposing a stale
    one means building it on text the requirement has already moved past.
    """

    def __init__(
        self,
        requirement_repository: RequirementRepositoryPort,
        analysis_repository: RequirementAnalysisRepositoryPort,
        epic_repository: EpicRepositoryPort,
        feature_repository: FeatureRepositoryPort,
        story_repository: StoryRepositoryPort,
        proposal_repository: StoryChangeProposalRepositoryPort,
        generator: FeatureGeneratorPort,
        clock: ClockPort,
        approval_invalidation: InvalidateApprovalWorkflow,
        transactions: TransactionManagerPort,
        *,
        authorization: RequirementAccessService,
        contexts: GenerationContextTokens,
        checks: GenerationChecks,
    ) -> None:
        self._checks = checks
        self._contexts = contexts
        self._requirements = requirement_repository
        self._analyses = analysis_repository
        self._epics = epic_repository
        self._features = feature_repository
        self._stories = story_repository
        self._proposals = proposal_repository
        self._generator = generator
        self._clock = clock
        self._approval_invalidation = approval_invalidation
        self._transactions = transactions
        self._authorization = authorization

    def execute(
        self, actor: ActorProfile, requirement_id: RequirementId, *, force: bool = False
    ) -> GenerateFeaturesResult:
        with (
            self._authorization.mutation(requirement_id, actor, RequirementPermission.MEMBER),
            self._contexts.guard(
                lambda: self._contexts.features(requirement_id),
                references_for=requirement_id,
                reference_targets=self._contexts.input_artifact_ids(requirement_id),
            ),
        ):
            return self._execute(requirement_id=requirement_id, force=force)

    def _execute(
        self, requirement_id: RequirementId, *, force: bool = False
    ) -> GenerateFeaturesResult:
        requirement = self._requirements.get(requirement_id)
        if requirement is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")

        analysis = self._analyses.get_by_requirement_id(requirement_id)
        if analysis is None:
            raise RequirementAnalysisNotFoundError(
                f"Requirement {requirement_id.value!r} has no analysis."
            )
        requirement.require_active()

        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None:
            raise EpicNotFoundError(f"No Epic exists for requirement {requirement_id.value!r}.")
        self._ensure_decomposable(epic)

        existing = self._features.get_by_epic_id(epic.id)
        expected_set_version = self._features.set_version(epic.id)
        expected_descendants = self._descendants(existing)
        human_owned_descendants = any(
            story.is_human_owned
            for feature in existing
            for story in self._stories.get_by_feature_id(feature.id)
        )
        pending_proposals = any(
            self._proposals.list_for_feature(feature.id) for feature in existing
        )
        if (
            any(feature.is_human_owned for feature in existing)
            or human_owned_descendants
            or pending_proposals
        ) and not force:
            raise FeatureRegenerationConflictError(
                f"Features for Epic {epic.id.value!r} or their descendants contain human "
                "work. Regenerate with force to authorize replacing the full set."
            )

        with self._transactions.external_call():
            features = self._checks.features(
                requirement,
                analysis,
                lambda guidance: [
                    replace(
                        self._to_feature(epic, candidate),
                        source_lineage=merge_lineage(
                            generation_lineage(analysis),
                            tuple(
                                item.through(f"epic:{epic.id.value}:v{epic.version}")
                                for item in epic.source_lineage
                            ),
                        ),
                    )
                    for candidate in self._generator.generate(
                        requirement, analysis, epic, guidance=guidance
                    )
                ],
            )
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            if (
                self._requirements.get(requirement_id) != requirement
                or self._analyses.get_by_requirement_id(requirement_id) != analysis
                or self._epics.get_by_requirement_id(requirement_id) != epic
                or self._features.get_by_epic_id(epic.id) != existing
                or self._descendants(existing) != expected_descendants
            ):
                raise ArtifactVersionConflictError(
                    "Requirement, analysis, or Epic changed while generation was running. "
                    "Reload it."
                )
            for feature in existing:
                self._proposals.delete_for_feature(feature.id)
            self._features.replace_for_epic(epic.id, features, expected_set_version)
            self._approval_invalidation.execute(requirement_id)
            self._checks.save(requirement_id, None)

        return GenerateFeaturesResult(features=features, replaced_existing=bool(existing))

    def _descendants(self, features: list[Feature]) -> tuple[object, ...]:
        return tuple(
            (
                feature.id,
                self._stories.set_version(feature.id),
                tuple(self._stories.get_by_feature_id(feature.id)),
                tuple(self._proposals.list_for_feature(feature.id)),
            )
            for feature in features
        )

    @staticmethod
    def _ensure_decomposable(epic: Epic) -> None:
        availability = epic.decomposition_availability()
        if not availability.allowed:
            raise EpicNotApprovedError(availability.reason)

    def _to_feature(self, epic: Epic, candidate: FeatureCandidate) -> Feature:
        return Feature(
            id=FeatureId(str(uuid.uuid4())),
            epic_id=epic.id,
            name=FeatureName(candidate["name"]),
            outcome=FeatureOutcome(candidate["outcome"]),
            delivery_drop=_parse(DeliveryDrop, candidate["delivery_drop"], "delivery drop"),
            splitting_pattern=_parse(
                SplittingPattern, candidate["splitting_pattern"], "splitting pattern"
            ),
            splitting_rationale=SplittingRationale(candidate["splitting_rationale"]),
            status=EpicStatus.GENERATED,
            provenance=Provenance(
                generated_at=self._clock.now(),
                model=candidate["model"],
                prompt_version=candidate["prompt_version"],
            ),
        )


def _parse[T: Enum](enum_type: type[T], raw: str, field: str) -> T:
    """Map a provider string onto a domain enum.

    An unrecognised value is a generation failure, not a silent default:
    quietly coercing an unknown splitting pattern to one of ours would
    fabricate the rationale a reviewer relies on.
    """
    member = value_of(enum_type, raw)
    if member is None:
        raise FeatureGenerationError(
            f"Provider returned unsupported {field} {raw!r}. "
            f"Supported: {supported_values(enum_type)}."
        )
    return member
