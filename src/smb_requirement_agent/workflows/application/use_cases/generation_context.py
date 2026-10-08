"""Content-bound preconditions for model-backed generation operations."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict
from typing import Any

from smb_requirement_agent.analysis.application.ports.analysis_audit_repository import (
    AnalysisAuditRepositoryPort,
)
from smb_requirement_agent.analysis.application.ports.reference_analysis import (
    ReferenceEvidencePort,
    require_analysis_references,
)
from smb_requirement_agent.analysis.application.ports.requirement_analysis_repository import (
    RequirementAnalysisRepositoryPort,
)
from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.application.ports.external_work import guard_external_work
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.breakdown.application.ports.epic_repository import EpicRepositoryPort
from smb_requirement_agent.breakdown.application.ports.feature_repository import (
    FeatureRepositoryPort,
)
from smb_requirement_agent.breakdown.application.ports.story_repository import (
    StoryChangeProposalRepositoryPort,
    StoryRepositoryPort,
)
from smb_requirement_agent.breakdown.domain.feature.value_objects import FeatureId
from smb_requirement_agent.breakdown.domain.story.value_objects import StoryId
from smb_requirement_agent.governance.domain.review.fingerprints import artifact_fingerprint
from smb_requirement_agent.jobs.domain.entities import AiJobOperation
from smb_requirement_agent.requirements.application.ports.document_repository import (
    DocumentRepositoryPort,
)
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

CONTEXT_TOKEN_FORMAT = "generation-context-v2"


class GenerationContextTokens:
    """Create and verify opaque digests of every input visible to generation."""

    @contextmanager
    def guard(
        self,
        current: Callable[[], str],
        *,
        references_for: RequirementId | None = None,
        reference_targets: tuple[str, ...] = (),
    ) -> Iterator[None]:
        """Bind provider work to its prepared hierarchy and recheck on resume."""
        expected = current()

        def require_references() -> None:
            if references_for is not None:
                analysis = self._analyses.get_by_requirement_id(references_for)
                if analysis is not None:
                    require_analysis_references(
                        self._references, analysis, target_ids=reference_targets
                    )

        def recheck() -> None:
            require_references()
            self.require(expected, current())

        recheck()
        with guard_external_work(recheck):
            yield
            require_references()

    @contextmanager
    def read_snapshot(self, requirement_id: RequirementId) -> Iterator[None]:
        with self._transactions.transaction():
            self._transactions.lock_requirement(requirement_id)
            yield

    def analysis_for(self, requirement: Requirement) -> str:
        with self.read_snapshot(requirement.id):
            if self._requirements.get(requirement.id) != requirement:
                raise ArtifactVersionConflictError(
                    "Requirement changed while its response was being prepared. Reload it."
                )
            return self.analysis(requirement.id)

    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        analyses: RequirementAnalysisRepositoryPort,
        audit: AnalysisAuditRepositoryPort,
        documents: DocumentRepositoryPort,
        epics: EpicRepositoryPort,
        features: FeatureRepositoryPort,
        stories: StoryRepositoryPort,
        proposals: StoryChangeProposalRepositoryPort,
        *,
        transactions: TransactionManagerPort,
        references: ReferenceEvidencePort,
    ) -> None:
        self._requirements = requirements
        self._references = references
        self._transactions = transactions
        self._analyses = analyses
        self._audit = audit
        self._documents = documents
        self._epics = epics
        self._features = features
        self._stories = stories
        self._proposals = proposals

    def analysis(self, requirement_id: RequirementId) -> str:
        requirement = self._requirements.get(requirement_id)
        payload: dict[str, Any] = {
            "scope": "analysis",
            "requirement_id": requirement_id.value,
            "requirement_version": requirement.version.value if requirement else None,
            "descendants": self._descendants(requirement_id),
            "documents": [
                {
                    "id": item.id.value,
                    "version": item.version_number,
                    "included_version_id": (
                        item.included_version_id.value if item.included_version_id else None
                    ),
                    "hidden_worksheets": list(item.included_hidden_worksheets),
                }
                for item in sorted(
                    self._documents.list_for_requirement(requirement_id),
                    key=lambda value: value.id.value,
                )
            ],
        }
        current = self._analyses.get_by_requirement_id(requirement_id)
        if current is not None:
            payload["stale_reference_proposals"] = self._references.stale_analysis(current)
            payload["current_analysis"] = {
                "id": current.id.value if current.id else None,
                "round": current.round_number,
                "version": current.version,
                "confirmed": current.is_human_confirmed,
                "clarifications": [
                    [item.kind.value, item.subject, item.answer] for item in current.clarifications
                ],
            }
        payload["questions"] = [
            [question.id.value, question.version, question.status.value, question.answer]
            for question in sorted(
                self._audit.list_questions(requirement_id), key=lambda value: value.id.value
            )
        ]
        return _token(payload)

    def _descendants(self, requirement_id: RequirementId) -> dict[str, Any]:
        """Bind every target a regeneration can replace or invalidate."""
        epic = self._epics.get_by_requirement_id(requirement_id)
        if epic is None:
            return {}
        return {
            "epic": asdict(epic),
            "feature_set_version": self._features.set_version(epic.id),
            "features": [
                {
                    "feature": asdict(feature),
                    "story_set_version": self._stories.set_version(feature.id),
                    "stories": [
                        asdict(item)
                        for item in sorted(
                            self._stories.get_by_feature_id(feature.id),
                            key=lambda item: item.id.value,
                        )
                    ],
                    "proposals": [
                        asdict(item)
                        for item in sorted(
                            self._proposals.list_for_feature(feature.id),
                            key=lambda item: item.id.value,
                        )
                    ],
                }
                for feature in sorted(
                    self._features.get_by_epic_id(epic.id), key=lambda item: item.id.value
                )
            ],
        }

    def epic(self, requirement_id: RequirementId) -> str:
        analysis = self._analyses.get_by_requirement_id(requirement_id)
        epic = self._epics.get_by_requirement_id(requirement_id)
        return _token(
            {
                "scope": "epic",
                "analysis_context": self.analysis(requirement_id),
                "analysis_id": analysis.id.value if analysis and analysis.id else None,
                "analysis_round": analysis.round_number if analysis else None,
                "analysis_version": analysis.version if analysis else None,
                "analysis_confirmed": analysis.is_human_confirmed if analysis else False,
                "target_version": epic.version if epic else 0,
                "target_fingerprint": artifact_fingerprint(epic) if epic else None,
            }
        )

    def features(self, requirement_id: RequirementId) -> str:
        epic = self._epics.get_by_requirement_id(requirement_id)
        return _token(
            {
                "scope": "features",
                "epic_context": self.epic(requirement_id),
                "epic_version": epic.version if epic else None,
                "epic_fingerprint": artifact_fingerprint(epic) if epic else None,
                "set_version": self._features.set_version(epic.id) if epic else None,
            }
        )

    def feature_set_version(self, requirement_id: RequirementId) -> int:
        epic = self._epics.get_by_requirement_id(requirement_id)
        return self._features.set_version(epic.id) if epic else 1

    def input_artifact_ids(
        self, requirement_id: RequirementId, feature_id: FeatureId | None = None
    ) -> tuple[str, ...]:
        epic = self._epics.get_by_requirement_id(requirement_id)
        return ((epic.id.value,) if epic else ()) + ((feature_id.value,) if feature_id else ())

    def story_set_version(self, feature_id: FeatureId) -> int:
        return self._stories.set_version(feature_id)

    def stories(self, requirement_id: RequirementId, feature_id: FeatureId) -> str:
        requirement = self._requirements.get(requirement_id)
        analysis = self._analyses.get_by_requirement_id(requirement_id)
        epic = self._epics.get_by_requirement_id(requirement_id)
        feature = self._features.get(epic.id, feature_id) if epic else None
        stories = self._stories.get_by_feature_id(feature_id)
        return _token(
            {
                "scope": "stories",
                "requirement": asdict(requirement) if requirement else None,
                "analysis": asdict(analysis) if analysis else None,
                "epic": asdict(epic) if epic else None,
                "feature_id": feature_id.value,
                "feature": asdict(feature) if feature else None,
                "set_version": self._stories.set_version(feature_id),
                "stories": [
                    asdict(item) for item in sorted(stories, key=lambda value: value.id.value)
                ],
            }
        )

    def story(self, requirement_id: RequirementId, feature_id: FeatureId, story_id: StoryId) -> str:
        story = self._stories.get(feature_id, story_id)
        return _token(
            {
                "scope": "story",
                "stories_context": self.stories(requirement_id, feature_id),
                "story_id": story_id.value,
                "story_version": story.version if story else None,
                "story_fingerprint": artifact_fingerprint(story) if story else None,
            }
        )

    def require_operation(
        self,
        requirement_id: RequirementId,
        operation: AiJobOperation,
        arguments: Mapping[str, object],
    ) -> None:
        """Verify a queued command against the current generation input snapshot."""
        current = self.for_operation(requirement_id, operation, arguments)
        if current is None:
            return
        displayed = arguments.get("context_token")
        if not isinstance(displayed, str) or not displayed.strip():
            raise ArtifactVersionConflictError(
                "A generation context token is required. Reload before trying again."
            )
        self.require(displayed, current)

    def for_operation(
        self,
        requirement_id: RequirementId,
        operation: AiJobOperation,
        arguments: Mapping[str, object],
    ) -> str | None:
        """Resolve the generation context required by an asynchronous operation."""
        if operation is AiJobOperation.ANALYSE_REQUIREMENT:
            return self.analysis(requirement_id)
        if operation is AiJobOperation.GENERATE_EPIC:
            return self.epic(requirement_id)
        if operation is AiJobOperation.GENERATE_FEATURES:
            return self.features(requirement_id)
        if operation not in {
            AiJobOperation.GENERATE_STORIES,
            AiJobOperation.REGENERATE_STORY,
            AiJobOperation.REGENERATE_STORY_SET,
            AiJobOperation.PROPOSE_STORY_CHANGE,
            AiJobOperation.EVALUATE_FEATURE_QUALITY,
        }:
            return None
        raw_feature_id = arguments.get("feature_id")
        if not isinstance(raw_feature_id, str):
            raise ArtifactVersionConflictError(
                "A Feature identity is required. Reload before trying again."
            )
        feature_id = FeatureId(raw_feature_id)
        if operation is AiJobOperation.REGENERATE_STORY:
            raw_story_id = arguments.get("story_id")
            if not isinstance(raw_story_id, str):
                raise ArtifactVersionConflictError(
                    "A Story identity is required. Reload before trying again."
                )
            return self.story(requirement_id, feature_id, StoryId(raw_story_id))
        return self.stories(requirement_id, feature_id)

    @staticmethod
    def require(displayed: str, current: str) -> None:
        if not hmac.compare_digest(displayed, current):
            raise ArtifactVersionConflictError(
                "The generation context changed. Reload and reconcile before trying again."
            )


def _token(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"{CONTEXT_TOKEN_FORMAT}:{hashlib.sha256(encoded).hexdigest()}"
