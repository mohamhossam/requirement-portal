"""Whether a breakdown can be submitted and approved (ADR-0021, ADR-0103 §4).

`artifact_states` lists each Epic, Feature and Story with the fingerprint an approval of it must
attest to. `readiness_reasons` says, in a fixed order, everything that stops the breakdown being
submitted or approved; an empty result means ready. `approval_subject` is what a final
approval attests to.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.review.evidence import ReviewEvidence, evidence_fingerprint
from smb_requirement_agent.domain.review.fingerprints import (
    artifact_fingerprint,
    breakdown_fingerprint,
)
from smb_requirement_agent.shared_kernel.approval import (
    Approval,
    ApprovalTarget,
    ApprovalTargetKind,
)
from smb_requirement_agent.shared_kernel.generation import GenerationStatus


@dataclass(frozen=True)
class ArtifactApprovalState:
    target: ApprovalTarget
    parent_id: str | None
    label: str
    status: GenerationStatus
    fingerprint: str
    version: int
    current_approval: Approval | None
    approvals: tuple[Approval, ...]


def artifact_states(evidence: ReviewEvidence) -> tuple[ArtifactApprovalState, ...]:
    items: list[tuple[ApprovalTargetKind, Epic | Feature | UserStory, str]] = []
    if evidence.epic is not None:
        items.append((ApprovalTargetKind.EPIC, evidence.epic, evidence.epic.name.value))
    items.extend((ApprovalTargetKind.FEATURE, item, item.name.value) for item in evidence.features)
    items.extend((ApprovalTargetKind.STORY, item, item.voice) for item in evidence.stories)
    result: list[ArtifactApprovalState] = []
    for kind, item, label in items:
        fingerprint = artifact_fingerprint(item)
        result.append(
            ArtifactApprovalState(
                ApprovalTarget(kind, item.id.value),
                (
                    item.requirement_id.value
                    if isinstance(item, Epic)
                    else item.epic_id.value
                    if isinstance(item, Feature)
                    else item.feature_id.value
                ),
                label,
                item.status,
                fingerprint,
                item.version,
                item.current_approval(fingerprint),
                item.approvals,
            )
        )
    return tuple(result)


def readiness_reasons(
    evidence: ReviewEvidence,
    review: BreakdownReview,
    artifacts: tuple[ArtifactApprovalState, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if evidence.stale_reference_proposal_ids:
        reasons.append(
            "Cited reference evidence changed. "
            "Re-analyse and reconcile its applicability before approval."
        )
    if not evidence.analysis.is_human_confirmed:
        reasons.append("The current analysis is not owner-confirmed.")
    if evidence.epic is None:
        reasons.append("The breakdown has no Epic.")
    if not evidence.features:
        reasons.append("The breakdown has no Features.")
    story_feature_ids = {item.feature_id for item in evidence.stories}
    missing_story_features = [
        item.id.value for item in evidence.features if item.id not in story_feature_ids
    ]
    if missing_story_features:
        reasons.append("Every Feature must have at least one Story.")
    if any(item.is_stale for item in ([evidence.epic] if evidence.epic else [])) or any(
        item.is_stale for item in (*evidence.features, *evidence.stories)
    ):
        reasons.append("All backlog artifacts must be current.")
    if any(
        item.current_approval is None or item.status is not GenerationStatus.APPROVED
        for item in artifacts
    ):
        reasons.append("Every Epic, Feature, and Story needs a current attributed approval.")
    if review.evidence_fingerprint != evidence_fingerprint(evidence):
        reasons.append("The breakdown review is stale and must be refreshed.")
    return tuple(reasons)


def approval_subject(evidence: ReviewEvidence, review: BreakdownReview) -> str | None:
    if evidence.epic is None or not evidence.features:
        return None
    return breakdown_fingerprint(
        evidence.requirement,
        evidence.analysis,
        evidence.epic,
        evidence.features,
        evidence.stories,
        review,
    )
