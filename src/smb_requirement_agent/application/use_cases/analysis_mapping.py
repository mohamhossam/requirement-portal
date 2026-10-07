"""Map provider-independent analysis candidates into the domain aggregate."""

import uuid

from smb_requirement_agent.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.application.use_cases.source_lineage import input_lineage
from smb_requirement_agent.domain.analysis.entities import (
    AnalysisDocumentReference,
    AnalysisStageProvenance,
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.value_objects import (
    Ambiguity,
    AnalysisClarificationEvidence,
    AnalysisEvidenceReference,
    AnalysisId,
    Assumption,
    BusinessRule,
    Constraint,
    HumanClarification,
    IntentProposal,
    IntentProposalId,
    IntentProposalStatus,
    KnownFact,
    OpenQuestion,
    PotentialDependency,
    is_additional_intent_proposal,
)
from smb_requirement_agent.domain.requirement.value_objects import RequirementVersion
from smb_requirement_agent.domain.shared.generation import Provenance
from smb_requirement_agent.domain.shared.identifiers import RequirementId


def analysis_evidence_key(kind: str, subject: str) -> str:
    return f"{kind}:{' '.join(subject.casefold().split())}"


def _evidence(
    candidate: RequirementAnalysisCandidate, kind: str, subject: str
) -> tuple[AnalysisEvidenceReference, ...]:
    values = candidate.get("evidence_references", {}).get(analysis_evidence_key(kind, subject), [])
    return tuple(
        AnalysisEvidenceReference(
            item["document_id"],
            item["version_id"],
            item["checksum_sha256"],
            item["block_id"],
            item["label"],
        )
        for item in values
    )


def build_analysis(
    requirement_id: RequirementId,
    candidate: RequirementAnalysisCandidate,
    clarifications: tuple[HumanClarification, ...],
    document_references: tuple[AnalysisDocumentReference, ...],
    *,
    analysis_id: AnalysisId | None = None,
    round_number: int | None = None,
    provenance: Provenance | None = None,
    source_requirement_version: RequirementVersion | None = None,
    carried_intent_proposals: tuple[IntentProposal, ...] = (),
    has_source_outcome: bool = False,
    source_desired_outcome: str | None = None,
    version: int = 1,
) -> RequirementAnalysis:
    """Construct a validated analysis from an analyzer candidate."""
    resolved_subjects = {item.subject.strip() for item in clarifications}

    carried = tuple(
        item for item in carried_intent_proposals if item.status is not IntentProposalStatus.PENDING
    )
    generated = tuple(
        IntentProposal(
            IntentProposalId(str(uuid.uuid4())),
            item["kind"],
            item["statement"],
            item["rationale"],
            tuple(item["success_measures"]),
            (),
            _evidence(candidate, "intent_proposal", item["statement"]),
            item.get("reference_evidence", ()),
            item.get("reference_conflict", False),
            item.get("reference_provenance"),
        )
        for item in candidate["intent_proposals"]
        if (
            not any(
                p.kind == item["kind"]
                and p.statement.casefold() == item["statement"].casefold()
                and p.reference_evidence == item["reference_evidence"]
                for p in carried
            )
            if item.get("reference_evidence")
            else is_additional_intent_proposal(
                item["kind"], item["statement"], carried, has_source_outcome=has_source_outcome
            )
        )
    )

    return RequirementAnalysis(
        source_lineage=input_lineage(clarifications, carried),
        requirement_id=requirement_id,
        known_facts=tuple(
            KnownFact(item, _evidence(candidate, "known_fact", item))
            for item in candidate["known_facts"]
        ),
        constraints=tuple(
            Constraint(item, _evidence(candidate, "constraint", item))
            for item in candidate["constraints"]
        ),
        business_rules=tuple(
            BusinessRule(item, _evidence(candidate, "business_rule", item))
            for item in candidate["business_rules"]
        ),
        assumptions=tuple(
            Assumption(item, _evidence(candidate, "assumption", item))
            for item in candidate["assumptions"]
            if item.strip() not in resolved_subjects
        ),
        open_questions=tuple(
            OpenQuestion(
                item["question"],
                item["rationale"],
                _evidence(candidate, "open_question", item["question"]),
            )
            for item in candidate["open_questions"]
            if item["question"].strip() not in resolved_subjects
        ),
        ambiguities=tuple(
            Ambiguity(
                item["statement"],
                item["reason"],
                _evidence(candidate, "ambiguity", item["statement"]),
            )
            for item in candidate["ambiguities"]
            if item["statement"].strip() not in resolved_subjects
        ),
        potential_dependencies=tuple(
            PotentialDependency(item, _evidence(candidate, "potential_dependency", item))
            for item in candidate["potential_dependencies"]
            if item.strip() not in resolved_subjects
        ),
        clarifications=clarifications,
        clarification_evidence=tuple(
            AnalysisClarificationEvidence(key, tuple(numbers))
            for key, numbers in candidate.get("clarification_references", {}).items()
        ),
        document_references=document_references,
        id=analysis_id,
        round_number=round_number,
        provenance=provenance,
        source_requirement_version=source_requirement_version,
        intent_proposals=(*carried, *generated),
        source_desired_outcome=source_desired_outcome,
        stage_provenance=tuple(
            AnalysisStageProvenance(
                item["stage"],
                item["model"],
                item["prompt_version"],
                item["generated_at"],
                item["input_fingerprint"],
            )
            for item in candidate.get("stage_provenance", [])
        ),
        version=version,
    )
