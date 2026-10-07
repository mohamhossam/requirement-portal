"""The characterised values: persisted payloads, approval fingerprints and context tokens.

Each case computes a value from the fixed samples with today's production code. The golden
files under `golden/` hold what that code produced when PR 1 of the bounded-context migration
was recorded (ADR-0103). A later PR that changes any of these values changes stored data,
invalidates existing approvals, or rejects tokens that clients already hold.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidencePort
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.value_objects import IntentProposal
from smb_requirement_agent.domain.review.evidence import evidence_fingerprint
from smb_requirement_agent.domain.review.fingerprints import (
    artifact_fingerprint,
    breakdown_fingerprint,
)
from smb_requirement_agent.domain.review.policy import BreakdownReviewPolicy
from smb_requirement_agent.identity.infrastructure.identity_payloads import (
    access_from_payload,
    access_to_payload,
    draft_ownership_from_payload,
    draft_ownership_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.activity_codec import (
    activity_from_payload,
    activity_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.analysis_payloads import (
    analysis_from_payload,
    analysis_round_from_payload,
    analysis_round_to_payload,
    analysis_to_payload,
    clarification_question_from_payload,
    clarification_question_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.backlog_payloads import (
    epic_from_payload,
    epic_to_payload,
    feature_from_payload,
    feature_to_payload,
    story_from_payload,
    story_proposal_from_payload,
    story_proposal_to_payload,
    story_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.document_payloads import (
    document_from_payload,
    document_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_audit_repository import (
    InMemoryAnalysisAuditRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_analysis_repository import (
    InMemoryRequirementAnalysisRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_document_repository import (
    InMemoryDocumentRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_epic_repository import (
    InMemoryEpicRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_feature_repository import (
    InMemoryFeatureRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_story_repository import (
    InMemoryStoryChangeProposalRepository,
    InMemoryStoryRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_transaction import (
    InMemoryTransactionManager,
)
from smb_requirement_agent.infrastructure.persistence.knowledge_payloads import (
    historic_requirement_state_from_payload,
    historic_requirement_state_to_payload,
    reference_document_state_from_payload,
    reference_document_state_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.requirement_snapshot import (
    requirement_draft_from_payload,
    requirement_draft_to_payload,
    requirement_from_payload,
    requirement_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.review_payloads import (
    review_from_payload,
    review_to_payload,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.characterisation import samples


@dataclass(frozen=True)
class PayloadCase:
    """A sample aggregate and the codec that persists it."""

    sample: Callable[[], Any]
    encode: Callable[[Any], Any]
    decode: Callable[[Any], Any]


PAYLOAD_CASES: dict[str, PayloadCase] = {
    "requirement": PayloadCase(
        samples.requirement, requirement_to_payload, requirement_from_payload
    ),
    "requirement_draft": PayloadCase(
        samples.requirement_draft, requirement_draft_to_payload, requirement_draft_from_payload
    ),
    "analysis": PayloadCase(samples.analysis, analysis_to_payload, analysis_from_payload),
    "analysis_round": PayloadCase(
        samples.analysis_round, analysis_round_to_payload, analysis_round_from_payload
    ),
    "question_open": PayloadCase(
        samples.open_question,
        clarification_question_to_payload,
        clarification_question_from_payload,
    ),
    "question_resolved": PayloadCase(
        samples.resolved_question,
        clarification_question_to_payload,
        clarification_question_from_payload,
    ),
    "epic_approved": PayloadCase(samples.approved_epic, epic_to_payload, epic_from_payload),
    "epic_stale": PayloadCase(samples.stale_epic, epic_to_payload, epic_from_payload),
    "feature_mapped": PayloadCase(samples.feature, feature_to_payload, feature_from_payload),
    "feature_approved_stale": PayloadCase(
        samples.second_feature, feature_to_payload, feature_from_payload
    ),
    "story_mapped": PayloadCase(samples.story, story_to_payload, story_from_payload),
    "story_approved": PayloadCase(samples.second_story, story_to_payload, story_from_payload),
    "story_proposal": PayloadCase(
        samples.story_proposal, story_proposal_to_payload, story_proposal_from_payload
    ),
    "breakdown_review": PayloadCase(samples.review, review_to_payload, review_from_payload),
    "source_document": PayloadCase(samples.document, document_to_payload, document_from_payload),
    "requirement_access": PayloadCase(samples.access, access_to_payload, access_from_payload),
    "draft_ownership": PayloadCase(
        samples.draft_ownership, draft_ownership_to_payload, draft_ownership_from_payload
    ),
    "activity_event": PayloadCase(
        samples.activity_event, activity_to_payload, activity_from_payload
    ),
    "reference_document_state": PayloadCase(
        samples.reference_document_state,
        reference_document_state_to_payload,
        reference_document_state_from_payload,
    ),
    "historic_requirement_state": PayloadCase(
        samples.historic_requirement_state,
        historic_requirement_state_to_payload,
        historic_requirement_state_from_payload,
    ),
}


def fingerprints() -> dict[str, str]:
    """ADR-0021 approval subjects and the review's evidence fingerprint."""
    evidence = samples.review_evidence()
    return {
        "artifact_epic_generated": artifact_fingerprint(samples.epic()),
        "artifact_epic_approved": artifact_fingerprint(samples.approved_epic()),
        "artifact_epic_stale": artifact_fingerprint(samples.stale_epic()),
        "artifact_feature_mapped": artifact_fingerprint(samples.feature()),
        "artifact_feature_approved_stale": artifact_fingerprint(samples.second_feature()),
        "artifact_story_mapped": artifact_fingerprint(samples.story()),
        "artifact_story_approved": artifact_fingerprint(samples.second_story()),
        "breakdown": breakdown_fingerprint(
            samples.requirement(),
            samples.analysis(),
            samples.approved_epic(),
            (samples.feature(), samples.second_feature()),
            (samples.story(), samples.second_story()),
            samples.review(),
        ),
        "review_evidence": evidence_fingerprint(evidence),
    }


def built_review() -> Any:
    """The review the deterministic review policy builds from the sample evidence."""
    review = BreakdownReviewPolicy().build(
        samples.review_evidence(), (samples.assessment(),), samples.T3
    )
    return review_to_payload(review)


class _CurrentReferences:
    """Every cited publication is current: the samples cite nothing withdrawn."""

    def stale_analysis(
        self, analysis: RequirementAnalysis, *, target_ids: Sequence[str] | None = None
    ) -> tuple[str, ...]:
        del analysis, target_ids
        return ()

    def stale_proposals(self, proposals: Sequence[IntentProposal]) -> tuple[str, ...]:
        del proposals
        return ()

    def require_current(self, evidence: Sequence[PublishedReference]) -> None:
        del evidence


def context_tokens() -> dict[str, str]:
    """The expected-context tokens for the full sample breakdown."""
    requirements = InMemoryRequirementRepository()
    analyses = InMemoryRequirementAnalysisRepository()
    audit = InMemoryAnalysisAuditRepository(lambda requirement_id: None)
    documents = InMemoryDocumentRepository()
    epics = InMemoryEpicRepository()
    features = InMemoryFeatureRepository()
    stories = InMemoryStoryRepository()
    proposals = InMemoryStoryChangeProposalRepository()
    requirements.add(samples.requirement())
    analyses.save(samples.analysis())
    audit.add_question(samples.open_question())
    audit.add_question(samples.resolved_question())
    documents.add(samples.document())
    epics.save(samples.approved_epic())
    features.replace_for_epic(
        samples.EPIC_ID, [samples.feature(), samples.second_feature()], expected_set_version=1
    )
    stories.replace_for_feature(
        samples.FEATURE_ID, [samples.story(), samples.second_story()], expected_set_version=1
    )
    proposals.save(samples.story_proposal())
    references: ReferenceEvidencePort = _CurrentReferences()
    tokens = GenerationContextTokens(
        requirements,
        analyses,
        audit,
        documents,
        epics,
        features,
        stories,
        proposals,
        transactions=InMemoryTransactionManager(_ignore, threading.RLock()),
        references=references,
    )
    requirement_id = samples.REQUIREMENT_ID
    return {
        "analysis": tokens.analysis(requirement_id),
        "epic": tokens.epic(requirement_id),
        "features": tokens.features(requirement_id),
        "stories": tokens.stories(requirement_id, samples.FEATURE_ID),
        "story": tokens.story(requirement_id, samples.FEATURE_ID, samples.STORY_ID),
    }


def _ignore(requirement_id: RequirementId) -> None:
    del requirement_id
