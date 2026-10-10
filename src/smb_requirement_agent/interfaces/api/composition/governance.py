"""Breakdown review, approval, revision history and export.

Built before the breakdown itself: approving an Epic, Feature or Story records
through the same approval recorder, and rejecting a Story goes through the
approval workflow.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass

import httpx
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.governance.application.ports.backlog_export import BacklogExportPort
from smb_requirement_agent.governance.application.ports.backlog_publisher import (
    BacklogPublisherPort,
)
from smb_requirement_agent.governance.application.publication import WorkItemKind
from smb_requirement_agent.governance.application.use_cases.approval_workflow import (
    AddReviewComment,
    ApprovalRecorder,
    ApproveBreakdown,
    GetApprovalWorkflow,
    SubmitForReview,
)
from smb_requirement_agent.governance.application.use_cases.breakdown_review import (
    GetBreakdownReview,
    RecordDecision,
    ResolveFlag,
    ReviewEvidenceLoader,
)
from smb_requirement_agent.governance.application.use_cases.export_breakdown import ExportBreakdown
from smb_requirement_agent.governance.application.use_cases.publish_breakdown import (
    PreviewPublication,
    PublishBreakdown,
)
from smb_requirement_agent.governance.application.use_cases.revision_history import (
    CompareBreakdownVersions,
    GetRevisionHistory,
)
from smb_requirement_agent.governance.domain.review.policy import ApprovalPolicy
from smb_requirement_agent.governance.infrastructure.publication.azure_devops import (
    AzureDevOpsConfiguration,
    AzureDevOpsWorkItemPublisher,
)
from smb_requirement_agent.governance.infrastructure.publication.fake import FakeBacklogPublisher
from smb_requirement_agent.governance.infrastructure.publication.unavailable import (
    UnavailableBacklogPublisher,
)
from smb_requirement_agent.infrastructure.config.options import AdoPublisher
from smb_requirement_agent.infrastructure.config.settings import AdoPublicationSettings
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters
from smb_requirement_agent.knowledge.application.use_cases.source_impact import SourceImpactReview
from smb_requirement_agent.references.application.ports.architecture_knowledge import (
    ActiveArchitectureReleasePort,
)
from smb_requirement_agent.references.application.ports.knowledge_handoff import (
    ApprovedBacklogOutboxPort,
)
from smb_requirement_agent.workflows.application.use_cases.identity_access import (
    RequirementAccessService,
)


@dataclass(frozen=True)
class ReviewWiring:
    current_release: ActiveArchitectureReleasePort
    review_evidence: ReviewEvidenceLoader
    get_breakdown_review: GetBreakdownReview
    approval_recorder: ApprovalRecorder
    get_approval_workflow: GetApprovalWorkflow
    record_decision: RecordDecision
    resolve_flag: ResolveFlag
    submit_for_review: SubmitForReview
    approve_breakdown: ApproveBreakdown
    add_review_comment: AddReviewComment
    get_revision_history: GetRevisionHistory
    compare_breakdown_versions: CompareBreakdownVersions
    export_breakdown: ExportBreakdown
    preview_publication: PreviewPublication
    publish_breakdown: PublishBreakdown


def build_backlog_publisher(
    settings: AdoPublicationSettings, resources: ExitStack
) -> BacklogPublisherPort:
    """The publisher ADO_PUBLISHER chooses (Slice 12)."""
    if settings.publisher is AdoPublisher.FAKE:
        return FakeBacklogPublisher()
    if settings.publisher is AdoPublisher.NONE:
        return UnavailableBacklogPublisher()
    if settings.personal_access_token is None:
        raise ValueError("Azure DevOps settings were validated without a token.")
    http = httpx.Client()
    resources.callback(http.close)
    return AzureDevOpsWorkItemPublisher(
        AzureDevOpsConfiguration(
            organization_url=settings.organization_url,
            project=settings.project,
            personal_access_token=settings.personal_access_token,
            area_path=settings.default_area_path,
            iteration_path=settings.iteration_path or None,
            work_item_types={
                WorkItemKind.EPIC: settings.epic_type,
                WorkItemKind.FEATURE: settings.feature_type,
                WorkItemKind.STORY: settings.story_type,
            },
            description_field=settings.description_field,
            acceptance_criteria_field=settings.acceptance_criteria_field,
            tags=settings.tags,
            squad_area_paths=dict(settings.squad_area_paths),
            timeout_seconds=settings.timeout_seconds,
        ),
        http,
    )


def build_review(
    persistence: PersistenceAdapters,
    clock: ClockPort,
    access: RequirementAccessService,
    source_impact: SourceImpactReview,
    exporters: tuple[BacklogExportPort, ...],
    current_release: ActiveArchitectureReleasePort,
    publisher: BacklogPublisherPort,
    handoffs: ApprovedBacklogOutboxPort | None = None,
) -> ReviewWiring:
    reviews = persistence.breakdown_review_repository
    transactions = persistence.transaction_manager
    evidence = ReviewEvidenceLoader(
        persistence.requirement_repository,
        persistence.analysis_repository,
        persistence.epic_repository,
        persistence.feature_repository,
        persistence.story_repository,
        persistence.analysis_audit_repository,
        source_impact,
    )
    get_review = GetBreakdownReview(evidence, reviews, current_release)
    recorder = ApprovalRecorder(persistence.access_repository, clock, access)
    workflow = GetApprovalWorkflow(evidence, reviews, recorder, ApprovalPolicy())
    return ReviewWiring(
        current_release=current_release,
        review_evidence=evidence,
        get_breakdown_review=get_review,
        approval_recorder=recorder,
        get_approval_workflow=workflow,
        record_decision=RecordDecision(
            get_review, reviews, clock, transactions, authorization=access
        ),
        resolve_flag=ResolveFlag(get_review, reviews, clock, transactions, authorization=access),
        submit_for_review=SubmitForReview(workflow, reviews, recorder, transactions),
        approve_breakdown=ApproveBreakdown(workflow, reviews, recorder, transactions, handoffs),
        add_review_comment=AddReviewComment(workflow, reviews, recorder, transactions, clock),
        get_revision_history=GetRevisionHistory(
            persistence.requirement_repository, persistence.revision_repository
        ),
        compare_breakdown_versions=CompareBreakdownVersions(
            persistence.requirement_repository, persistence.revision_repository
        ),
        export_breakdown=ExportBreakdown(
            persistence.requirement_repository,
            access,
            persistence.revision_repository,
            exporters,
        ),
        preview_publication=PreviewPublication(
            persistence.requirement_repository, access, persistence.revision_repository, publisher
        ),
        publish_breakdown=PublishBreakdown(
            persistence.requirement_repository, access, persistence.revision_repository, publisher
        ),
    )
