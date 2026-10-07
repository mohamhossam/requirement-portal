"""FastAPI dependency providers.

Each provider pulls a use case out of the container held on the application
state, which is built once during startup by `interfaces.api.main`.  Tests
override `get_container` to supply an isolated graph.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from smb_kernel.http.service_auth import CALLER_SCOPE_KEY
from smb_kernel.identity.ports import IdentityCredential
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import AuthenticationRequiredError
from smb_requirement_agent.application.ports.reference_grounding import ReferenceReviewPort
from smb_requirement_agent.application.use_cases.activity_reporting import (
    GetOperationalReport,
    ListActivity,
)
from smb_requirement_agent.application.use_cases.ai_jobs import AiJobs, Notifications
from smb_requirement_agent.application.use_cases.analysis_collaboration import AnalysisCollaboration
from smb_requirement_agent.application.use_cases.analyze_requirement import AnalyzeRequirement
from smb_requirement_agent.application.use_cases.answer_suggestions import (
    SuggestClarificationAnswers,
)
from smb_requirement_agent.application.use_cases.approval_workflow import (
    AddReviewComment,
    ApproveBreakdown,
    ApproveStory,
    GetApprovalWorkflow,
    RejectStory,
    SubmitForReview,
)
from smb_requirement_agent.application.use_cases.approve_epic import ApproveEpic
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
)
from smb_requirement_agent.application.use_cases.architecture_mapping_jobs import (
    ArchitectureMappingJobs,
)
from smb_requirement_agent.application.use_cases.breakdown_review import (
    GenerateBreakdownReview,
    GetBreakdownReview,
    RecordDecision,
    ResolveFlag,
    ResolveOpenQuestion,
)
from smb_requirement_agent.application.use_cases.clarify_requirement_analysis import (
    ClarifyRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.confirm_requirement_analysis import (
    ConfirmRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.corpus_actions import (
    BulkReindexRequirements,
    ReinstateToCorpus,
    RetireFromCorpus,
)
from smb_requirement_agent.application.use_cases.edit_epic import EditEpic
from smb_requirement_agent.application.use_cases.export_breakdown import ExportBreakdown
from smb_requirement_agent.application.use_cases.feature_review import (
    ApproveFeature,
    EditFeature,
    GetFeatures,
)
from smb_requirement_agent.application.use_cases.generate_epic import GenerateEpic
from smb_requirement_agent.application.use_cases.generate_features import GenerateFeatures
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.get_epic import GetEpic
from smb_requirement_agent.application.use_cases.get_requirement_analysis import (
    GetRequirementAnalysis,
)
from smb_requirement_agent.application.use_cases.identity_access import (
    RequirementAccessService,
    SearchKnownActors,
)
from smb_requirement_agent.application.use_cases.internal_reads import InternalReads
from smb_requirement_agent.application.use_cases.knowledge_portfolio import (
    KnowledgePortfolio,
    NudgeFindingOwners,
)
from smb_requirement_agent.application.use_cases.knowledge_views import KnowledgeViews
from smb_requirement_agent.application.use_cases.prior_art import GetPriorArt, HistoricCitations
from smb_requirement_agent.application.use_cases.reference_currency import (
    CurrentArchitectureRelease,
)
from smb_requirement_agent.application.use_cases.requirement_commands import RequirementCommands
from smb_requirement_agent.application.use_cases.requirement_impact import (
    PreviewRequirementImpact,
    UpdateRequirementWithImpact,
)
from smb_requirement_agent.application.use_cases.requirement_indexing import (
    IndexRequirementKnowledge,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    DecideKnowledgeFinding,
    EnsureKnowledgeScreen,
    GetKnowledgeReview,
)
from smb_requirement_agent.application.use_cases.requirement_worklist import (
    RequirementWorklistReader,
)
from smb_requirement_agent.application.use_cases.revision_history import (
    CompareBreakdownVersions,
    GetRevisionHistory,
)
from smb_requirement_agent.application.use_cases.saved_views import SavedViews
from smb_requirement_agent.application.use_cases.source_impact import SourceImpactReview
from smb_requirement_agent.application.use_cases.story_change_proposals import StoryChangeProposals
from smb_requirement_agent.application.use_cases.story_quality import (
    GetFeatureQualitySnapshot,
    SuggestStorySplit,
    ValidateFeatureStories,
    ValidateStory,
)
from smb_requirement_agent.application.use_cases.story_workflow import (
    EditStory,
    GenerateStories,
    GetStories,
    MergeStories,
    RegenerateStory,
    SplitStory,
)
from smb_requirement_agent.application.use_cases.unified_knowledge_search import (
    UnifiedKnowledgeSearch,
)
from smb_requirement_agent.identity.application.ports.identity import Actor
from smb_requirement_agent.infrastructure.config.options import IdentityProvider
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.error_handlers import status_code_for
from smb_requirement_agent.requirements.application.use_cases.attachment_ingestion import (
    AttachmentIngestion,
)
from smb_requirement_agent.requirements.application.use_cases.documents import (
    GetDocument,
    ListDocuments,
    RemoveDocument,
    SetDocumentInclusion,
    SetHiddenWorksheetInclusion,
    UploadDocument,
)
from smb_requirement_agent.requirements.application.use_cases.get_requirement import GetRequirement
from smb_requirement_agent.requirements.application.use_cases.owned_requirements import (
    CreateOwnedRequirement,
    CreateOwnedRequirementDraft,
    GetOwnedRequirementDraft,
    ListOwnedRequirementDrafts,
    PromoteOwnedRequirementDraft,
    SaveOwnedRequirementDraft,
)
from smb_requirement_agent.shared_kernel.actors import ActorProfile


def get_container(request: Request) -> Container:
    """Return the container built at application startup."""
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]
bearer_scheme = HTTPBearer(auto_error=False, bearerFormat="JWT")


def get_current_actor(
    container: ContainerDep,
    credential: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    actor_hint: Annotated[str | None, Header(alias="X-Fake-Actor-Id")] = None,
) -> ActorProfile:
    bearer = credential.credentials if credential is not None else None
    if container.settings.identity_provider is IdentityProvider.OIDC and actor_hint:
        raise AuthenticationRequiredError("Fake actor headers are disabled in OIDC mode.")
    return container.resolve_current_actor.execute(IdentityCredential(bearer, actor_hint))


CurrentActorDep = Annotated[ActorProfile, Depends(get_current_actor)]


def require_service_caller(request: Request) -> str:
    """The platform service the middleware authenticated on an /internal route (ADR-0099).

    The second wall: a route that somehow ran without the middleware's check
    still refuses, rather than answering as nobody.
    """
    caller = request.scope.get(CALLER_SCOPE_KEY)
    if not isinstance(caller, str) or not caller:
        raise HTTPException(status_code=401, detail="An internal request needs a service token.")
    return caller


def require_authenticated_actor(actor: CurrentActorDep) -> None:
    return None


# Refusals that always precede any provider call: the budget is given back.
# A 409 is not here, because a conflict can surface at commit after a model
# call has already been paid for.
_REFUNDED_STATUSES = frozenset({401, 403, 404, 422})


def limit_provider_calls(container: ContainerDep, actor: CurrentActorDep) -> Iterator[None]:
    """Count one provider-calling operation against the caller's per-minute budget.

    Attach to every route that calls an AI provider, synchronously or by queueing
    a job; `tests/architecture/test_provider_rate_limit.py` holds the list. A
    request refused before it could reach a provider is refunded.
    """
    ticket = container.provider_call_rate_limit.acquire(actor)
    try:
        yield
    except Exception as exc:
        if ticket is not None and _refused_before_provider(exc):
            container.provider_call_rate_limit.refund(ticket)
        raise


def _refused_before_provider(exc: Exception) -> bool:
    if isinstance(exc, RequestValidationError):
        return True
    return status_code_for(exc) in _REFUNDED_STATUSES


def get_search_known_actors(container: ContainerDep) -> SearchKnownActors:
    return container.search_known_actors


def get_ai_jobs(container: ContainerDep) -> AiJobs:
    return container.ai_jobs


def get_notifications(container: ContainerDep) -> Notifications:
    return container.notifications


def get_list_activity(container: ContainerDep) -> ListActivity:
    return container.list_activity


def get_operational_report(container: ContainerDep) -> GetOperationalReport:
    return container.get_operational_report


def get_saved_views(container: ContainerDep) -> SavedViews:
    return container.saved_views


def get_requirement_access(container: ContainerDep) -> RequirementAccessService:
    return container.requirement_access


def get_create_requirement(container: ContainerDep) -> CreateOwnedRequirement:
    return container.create_requirement


def get_get_requirement(container: ContainerDep) -> GetRequirement:
    return container.get_requirement


def get_list_requirement_worklist(container: ContainerDep) -> RequirementWorklistReader:
    return container.list_requirement_worklist


def get_create_requirement_draft(container: ContainerDep) -> CreateOwnedRequirementDraft:
    return container.create_requirement_draft


def get_get_requirement_draft(container: ContainerDep) -> GetOwnedRequirementDraft:
    return container.get_requirement_draft


def get_list_requirement_drafts(container: ContainerDep) -> ListOwnedRequirementDrafts:
    return container.list_requirement_drafts


def get_save_requirement_draft(container: ContainerDep) -> SaveOwnedRequirementDraft:
    return container.save_requirement_draft


def get_promote_requirement_draft(container: ContainerDep) -> PromoteOwnedRequirementDraft:
    return container.promote_requirement_draft


def get_upload_document(container: ContainerDep) -> UploadDocument:
    return container.upload_document


def get_list_documents(container: ContainerDep) -> ListDocuments:
    return container.list_documents


def get_get_document(container: ContainerDep) -> GetDocument:
    return container.get_document


def get_set_document_inclusion(container: ContainerDep) -> SetDocumentInclusion:
    return container.set_document_inclusion


def get_set_hidden_worksheet_inclusion(
    container: ContainerDep,
) -> SetHiddenWorksheetInclusion:
    return container.set_hidden_worksheet_inclusion


def get_remove_document(container: ContainerDep) -> RemoveDocument:
    return container.remove_document


def get_preview_requirement_impact(container: ContainerDep) -> PreviewRequirementImpact:
    return container.preview_requirement_impact


def get_update_requirement(container: ContainerDep) -> UpdateRequirementWithImpact:
    return container.update_requirement


def get_analyze_requirement(container: ContainerDep) -> AnalyzeRequirement:
    return container.analyze_requirement


def get_generation_context_tokens(container: ContainerDep) -> GenerationContextTokens:
    return container.generation_context_tokens


def get_requirement_commands(container: ContainerDep) -> RequirementCommands:
    return container.requirement_commands


RequirementCommandsDep = Annotated[RequirementCommands, Depends(get_requirement_commands)]


def get_analysis_collaboration(container: ContainerDep) -> AnalysisCollaboration:
    return container.analysis_collaboration


def get_clarify_requirement_analysis(container: ContainerDep) -> ClarifyRequirementAnalysis:
    return container.clarify_requirement_analysis


def get_confirm_requirement_analysis(container: ContainerDep) -> ConfirmRequirementAnalysis:
    return container.confirm_requirement_analysis


def get_get_requirement_analysis(container: ContainerDep) -> GetRequirementAnalysis:
    return container.get_requirement_analysis


def get_generate_epic(container: ContainerDep) -> GenerateEpic:
    return container.generate_epic


def get_get_epic(container: ContainerDep) -> GetEpic:
    return container.get_epic


def get_edit_epic(container: ContainerDep) -> EditEpic:
    return container.edit_epic


def get_approve_epic(container: ContainerDep) -> ApproveEpic:
    return container.approve_epic


def get_generate_features(container: ContainerDep) -> GenerateFeatures:
    return container.generate_features


def get_get_features(container: ContainerDep) -> GetFeatures:
    return container.get_features


def get_edit_feature(container: ContainerDep) -> EditFeature:
    return container.edit_feature


def get_approve_feature(container: ContainerDep) -> ApproveFeature:
    return container.approve_feature


def get_approve_story(container: ContainerDep) -> ApproveStory:
    return container.approve_story


def get_reject_story(container: ContainerDep) -> RejectStory:
    return container.reject_story


def get_generate_stories(container: ContainerDep) -> GenerateStories:
    return container.generate_stories


def get_get_stories(container: ContainerDep) -> GetStories:
    return container.get_stories


def get_edit_story(container: ContainerDep) -> EditStory:
    return container.edit_story


def get_split_story(container: ContainerDep) -> SplitStory:
    return container.split_story


def get_merge_stories(container: ContainerDep) -> MergeStories:
    return container.merge_stories


def get_regenerate_story(container: ContainerDep) -> RegenerateStory:
    return container.regenerate_story


def get_story_change_proposals(container: ContainerDep) -> StoryChangeProposals:
    return container.story_change_proposals


def get_validate_story(container: ContainerDep) -> ValidateStory:
    return container.validate_story


def get_validate_feature_stories(container: ContainerDep) -> ValidateFeatureStories:
    return container.validate_feature_stories


def get_feature_quality_snapshot(container: ContainerDep) -> GetFeatureQualitySnapshot:
    return container.get_feature_quality_snapshot


def get_suggest_story_split(container: ContainerDep) -> SuggestStorySplit:
    return container.suggest_story_split


def get_map_breakdown_architecture(container: ContainerDep) -> MapBreakdownArchitecture:
    return container.map_breakdown_architecture


def get_generate_breakdown_review(container: ContainerDep) -> GenerateBreakdownReview:
    return container.generate_breakdown_review


def get_get_breakdown_review(container: ContainerDep) -> GetBreakdownReview:
    return container.get_breakdown_review


def get_record_decision(container: ContainerDep) -> RecordDecision:
    return container.record_decision


def get_resolve_flag(container: ContainerDep) -> ResolveFlag:
    return container.resolve_flag


def get_resolve_open_question(container: ContainerDep) -> ResolveOpenQuestion:
    return container.resolve_open_question


def get_approval_workflow(container: ContainerDep) -> GetApprovalWorkflow:
    return container.get_approval_workflow


def get_submit_for_review(container: ContainerDep) -> SubmitForReview:
    return container.submit_for_review


def get_approve_breakdown(container: ContainerDep) -> ApproveBreakdown:
    return container.approve_breakdown


def get_add_review_comment(container: ContainerDep) -> AddReviewComment:
    return container.add_review_comment


def get_revision_history(container: ContainerDep) -> GetRevisionHistory:
    return container.get_revision_history


def get_compare_breakdown_versions(container: ContainerDep) -> CompareBreakdownVersions:
    return container.compare_breakdown_versions


def get_export_breakdown(container: ContainerDep) -> ExportBreakdown:
    return container.export_breakdown


def get_get_knowledge_review(container: ContainerDep) -> GetKnowledgeReview:
    return container.get_knowledge_review


def get_get_prior_art(container: ContainerDep) -> GetPriorArt:
    return container.get_prior_art


def get_historic_citations(container: ContainerDep) -> HistoricCitations:
    return container.historic_citations


def get_ensure_knowledge_screen(container: ContainerDep) -> EnsureKnowledgeScreen:
    return container.ensure_knowledge_screen


def get_decide_knowledge_finding(container: ContainerDep) -> DecideKnowledgeFinding:
    return container.decide_knowledge_finding


def get_suggest_clarification_answers(container: ContainerDep) -> SuggestClarificationAnswers:
    return container.suggest_clarification_answers


def get_requirement_indexer(container: ContainerDep) -> IndexRequirementKnowledge:
    return container.requirement_indexer


def get_unified_knowledge_search(container: ContainerDep) -> UnifiedKnowledgeSearch:
    return container.unified_knowledge_search


def get_attachment_ingestion(container: ContainerDep) -> AttachmentIngestion:
    return container.attachment_ingestion


def get_source_impact(container: ContainerDep) -> SourceImpactReview:
    return container.source_impact


def get_knowledge_views(container: ContainerDep) -> KnowledgeViews:
    return container.knowledge_views


def get_current_release(container: ContainerDep) -> CurrentArchitectureRelease:
    return container.current_release


def get_internal_reads(container: ContainerDep) -> InternalReads:
    return container.internal_reads


def get_knowledge_portfolio(container: ContainerDep) -> KnowledgePortfolio:
    return container.knowledge_portfolio


def get_nudge_finding_owners(container: ContainerDep) -> NudgeFindingOwners:
    return container.nudge_finding_owners


def get_retire_from_corpus(container: ContainerDep) -> RetireFromCorpus:
    return container.retire_from_corpus


def get_reinstate_to_corpus(container: ContainerDep) -> ReinstateToCorpus:
    return container.reinstate_to_corpus


def get_bulk_reindex(container: ContainerDep) -> BulkReindexRequirements:
    return container.bulk_reindex


def get_knowledge_actor(actor: CurrentActorDep) -> Actor:
    """The role-bearing actor that architecture knowledge authorizes against."""
    return Actor(actor.id.value, actor.roles)


KnowledgeActorDep = Annotated[Actor, Depends(get_knowledge_actor)]


def get_clock(container: ContainerDep) -> ClockPort:
    return container.clock


def get_reference_reviews(container: ContainerDep) -> ReferenceReviewPort:
    return container.reference_currency


def get_architecture_mapping_jobs(container: ContainerDep) -> ArchitectureMappingJobs:
    return container.architecture_mapping_jobs
