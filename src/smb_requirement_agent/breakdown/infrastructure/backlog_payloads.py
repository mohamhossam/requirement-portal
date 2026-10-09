"""Snapshot mapping for the generated backlog.

Epics, Features, Stories and Story change proposals.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import TypeAdapter

from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.breakdown.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
)
from smb_requirement_agent.breakdown.domain.feature.entities import Feature
from smb_requirement_agent.breakdown.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureName,
    FeatureOutcome,
    SplittingPattern,
    SplittingRationale,
)
from smb_requirement_agent.breakdown.domain.story.entities import (
    StoryChangeOperation,
    StoryChangeProposal,
    StoryDraft,
    UserStory,
)
from smb_requirement_agent.breakdown.domain.story.value_objects import (
    AcceptanceCriterion,
    BusinessValue,
    DesiredAction,
    StoryId,
    StoryProposalId,
    UserRole,
)
from smb_requirement_agent.breakdown.infrastructure.backlog_codecs import (
    architecture_from_payload,
    architecture_to_payload,
    quality_assessment_from_payload,
    quality_assessment_to_payload,
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
    generation_from_payload,
    generation_to_payload,
)
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


def epic_to_payload(value: Epic) -> JsonObject:
    return {
        "source_lineage": TypeAdapter(tuple[SourceLineage, ...]).dump_python(
            value.source_lineage, mode="json"
        ),
        "id": value.id.value,
        "requirement_id": value.requirement_id.value,
        "name": value.name.value,
        "outcome": value.outcome.value,
        "business_case": value.business_case.value,
        "version": value.version,
        **generation_to_payload(value.status, value.provenance, value.staleness, value.approvals),
    }


def epic_from_payload(data: JsonObject) -> Epic:
    status, provenance, staleness, approvals = generation_from_payload(data)
    return Epic(
        source_lineage=TypeAdapter(tuple[SourceLineage, ...]).validate_python(
            data.get("source_lineage", [])
        ),
        id=EpicId(required_text(data, "id")),
        requirement_id=RequirementId(required_text(data, "requirement_id")),
        name=EpicName(required_text(data, "name")),
        outcome=BusinessOutcome(required_text(data, "outcome")),
        business_case=BusinessCase(required_text(data, "business_case")),
        status=status,
        provenance=provenance,
        staleness=staleness,
        approvals=approvals,
        version=optional_integer(data, "version", 1),
    )


def feature_to_payload(value: Feature) -> JsonObject:
    return {
        "source_lineage": TypeAdapter(tuple[SourceLineage, ...]).dump_python(
            value.source_lineage, mode="json"
        ),
        "id": value.id.value,
        "epic_id": value.epic_id.value,
        "name": value.name.value,
        "outcome": value.outcome.value,
        "delivery_drop": value.delivery_drop.value,
        "splitting_pattern": value.splitting_pattern.value,
        "splitting_rationale": value.splitting_rationale.value,
        "architecture": architecture_to_payload(value.architecture),
        "version": value.version,
        **generation_to_payload(value.status, value.provenance, value.staleness, value.approvals),
    }


def feature_from_payload(data: JsonObject) -> Feature:
    status, provenance, staleness, approvals = generation_from_payload(data)
    return Feature(
        source_lineage=TypeAdapter(tuple[SourceLineage, ...]).validate_python(
            data.get("source_lineage", [])
        ),
        id=FeatureId(required_text(data, "id")),
        epic_id=EpicId(required_text(data, "epic_id")),
        name=FeatureName(required_text(data, "name")),
        outcome=FeatureOutcome(required_text(data, "outcome")),
        delivery_drop=DeliveryDrop(required_text(data, "delivery_drop")),
        splitting_pattern=SplittingPattern(required_text(data, "splitting_pattern")),
        splitting_rationale=SplittingRationale(required_text(data, "splitting_rationale")),
        architecture=architecture_from_payload(data.get("architecture")),
        status=status,
        provenance=provenance,
        staleness=staleness,
        approvals=approvals,
        version=optional_integer(data, "version", 1),
    )


def story_to_payload(value: UserStory) -> JsonObject:
    return {
        "source_lineage": TypeAdapter(tuple[SourceLineage, ...]).dump_python(
            value.source_lineage, mode="json"
        ),
        "id": value.id.value,
        "feature_id": value.feature_id.value,
        "role": value.role.value,
        "action": value.action.value,
        "value": value.value.value,
        "acceptance_criteria": [
            {"given": item.given, "when": item.when, "then": item.then}
            for item in value.acceptance_criteria
        ],
        "architecture": architecture_to_payload(value.architecture),
        "version": value.version,
        **generation_to_payload(value.status, value.provenance, value.staleness, value.approvals),
    }


def story_from_payload(data: JsonObject) -> UserStory:
    status, provenance, staleness, approvals = generation_from_payload(data)
    return UserStory(
        source_lineage=TypeAdapter(tuple[SourceLineage, ...]).validate_python(
            data.get("source_lineage", [])
        ),
        id=StoryId(required_text(data, "id")),
        feature_id=FeatureId(required_text(data, "feature_id")),
        role=UserRole(required_text(data, "role")),
        action=DesiredAction(required_text(data, "action")),
        value=BusinessValue(required_text(data, "value")),
        acceptance_criteria=tuple(
            AcceptanceCriterion(
                required_text(json_object(item), "given"),
                required_text(json_object(item), "when"),
                required_text(json_object(item), "then"),
            )
            for item in json_array(data, "acceptance_criteria")
        ),
        architecture=architecture_from_payload(data.get("architecture")),
        status=status,
        provenance=provenance,
        staleness=staleness,
        approvals=approvals,
        version=optional_integer(data, "version", 1),
    )


def story_proposal_to_payload(value: StoryChangeProposal) -> JsonObject:
    return {
        "prepared_candidates": [story_to_payload(item) for item in value.prepared_candidates],
        "quality_assessments": [
            quality_assessment_to_payload(item) for item in value.quality_assessments
        ],
        "source_set_fingerprint": value.source_set_fingerprint,
        "generation_context": value.generation_context,
        "version": value.version,
        "id": value.id.value,
        "feature_id": value.feature_id.value,
        "operation": value.operation.value,
        "source_story_ids": [item.value for item in value.source_story_ids],
        "source_fingerprint": value.source_fingerprint,
        "candidates": [
            {
                "role": candidate.role.value,
                "action": candidate.action.value,
                "value": candidate.value.value,
                "acceptance_criteria": [
                    {"given": item.given, "when": item.when, "then": item.then}
                    for item in candidate.acceptance_criteria
                ],
                "provenance": None
                if candidate.provenance is None
                else {
                    "generated_at": candidate.provenance.generated_at.isoformat(),
                    "model": candidate.provenance.model,
                    "prompt_version": candidate.provenance.prompt_version,
                },
            }
            for candidate in value.candidates
        ],
    }


def story_proposal_from_payload(data: JsonObject) -> StoryChangeProposal:
    return StoryChangeProposal(
        id=StoryProposalId(required_text(data, "id")),
        feature_id=FeatureId(required_text(data, "feature_id")),
        operation=StoryChangeOperation(required_text(data, "operation")),
        source_story_ids=tuple(
            StoryId(item_text(item)) for item in json_array(data, "source_story_ids")
        ),
        source_fingerprint=required_text(data, "source_fingerprint"),
        candidates=tuple(
            _story_draft_from_payload(json_object(item)) for item in json_array(data, "candidates")
        ),
        version=optional_integer(data, "version", 1),
        prepared_candidates=tuple(
            story_from_payload(json_object(item))
            for item in optional_json_array(data, "prepared_candidates")
        ),
        quality_assessments=tuple(
            quality_assessment_from_payload(json_object(item))
            for item in optional_json_array(data, "quality_assessments")
        ),
        source_set_fingerprint=nullable_text(data, "source_set_fingerprint"),
        generation_context=nullable_text(data, "generation_context"),
    )


def _story_draft_from_payload(data: JsonObject) -> StoryDraft:
    raw_provenance = data.get("provenance")
    provenance = None
    if raw_provenance is not None:
        item = json_object(raw_provenance)
        provenance = Provenance(
            datetime.fromisoformat(required_text(item, "generated_at")),
            required_text(item, "model"),
            required_text(item, "prompt_version"),
        )
    return StoryDraft(
        UserRole(required_text(data, "role")),
        DesiredAction(required_text(data, "action")),
        BusinessValue(required_text(data, "value")),
        tuple(
            AcceptanceCriterion(
                required_text(json_object(item), "given"),
                required_text(json_object(item), "when"),
                required_text(json_object(item), "then"),
            )
            for item in json_array(data, "acceptance_criteria")
        ),
        provenance,
    )
