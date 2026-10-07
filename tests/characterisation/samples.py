"""Fixed, fully populated aggregates for the characterisation tests (ADR-0103, PR 1).

Every value here is a literal, so the payloads, fingerprints and tokens computed from them are
stable across runs and machines. The bounded-context migration moves the classes these
samples are built from; the golden files built from them must not change while it does.

Change a sample only together with a deliberate, reviewed change to the golden files.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

from smb_kernel.documents.model import (
    DocumentEvidenceBlock,
    DocumentVersionId,
    EvidenceBlockKind,
)
from smb_kernel.identity.actor import ActorId

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
from smb_requirement_agent.application.ports.activity import (
    ActivityAction,
    ActivityCategory,
    ActivityEvent,
    AuditSourceKind,
    AuditSourceReference,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureCitation,
    ArchitectureDependency,
    ArchitectureImpact,
    OrganisationReference,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.knowledge import RelationshipKind
from smb_requirement_agent.domain.document.reference import (
    CurrentPublication,
    ReferenceDocumentState,
)
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.value_objects import (
    BusinessCase,
    BusinessOutcome,
    EpicId,
    EpicName,
)
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import (
    DeliveryDrop,
    FeatureId,
    FeatureName,
    FeatureOutcome,
    SplittingPattern,
    SplittingRationale,
)
from smb_requirement_agent.domain.knowledge.historic import (
    HistoricPublication,
    HistoricRequirementState,
)
from smb_requirement_agent.domain.review.entities import (
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
from smb_requirement_agent.domain.review.evidence import ReviewEvidence
from smb_requirement_agent.domain.story.entities import (
    StoryChangeOperation,
    StoryChangeProposal,
    StoryDraft,
    UserStory,
)
from smb_requirement_agent.domain.story.quality import (
    FindingSource,
    InvestAssessment,
    InvestCriterion,
    ValidationFinding,
)
from smb_requirement_agent.domain.story.value_objects import (
    AcceptanceCriterion,
    BusinessValue,
    DesiredAction,
    StoryId,
    StoryProposalId,
    UserRole,
)
from smb_requirement_agent.identity.domain.entities import (
    AccessChange,
    AccessChangeKind,
    AssignmentRole,
    DraftOwnership,
    RequirementAccess,
    RequirementAssignment,
)
from smb_requirement_agent.requirements.domain.document.entities import (
    SourceDocument,
    SourceDocumentVersion,
)
from smb_requirement_agent.requirements.domain.document.value_objects import (
    DocumentId,
    ExtractionStatus,
)
from smb_requirement_agent.requirements.domain.requirement.entities import (
    Requirement,
    RequirementDraft,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
    RequirementVersion,
)
from smb_requirement_agent.shared_kernel.actors import ActorSnapshot
from smb_requirement_agent.shared_kernel.approval import (
    Approval,
    ApprovalDecision,
    ApprovalId,
    ApprovalTarget,
    ApprovalTargetKind,
    ReviewComment,
)
from smb_requirement_agent.shared_kernel.generation import GenerationStatus, Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.staleness import Staleness, StaleReason

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
T1 = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
T2 = datetime(2026, 3, 2, 11, 30, tzinfo=UTC)
T3 = datetime(2026, 3, 3, 14, 15, tzinfo=UTC)

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64

REQUIREMENT_ID = RequirementId("req-golden-1")
DRAFT_ID = RequirementId("draft-golden-1")
ANALYSIS_ID = AnalysisId("analysis-golden-1")
EPIC_ID = EpicId("epic-golden-1")
FEATURE_ID = FeatureId("feature-golden-1")
SECOND_FEATURE_ID = FeatureId("feature-golden-2")
STORY_ID = StoryId("story-golden-1")
SECOND_STORY_ID = StoryId("story-golden-2")
QUESTION_ID = QuestionId("question-golden-1")
RESOLVED_QUESTION_ID = QuestionId("question-golden-2")

OWNER = ActorSnapshot(ActorId("actor-owner"), "Olivia Owner", "olivia@example.test")
REVIEWER = ActorSnapshot(ActorId("actor-reviewer"), "Ravi Reviewer", None)

GENERATED = Provenance(T0, "golden-model", "golden-prompt-v1")


def requirement() -> Requirement:
    return Requirement(
        id=REQUIREMENT_ID,
        title=RequirementTitle("Business SIM bundle self-service"),
        description=RequirementDescription(
            "Let SMB customers add a SIM bundle to an existing account through the portal."
        ),
        status=RequirementStatus.DRAFT,
        desired_outcome=RequirementContext("Halve bundle activation time."),
        customer_context=RequirementContext("SMB customers with 5 to 50 lines."),
        channels=(RequirementContext("B2B portal"), RequirementContext("Mobile app")),
        systems=(RequirementContext("BCRM"),),
        business_rules=(RequirementContext("Credit check before activation."),),
        constraints=(RequirementContext("No change to billing cycles."),),
        version=RequirementVersion(3),
        updated_at=T1,
    )


def requirement_draft() -> RequirementDraft:
    return RequirementDraft(
        id=DRAFT_ID,
        title="Draft bundle request",
        description="Partially captured need.",
        desired_outcome="",
        customer_context="Existing SMB accounts.",
        channels=("B2B portal",),
        systems=(),
        business_rules=("Credit check first.",),
        constraints=(),
        version=RequirementVersion(2),
        updated_at=T1,
    )


def _evidence() -> AnalysisEvidenceReference:
    return AnalysisEvidenceReference(
        "doc-golden-1", "doc-version-golden-1", SHA_B, "block-1", "Scope"
    )


def analysis() -> RequirementAnalysis:
    proposal = IntentProposal(
        id=IntentProposalId("proposal-golden-1"),
        kind=IntentProposalKind.BUSINESS_RULE,
        statement="Credit check must complete before activation.",
        rationale="The source names a credit check without ordering it.",
        decisions=(
            IntentProposalDecision(
                status=IntentProposalStatus.ACCEPTED,
                final_statement="Credit check must complete before activation.",
                success_measures=(),
                decided_by=OWNER,
                decided_at=T1,
                version=2,
            ),
        ),
    )
    return RequirementAnalysis(
        requirement_id=REQUIREMENT_ID,
        known_facts=(KnownFact("Customers already hold SMB accounts.", (_evidence(),)),),
        constraints=(Constraint("Billing cycles stay unchanged."),),
        business_rules=(BusinessRule("A credit check precedes activation."),),
        assumptions=(Assumption("Bundles are prepaid."),),
        open_questions=(OpenQuestion("Which bundle sizes apply?", "Pricing is unstated."),),
        ambiguities=(Ambiguity("Activation time", "No baseline is given."),),
        potential_dependencies=(PotentialDependency("BCRM order API availability."),),
        clarifications=(
            HumanClarification(
                kind=ClarificationKind.OPEN_QUESTION,
                subject="Which channels?",
                answer="Portal and app.",
                question_id=RESOLVED_QUESTION_ID,
                answered_by=OWNER,
                answered_at=T1,
            ),
        ),
        confirmed_at=T2,
        confirmed_by=OWNER,
        document_references=(
            AnalysisDocumentReference("doc-golden-1", "doc-version-golden-1", "scope.docx", SHA_B),
        ),
        id=ANALYSIS_ID,
        round_number=2,
        provenance=GENERATED,
        source_requirement_version=RequirementVersion(3),
        intent_proposals=(proposal,),
        source_desired_outcome="Halve bundle activation time.",
        stage_provenance=(
            AnalysisStageProvenance("evidence", "golden-model", "golden-prompt-v1", T0, SHA_A),
        ),
        version=4,
    )


def open_question() -> ClarificationQuestion:
    return ClarificationQuestion(
        id=QUESTION_ID,
        requirement_id=REQUIREMENT_ID,
        first_analysis_id=ANALYSIS_ID,
        kind=ClarificationKind.OPEN_QUESTION,
        subject="Which bundle sizes apply?",
        rationale="Pricing is unstated.",
        severity=ClarificationSeverity.HIGH,
        is_blocker=True,
        source=ClarificationSource.AI,
        status=ClarificationStatus.IN_PROGRESS,
        version=3,
        assignee=REVIEWER,
        assignment_history=(QuestionAssignmentChange(REVIEWER, OWNER, T1),),
        draft_answer="Probably 5, 10 and 20 lines.",
        draft_updated_by=REVIEWER,
        draft_updated_at=T2,
    )


def resolved_question() -> ClarificationQuestion:
    return ClarificationQuestion(
        id=RESOLVED_QUESTION_ID,
        requirement_id=REQUIREMENT_ID,
        first_analysis_id=ANALYSIS_ID,
        kind=ClarificationKind.OPEN_QUESTION,
        subject="Which channels?",
        rationale=None,
        severity=ClarificationSeverity.MEDIUM,
        is_blocker=False,
        source=ClarificationSource.HUMAN,
        status=ClarificationStatus.RESOLVED,
        version=2,
        asked_by=OWNER,
        asked_at=T0,
        answer="Portal and app.",
        answered_by=OWNER,
        answered_at=T1,
    )


def analysis_round() -> AnalysisRound:
    return AnalysisRound(
        analysis=analysis(),
        question_ids=(QUESTION_ID, RESOLVED_QUESTION_ID),
        question_changes=(
            AnalysisQuestionChange(
                QuestionChangeAction.RETAINED, QUESTION_ID, "Still unanswered by the source."
            ),
        ),
    )


def architecture() -> ArchitectureImpact:
    bcrm = SystemReference(
        id="sys-bcrm",
        name="BCRM",
        catalogued=True,
        capabilities=(SystemCapability("cap-order", "Order capture"),),
        constraints=("Batch window 01:00-03:00",),
        squads=(OrganisationReference("squad-orders", "Orders squad"),),
        value_streams=(OrganisationReference("vs-smb", "SMB"),),
        products=(OrganisationReference("prod-bundle", "SIM bundle"),),
    )
    cbcm = SystemReference(id="sys-cbcm", name="CBCM", catalogued=True)
    return ArchitectureImpact(
        knowledge_version="catalogue-7",
        mapped_at=T1,
        systems=(bcrm, cbcm),
        dependencies=(
            ArchitectureDependency(
                "sys-bcrm", "sys-cbcm", "Activation request", RelationshipKind.CALLS_API
            ),
        ),
        citation_ids=("chunk-1",),
        model="golden-model",
        embedding_model="golden-embedding",
        prompt_version="golden-mapping-v1",
        index_revision=5,
        evidence_classification="ai_inference",
        citations=(ArchitectureCitation("sys-bcrm", "chunk-1", "BCRM captures SMB orders."),),
    )


def epic() -> Epic:
    return Epic(
        id=EPIC_ID,
        requirement_id=REQUIREMENT_ID,
        name=EpicName("SMB bundle self-service"),
        outcome=BusinessOutcome("SMB customers activate bundles without an agent."),
        business_case=BusinessCase("Agent-assisted activation costs time and money."),
        status=GenerationStatus.GENERATED,
        provenance=GENERATED,
        version=2,
    )


def _approval(kind: ApprovalTargetKind, item_id: str, fingerprint: str) -> Approval:
    return Approval(
        id=ApprovalId(f"approval-{item_id}"),
        target=ApprovalTarget(kind, item_id),
        decision=ApprovalDecision.APPROVED,
        subject_fingerprint=fingerprint,
        recorded_by=OWNER,
        recorded_at=T2,
        rationale="Matches the confirmed analysis.",
    )


def approved_epic() -> Epic:
    return replace(
        epic(),
        status=GenerationStatus.APPROVED,
        approvals=(_approval(ApprovalTargetKind.EPIC, EPIC_ID.value, SHA_A),),
    )


def stale_epic() -> Epic:
    return replace(epic(), staleness=Staleness(StaleReason.REQUIREMENT_CHANGED, T3))


def feature() -> Feature:
    return Feature(
        id=FEATURE_ID,
        epic_id=EPIC_ID,
        name=FeatureName("Portal bundle ordering"),
        outcome=FeatureOutcome("Customers order a bundle in the portal."),
        delivery_drop=DeliveryDrop.MVP,
        splitting_pattern=SplittingPattern.CHANNEL,
        splitting_rationale=SplittingRationale("The portal is the first channel."),
        architecture=architecture(),
        status=GenerationStatus.EDITED,
        provenance=GENERATED,
        version=3,
    )


def second_feature() -> Feature:
    return Feature(
        id=SECOND_FEATURE_ID,
        epic_id=EPIC_ID,
        name=FeatureName("App bundle ordering"),
        outcome=FeatureOutcome("Customers order a bundle in the app."),
        delivery_drop=DeliveryDrop.LATER,
        splitting_pattern=SplittingPattern.CHANNEL,
        splitting_rationale=SplittingRationale("The app follows the portal."),
        status=GenerationStatus.APPROVED,
        provenance=GENERATED,
        approvals=(_approval(ApprovalTargetKind.FEATURE, SECOND_FEATURE_ID.value, SHA_B),),
        staleness=Staleness(StaleReason.EPIC_CHANGED, T3),
    )


def story() -> UserStory:
    return UserStory(
        id=STORY_ID,
        feature_id=FEATURE_ID,
        role=UserRole("SMB account administrator"),
        action=DesiredAction("to add a SIM bundle in the portal"),
        value=BusinessValue("new lines work the same day"),
        acceptance_criteria=(
            AcceptanceCriterion(
                "an account with a passed credit check",
                "the administrator orders a 10-line bundle",
                "the bundle is active within one hour",
            ),
            AcceptanceCriterion(
                "an account with a failed credit check",
                "the administrator orders a bundle",
                "the order is refused with the reason",
            ),
        ),
        architecture=architecture(),
        status=GenerationStatus.GENERATED,
        provenance=GENERATED,
    )


def second_story() -> UserStory:
    return UserStory(
        id=SECOND_STORY_ID,
        feature_id=FEATURE_ID,
        role=UserRole("SMB account administrator"),
        action=DesiredAction("to see bundle activation status"),
        value=BusinessValue("I know when lines are usable"),
        acceptance_criteria=(
            AcceptanceCriterion(
                "a pending bundle order", "the administrator opens it", "its status is shown"
            ),
        ),
        status=GenerationStatus.APPROVED,
        provenance=GENERATED,
        approvals=(_approval(ApprovalTargetKind.STORY, SECOND_STORY_ID.value, SHA_C),),
        version=2,
    )


def assessment() -> InvestAssessment:
    return InvestAssessment(
        story_id=STORY_ID,
        findings=tuple(
            ValidationFinding(
                criterion,
                criterion is not InvestCriterion.SMALL,
                f"{criterion.value} checked",
                FindingSource.DETERMINISTIC,
            )
            for criterion in InvestCriterion
        ),
        provenance=GENERATED,
    )


def story_proposal() -> StoryChangeProposal:
    return StoryChangeProposal(
        id=StoryProposalId("proposal-story-golden-1"),
        feature_id=FEATURE_ID,
        operation=StoryChangeOperation.SPLIT,
        source_story_ids=(STORY_ID,),
        source_fingerprint=SHA_A,
        candidates=(
            StoryDraft(
                UserRole("SMB account administrator"),
                DesiredAction("to order a bundle"),
                BusinessValue("lines are requested"),
                (AcceptanceCriterion("an account", "an order is placed", "it is recorded"),),
            ),
            StoryDraft(
                UserRole("SMB account administrator"),
                DesiredAction("to activate a bundle"),
                BusinessValue("lines work"),
                (AcceptanceCriterion("a recorded order", "activation runs", "lines are live"),),
            ),
        ),
        version=2,
    )


def _source(kind: ReviewSourceKind, item_id: str, label: str) -> ReviewSource:
    return ReviewSource(kind, item_id, label)


def review() -> BreakdownReview:
    decision = Decision(
        id=DecisionId("decision-golden-1"),
        decision="Accept the prepaid assumption for the MVP.",
        rationale="Postpaid follows in Drop 2.",
        recorded_at=T2,
        target_flag_id=FlagId("flag-golden-2"),
        recorded_by=OWNER,
    )
    return BreakdownReview(
        requirement_id=REQUIREMENT_ID,
        generated_at=T2,
        ruleset_version="breakdown-review-v3",
        evidence_fingerprint=SHA_A,
        dependencies=(
            Dependency(
                DependencyId("dependency-golden-1"),
                "BCRM order API availability.",
                _source(ReviewSourceKind.ANALYSIS, ANALYSIS_ID.value, "Analysis"),
                DependencyEvidenceKind.POTENTIAL,
            ),
        ),
        risks=(
            Risk(
                RiskId("risk-golden-1"),
                FlagSeverity.WARNING,
                "Two systems change together.",
                _source(ReviewSourceKind.FEATURE, FEATURE_ID.value, "Portal bundle ordering"),
            ),
        ),
        flags=(
            Flag(
                id=FlagId("flag-golden-1"),
                category=FlagCategory.OPEN_QUESTION,
                severity=FlagSeverity.BLOCKING,
                title="Open question",
                detail="Which bundle sizes apply?",
                source=_source(ReviewSourceKind.ANALYSIS, QUESTION_ID.value, "Bundle sizes"),
                resolution_policy=ResolutionPolicy.CLARIFICATION,
            ),
            Flag(
                id=FlagId("flag-golden-2"),
                category=FlagCategory.ASSUMPTION,
                severity=FlagSeverity.WARNING,
                title="Assumption",
                detail="Bundles are prepaid.",
                source=_source(ReviewSourceKind.ANALYSIS, ANALYSIS_ID.value, "Analysis"),
                resolution_policy=ResolutionPolicy.DECISION,
                status=FlagStatus.RESOLVED,
                resolution_decision_id=DecisionId("decision-golden-1"),
            ),
        ),
        recommendations=(
            Recommendation(
                RecommendationId("recommendation-golden-1"),
                "Split the ordering Story.",
                "It fails the Small criterion.",
                _source(ReviewSourceKind.STORY, STORY_ID.value, "Order a bundle"),
            ),
        ),
        quality_assessments=(assessment(),),
        decisions=(decision,),
        status=BreakdownStatus.UNDER_REVIEW,
        submitted_fingerprint=SHA_B,
        approvals=(_approval(ApprovalTargetKind.FLAG, "flag-golden-2", SHA_C),),
        comments=(
            ReviewComment(
                "comment-golden-1",
                ApprovalTarget(ApprovalTargetKind.BREAKDOWN, REQUIREMENT_ID.value),
                "Ready once sizes are known.",
                REVIEWER,
                T3,
            ),
        ),
        version=5,
        knowledge_version="catalogue-7",
    )


def document() -> SourceDocument:
    block = DocumentEvidenceBlock(
        id="block-1",
        kind=EvidenceBlockKind.PARAGRAPH,
        ordinal=1,
        section_path=("Scope",),
        label="Scope",
        content_fingerprint=SHA_C,
        text="SMB customers add SIM bundles through the portal.",
    )
    version = SourceDocumentVersion(
        id=DocumentVersionId("doc-version-golden-1"),
        number=1,
        filename="scope.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=2048,
        checksum_sha256=SHA_B,
        extraction_status=ExtractionStatus.READY,
        created_at=T0,
        extracted_text="SMB customers add SIM bundles through the portal.",
        extraction_version="golden-extractor-1",
        evidence_blocks=(block,),
    )
    return SourceDocument(
        id=DocumentId("doc-golden-1"),
        versions=(version,),
        requirement_id=REQUIREMENT_ID,
        included_version_id=version.id,
        version_number=2,
    )


def access() -> RequirementAccess:
    return RequirementAccess(
        requirement_id=REQUIREMENT_ID,
        owner=RequirementAssignment(OWNER, AssignmentRole.OWNER, T0, OWNER),
        reviewers=(RequirementAssignment(REVIEWER, AssignmentRole.REVIEWER, T1, OWNER),),
        changes=(
            AccessChange(AccessChangeKind.CLAIMED, OWNER, OWNER, T0),
            AccessChange(AccessChangeKind.REVIEWER_ASSIGNED, REVIEWER, OWNER, T1),
        ),
        version=3,
    )


def draft_ownership() -> DraftOwnership:
    return DraftOwnership(
        draft_id=DRAFT_ID,
        owner=RequirementAssignment(OWNER, AssignmentRole.OWNER, T0, OWNER),
    )


def activity_event() -> ActivityEvent:
    return ActivityEvent(
        id="activity-golden-1",
        requirement_id=REQUIREMENT_ID,
        requirement_title="Business SIM bundle self-service",
        category=ActivityCategory.REQUIREMENT,
        action=ActivityAction.REQUIREMENT_UPDATED,
        summary="Requirement updated to version 3.",
        occurred_at=T1,
        actor=OWNER,
        target_id=REQUIREMENT_ID.value,
        resource_path=f"/requirements/{REQUIREMENT_ID.value}",
        sources=(AuditSourceReference(AuditSourceKind.REQUIREMENT_REVISION, "revision-golden-3"),),
    )


def reference_document_state() -> ReferenceDocumentState:
    return ReferenceDocumentState(
        document_id="library-doc-golden-1",
        owner_id="actor-librarian",
        title="SMB activation policy",
        version=4,
        published=CurrentPublication(
            publication_id="publication-golden-1",
            fingerprint=SHA_A,
            version_id="library-version-golden-2",
            version_number=2,
            revision_id="library-revision-golden-3",
            block_labels=(("block-1", "Activation"), ("block-2", "Credit")),
            passages=(("block-1", "Activation completes within one hour."),),
        ),
        review_due_on=date(2026, 9, 1),
    )


def historic_requirement_state() -> HistoricRequirementState:
    return HistoricRequirementState(
        historic_requirement_id="historic-golden-1",
        version=2,
        published=HistoricPublication(
            number=1,
            fingerprint=SHA_B,
            title="2024 bundle activation BRD",
            published_at=T0,
            published_by="actor-librarian",
            root_ids=(101, 102),
        ),
    )


def review_evidence() -> ReviewEvidence:
    return ReviewEvidence(
        requirement=requirement(),
        analysis=analysis(),
        epic=approved_epic(),
        features=(feature(), second_feature()),
        stories=(story(), second_story()),
        questions=(open_question(), resolved_question()),
    )
