"""Ask the knowledge portal where an analysed requirement sits in the portfolio (ADR-0115).

Each analysis round, once its facts exist, sends the requirement, those facts and the
answers given so far to `POST /internal/architecture/assess`, and records what came back
as the round's product impact. A person decides it before the analysis is confirmed.
With no knowledge portal linked (ADR-0104) nothing is asked, and nothing is blocked.
"""

from __future__ import annotations

import logging
from datetime import datetime

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.domain.errors import RequirementAnalysisError
from smb_requirement_agent.analysis.domain.product_impact import (
    CapabilityNeed,
    ImpactGap,
    ImpactOwner,
    ImpactPathStep,
    ImpactQuestion,
    ImpactSystem,
    ProductImpact,
    ProductImpactStatus,
    ProductVerdict,
)
from smb_requirement_agent.analysis.domain.value_objects import HumanClarification
from smb_requirement_agent.application.errors import ServiceResponseError, ServiceUnavailableError
from smb_requirement_agent.references.application.ports.architecture_assessment import (
    ArchitectureAssessment,
    ArchitectureAssessmentPort,
    AssessmentQuery,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement

_log = logging.getLogger(__name__)


class AssessProductImpact:
    def __init__(self, assessment: ArchitectureAssessmentPort, clock: ClockPort) -> None:
        self._assessment = assessment
        self._clock = clock

    def augment(
        self,
        requirement: Requirement,
        candidate: RequirementAnalysisCandidate,
        clarifications: tuple[HumanClarification, ...],
    ) -> RequirementAnalysisCandidate:
        if not self._assessment.is_connected():
            return {**candidate, "product_impact_status": ProductImpactStatus.NOT_CONNECTED}
        try:
            answer = self._assessment.assess(
                assessment_query(requirement, candidate, clarifications)
            )
        except (ServiceUnavailableError, ServiceResponseError) as exc:
            # A refusal is the knowledge portal's to fix; the analysis carries on without it.
            _log.warning("Product impact not assessed: %s", exc)
            return {**candidate, "product_impact_status": ProductImpactStatus.UNAVAILABLE}
        if answer is None:
            # A knowledge portal released before the assessment: as good as not linked.
            return {**candidate, "product_impact_status": ProductImpactStatus.NOT_CONNECTED}
        try:
            impact = product_impact(answer, self._clock.now())
        except RequirementAnalysisError as exc:
            _log.warning("Product impact unusable: %s", exc)
            return {**candidate, "product_impact_status": ProductImpactStatus.UNAVAILABLE}
        return {
            **candidate,
            "product_impact": impact,
            "product_impact_status": ProductImpactStatus.ASSESSED,
        }


def assessment_query(
    requirement: Requirement,
    candidate: RequirementAnalysisCandidate,
    clarifications: tuple[HumanClarification, ...],
) -> AssessmentQuery:
    """The requirement as analysed: its own words, its facts, and the answers given."""
    outcome = requirement.desired_outcome.value if requirement.desired_outcome else None
    return AssessmentQuery(
        text=tuple(
            item.strip()
            for item in (
                requirement.title.value,
                requirement.description.value,
                *((outcome,) if outcome else ()),
                *candidate["known_facts"],
                *candidate["constraints"],
                *candidate["business_rules"],
                # The answers alone: the questions' own words would read as needs.
                *(item.answer for item in clarifications),
            )
            if item.strip()
        ),
        declared_systems=tuple(item.value for item in requirement.systems),
    )


def product_impact(answer: ArchitectureAssessment, at: datetime) -> ProductImpact:
    """The round's product impact, in this application's own terms."""
    offering_names = {
        step.id: step.label
        for system in answer.systems
        for path in system.paths
        for step in path
        if step.kind == "offering" and step.label.strip()
    }
    strong = {
        concept.concept_id
        for facet in answer.facets
        for concept in facet.concepts
        if not concept.weak
    }
    weak = {
        concept.concept_id for facet in answer.facets for concept in facet.concepts if concept.weak
    } - strong
    proposal = answer.proposal
    return ProductImpact(
        release_id=answer.knowledge_version,
        suggested_verdict=ProductVerdict(answer.verdict) if answer.verdict else None,
        reason=answer.verdict_reason,
        assessed_at=at,
        offering_id=answer.offering_id,
        offering_name=offering_names.get(answer.offering_id or ""),
        proposal=(proposal.summary.strip() or None) if proposal else None,
        new_values=tuple(item for item in (proposal.new_values if proposal else ()) if item),
        needs=tuple(
            CapabilityNeed(
                item.concept_id, item.label, item.path, item.covered, item.concept_id in weak
            )
            for item in answer.coverage
        ),
        gaps=tuple(
            ImpactGap(item.kind, item.concept_id, item.label, item.reason, item.system_id)
            for item in answer.gaps
        ),
        systems=tuple(
            ImpactSystem(
                item.id,
                item.name,
                item.role,
                item.change_type,
                tuple(
                    tuple(ImpactPathStep(step.kind, step.id, step.label) for step in path)
                    for path in item.paths
                ),
            )
            for item in answer.systems
        ),
        owners=tuple(
            ImpactOwner(
                item.concept_id,
                item.system_id,
                tuple(squad.name for squad in item.squads),
                tuple(seat.person_name for seat in item.seats if seat.person_name),
                sum(1 for seat in item.seats if seat.person_id is None),
            )
            for item in answer.owners
        ),
        questions=tuple(
            ImpactQuestion(
                item.facet, item.question, tuple(option.label for option in item.options)
            )
            for item in answer.questions
            if item.question.strip()
        ),
        uncertainty=answer.uncertainty,
        model=answer.model,
        prompt_version=answer.prompt_version,
    )
