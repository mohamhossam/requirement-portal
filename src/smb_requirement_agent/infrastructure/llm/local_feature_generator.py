"""Feature generator backed by a local OpenAI-compatible model server."""

import httpx
from smb_kernel.diagnostics import DebugTrace, NullDebugTrace
from smb_kernel.llm.local_structured_output import (
    LocalStructuredOutputClient,
)
from smb_kernel.llm.structured_output import (
    StructuredOutputClient,
    StructuredOutputError,
)

from smb_requirement_agent.analysis.domain.entities import RequirementAnalysis
from smb_requirement_agent.application.errors import FeatureGenerationError
from smb_requirement_agent.breakdown.application.ports.feature_generator import FeatureCandidate
from smb_requirement_agent.breakdown.application.ports.generation_guidance import (
    EMPTY_GENERATION_GUIDANCE,
    GenerationGuidance,
)
from smb_requirement_agent.breakdown.domain.epic.entities import Epic
from smb_requirement_agent.infrastructure.llm.backlog_mappers import to_feature_candidates
from smb_requirement_agent.infrastructure.llm.prompts.feature_prompt import (
    FEATURE_SYSTEM_PROMPT,
    PROMPT_VERSION,
    build_feature_user_prompt,
)
from smb_requirement_agent.infrastructure.llm.schemas.feature_schema import FeatureSetSchema
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


class StructuredFeatureGeneratorAdapter:
    """Provider-labelled Feature generation over a structured-output client."""

    def __init__(self, client: StructuredOutputClient, provider_name: str) -> None:
        self._client = client
        self._provider_name = provider_name

    def generate(
        self,
        requirement: Requirement,
        analysis: RequirementAnalysis,
        epic: Epic,
        *,
        guidance: GenerationGuidance = EMPTY_GENERATION_GUIDANCE,
    ) -> list[FeatureCandidate]:
        try:
            parsed = self._client.parse(
                system_prompt=FEATURE_SYSTEM_PROMPT,
                user_prompt=build_feature_user_prompt(
                    title=requirement.title.value,
                    description=requirement.description.value,
                    known_facts=[fact.statement for fact in analysis.known_facts],
                    constraints=[constraint.statement for constraint in analysis.constraints]
                    + list(analysis.accepted_constraints),
                    business_rules=[rule.statement for rule in analysis.business_rules]
                    + list(analysis.accepted_business_rules),
                    assumptions=[assumption.statement for assumption in analysis.assumptions],
                    open_questions=[question.question for question in analysis.open_questions],
                    clarifications=[
                        f"{item.subject}: {item.answer}" for item in analysis.clarifications
                    ],
                    epic_name=epic.name.value,
                    epic_outcome=epic.outcome.value,
                    epic_business_case=epic.business_case.value,
                    desired_outcome=analysis.effective_desired_outcome(),
                    guidance=guidance,
                ),
                schema_type=FeatureSetSchema,
            )
        except StructuredOutputError as exc:
            raise FeatureGenerationError(
                f"{self._provider_name} Feature generation failed: {exc}"
            ) from exc
        return to_feature_candidates(
            parsed,
            model=self._client.model,
            prompt_version=PROMPT_VERSION,
        )


class LocalFeatureGenerator(StructuredFeatureGeneratorAdapter):
    """Decompose approved Epics through a local structured-output endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str | None,
        context_window_tokens: int = 8192,
        max_output_tokens: int = 4096,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        super().__init__(
            LocalStructuredOutputClient(
                base_url=base_url,
                http_client=http_client,
                model=model,
                timeout_seconds=timeout_seconds,
                reasoning_effort=reasoning_effort,
                context_window_tokens=context_window_tokens,
                max_output_tokens=max_output_tokens,
                debug_trace=debug_trace if debug_trace is not None else NullDebugTrace(),
            ),
            "Local LLM",
        )
