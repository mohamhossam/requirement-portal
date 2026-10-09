"""The evidence a breakdown review is built from, and its change-detecting fingerprint."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass

from smb_requirement_agent.analysis.domain.entities import (
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.breakdown.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.breakdown.domain.story.quality import StoryQualityEvidence
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


@dataclass(frozen=True)
class ReviewEvidence:
    requirement: Requirement
    analysis: RequirementAnalysis
    epic: Epic | None
    features: tuple[Feature, ...]
    stories: tuple[UserStory, ...]
    questions: tuple[ClarificationQuestion, ...] = ()
    stale_reference_proposal_ids: tuple[str, ...] = ()


def evidence_fingerprint(evidence: ReviewEvidence) -> str:
    payload = {
        "quality_context": [
            asdict(
                StoryQualityEvidence.from_context(evidence.requirement, evidence.analysis, feature)
            )
            for feature in evidence.features
        ],
        "analysis": {
            "facts": [item.statement for item in evidence.analysis.known_facts],
            "constraints": [item.statement for item in evidence.analysis.constraints],
            "rules": [item.statement for item in evidence.analysis.business_rules],
            "assumptions": [item.statement for item in evidence.analysis.assumptions],
            "questions": [
                [item.question, item.rationale] for item in evidence.analysis.open_questions
            ],
            "ambiguities": [
                [item.statement, item.reason] for item in evidence.analysis.ambiguities
            ],
            "potential_dependencies": [
                item.statement for item in evidence.analysis.potential_dependencies
            ],
            "clarifications": [
                [item.kind.value, item.subject, item.answer]
                for item in evidence.analysis.clarifications
            ],
            "collaborative_questions": [
                [
                    item.id.value,
                    item.kind.value,
                    item.subject,
                    item.severity.value,
                    item.is_blocker,
                    item.status.value,
                ]
                for item in evidence.questions
            ],
        },
        "epic": _epic_evidence(evidence.epic) if evidence.epic else None,
        "features": [_feature_evidence(item) for item in evidence.features],
        "stories": [_story_evidence(item) for item in evidence.stories],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    references = [
        (p.id.value, [asdict(c) for c in p.reference_evidence])
        for p in evidence.analysis.intent_proposals
        if p.reference_evidence
    ]
    if references:
        canonical += json.dumps(
            {"references": references, "stale": evidence.stale_reference_proposal_ids},
            sort_keys=True,
            separators=(",", ":"),
        )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _generation_evidence(item: Epic | Feature | UserStory) -> dict[str, object]:
    return {
        "id": item.id.value,
        "stale": item.is_stale,
        "architecture": _architecture_evidence(
            item.architecture if isinstance(item, (Feature, UserStory)) else None
        ),
    }


def _feature_evidence(item: Feature) -> dict[str, object]:
    return {
        **_generation_evidence(item),
        "name": item.name.value,
        "outcome": item.outcome.value,
        "delivery_drop": item.delivery_drop.value,
        "splitting_pattern": item.splitting_pattern.value,
        "splitting_rationale": item.splitting_rationale.value,
    }


def _epic_evidence(item: Epic) -> dict[str, object]:
    return {
        **_generation_evidence(item),
        "name": item.name.value,
        "outcome": item.outcome.value,
        "business_case": item.business_case.value,
    }


def _story_evidence(item: UserStory) -> dict[str, object]:
    return {
        **_generation_evidence(item),
        "feature_id": item.feature_id.value,
        "voice": item.voice,
        "criteria": [[entry.given, entry.when, entry.then] for entry in item.acceptance_criteria],
    }


def _architecture_evidence(value: ArchitectureImpact | None) -> object:
    if value is None:
        return None
    return {
        "version": value.knowledge_version,
        "systems": [
            {
                "id": item.id,
                "capabilities": [capability.id for capability in item.capabilities],
                "squads": [squad.id for squad in item.squads],
                "value_streams": [stream.id for stream in item.value_streams],
                "products": [product.id for product in item.products],
            }
            for item in value.systems
        ],
        "dependencies": [item.digest_fields() for item in value.dependencies],
    }
