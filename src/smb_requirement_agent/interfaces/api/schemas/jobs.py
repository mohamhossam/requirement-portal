"""HTTP schemas for durable AI jobs and actor notifications."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from smb_requirement_agent.domain.jobs.entities import (
    AiJobOperation,
    AiJobOrigin,
    AiJobStatus,
    NotificationKind,
)
from smb_requirement_agent.interfaces.api.schemas.analysis import (
    ClarificationAnswerRequest,
    ClarificationResolutionBatch,
)
from smb_requirement_agent.interfaces.api.schemas.bounds import (
    MAX_IDENTIFIER_CHARACTERS,
    MAX_ITEMS,
    MAX_TEXT_CHARACTERS,
    Identifier,
    Text,
)
from smb_requirement_agent.interfaces.api.schemas.identity import ActorResponse


class _JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalyseRequirementJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.ANALYSE_REQUIREMENT]
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    force: bool = False


class ClarifyAnalysisJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.CLARIFY_REQUIREMENT_ANALYSIS]
    answers: list[ClarificationAnswerRequest] = Field(min_length=1, max_length=MAX_ITEMS)
    expected_analysis_version: int = Field(ge=1)


class ResolveQuestionJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.RESOLVE_CLARIFICATION_QUESTION]
    question_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    answer: Text | None = None
    expected_version: int = Field(ge=1)
    source_suggestion_id: Identifier | None = None


class ResolveQuestionsJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.RESOLVE_CLARIFICATION_QUESTIONS]
    answers: ClarificationResolutionBatch


class GenerateEpicJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.GENERATE_EPIC]
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    force: bool = False


class GenerateFeaturesJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.GENERATE_FEATURES]
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    force: bool = False


class GenerateStoriesJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.GENERATE_STORIES]
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    feature_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)


class RegenerateStoryJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.REGENERATE_STORY]
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    feature_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    story_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    force: bool = False


class RegenerateStorySetJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.REGENERATE_STORY_SET]
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    feature_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    force: bool = False


class ProposeStoryChangeJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.PROPOSE_STORY_CHANGE]
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    feature_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    change_operation: Literal["split", "merge"]
    source_story_ids: list[Identifier] = Field(min_length=1, max_length=MAX_ITEMS)


class EvaluateFeatureQualityJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.EVALUATE_FEATURE_QUALITY]
    context_token: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    feature_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)


class GenerateBreakdownReviewJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.GENERATE_BREAKDOWN_REVIEW]


class ResolveReviewOpenQuestionJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.RESOLVE_REVIEW_OPEN_QUESTION]
    flag_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    answer: str = Field(min_length=1, max_length=MAX_TEXT_CHARACTERS)
    expected_fingerprint: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    expected_version: int = Field(ge=1)


class ScreenRequirementKnowledgeJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.SCREEN_REQUIREMENT_KNOWLEDGE]
    knowledge_fingerprint: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)


class SuggestClarificationAnswersJobRequest(_JobRequest):
    operation: Literal[AiJobOperation.SUGGEST_CLARIFICATION_ANSWERS]
    question_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_CHARACTERS)
    expected_version: int = Field(ge=1)


AiJobStartRequest = Annotated[
    AnalyseRequirementJobRequest
    | ClarifyAnalysisJobRequest
    | ResolveQuestionJobRequest
    | ResolveQuestionsJobRequest
    | GenerateEpicJobRequest
    | GenerateFeaturesJobRequest
    | GenerateStoriesJobRequest
    | RegenerateStoryJobRequest
    | RegenerateStorySetJobRequest
    | ProposeStoryChangeJobRequest
    | EvaluateFeatureQualityJobRequest
    | GenerateBreakdownReviewJobRequest
    | ResolveReviewOpenQuestionJobRequest
    | ScreenRequirementKnowledgeJobRequest
    | SuggestClarificationAnswersJobRequest,
    Field(discriminator="operation"),
]


class AiJobFailureResponse(BaseModel):
    code: str
    message: str
    retryable: bool
    correlation_id: str


class RetryAiJobRequest(_JobRequest):
    expected_version: int = Field(ge=1)


class AiJobResultResourceResponse(BaseModel):
    kind: str
    path: str


class AiJobResponse(BaseModel):
    id: str
    version: int
    requirement_id: str
    operation: AiJobOperation
    status: AiJobStatus
    created_by: ActorResponse
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancel_requested_at: datetime | None
    attempt_count: int
    retry_of_job_id: str | None
    failure: AiJobFailureResponse | None
    result_resources: list[AiJobResultResourceResponse]
    item_count: int | None = None
    origin: AiJobOrigin = AiJobOrigin.USER
    phase: str | None = None
    completed_units: int = 0
    total_units: int | None = None
    current_section_label: str | None = None


class NotificationResponse(BaseModel):
    id: str
    job_id: str | None
    kind: NotificationKind
    message: str
    created_at: datetime
    resource_path: str | None
    read_at: datetime | None


class NotificationPreferenceRequest(BaseModel):
    browser_enabled: bool


class CancelAiJobRequest(BaseModel):
    expected_version: int = Field(ge=1)


class NotificationPreferenceResponse(BaseModel):
    browser_enabled: bool
