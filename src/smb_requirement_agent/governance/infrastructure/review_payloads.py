"""Snapshot mapping for breakdown reviews, their flags and review sources."""

from __future__ import annotations

from datetime import datetime

from smb_requirement_agent.breakdown.infrastructure.backlog_codecs import (
    quality_assessment_from_payload,
)
from smb_requirement_agent.governance.domain.review.entities import (
    BreakdownReview,
    BreakdownStatus,
    Decision,
    DecisionId,
    Dependency,
    DependencyEvidenceKind,
    DependencyId,
    Flag,
    FlagCategory,
    FlagId,
    FlagSeverity,
    FlagStatus,
    Recommendation,
    RecommendationId,
    ResolutionPolicy,
    ReviewSource,
    ReviewSourceKind,
    Risk,
    RiskId,
)
from smb_requirement_agent.infrastructure.persistence.payload_fields import (
    JsonObject,
    item_text,
    json_array,
    json_object,
    nullable_text,
    optional_integer,
    optional_json_array,
    required_text,
)
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    actor_fields_from_payload,
    actor_fields_to_payload,
    approval_from_payload,
    approval_to_payload,
    as_snapshot,
    comment_from_payload,
    comment_to_payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def review_to_payload(value: BreakdownReview) -> JsonObject:
    return {
        "version": value.version,
        "requirement_id": value.requirement_id.value,
        "generated_at": value.generated_at.isoformat(),
        "ruleset_version": value.ruleset_version,
        "evidence_fingerprint": value.evidence_fingerprint,
        "knowledge_version": value.knowledge_version,
        "status": value.status.value,
        "submitted_fingerprint": value.submitted_fingerprint,
        "approvals": [approval_to_payload(item) for item in value.approvals],
        "comments": [comment_to_payload(item) for item in value.comments],
        "dependencies": [
            {
                "id": item.id.value,
                "description": item.description,
                "source": _review_source_to_payload(item.source),
                "evidence_kind": item.evidence_kind.value,
            }
            for item in value.dependencies
        ],
        "risks": [
            {
                "id": item.id.value,
                "severity": item.severity.value,
                "description": item.description,
                "source": _review_source_to_payload(item.source),
            }
            for item in value.risks
        ],
        "flags": [
            {
                "id": item.id.value,
                "category": item.category.value,
                "severity": item.severity.value,
                "title": item.title,
                "detail": item.detail,
                "source": _review_source_to_payload(item.source),
                "resolution_policy": item.resolution_policy.value,
                "status": item.status.value,
                "resolution_decision_id": (
                    item.resolution_decision_id.value if item.resolution_decision_id else None
                ),
            }
            for item in value.flags
        ],
        "recommendations": [
            {
                "id": item.id.value,
                "action": item.action,
                "rationale": item.rationale,
                "source": _review_source_to_payload(item.source),
            }
            for item in value.recommendations
        ],
        "quality_assessments": [
            {
                "story_id": item.story_id.value,
                "findings": [
                    {
                        "criterion": finding.criterion.value,
                        "passed": finding.passed,
                        "message": finding.message,
                        "source": finding.source.value,
                    }
                    for finding in item.findings
                ],
                "provenance": {
                    "generated_at": item.provenance.generated_at.isoformat(),
                    "model": item.provenance.model,
                    "prompt_version": item.provenance.prompt_version,
                },
            }
            for item in value.quality_assessments
        ],
        "decisions": [
            {
                "id": item.id.value,
                "decision": item.decision,
                "rationale": item.rationale,
                "recorded_at": item.recorded_at.isoformat(),
                "target_flag_id": item.target_flag_id.value if item.target_flag_id else None,
                "recorded_by": actor_fields_to_payload(item.recorded_by)
                if item.recorded_by
                else None,
            }
            for item in value.decisions
        ],
    }


def review_from_payload(data: JsonObject) -> BreakdownReview:
    return BreakdownReview(
        version=optional_integer(data, "version", 1),
        requirement_id=RequirementId(required_text(data, "requirement_id")),
        generated_at=datetime.fromisoformat(required_text(data, "generated_at")),
        ruleset_version=required_text(data, "ruleset_version"),
        evidence_fingerprint=required_text(data, "evidence_fingerprint"),
        knowledge_version=nullable_text(data, "knowledge_version"),
        status=BreakdownStatus(item_text(data.get("status", BreakdownStatus.GENERATED.value))),
        submitted_fingerprint=nullable_text(data, "submitted_fingerprint"),
        approvals=tuple(
            approval_from_payload(json_object(item))
            for item in optional_json_array(data, "approvals")
        ),
        comments=tuple(
            comment_from_payload(json_object(item))
            for item in optional_json_array(data, "comments")
        ),
        dependencies=tuple(
            Dependency(
                DependencyId(required_text(json_object(item), "id")),
                required_text(json_object(item), "description"),
                _review_source_from_payload(json_object(json_object(item)["source"])),
                DependencyEvidenceKind(required_text(json_object(item), "evidence_kind")),
            )
            for item in json_array(data, "dependencies")
        ),
        risks=tuple(
            Risk(
                RiskId(required_text(json_object(item), "id")),
                FlagSeverity(required_text(json_object(item), "severity")),
                required_text(json_object(item), "description"),
                _review_source_from_payload(json_object(json_object(item)["source"])),
            )
            for item in json_array(data, "risks")
        ),
        flags=tuple(_flag_from_payload(json_object(item)) for item in json_array(data, "flags")),
        recommendations=tuple(
            Recommendation(
                RecommendationId(required_text(json_object(item), "id")),
                required_text(json_object(item), "action"),
                required_text(json_object(item), "rationale"),
                _review_source_from_payload(json_object(json_object(item)["source"])),
            )
            for item in json_array(data, "recommendations")
        ),
        quality_assessments=tuple(
            quality_assessment_from_payload(json_object(item))
            for item in json_array(data, "quality_assessments")
        ),
        decisions=tuple(
            Decision(
                DecisionId(required_text(json_object(item), "id")),
                required_text(json_object(item), "decision"),
                required_text(json_object(item), "rationale"),
                datetime.fromisoformat(required_text(json_object(item), "recorded_at")),
                (
                    FlagId(item_text(json_object(item)["target_flag_id"]))
                    if json_object(item).get("target_flag_id") is not None
                    else None
                ),
                (
                    as_snapshot(
                        actor_fields_from_payload(
                            json_object(json_object(item)["recorded_by"]), snapshot=True
                        )
                    )
                    if json_object(item).get("recorded_by") is not None
                    else None
                ),
            )
            for item in json_array(data, "decisions")
        ),
    )


def _review_source_to_payload(value: ReviewSource) -> JsonObject:
    return {"kind": value.kind.value, "item_id": value.item_id, "label": value.label}


def _review_source_from_payload(data: JsonObject) -> ReviewSource:
    return ReviewSource(
        ReviewSourceKind(required_text(data, "kind")),
        required_text(data, "item_id"),
        required_text(data, "label"),
    )


def _flag_from_payload(data: JsonObject) -> Flag:
    raw_decision_id = data.get("resolution_decision_id")
    return Flag(
        FlagId(required_text(data, "id")),
        FlagCategory(required_text(data, "category")),
        FlagSeverity(required_text(data, "severity")),
        required_text(data, "title"),
        required_text(data, "detail"),
        _review_source_from_payload(json_object(data["source"])),
        ResolutionPolicy(required_text(data, "resolution_policy")),
        FlagStatus(required_text(data, "status")),
        DecisionId(item_text(raw_decision_id)) if raw_decision_id is not None else None,
    )
