"""Epic generator backed by a local OpenAI-compatible model server."""

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
from smb_requirement_agent.breakdown.application.errors import EpicGenerationError
from smb_requirement_agent.breakdown.application.ports.epic_generator import EpicCandidate
from smb_requirement_agent.breakdown.infrastructure.llm.backlog_mappers import to_epic_candidate
from smb_requirement_agent.breakdown.infrastructure.llm.prompts.epic_prompt import (
    EPIC_SYSTEM_PROMPT,
    PROMPT_VERSION,
    build_epic_user_prompt,
)
from smb_requirement_agent.breakdown.infrastructure.llm.schemas.epic_schema import EpicSchema
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


class StructuredEpicGeneratorAdapter:
    """Provider-labelled Epic generation over a structured-output client."""

    def __init__(self, client: StructuredOutputClient, provider_name: str) -> None:
        self._client = client
        self._provider_name = provider_name

    def generate(self, requirement: Requirement, analysis: RequirementAnalysis) -> EpicCandidate:
        try:
            parsed = self._client.parse(
                system_prompt=EPIC_SYSTEM_PROMPT,
                user_prompt=build_epic_user_prompt(
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
                    desired_outcome=analysis.effective_desired_outcome(),
                ),
                schema_type=EpicSchema,
            )
        except StructuredOutputError as exc:
            raise EpicGenerationError(
                f"{self._provider_name} Epic generation failed: {exc}"
            ) from exc
        return to_epic_candidate(
            parsed,
            model=self._client.model,
            prompt_version=PROMPT_VERSION,
        )


class LocalEpicGenerator(StructuredEpicGeneratorAdapter):
    """Generate Epics through a local structured-output endpoint."""

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
