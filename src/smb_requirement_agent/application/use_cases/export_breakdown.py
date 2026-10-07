"""Export one exact, formally approved immutable backlog revision."""

from __future__ import annotations

import re

from smb_requirement_agent.application.errors import (
    BreakdownRevisionNotExportableError,
    RequirementNotFoundError,
)
from smb_requirement_agent.application.exports import (
    EXPORT_SCHEMA_VERSION,
    ExportAcceptanceCriterion,
    ExportActor,
    ExportApproval,
    ExportArchitecture,
    ExportArchitectureDependency,
    ExportArtifact,
    ExportCapability,
    ExportCounts,
    ExportEpic,
    ExportFeature,
    ExportFormat,
    ExportJourneyNeighbour,
    ExportJourneyStep,
    ExportManifest,
    ExportOfferingDuty,
    ExportOrganisationReference,
    ExportProductContext,
    ExportProvenance,
    ExportStory,
    ExportSystem,
    NeutralBacklogExport,
)
from smb_requirement_agent.application.ports.backlog_export import BacklogExportPort
from smb_requirement_agent.application.ports.breakdown_repository import BreakdownRepositoryPort
from smb_requirement_agent.application.ports.requirement_repository import RequirementRepositoryPort
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    RequirementPermission,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureDependency,
    ArchitectureImpact,
    JourneyNeighbour,
    JourneyStep,
    OrganisationReference,
    ProductContext,
    SystemReference,
)
from smb_requirement_agent.domain.review.entities import BreakdownStatus
from smb_requirement_agent.domain.revision.entities import BreakdownRevision, RevisionNumber
from smb_requirement_agent.domain.revision.errors import RevisionNotFoundError
from smb_requirement_agent.domain.shared.actors import ActorProfile
from smb_requirement_agent.domain.shared.approval import (
    Approval,
    ApprovalDecision,
    ApprovalTargetKind,
)
from smb_requirement_agent.domain.shared.generation import Provenance
from smb_requirement_agent.domain.shared.identifiers import RequirementId


def formal_final_approval(revision: BreakdownRevision) -> Approval | None:
    """Return the latest formal approval attesting to this saved submission."""
    review = revision.review
    if (
        review is None
        or review.status is not BreakdownStatus.APPROVED
        or review.submitted_fingerprint is None
    ):
        return None
    return next(
        (
            approval
            for approval in reversed(review.approvals)
            if approval.decision is ApprovalDecision.APPROVED
            and approval.target.kind is ApprovalTargetKind.BREAKDOWN
            and approval.target.item_id == revision.requirement_id.value
            and approval.attests_to(review.submitted_fingerprint)
        ),
        None,
    )


def is_exportable_revision(revision: BreakdownRevision) -> bool:
    return formal_final_approval(revision) is not None and _has_complete_tree(revision)


def approved_backlog_document(revision: BreakdownRevision) -> NeutralBacklogExport | None:
    """The export of a formally approved, complete revision; None when it is not exportable."""
    approval = formal_final_approval(revision)
    if approval is None or not _has_complete_tree(revision):
        return None
    return _document(revision, approval)


class ExportBreakdown:
    def __init__(
        self,
        requirements: RequirementRepositoryPort,
        authorization: RequirementAccessService,
        revisions: BreakdownRepositoryPort,
        exporters: tuple[BacklogExportPort, ...],
    ) -> None:
        self._requirements = requirements
        self._authorization = authorization
        self._revisions = revisions
        self._exporters = {exporter.format: exporter for exporter in exporters}
        if len(self._exporters) != len(exporters):
            raise ValueError("Each backlog exporter must own a unique format.")

    def execute(
        self,
        requirement_id: RequirementId,
        revision_number: RevisionNumber,
        export_format: ExportFormat,
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
        approval = formal_final_approval(revision)
        if approval is None or not _has_complete_tree(revision):
            raise BreakdownRevisionNotExportableError(
                "Only an immutable revision with a formal final approval can be exported."
            )
        exporter = self._exporters[export_format]
        safe_id = re.sub(r"[^A-Za-z0-9._-]+", "-", requirement_id.value).strip("-._")
        safe_id = safe_id or "requirement"
        return ExportArtifact(
            filename=(
                f"requirement-{safe_id}-breakdown-v{revision_number.value}.{exporter.extension}"
            ),
            media_type=exporter.media_type,
            content=exporter.render(_document(revision, approval)),
        )


def _has_complete_tree(revision: BreakdownRevision) -> bool:
    if revision.epic is None or not revision.features:
        return False
    story_feature_ids = {story.feature_id for story in revision.stories}
    return all(feature.id in story_feature_ids for feature in revision.features)


def _provenance(value: Provenance) -> ExportProvenance:
    return ExportProvenance(value.generated_at, value.model, value.prompt_version)


def _references(
    values: tuple[OrganisationReference, ...],
) -> tuple[ExportOrganisationReference, ...]:
    return tuple(ExportOrganisationReference(item.id, item.name) for item in values)


def _system(item: SystemReference) -> ExportSystem:
    return ExportSystem(
        id=item.id,
        name=item.name,
        catalogued=item.catalogued,
        capabilities=tuple(
            ExportCapability(
                capability.id,
                capability.name,
                capability.domain_path,
                capability.component_name,
            )
            for capability in item.capabilities
        ),
        squads=_references(item.squads),
        value_streams=_references(item.value_streams),
        products=_references(item.products),
    )


def _dependency(item: ArchitectureDependency) -> ExportArchitectureDependency:
    return ExportArchitectureDependency(
        item.source_system_id, item.target_system_id, item.description, item.kind.value
    )


def _architecture(value: ArchitectureImpact | None) -> ExportArchitecture | None:
    if value is None:
        return None
    return ExportArchitecture(
        knowledge_version=value.knowledge_version,
        mapped_at=value.mapped_at,
        systems=tuple(_system(item) for item in value.systems),
        dependencies=tuple(_dependency(item) for item in value.dependencies),
        adjacent_systems=tuple(_system(item) for item in value.adjacent_systems),
        adjacent_dependencies=tuple(_dependency(item) for item in value.adjacent_dependencies),
        product_contexts=tuple(_product_context(item) for item in value.product_contexts),
        journey_steps=tuple(_journey_step(item) for item in value.journey_steps),
    )


def _product_context(item: ProductContext) -> ExportProductContext:
    return ExportProductContext(
        item.product_id,
        item.product_name,
        item.matched_terms,
        item.order_type,
        tuple(
            ExportOfferingDuty(
                duty.component_id,
                duty.component_name,
                duty.system_id,
                duty.system_name,
                duty.role,
                duty.description,
            )
            for duty in item.responsibilities
        ),
    )


def _neighbour(item: JourneyNeighbour) -> ExportJourneyNeighbour:
    return ExportJourneyNeighbour(item.number, item.name, item.system_id, item.system_name)


def _journey_step(item: JourneyStep) -> ExportJourneyStep:
    return ExportJourneyStep(
        item.system_id,
        item.journey_id,
        item.journey_name,
        item.fulfils,
        item.number,
        item.name,
        item.performs,
        tuple(_neighbour(other) for other in item.before),
        tuple(_neighbour(other) for other in item.after),
    )


def _document(revision: BreakdownRevision, approval: Approval) -> NeutralBacklogExport:
    epic = revision.epic
    if epic is None:
        raise BreakdownRevisionNotExportableError("The approved revision contains no Epic.")
    stories_by_feature = {
        feature.id: tuple(story for story in revision.stories if story.feature_id == feature.id)
        for feature in revision.features
    }
    features = tuple(
        ExportFeature(
            sequence=feature_sequence,
            id=feature.id.value,
            epic_id=feature.epic_id.value,
            name=feature.name.value,
            outcome=feature.outcome.value,
            delivery_drop=feature.delivery_drop.value,
            splitting_pattern=feature.splitting_pattern.value,
            splitting_rationale=feature.splitting_rationale.value,
            status=feature.status.value,
            provenance=_provenance(feature.provenance),
            architecture=_architecture(feature.architecture),
            stories=tuple(
                ExportStory(
                    sequence=story_sequence,
                    id=story.id.value,
                    feature_id=story.feature_id.value,
                    role=story.role.value,
                    action=story.action.value,
                    value=story.value.value,
                    voice=story.voice,
                    status=story.status.value,
                    provenance=_provenance(story.provenance),
                    acceptance_criteria=tuple(
                        ExportAcceptanceCriterion(
                            index, criterion.given, criterion.when, criterion.then
                        )
                        for index, criterion in enumerate(story.acceptance_criteria, start=1)
                    ),
                    architecture=_architecture(story.architecture),
                )
                for story_sequence, story in enumerate(stories_by_feature[feature.id], start=1)
            ),
        )
        for feature_sequence, feature in enumerate(revision.features, start=1)
    )
    actor = approval.recorded_by
    return NeutralBacklogExport(
        schema_version=EXPORT_SCHEMA_VERSION,
        manifest=ExportManifest(
            requirement_id=revision.requirement_id.value,
            breakdown_revision=revision.number.value,
            revision_created_at=revision.created_at,
            final_approval=ExportApproval(
                id=approval.id.value,
                subject_fingerprint=approval.subject_fingerprint,
                recorded_by=ExportActor(actor.id.value, actor.display_name, actor.email),
                recorded_at=approval.recorded_at,
                rationale=approval.rationale,
            ),
            counts=ExportCounts(
                epics=1,
                features=len(features),
                stories=sum(len(feature.stories) for feature in features),
                acceptance_criteria=sum(
                    len(story.acceptance_criteria)
                    for feature in features
                    for story in feature.stories
                ),
            ),
        ),
        epic=ExportEpic(
            id=epic.id.value,
            requirement_id=epic.requirement_id.value,
            name=epic.name.value,
            outcome=epic.outcome.value,
            business_case=epic.business_case.value,
            status=epic.status.value,
            provenance=_provenance(epic.provenance),
            features=features,
        ),
    )
