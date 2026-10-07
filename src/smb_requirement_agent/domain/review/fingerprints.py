"""Canonical approval subjects: what an approval attests to (ADR-0021).

The output is part of every recorded approval. A change here makes existing approvals
non-current; `tests/characterisation/golden/fingerprints.json` pins it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.breakdown.domain.architecture.entities import ArchitectureImpact
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


def _digest(payload: object) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _provenance(item: Epic | Feature | UserStory) -> list[str]:
    value = item.provenance
    return [value.generated_at.isoformat(), value.model, value.prompt_version]


def _staleness(item: Epic | Feature | UserStory) -> list[str] | None:
    value = item.staleness
    return [value.reason.value, value.since.isoformat()] if value else None


def _architecture(value: ArchitectureImpact | None) -> object:
    if value is None:
        return None
    return {
        "knowledge_version": value.knowledge_version,
        "mapped_at": value.mapped_at.isoformat(),
        "systems": [
            {
                "id": system.id,
                "name": system.name,
                "catalogued": system.catalogued,
                "capabilities": sorted(
                    ([item.id, item.name] for item in system.capabilities),
                    key=lambda item: item[0],
                ),
                "squads": [[item.id, item.name] for item in system.squads],
                "value_streams": [[item.id, item.name] for item in system.value_streams],
                "products": [[item.id, item.name] for item in system.products],
            }
            for system in sorted(value.systems, key=lambda item: item.id)
        ],
        "dependencies": sorted(item.digest_fields() for item in value.dependencies),
    }


def artifact_fingerprint(item: Epic | Feature | UserStory) -> str:
    common: dict[str, object] = {
        "id": item.id.value,
        "provenance": _provenance(item),
        "staleness": _staleness(item),
    }
    if item.source_lineage:
        common["source_lineage"] = [asdict(origin) for origin in item.source_lineage]
    payload: dict[str, object]
    if isinstance(item, Epic):
        payload = {
            **common,
            "kind": "epic",
            "requirement_id": item.requirement_id.value,
            "name": item.name.value,
            "outcome": item.outcome.value,
            "business_case": item.business_case.value,
        }
    elif isinstance(item, Feature):
        payload = {
            **common,
            "kind": "feature",
            "epic_id": item.epic_id.value,
            "name": item.name.value,
            "outcome": item.outcome.value,
            "delivery_drop": item.delivery_drop.value,
            "splitting_pattern": item.splitting_pattern.value,
            "splitting_rationale": item.splitting_rationale.value,
            "architecture": _architecture(item.architecture),
        }
    else:
        payload = {
            **common,
            "kind": "story",
            "feature_id": item.feature_id.value,
            "role": item.role.value,
            "action": item.action.value,
            "value": item.value.value,
            "acceptance_criteria": [
                [entry.given, entry.when, entry.then] for entry in item.acceptance_criteria
            ],
            "architecture": _architecture(item.architecture),
        }
    return _digest(payload)


def breakdown_fingerprint(
    requirement: Requirement,
    analysis: RequirementAnalysis,
    epic: Epic,
    features: tuple[Feature, ...],
    stories: tuple[UserStory, ...],
    review: BreakdownReview,
) -> str:
    return _digest(
        {
            "requirement": [requirement.id.value, requirement.version.value],
            "analysis": {
                "id": analysis.id.value if analysis.id else None,
                "round": analysis.round_number,
                "source_version": (
                    analysis.source_requirement_version.value
                    if analysis.source_requirement_version
                    else None
                ),
                "confirmed": analysis.is_human_confirmed,
            },
            "epic": artifact_fingerprint(epic),
            "features": [
                artifact_fingerprint(item) for item in sorted(features, key=lambda x: x.id.value)
            ],
            "stories": [
                artifact_fingerprint(item) for item in sorted(stories, key=lambda x: x.id.value)
            ],
            "review": {
                "ruleset": review.ruleset_version,
                "evidence": review.evidence_fingerprint,
                "flags": [
                    [
                        item.id.value,
                        item.status.value,
                        item.resolution_decision_id.value if item.resolution_decision_id else None,
                    ]
                    for item in sorted(review.flags, key=lambda x: x.id.value)
                ],
            },
        }
    )
