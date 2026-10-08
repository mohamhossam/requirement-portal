"""Snapshot mapping for requirement analyses, analysis rounds and clarification questions."""

from __future__ import annotations

from datetime import datetime

from pydantic import TypeAdapter

from smb_requirement_agent.analysis.domain.entities import (
    AnalysisDocumentReference,
    AnalysisQuestionChange,
    AnalysisRound,
    AnalysisStageProvenance,
    ClarificationQuestion,
    QuestionAssignmentChange,
    RequirementAnalysis,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    Ambiguity,
    AnalysisClarificationEvidence,
    AnalysisEvidenceReference,
    AnalysisId,
    Assumption,
    BusinessRule,
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    ClarificationStatus,
    Constraint,
    HumanClarification,
    IntentProposal,
    IntentProposalDecision,
    IntentProposalId,
    IntentProposalKind,
    IntentProposalStatus,
    KnownFact,
    OpenQuestion,
    PotentialDependency,
    QuestionChangeAction,
    QuestionId,
)
from smb_requirement_agent.infrastructure.persistence.payload_fields import (
    JsonObject,
    boolean_field,
    integer_field,
    item_text,
    json_array,
    json_object,
    nullable_text,
    optional_datetime,
    optional_integer,
    optional_json_array,
    required_text,
    text_array,
)
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    actor_fields_from_payload,
    actor_fields_to_payload,
    as_snapshot,
    optional_actor_snapshot,
    required_actor_snapshot,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import RequirementVersion
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


def analysis_to_payload(value: RequirementAnalysis) -> JsonObject:
    return {
        "source_lineage": TypeAdapter(tuple[SourceLineage, ...]).dump_python(
            value.source_lineage, mode="json"
        ),
        "clarification_evidence": [
            {
                "evidence_key": item.evidence_key,
                "clarification_numbers": list(item.clarification_numbers),
            }
            for item in value.clarification_evidence
        ],
        "version": value.version,
        "requirement_id": value.requirement_id.value,
        "known_facts": [
            _analysis_item_payload(item.statement, item.evidence_references)
            for item in value.known_facts
        ],
        "constraints": [
            _analysis_item_payload(item.statement, item.evidence_references)
            for item in value.constraints
        ],
        "business_rules": [
            _analysis_item_payload(item.statement, item.evidence_references)
            for item in value.business_rules
        ],
        "assumptions": [
            _analysis_item_payload(item.statement, item.evidence_references)
            for item in value.assumptions
        ],
        "open_questions": [
            {
                "question": item.question,
                "rationale": item.rationale,
                "evidence_references": evidence_payload(item.evidence_references),
            }
            for item in value.open_questions
        ],
        "ambiguities": [
            {
                "statement": item.statement,
                "reason": item.reason,
                "evidence_references": evidence_payload(item.evidence_references),
            }
            for item in value.ambiguities
        ],
        "potential_dependencies": [
            _analysis_item_payload(item.statement, item.evidence_references)
            for item in value.potential_dependencies
        ],
        "clarifications": [
            {
                "kind": item.kind.value,
                "subject": item.subject,
                "answer": item.answer,
                "question_id": item.question_id.value if item.question_id else None,
                "answered_by": (
                    actor_fields_to_payload(item.answered_by) if item.answered_by else None
                ),
                "answered_at": item.answered_at.isoformat() if item.answered_at else None,
                "source_suggestion_id": item.source_suggestion_id,
                "source_lineage": TypeAdapter(tuple[SourceLineage, ...]).dump_python(
                    item.source_lineage, mode="json"
                ),
            }
            for item in value.clarifications
        ],
        "confirmed_at": value.confirmed_at.isoformat() if value.confirmed_at else None,
        "confirmed_by": actor_fields_to_payload(value.confirmed_by) if value.confirmed_by else None,
        "document_references": [
            {
                "document_id": item.document_id,
                "version_id": item.version_id,
                "filename": item.filename,
                "checksum_sha256": item.checksum_sha256,
            }
            for item in value.document_references
        ],
        "analysis_id": value.id.value if value.id else None,
        "round_number": value.round_number,
        "provenance": (
            {
                "generated_at": value.provenance.generated_at.isoformat(),
                "model": value.provenance.model,
                "prompt_version": value.provenance.prompt_version,
            }
            if value.provenance
            else None
        ),
        "source_requirement_version": (
            value.source_requirement_version.value if value.source_requirement_version else None
        ),
        "intent_proposals": [
            {
                "id": item.id.value,
                "kind": item.kind.value,
                "statement": item.statement,
                "rationale": item.rationale,
                "success_measures": list(item.success_measures),
                "reference_evidence": TypeAdapter(tuple[PublishedReference, ...]).dump_python(
                    item.reference_evidence, mode="json"
                ),
                "reference_conflict": item.reference_conflict,
                "reference_provenance": TypeAdapter[Provenance | None](
                    Provenance | None
                ).dump_python(item.reference_provenance, mode="json"),
                "evidence_references": evidence_payload(item.evidence_references),
                "decisions": [
                    {
                        "status": decision.status.value,
                        "final_statement": decision.final_statement,
                        "success_measures": list(decision.success_measures),
                        "decided_by": actor_fields_to_payload(decision.decided_by),
                        "decided_at": decision.decided_at.isoformat(),
                        "version": decision.version,
                        "rationale": decision.rationale,
                    }
                    for decision in item.decisions
                ],
            }
            for item in value.intent_proposals
        ],
        "source_desired_outcome": value.source_desired_outcome,
        "stage_provenance": [
            {
                "stage": item.stage,
                "model": item.model,
                "prompt_version": item.prompt_version,
                "generated_at": item.generated_at.isoformat(),
                "input_fingerprint": item.input_fingerprint,
            }
            for item in value.stage_provenance
        ],
    }


def analysis_from_payload(data: JsonObject) -> RequirementAnalysis:
    return RequirementAnalysis(
        source_lineage=TypeAdapter(tuple[SourceLineage, ...]).validate_python(
            data.get("source_lineage", [])
        ),
        clarification_evidence=tuple(
            AnalysisClarificationEvidence(
                required_text(json_object(item), "evidence_key"),
                tuple(
                    integer_field({"number": number}, "number")
                    for number in json_array(json_object(item), "clarification_numbers")
                ),
            )
            for item in (
                json_array(data, "clarification_evidence")
                if "clarification_evidence" in data
                else []
            )
        ),
        requirement_id=RequirementId(required_text(data, "requirement_id")),
        known_facts=tuple(
            KnownFact(_analysis_item_text(item), _analysis_item_evidence(item))
            for item in json_array(data, "known_facts")
        ),
        constraints=tuple(
            Constraint(_analysis_item_text(item), _analysis_item_evidence(item))
            for item in json_array(data, "constraints")
        ),
        business_rules=tuple(
            BusinessRule(_analysis_item_text(item), _analysis_item_evidence(item))
            for item in json_array(data, "business_rules")
        ),
        assumptions=tuple(
            Assumption(_analysis_item_text(item), _analysis_item_evidence(item))
            for item in json_array(data, "assumptions")
        ),
        open_questions=tuple(
            OpenQuestion(
                required_text(json_object(item), "question"),
                required_text(json_object(item), "rationale"),
                _analysis_item_evidence(item),
            )
            for item in json_array(data, "open_questions")
        ),
        ambiguities=tuple(
            Ambiguity(
                required_text(json_object(item), "statement"),
                required_text(json_object(item), "reason"),
                _analysis_item_evidence(item),
            )
            for item in json_array(data, "ambiguities")
        ),
        potential_dependencies=tuple(
            PotentialDependency(_analysis_item_text(item), _analysis_item_evidence(item))
            for item in json_array(data, "potential_dependencies")
        ),
        clarifications=tuple(
            HumanClarification(
                ClarificationKind(required_text(json_object(item), "kind")),
                required_text(json_object(item), "subject"),
                required_text(json_object(item), "answer"),
                (
                    QuestionId(item_text(json_object(item)["question_id"]))
                    if json_object(item).get("question_id") is not None
                    else None
                ),
                (
                    as_snapshot(
                        actor_fields_from_payload(
                            json_object(json_object(item)["answered_by"]), snapshot=True
                        )
                    )
                    if json_object(item).get("answered_by") is not None
                    else None
                ),
                (
                    datetime.fromisoformat(item_text(json_object(item)["answered_at"]))
                    if json_object(item).get("answered_at") is not None
                    else None
                ),
                nullable_text(json_object(item), "source_suggestion_id"),
                TypeAdapter(tuple[SourceLineage, ...]).validate_python(
                    json_object(item).get("source_lineage", [])
                ),
            )
            for item in json_array(data, "clarifications")
        ),
        confirmed_at=(
            datetime.fromisoformat(item_text(data["confirmed_at"]))
            if data.get("confirmed_at") is not None
            else None
        ),
        confirmed_by=(
            as_snapshot(actor_fields_from_payload(json_object(data["confirmed_by"]), snapshot=True))
            if data.get("confirmed_by") is not None
            else None
        ),
        document_references=tuple(
            AnalysisDocumentReference(
                document_id=required_text(json_object(item), "document_id"),
                version_id=required_text(json_object(item), "version_id"),
                filename=required_text(json_object(item), "filename"),
                checksum_sha256=required_text(json_object(item), "checksum_sha256"),
            )
            for item in (
                json_array(data, "document_references") if "document_references" in data else []
            )
        ),
        id=(AnalysisId(item_text(data["analysis_id"])) if data.get("analysis_id") else None),
        round_number=(
            integer_field(data, "round_number") if data.get("round_number") is not None else None
        ),
        provenance=(
            Provenance(
                datetime.fromisoformat(
                    required_text(json_object(data["provenance"]), "generated_at")
                ),
                required_text(json_object(data["provenance"]), "model"),
                required_text(json_object(data["provenance"]), "prompt_version"),
            )
            if data.get("provenance") is not None
            else None
        ),
        source_requirement_version=(
            RequirementVersion(integer_field(data, "source_requirement_version"))
            if data.get("source_requirement_version") is not None
            else None
        ),
        intent_proposals=tuple(
            IntentProposal(
                IntentProposalId(required_text(json_object(item), "id")),
                IntentProposalKind(required_text(json_object(item), "kind")),
                required_text(json_object(item), "statement"),
                required_text(json_object(item), "rationale"),
                tuple(text_array(json_object(item), "success_measures")),
                tuple(
                    IntentProposalDecision(
                        IntentProposalStatus(required_text(json_object(decision), "status")),
                        (
                            item_text(json_object(decision)["final_statement"])
                            if json_object(decision).get("final_statement") is not None
                            else None
                        ),
                        tuple(text_array(json_object(decision), "success_measures")),
                        as_snapshot(
                            actor_fields_from_payload(
                                json_object(json_object(decision)["decided_by"]), snapshot=True
                            )
                        ),
                        datetime.fromisoformat(required_text(json_object(decision), "decided_at")),
                        integer_field(json_object(decision), "version"),
                        TypeAdapter(str | None).validate_python(
                            json_object(decision).get("rationale")
                        ),
                    )
                    for decision in json_array(json_object(item), "decisions")
                ),
                _analysis_item_evidence(item),
                reference_evidence=TypeAdapter(tuple[PublishedReference, ...]).validate_python(
                    json_object(item).get("reference_evidence", [])
                ),
                reference_conflict=TypeAdapter(bool).validate_python(
                    json_object(item).get("reference_conflict", False), strict=True
                ),
                reference_provenance=TypeAdapter(Provenance | None).validate_python(
                    json_object(item).get("reference_provenance")
                ),
            )
            for item in (json_array(data, "intent_proposals") if "intent_proposals" in data else [])
        ),
        source_desired_outcome=(
            item_text(data["source_desired_outcome"])
            if data.get("source_desired_outcome") is not None
            else None
        ),
        stage_provenance=tuple(
            AnalysisStageProvenance(
                required_text(json_object(item), "stage"),
                required_text(json_object(item), "model"),
                required_text(json_object(item), "prompt_version"),
                datetime.fromisoformat(required_text(json_object(item), "generated_at")),
                required_text(json_object(item), "input_fingerprint"),
            )
            for item in optional_json_array(data, "stage_provenance")
        ),
        version=optional_integer(data, "version", 1),
    )


def analysis_round_to_payload(value: AnalysisRound) -> JsonObject:
    return {
        "analysis": analysis_to_payload(value.analysis),
        "question_ids": [item.value for item in value.question_ids],
        "question_changes": [
            {
                "action": item.action.value,
                "question_id": item.question_id.value,
                "rationale": item.rationale,
                "replacement_question_id": (
                    item.replacement_question_id.value if item.replacement_question_id else None
                ),
            }
            for item in value.question_changes
        ],
    }


def analysis_round_from_payload(data: JsonObject) -> AnalysisRound:
    return AnalysisRound(
        analysis_from_payload(json_object(data["analysis"])),
        tuple(QuestionId(item_text(item)) for item in json_array(data, "question_ids")),
        tuple(
            AnalysisQuestionChange(
                QuestionChangeAction(required_text(json_object(item), "action")),
                QuestionId(required_text(json_object(item), "question_id")),
                required_text(json_object(item), "rationale"),
                (
                    QuestionId(item_text(json_object(item)["replacement_question_id"]))
                    if json_object(item).get("replacement_question_id") is not None
                    else None
                ),
            )
            for item in (json_array(data, "question_changes") if "question_changes" in data else [])
        ),
    )


def clarification_question_to_payload(value: ClarificationQuestion) -> JsonObject:
    return {
        "id": value.id.value,
        "requirement_id": value.requirement_id.value,
        "first_analysis_id": value.first_analysis_id.value,
        "kind": value.kind.value,
        "subject": value.subject,
        "rationale": value.rationale,
        "severity": value.severity.value,
        "is_blocker": value.is_blocker,
        "source": value.source.value,
        "status": value.status.value,
        "version": value.version,
        "asked_by": actor_fields_to_payload(value.asked_by) if value.asked_by else None,
        "asked_at": value.asked_at.isoformat() if value.asked_at else None,
        "assignee": actor_fields_to_payload(value.assignee) if value.assignee else None,
        "assignment_history": [
            {
                "assignee": actor_fields_to_payload(item.assignee) if item.assignee else None,
                "changed_by": actor_fields_to_payload(item.changed_by),
                "changed_at": item.changed_at.isoformat(),
            }
            for item in value.assignment_history
        ],
        "draft_answer": value.draft_answer,
        "draft_updated_by": (
            actor_fields_to_payload(value.draft_updated_by) if value.draft_updated_by else None
        ),
        "draft_updated_at": (
            value.draft_updated_at.isoformat() if value.draft_updated_at else None
        ),
        "answer": value.answer,
        "answered_by": actor_fields_to_payload(value.answered_by) if value.answered_by else None,
        "answered_at": value.answered_at.isoformat() if value.answered_at else None,
        "classification_changed_by": (
            actor_fields_to_payload(value.classification_changed_by)
            if value.classification_changed_by
            else None
        ),
        "classification_changed_at": (
            value.classification_changed_at.isoformat() if value.classification_changed_at else None
        ),
        "replaces_question_id": (
            value.replaces_question_id.value if value.replaces_question_id else None
        ),
    }


def clarification_question_from_payload(data: JsonObject) -> ClarificationQuestion:
    return ClarificationQuestion(
        id=QuestionId(required_text(data, "id")),
        requirement_id=RequirementId(required_text(data, "requirement_id")),
        first_analysis_id=AnalysisId(required_text(data, "first_analysis_id")),
        kind=ClarificationKind(required_text(data, "kind")),
        subject=required_text(data, "subject"),
        rationale=nullable_text(data, "rationale"),
        severity=ClarificationSeverity(required_text(data, "severity")),
        is_blocker=boolean_field(data, "is_blocker"),
        source=ClarificationSource(required_text(data, "source")),
        status=ClarificationStatus(required_text(data, "status")),
        version=integer_field(data, "version"),
        asked_by=optional_actor_snapshot(data, "asked_by"),
        asked_at=optional_datetime(data, "asked_at"),
        assignee=optional_actor_snapshot(data, "assignee"),
        assignment_history=tuple(
            QuestionAssignmentChange(
                optional_actor_snapshot(json_object(item), "assignee"),
                required_actor_snapshot(json_object(item), "changed_by"),
                datetime.fromisoformat(required_text(json_object(item), "changed_at")),
            )
            for item in json_array(data, "assignment_history")
        ),
        draft_answer=nullable_text(data, "draft_answer"),
        draft_updated_by=optional_actor_snapshot(data, "draft_updated_by"),
        draft_updated_at=optional_datetime(data, "draft_updated_at"),
        answer=nullable_text(data, "answer"),
        answered_by=optional_actor_snapshot(data, "answered_by"),
        answered_at=optional_datetime(data, "answered_at"),
        classification_changed_by=optional_actor_snapshot(data, "classification_changed_by"),
        classification_changed_at=optional_datetime(data, "classification_changed_at"),
        replaces_question_id=(
            QuestionId(item_text(data["replaces_question_id"]))
            if data.get("replaces_question_id") is not None
            else None
        ),
    )


def _analysis_item_payload(
    statement: str, values: tuple[AnalysisEvidenceReference, ...]
) -> JsonObject:
    return {"statement": statement, "evidence_references": evidence_payload(values)}


def _analysis_item_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return required_text(json_object(value), "statement")


def _analysis_item_evidence(value: object) -> tuple[AnalysisEvidenceReference, ...]:
    if isinstance(value, str):
        return ()
    data = json_object(value)
    return tuple(
        AnalysisEvidenceReference(
            required_text(json_object(item), "document_id"),
            required_text(json_object(item), "version_id"),
            required_text(json_object(item), "checksum_sha256"),
            required_text(json_object(item), "block_id"),
            required_text(json_object(item), "label"),
        )
        for item in optional_json_array(data, "evidence_references")
    )


def evidence_payload(
    values: tuple[AnalysisEvidenceReference, ...],
) -> list[JsonObject]:
    return [
        {
            "document_id": item.document_id,
            "version_id": item.version_id,
            "checksum_sha256": item.checksum_sha256,
            "block_id": item.block_id,
            "label": item.label,
        }
        for item in values
    ]
