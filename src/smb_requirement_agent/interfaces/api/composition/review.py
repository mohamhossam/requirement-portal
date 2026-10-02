"""Breakdown review, approval, revision history and export.

Built before the breakdown itself: approving an Epic, Feature or Story records
through the same approval recorder, and rejecting a Story goes through the
approval workflow.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ActiveArchitectureReleasePort,
)
from smb_requirement_agent.application.ports.backlog_export import BacklogExportPort
from smb_requirement_agent.application.use_cases.approval_policy import ApprovalPolicy
from smb_requirement_agent.application.use_cases.approval_workflow import (
    AddReviewComment,
    ApprovalRecorder,
    ApproveBreakdown,
    GetApprovalWorkflow,
    SubmitForReview,
)
from smb_requirement_agent.application.use_cases.breakdown_review import (
    GetBreakdownReview,
    RecordDecision,
    ResolveFlag,
    ReviewEvidenceLoader,
)
from smb_requirement_agent.application.use_cases.export_breakdown import ExportBreakdown
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.application.use_cases.revision_history import (
    CompareBreakdownVersions,
    GetRevisionHistory,
)
from smb_requirement_agent.application.use_cases.source_impact import SourceImpactReview
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters


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


def build_review(
    persistence: PersistenceAdapters,
    clock: ClockPort,
    access: RequirementAccessService,
    source_impact: SourceImpactReview,
    exporters: tuple[BacklogExportPort, ...],
    current_release: ActiveArchitectureReleasePort,
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
        approve_breakdown=ApproveBreakdown(workflow, reviews, recorder, transactions),
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
    )
