"""Render one immutable revision's confirmed analysis as a Business Requirements Document."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.analysis.domain.value_objects import (
    AnalysisEvidenceReference,
    ClarificationKind,
    HumanClarification,
    IntentProposalKind,
    IntentProposalStatus,
)
from smb_requirement_agent.governance.application.errors import (
    RequirementSpecificationNotAvailableError,
)
from smb_requirement_agent.governance.application.exports import ExportArtifact
from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.governance.application.ports.specification_export import (
    SpecificationExportPort,
)
from smb_requirement_agent.governance.application.specification import (
    SPECIFICATION_SCHEMA_VERSION,
    RequirementSpecification,
    SpecificationActor,
    SpecificationBacklog,
    SpecificationCounts,
    SpecificationCriterion,
    SpecificationEpic,
    SpecificationEvidence,
    SpecificationFeature,
    SpecificationFormat,
    SpecificationImpactGap,
    SpecificationImpactSystem,
    SpecificationManifest,
    SpecificationObjectives,
    SpecificationProductImpact,
    SpecificationResolution,
    SpecificationResolvable,
    SpecificationRisk,
    SpecificationScope,
    SpecificationSignature,
    SpecificationSourceDocument,
    SpecificationStakeholder,
    SpecificationStatement,
    SpecificationStory,
    SpecificationSummary,
    StatementOrigin,
)
from smb_requirement_agent.governance.application.use_cases.export_breakdown import (
    formal_final_approval,
    is_exportable_revision,
)
from smb_requirement_agent.governance.domain.revision.entities import (
    BreakdownRevision,
    RequirementRevision,
    RevisionNumber,
)
from smb_requirement_agent.governance.domain.revision.errors import RevisionNotFoundError
from smb_requirement_agent.identity.application.ports.requirement_access import (
    RequirementAccessPort,
    RequirementPermission,
)
from smb_requirement_agent.requirements.application.errors import RequirementNotFoundError
from smb_requirement_agent.requirements.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile, ActorSnapshot
from smb_requirement_agent.shared_kernel.approval import Approval
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

_UNRECORDED = "Not recorded"


def is_specification_available(revision: BreakdownRevision) -> bool:
    """A document exists for a revision whose analysis the Requirement Owner confirmed."""
    return revision.analysis is not None and revision.analysis.is_human_confirmed


def select_requirement_revision(
    requirement_revisions: Sequence[RequirementRevision], breakdown: BreakdownRevision
) -> RequirementRevision | None:
    """The Requirement snapshot the confirmed analysis was made from.

    By the version the analysis recorded; otherwise the newest snapshot taken no later than the
    breakdown revision; otherwise the newest there is.
    """
    if not requirement_revisions:
        return None
    analysis = breakdown.analysis
    if analysis is not None and analysis.source_requirement_version is not None:
        wanted = analysis.source_requirement_version
        for item in reversed(requirement_revisions):
            if item.requirement.version == wanted:
                return item
    for item in reversed(requirement_revisions):
        if item.created_at <= breakdown.created_at:
            return item
    return requirement_revisions[-1]


class ExportRequirementSpecification:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        authorization: RequirementAccessPort,
        revisions: BreakdownRepositoryPort,
        exporters: tuple[SpecificationExportPort, ...],
    ) -> None:
        self._requirements = requirements
        self._authorization = authorization
        self._revisions = revisions
        self._exporters = {exporter.format: exporter for exporter in exporters}
        if len(self._exporters) != len(exporters):
            raise ValueError("Each specification exporter must own a unique format.")

    def execute(
        self,
        requirement_id: RequirementId,
        revision_number: RevisionNumber,
        export_format: SpecificationFormat,
        actor: ActorProfile,
    ) -> ExportArtifact:
        if self._requirements.get(requirement_id) is None:
            raise RequirementNotFoundError(f"Requirement {requirement_id.value!r} not found.")
        self._authorization.require(requirement_id, actor, RequirementPermission.MEMBER)
        revision = self._revisions.get_breakdown_revision(requirement_id, revision_number)
        if revision is None:
            raise RevisionNotFoundError(
                f"Breakdown revision {revision_number.value} does not exist."
            )
        if not is_specification_available(revision):
            raise RequirementSpecificationNotAvailableError(
                "The selected revision has no analysis confirmed by the Requirement Owner."
            )
        requirement_revision = select_requirement_revision(
            self._revisions.list_requirement_revisions(requirement_id), revision
        )
        if requirement_revision is None:
            raise RequirementSpecificationNotAvailableError(
                "No Requirement version is recorded for the selected revision."
            )
        exporter = self._exporters[export_format]
        safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", requirement_id.value).strip("-._")
        safe_id = safe_id or "requirement"
        return ExportArtifact(
            filename=(
                f"requirement-{safe_id}-business-requirements-v{revision_number.value}"
                f".{exporter.extension}"
            ),
            media_type=exporter.media_type,
            content=exporter.render(
                build_requirement_specification(revision, requirement_revision)
            ),
        )


def build_requirement_specification(
    breakdown: BreakdownRevision, requirement_revision: RequirementRevision
) -> RequirementSpecification:
    """Copy a confirmed revision into the document contract. Raises when unconfirmed."""
    analysis = breakdown.analysis
    if analysis is None or not analysis.is_human_confirmed:
        raise RequirementSpecificationNotAvailableError(
            "The selected revision has no analysis confirmed by the Requirement Owner."
        )
    requirement = requirement_revision.requirement
    filenames = {item.document_id: item.filename for item in analysis.document_references}

    def evidence(
        references: tuple[AnalysisEvidenceReference, ...],
    ) -> tuple[SpecificationEvidence, ...]:
        return tuple(
            SpecificationEvidence(filenames.get(item.document_id, item.document_id), item.label)
            for item in references
        )

    business_requirements = _statements(
        "BR",
        (
            (item.statement, StatementOrigin.ANALYSIS, evidence(item.evidence_references))
            for item in analysis.known_facts
        ),
    )
    business_rules = _statements(
        "RL",
        [
            *((item.value, StatementOrigin.CAPTURED, ()) for item in requirement.business_rules),
            *(
                (item.statement, StatementOrigin.ANALYSIS, evidence(item.evidence_references))
                for item in analysis.business_rules
            ),
            *(
                (item, StatementOrigin.ACCEPTED_PROPOSAL, ())
                for item in analysis.accepted_business_rules
            ),
        ],
    )
    constraints = _statements(
        "CN",
        [
            *((item.value, StatementOrigin.CAPTURED, ()) for item in requirement.constraints),
            *(
                (item.statement, StatementOrigin.ANALYSIS, evidence(item.evidence_references))
                for item in analysis.constraints
            ),
            *(
                (item, StatementOrigin.ACCEPTED_PROPOSAL, ())
                for item in analysis.accepted_constraints
            ),
        ],
    )
    assumptions = _resolvables(
        "AS",
        ClarificationKind.ASSUMPTION,
        (
            (item.statement, None, evidence(item.evidence_references))
            for item in analysis.assumptions
        ),
        analysis.clarifications,
    )
    dependencies = _resolvables(
        "DP",
        ClarificationKind.POTENTIAL_DEPENDENCY,
        (
            (item.statement, None, evidence(item.evidence_references))
            for item in analysis.potential_dependencies
        ),
        analysis.clarifications,
    )
    open_questions = _resolvables(
        "OQ",
        ClarificationKind.OPEN_QUESTION,
        (
            (item.question, item.rationale, evidence(item.evidence_references))
            for item in analysis.open_questions
        ),
        analysis.clarifications,
    )
    ambiguities = _resolvables(
        "AM",
        ClarificationKind.AMBIGUITY,
        (
            (item.statement, item.reason, evidence(item.evidence_references))
            for item in analysis.ambiguities
        ),
        analysis.clarifications,
    )
    backlog = _backlog(breakdown)
    confirmation = SpecificationSignature(
        _actor(analysis.confirmed_by),
        analysis.confirmed_at if analysis.confirmed_at is not None else breakdown.created_at,
    )
    return RequirementSpecification(
        schema_version=SPECIFICATION_SCHEMA_VERSION,
        manifest=SpecificationManifest(
            requirement_id=breakdown.requirement_id.value,
            title=requirement.title.value,
            requirement_version=requirement.version.value,
            breakdown_revision=breakdown.number.value,
            revision_created_at=breakdown.created_at,
            analysis_round=analysis.round_number,
            analysis_generated_at=(
                analysis.provenance.generated_at if analysis.provenance is not None else None
            ),
            analysis_model=analysis.provenance.model if analysis.provenance is not None else None,
            analysis_prompt_version=(
                analysis.provenance.prompt_version if analysis.provenance is not None else None
            ),
            confirmation=confirmation,
            backlog_approval=backlog.approval if backlog is not None else None,
        ),
        summary=SpecificationSummary(
            description=requirement.description.value,
            counts=SpecificationCounts(
                business_requirements=len(business_requirements),
                business_rules=len(business_rules),
                constraints=len(constraints),
                assumptions=len(assumptions),
                dependencies=len(dependencies),
                open_questions=len(open_questions),
                ambiguities=len(ambiguities),
                resolved_clarifications=sum(
                    item.resolution is not None
                    for item in (*assumptions, *dependencies, *open_questions, *ambiguities)
                ),
            ),
        ),
        objectives=_objectives(analysis, requirement_revision),
        scope=SpecificationScope(
            customer_context=(
                requirement.customer_context.value
                if requirement.customer_context is not None
                else None
            ),
            channels=tuple(item.value for item in requirement.channels),
            systems=tuple(item.value for item in requirement.systems),
        ),
        stakeholders=_stakeholders(requirement_revision),
        business_requirements=business_requirements,
        business_rules=business_rules,
        constraints=constraints,
        assumptions=assumptions,
        dependencies=dependencies,
        open_questions=open_questions,
        ambiguities=ambiguities,
        product_impact=_product_impact(analysis),
        functional_requirements=backlog,
        source_documents=tuple(
            SpecificationSourceDocument(item.filename, item.version_id, item.checksum_sha256)
            for item in analysis.document_references
        ),
    )


def _actor(snapshot: ActorSnapshot | None) -> SpecificationActor:
    return SpecificationActor(snapshot.display_name if snapshot is not None else _UNRECORDED)


def _signature(approval: Approval) -> SpecificationSignature:
    return SpecificationSignature(
        _actor(approval.recorded_by), approval.recorded_at, approval.rationale
    )


def _statements(
    prefix: str,
    items: Iterable[tuple[str, StatementOrigin, tuple[SpecificationEvidence, ...]]],
) -> tuple[SpecificationStatement, ...]:
    """Number the statements, keeping the first of any repeated wording."""
    seen: set[str] = set()
    kept: list[tuple[str, StatementOrigin, tuple[SpecificationEvidence, ...]]] = []
    for text, origin, evidence in items:
        key = " ".join(text.split()).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        kept.append((text.strip(), origin, evidence))
    return tuple(
        SpecificationStatement(f"{prefix}-{index:02d}", text, origin, evidence)
        for index, (text, origin, evidence) in enumerate(kept, start=1)
    )


def _resolvables(
    prefix: str,
    kind: ClarificationKind,
    items: Iterable[tuple[str, str | None, tuple[SpecificationEvidence, ...]]],
    clarifications: tuple[HumanClarification, ...],
) -> tuple[SpecificationResolvable, ...]:
    """Open items first, each with its answer when a person gave one, then answered items the
    analysis no longer lists, so every clarification stays in the record."""
    answers: dict[str, HumanClarification] = {}
    for item in clarifications:
        if item.kind is kind:
            answers[item.subject.strip()] = item
    rows: list[tuple[str, str | None, tuple[SpecificationEvidence, ...], HumanClarification | None]]
    rows = []
    seen: set[str] = set()
    for text, rationale, evidence in items:
        subject = text.strip()
        seen.add(subject)
        rows.append((subject, rationale, evidence, answers.get(subject)))
    for subject, answer in answers.items():
        if subject not in seen:
            rows.append((subject, None, (), answer))
    return tuple(
        SpecificationResolvable(
            id=f"{prefix}-{index:02d}",
            text=text,
            rationale=rationale,
            evidence=evidence,
            resolution=(
                SpecificationResolution(
                    answer.answer,
                    _actor(answer.answered_by) if answer.answered_by is not None else None,
                    answer.answered_at,
                )
                if answer is not None
                else None
            ),
        )
        for index, (text, rationale, evidence, answer) in enumerate(rows, start=1)
    )


def _objectives(
    analysis: RequirementAnalysis, requirement_revision: RequirementRevision
) -> SpecificationObjectives:
    requirement = requirement_revision.requirement
    source = requirement.desired_outcome.value if requirement.desired_outcome is not None else None
    outcome = analysis.effective_desired_outcome(source)
    origin: StatementOrigin | None
    if outcome is None:
        origin = None
    elif (source and source.strip()) or (
        analysis.source_desired_outcome and analysis.source_desired_outcome.strip()
    ):
        origin = StatementOrigin.CAPTURED
    else:
        origin = StatementOrigin.ACCEPTED_PROPOSAL
    measures = tuple(
        measure
        for proposal in analysis.intent_proposals
        if proposal.kind is IntentProposalKind.DESIRED_OUTCOME
        and proposal.status in (IntentProposalStatus.ACCEPTED, IntentProposalStatus.EDITED)
        for measure in proposal.effective_success_measures
    )
    return SpecificationObjectives(outcome, origin, measures)


def _stakeholders(
    requirement_revision: RequirementRevision,
) -> tuple[SpecificationStakeholder, ...]:
    access = requirement_revision.access
    if access is None:
        return ()
    people: list[SpecificationStakeholder] = []
    if access.owner is not None:
        people.append(
            SpecificationStakeholder(
                access.owner.actor.display_name, "Requirement Owner", access.owner.assigned_at
            )
        )
    people.extend(
        SpecificationStakeholder(item.actor.display_name, "Reviewer", item.assigned_at)
        for item in access.reviewers
    )
    return tuple(people)


def _product_impact(analysis: RequirementAnalysis) -> SpecificationProductImpact | None:
    impact = analysis.product_impact
    if impact is None:
        return None
    status = (
        analysis.product_impact_status.value
        if analysis.product_impact_status is not None
        else "assessed"
    )
    return SpecificationProductImpact(
        status=status,
        suggested_verdict=(
            impact.suggested_verdict.value if impact.suggested_verdict is not None else None
        ),
        verdict=impact.verdict.value if impact.verdict is not None else None,
        decision=impact.decision.value if impact.decision is not None else None,
        reason=impact.reason,
        offering_name=impact.offering_name,
        systems=tuple(
            SpecificationImpactSystem(item.name, item.role, item.change_type)
            for item in impact.systems
        ),
        gaps=tuple(SpecificationImpactGap(item.label, item.reason) for item in impact.gaps),
        decided=(
            SpecificationSignature(_actor(impact.decided_by), impact.decided_at, impact.rationale)
            if impact.decided_by is not None and impact.decided_at is not None
            else None
        ),
    )


def _backlog(breakdown: BreakdownRevision) -> SpecificationBacklog | None:
    """The approved tree, or nothing: an unapproved backlog never reaches the document."""
    approval = formal_final_approval(breakdown)
    epic = breakdown.epic
    if approval is None or epic is None or not is_exportable_revision(breakdown):
        return None
    features: list[SpecificationFeature] = []
    for feature_index, feature in enumerate(breakdown.features, start=1):
        feature_id = f"FR-{feature_index:02d}"
        stories = tuple(
            SpecificationStory(
                id=f"{feature_id}.{story_index}",
                role=story.role.value,
                action=story.action.value,
                value=story.value.value,
                kind=story.kind.value,
                criteria=tuple(
                    SpecificationCriterion(item.given, item.when, item.then)
                    for item in story.acceptance_criteria
                ),
            )
            for story_index, story in enumerate(
                (item for item in breakdown.stories if item.feature_id == feature.id), start=1
            )
        )
        features.append(
            SpecificationFeature(
                id=feature_id,
                name=feature.name.value,
                outcome=feature.outcome.value,
                delivery_drop=feature.delivery_drop.value,
                kind=feature.kind.value,
                acceptance_criteria=tuple(item.value for item in feature.acceptance_criteria),
                stories=stories,
            )
        )
    review = breakdown.review
    return SpecificationBacklog(
        epic=SpecificationEpic(epic.name.value, epic.outcome.value, epic.business_case.value),
        features=tuple(features),
        approval=_signature(approval),
        dependencies=(
            tuple(item.description for item in review.dependencies) if review is not None else ()
        ),
        risks=(
            tuple(SpecificationRisk(item.severity.value, item.description) for item in review.risks)
            if review is not None
            else ()
        ),
    )
