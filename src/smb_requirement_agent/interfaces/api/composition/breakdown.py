"""The backlog breakdown: Epic, Features and Stories, their quality and architecture.

Generation, editing and approval of each level, Story quality, architecture
mapping, and generating and answering the breakdown review.
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.ports.architecture_knowledge import ArchitectureKnowledgePort
from smb_requirement_agent.application.ports.domain_events import DomainEventPublisher
from smb_requirement_agent.application.ports.epic_generator import EpicGeneratorPort
from smb_requirement_agent.application.ports.feature_generator import FeatureGeneratorPort
from smb_requirement_agent.application.ports.story_generator import StoryGeneratorPort
from smb_requirement_agent.application.ports.story_quality_evaluator import (
    StoryQualityEvaluatorPort,
)
from smb_requirement_agent.application.use_cases.ai_jobs import AnalysisProgressReporter
from smb_requirement_agent.application.use_cases.analysis_collaboration import (
    AnalysisCollaboration,
)
from smb_requirement_agent.application.use_cases.approval_workflow import (
    ApproveStory,
    RejectStory,
)
from smb_requirement_agent.application.use_cases.approve_epic import ApproveEpic
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapBreakdownArchitecture,
    MapFeatureArchitecture,
    MapStoryArchitecture,
)
from smb_requirement_agent.application.use_cases.breakdown_review import (
    GenerateBreakdownReview,
    GovernanceCandidateReview,
    RefreshSavedBreakdownReview,
    ResolveOpenQuestion,
)
from smb_requirement_agent.application.use_cases.edit_epic import EditEpic
from smb_requirement_agent.application.use_cases.feature_review import (
    ApproveFeature,
    EditFeature,
    GetFeatures,
)
from smb_requirement_agent.application.use_cases.generate_epic import GenerateEpic
from smb_requirement_agent.application.use_cases.generate_features import GenerateFeatures
from smb_requirement_agent.application.use_cases.generation_checks import GenerationChecks
from smb_requirement_agent.application.use_cases.generation_context import GenerationContextTokens
from smb_requirement_agent.application.use_cases.get_epic import GetEpic
from smb_requirement_agent.application.use_cases.identity_access import RequirementAccessService
from smb_requirement_agent.application.use_cases.story_change_proposals import StoryChangeProposals
from smb_requirement_agent.application.use_cases.story_quality import (
    AssessStoryCandidate,
    EvaluateFeatureStories,
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
from smb_requirement_agent.domain.review.policy import BreakdownReviewPolicy
from smb_requirement_agent.interfaces.api.composition.persistence import PersistenceAdapters
from smb_requirement_agent.interfaces.api.composition.review import ReviewWiring


@dataclass(frozen=True)
class BreakdownModels:
    """The model ports the breakdown generates and evaluates with."""

    epic_generator: EpicGeneratorPort
    feature_generator: FeatureGeneratorPort
    story_generator: StoryGeneratorPort
    story_quality_evaluator: StoryQualityEvaluatorPort


@dataclass(frozen=True)
class BreakdownWiring:
    generate_epic: GenerateEpic
    get_epic: GetEpic
    edit_epic: EditEpic
    approve_epic: ApproveEpic
    generate_features: GenerateFeatures
    get_features: GetFeatures
    edit_feature: EditFeature
    approve_feature: ApproveFeature
    generate_stories: GenerateStories
    get_stories: GetStories
    edit_story: EditStory
    split_story: SplitStory
    merge_stories: MergeStories
    regenerate_story: RegenerateStory
    story_change_proposals: StoryChangeProposals
    approve_story: ApproveStory
    reject_story: RejectStory
    validate_story: ValidateStory
    validate_feature_stories: ValidateFeatureStories
    evaluate_feature_stories: EvaluateFeatureStories
    get_feature_quality_snapshot: GetFeatureQualitySnapshot
    suggest_story_split: SuggestStorySplit
    map_feature_architecture: MapFeatureArchitecture
    map_story_architecture: MapStoryArchitecture
    map_breakdown_architecture: MapBreakdownArchitecture
    generate_breakdown_review: GenerateBreakdownReview
    resolve_open_question: ResolveOpenQuestion


def build_breakdown(
    persistence: PersistenceAdapters,
    models: BreakdownModels,
    architecture: ArchitectureKnowledgePort,
    review: ReviewWiring,
    collaboration: AnalysisCollaboration,
    contexts: GenerationContextTokens,
    events: DomainEventPublisher,
    clock: ClockPort,
    access: RequirementAccessService,
) -> BreakdownWiring:
    requirements = persistence.requirement_repository
    analyses = persistence.analysis_repository
    epics = persistence.epic_repository
    features = persistence.feature_repository
    stories = persistence.story_repository
    transactions = persistence.transaction_manager
    # Every Story-set change shares one argument list; only the model use differs.
    story_set = (requirements, analyses, epics, features, stories, transactions)

    get_stories = GetStories(*story_set, events, authorization=access)
    validate_story = ValidateStory(get_stories, models.story_quality_evaluator, clock)
    validate_feature_stories = ValidateFeatureStories(get_stories, validate_story)
    map_feature = MapFeatureArchitecture(architecture)
    map_story = MapStoryArchitecture(architecture)
    checks = GenerationChecks(
        architecture,
        map_feature,
        map_story,
        AssessStoryCandidate(models.story_quality_evaluator, clock),
        persistence.story_quality_repository,
        GovernanceCandidateReview(
            BreakdownReviewPolicy(),
            RefreshSavedBreakdownReview(
                review.review_evidence,
                persistence.breakdown_review_repository,
                persistence.story_quality_repository,
                BreakdownReviewPolicy(),
                clock,
                review.current_release,
            ),
            clock,
        ),
        clock,
        AnalysisProgressReporter(persistence.ai_job_repository, clock),
    )
    return BreakdownWiring(
        generate_epic=GenerateEpic(
            requirements,
            analyses,
            epics,
            models.epic_generator,
            clock,
            events,
            transactions,
            authorization=access,
            contexts=contexts,
        ),
        get_epic=GetEpic(requirements, epics),
        edit_epic=EditEpic(requirements, epics, events, transactions, authorization=access),
        approve_epic=ApproveEpic(requirements, epics, review.approval_recorder, transactions),
        generate_features=GenerateFeatures(
            requirements,
            analyses,
            epics,
            features,
            stories,
            persistence.story_proposal_repository,
            models.feature_generator,
            clock,
            events,
            transactions,
            authorization=access,
            contexts=contexts,
            checks=checks,
        ),
        get_features=GetFeatures(requirements, epics, features),
        edit_feature=EditFeature(
            requirements, epics, features, events, transactions, authorization=access
        ),
        approve_feature=ApproveFeature(
            requirements, epics, features, review.approval_recorder, transactions
        ),
        generate_stories=GenerateStories(
            *story_set,
            events,
            generator=models.story_generator,
            clock=clock,
            authorization=access,
            contexts=contexts,
            checks=checks,
        ),
        get_stories=get_stories,
        edit_story=EditStory(*story_set, events, authorization=access),
        split_story=SplitStory(*story_set, events, authorization=access),
        merge_stories=MergeStories(*story_set, events, authorization=access),
        regenerate_story=RegenerateStory(
            *story_set,
            events,
            proposals=persistence.story_proposal_repository,
            generator=models.story_generator,
            clock=clock,
            authorization=access,
            contexts=contexts,
            checks=checks,
        ),
        story_change_proposals=StoryChangeProposals(
            *story_set,
            events,
            proposals=persistence.story_proposal_repository,
            generator=models.story_generator,
            clock=clock,
            authorization=access,
            contexts=contexts,
            checks=checks,
        ),
        approve_story=ApproveStory(
            requirements, epics, features, stories, review.approval_recorder, transactions
        ),
        reject_story=RejectStory(
            review.get_approval_workflow,
            requirements,
            epics,
            features,
            stories,
            persistence.breakdown_review_repository,
            review.approval_recorder,
            transactions,
        ),
        validate_story=validate_story,
        validate_feature_stories=validate_feature_stories,
        evaluate_feature_stories=EvaluateFeatureStories(
            get_stories,
            validate_feature_stories,
            persistence.story_quality_repository,
            transactions,
            clock,
            authorization=access,
        ),
        get_feature_quality_snapshot=GetFeatureQualitySnapshot(
            get_stories, persistence.story_quality_repository
        ),
        suggest_story_split=SuggestStorySplit(validate_story),
        map_feature_architecture=map_feature,
        map_story_architecture=map_story,
        map_breakdown_architecture=MapBreakdownArchitecture(
            *story_set,
            map_feature,
            map_story,
            clock,
            events,
            authorization=access,
        ),
        generate_breakdown_review=GenerateBreakdownReview(
            review.review_evidence,
            persistence.breakdown_review_repository,
            validate_story,
            BreakdownReviewPolicy(),
            clock,
            transactions,
            review.current_release,
            authorization=access,
            quality=persistence.story_quality_repository,
        ),
        resolve_open_question=ResolveOpenQuestion(
            review.get_breakdown_review,
            persistence.breakdown_review_repository,
            collaboration,
            clock,
            transactions,
        ),
    )
