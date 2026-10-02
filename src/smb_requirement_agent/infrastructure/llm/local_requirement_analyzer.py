"""Requirement analyzer backed by a local OpenAI-compatible model server."""

import logging
import time
from collections.abc import Sequence

import httpx
from pydantic import ValidationError

from smb_requirement_agent.application.errors import (
    ModelTransportError,
    RequirementAnalysisGenerationError,
)
from smb_requirement_agent.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    AnalysisDocumentContext,
    RequirementAnalysisCandidate,
    RequirementAnalyzerPort,
)
from smb_requirement_agent.domain.analysis.value_objects import (
    ClarificationKind,
    HumanClarification,
    IntentProposal,
)
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.infrastructure.diagnostics import DebugTrace, NullDebugTrace
from smb_requirement_agent.infrastructure.llm.candidate_mappers import (
    analysis_evidence_subjects,
    attach_analysis_evidence,
    normalize_analysis_intent,
    salvage_human_citations,
    to_analysis_candidate,
    to_analysis_content_candidate,
    to_clarification_questions,
    to_desired_outcome_review,
)
from smb_requirement_agent.infrastructure.llm.local_structured_output import (
    LocalStructuredOutputClient,
)
from smb_requirement_agent.infrastructure.llm.prompts.analysis_prompt import (
    CITATION_RECOVERY_SYSTEM_PROMPT,
    CLARIFICATION_REVIEW_SYSTEM_PROMPT,
    COMPLETE_ANALYSIS_RETRY_INSTRUCTION,
    DESIRED_OUTCOME_REVIEW_SYSTEM_PROMPT,
    PROMPT_VERSION,
    QUESTION_RECONCILIATION_RECOVERY_SYSTEM_PROMPT,
    REQUIREMENT_ANALYSIS_SYSTEM_PROMPT,
    UNCERTAINTY_RATIONALE_RECOVERY_SYSTEM_PROMPT,
    build_citation_recovery_prompt,
    build_clarification_review_prompt,
    build_desired_outcome_review_prompt,
    build_question_reconciliation_recovery_prompt,
    build_uncertainty_rationale_recovery_prompt,
    build_user_prompt,
    format_structured_context,
    vague_terms,
)
from smb_requirement_agent.infrastructure.llm.schemas.analysis_schema import (
    ActiveQuestionReviewSchema,
    AnalysisEvidenceCitationSchema,
    ClarificationReviewSchema,
    DesiredOutcomeReviewSchema,
    IndexedQuestionReconciliationSchema,
    IndexedUncertaintyRationaleRecoverySchema,
    RequirementAnalysisSchema,
    citation_recovery_schema,
)
from smb_requirement_agent.infrastructure.llm.structured_output import (
    StructuredOutputClient,
    StructuredOutputError,
    StructuredResponseValidationError,
    response_validation_error,
)

logger = logging.getLogger("smb_requirement_agent.llm.local_analysis")


class StructuredRequirementAnalyzerAdapter(RequirementAnalyzerPort):
    """Provider-labelled requirement analysis over a structured-output client."""

    def __init__(
        self,
        *,
        client: StructuredOutputClient,
        provider_name: str,
        vision_enabled: bool,
        vision_error: str,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        self._debug_trace = debug_trace if debug_trace is not None else NullDebugTrace()
        self._client = client
        self._provider_name = provider_name
        self._vision_enabled = vision_enabled
        self._vision_error = vision_error

    @property
    def model(self) -> str:
        return self._client.model

    @property
    def configuration_fingerprint(self) -> str:
        return str(getattr(self._client, "configuration_fingerprint", ""))

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    def analyze_evidence(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext],
        intent_decisions: Sequence[IntentProposal],
        active_questions: Sequence[ActiveQuestionContext],
    ) -> RequirementAnalysisCandidate:
        return self.analyze(
            requirement, clarifications, documents, intent_decisions, active_questions
        )

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        structured_context = format_structured_context(requirement)
        source_text = "\n".join(
            (
                requirement.title.value,
                requirement.description.value,
                structured_context,
                *(item["extracted_text"] for item in documents),
            )
        )
        user_prompt = build_user_prompt(
            title=requirement.title.value,
            description=requirement.description.value,
            structured_context=structured_context,
            documents=documents,
            clarifications=[
                (item.kind.value, item.subject, item.answer) for item in clarifications
            ],
            intent_decisions=[
                (item.kind.value, item.status.value, item.effective_statement)
                for item in intent_decisions
                if item.status.value != "pending"
            ],
            active_questions=active_questions,
        )
        try:
            images = tuple(
                (asset["mime_type"], asset["content"])
                for document in documents
                for asset in document.get("image_assets", [])
            )
            if images and not self._vision_enabled:
                raise RequirementAnalysisGenerationError(self._vision_error)
            parsed = self._client.parse(
                system_prompt=REQUIREMENT_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                schema_type=RequirementAnalysisSchema,
                images=images,
            )
        except (StructuredOutputError, ModelTransportError) as exc:
            raise RequirementAnalysisGenerationError(
                f"{self._provider_name} analysis failed: {exc}"
            ) from exc

        has_structured_evidence = any(item.get("evidence_blocks") for item in documents)
        parsed = normalize_analysis_intent(
            parsed,
            intent_decisions,
            has_source_outcome=requirement.desired_outcome is not None,
            debug_trace=self._debug_trace,
        )
        has_active_ai_questions = any(item["source"].value == "ai" for item in active_questions)
        if not has_active_ai_questions and parsed.active_question_reviews:
            self._debug_trace.record(
                "analysis.question_reviews_discarded",
                reason="no active AI questions were supplied",
                discarded_count=len(parsed.active_question_reviews),
            )
            parsed = parsed.model_copy(update={"active_question_reviews": []})
        if not has_structured_evidence:
            parsed = self._discard_unsuppliable_citations(parsed, len(clarifications))
        if has_structured_evidence:
            parsed = self._repair_missing_uncertainty_rationales(parsed, documents, images)

        try:
            candidate = to_analysis_content_candidate(
                parsed,
                model=self._client.model,
                prompt_version=PROMPT_VERSION,
                source_text=source_text,
                active_questions=active_questions,
                debug_trace=self._debug_trace,
            )
        except RequirementAnalysisGenerationError as exc:
            if has_active_ai_questions:
                logger.warning(
                    "%s model %s returned unusable question reconciliation; "
                    "running focused recovery.",
                    self._provider_name,
                    self._client.model,
                )
                parsed = self._recover_question_reconciliation(
                    parsed,
                    user_prompt,
                    active_questions,
                    exc,
                )
                try:
                    candidate = to_analysis_content_candidate(
                        parsed,
                        model=self._client.model,
                        prompt_version=PROMPT_VERSION,
                        source_text=source_text,
                        active_questions=active_questions,
                        debug_trace=self._debug_trace,
                    )
                except RequirementAnalysisGenerationError as recovery_error:
                    raise RequirementAnalysisGenerationError(
                        f"{self._provider_name} question reconciliation remained unusable after "
                        f"focused recovery. Initial validation: {exc}"
                    ) from recovery_error
            elif has_structured_evidence:
                raise
            else:
                logger.warning(
                    "%s model %s returned an unusable analysis; retrying once.",
                    self._provider_name,
                    self._client.model,
                )
                candidate = self._retry_complete_analysis(
                    user_prompt,
                    source_text,
                    active_questions,
                    documents,
                    intent_decisions,
                    requirement.desired_outcome is not None,
                )

        if has_structured_evidence:
            try:
                return attach_analysis_evidence(
                    parsed,
                    candidate,
                    documents=documents,
                    debug_trace=self._debug_trace,
                    clarification_count=len(clarifications),
                )
            except RequirementAnalysisGenerationError as exc:
                return self._recover_evidence_citations(
                    parsed,
                    candidate,
                    documents,
                    images,
                    exc,
                    clarifications,
                    "\n".join(
                        (
                            requirement.description.value,
                            structured_context,
                            *(
                                f"Owner-confirmed {item.kind.value}: {item.effective_statement}"
                                for item in intent_decisions
                                if item.status.value in {"accepted", "edited"}
                                and item.effective_statement is not None
                            ),
                        )
                    ),
                )

        if parsed.evidence_citations:
            parsed = self._salvage_human_citations(parsed, candidate, len(clarifications))
        candidate = attach_analysis_evidence(
            parsed,
            candidate,
            documents=documents,
            debug_trace=self._debug_trace,
            clarification_count=len(clarifications),
        )

        candidate = self._ensure_desired_outcome(
            requirement,
            clarifications,
            intent_decisions,
            structured_context,
            source_text,
            candidate,
        )
        return self._add_focused_questions(requirement, clarifications, active_questions, candidate)

    def _discard_unsuppliable_citations(
        self,
        parsed: RequirementAnalysisSchema,
        clarification_count: int,
    ) -> RequirementAnalysisSchema:
        """Drop citations when the request supplied nothing that could be cited."""
        if clarification_count or not parsed.evidence_citations:
            return parsed
        logger.warning(
            "%s model %s cited evidence although none was supplied; discarding citations.",
            self._provider_name,
            self._client.model,
        )
        self._debug_trace.record(
            "analysis.evidence_citations_discarded",
            reason="no evidence blocks or human answers were supplied",
            discarded_count=len(parsed.evidence_citations),
        )
        return parsed.model_copy(update={"evidence_citations": []})

    def _salvage_human_citations(
        self,
        parsed: RequirementAnalysisSchema,
        candidate: RequirementAnalysisCandidate,
        clarification_count: int,
    ) -> RequirementAnalysisSchema:
        """Drop unusable optional citations when only human answers can be cited."""
        salvaged, dropped = salvage_human_citations(parsed, candidate, clarification_count)
        if dropped:
            logger.warning(
                "%s model %s returned %d unusable human-answer citations; discarding them.",
                self._provider_name,
                self._client.model,
                dropped,
            )
            self._debug_trace.record(
                "analysis.human_citations_discarded",
                reason="citation subject or answer number did not match the analysis",
                discarded_count=dropped,
                kept_count=len(salvaged.evidence_citations),
            )
        return salvaged

    def _ensure_desired_outcome(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        intent_decisions: Sequence[IntentProposal],
        structured_context: str,
        source_text: str,
        candidate: RequirementAnalysisCandidate,
    ) -> RequirementAnalysisCandidate:
        has_confirmed_outcome = any(
            item.kind.value == "desired_outcome" and item.effective_statement is not None
            for item in intent_decisions
        )
        has_proposed_outcome = any(
            item["kind"].value == "desired_outcome" for item in candidate["intent_proposals"]
        )
        if requirement.desired_outcome is not None or has_confirmed_outcome or has_proposed_outcome:
            return candidate

        logger.info(
            "%s model %s omitted desired intent; running focused outcome review.",
            self._provider_name,
            self._client.model,
        )
        try:
            parsed = self._client.parse(
                system_prompt=DESIRED_OUTCOME_REVIEW_SYSTEM_PROMPT,
                user_prompt=build_desired_outcome_review_prompt(
                    requirement.title.value,
                    requirement.description.value,
                    structured_context,
                    [(item.kind.value, item.subject, item.answer) for item in clarifications],
                ),
                schema_type=DesiredOutcomeReviewSchema,
            )
            proposal, blocker = to_desired_outcome_review(parsed, source_text=source_text)
        except (StructuredOutputError, RequirementAnalysisGenerationError) as exc:
            raise RequirementAnalysisGenerationError(
                f"{self._provider_name} desired-outcome review failed: {exc}"
            ) from exc
        if proposal is not None:
            candidate["intent_proposals"].append(proposal)
        if blocker is not None:
            candidate["open_questions"].append(blocker)
            candidate.setdefault("new_uncertainties", []).append(
                {
                    "kind": ClarificationKind.OPEN_QUESTION,
                    "subject": blocker["question"],
                    "rationale": blocker["rationale"],
                }
            )
        return candidate

    def _recover_question_reconciliation(
        self,
        parsed: RequirementAnalysisSchema,
        user_prompt: str,
        active_questions: Sequence[ActiveQuestionContext],
        original_error: RequirementAnalysisGenerationError,
    ) -> RequirementAnalysisSchema:
        try:
            ai_questions = tuple(item for item in active_questions if item["source"].value == "ai")
            focused = self._client.parse(
                system_prompt=QUESTION_RECONCILIATION_RECOVERY_SYSTEM_PROMPT,
                user_prompt=build_question_reconciliation_recovery_prompt(
                    user_prompt, active_questions
                ),
                schema_type=IndexedQuestionReconciliationSchema,
            )
            received_numbers = [item.question_number for item in focused.active_question_reviews]
            expected_numbers = set(range(1, len(ai_questions) + 1))
            if (
                len(received_numbers) != len(ai_questions)
                or set(received_numbers) != expected_numbers
            ):
                raise RequirementAnalysisGenerationError(
                    f"{self._provider_name} did not review every numbered active AI question "
                    "exactly once."
                )
            reviews_by_number = {
                item.question_number: item for item in focused.active_question_reviews
            }
            stable_reviews = [
                ActiveQuestionReviewSchema(
                    question_id=question["question_id"],
                    action=reviews_by_number[number].action,
                    rationale=reviews_by_number[number].rationale,
                    replacement=reviews_by_number[number].replacement,
                )
                for number, question in enumerate(ai_questions, start=1)
            ]
            return parsed.model_copy(
                update={
                    "active_question_reviews": stable_reviews,
                    "new_uncertainties": focused.new_uncertainties,
                }
            )
        except (StructuredOutputError, RequirementAnalysisGenerationError) as exc:
            raise RequirementAnalysisGenerationError(
                f"{self._provider_name} question reconciliation remained unusable after focused "
                f"recovery. Initial validation: {original_error}"
            ) from exc

    def _repair_missing_uncertainty_rationales(
        self,
        parsed: RequirementAnalysisSchema,
        documents: Sequence[AnalysisDocumentContext],
        images: Sequence[tuple[str, bytes]],
    ) -> RequirementAnalysisSchema:
        missing = tuple(
            (index, item)
            for index, item in enumerate(parsed.new_uncertainties)
            if item.kind in (ClarificationKind.OPEN_QUESTION, ClarificationKind.AMBIGUITY)
            and (item.rationale is None or not item.rationale.strip())
        )
        if not missing:
            return parsed

        self._debug_trace.record(
            "analysis.uncertainty_rationale_repair_started",
            uncertainty_count=len(missing),
        )
        frozen = tuple((item.kind.value, item.subject) for _, item in missing)
        try:
            focused = self._client.parse(
                system_prompt=UNCERTAINTY_RATIONALE_RECOVERY_SYSTEM_PROMPT,
                user_prompt=build_uncertainty_rationale_recovery_prompt(frozen, documents),
                schema_type=IndexedUncertaintyRationaleRecoverySchema,
                images=images,
            )
            numbers = [item.uncertainty_number for item in focused.rationales]
            expected = set(range(1, len(missing) + 1))
            if len(numbers) != len(set(numbers)) or set(numbers) != expected:
                raise RequirementAnalysisGenerationError(
                    f"{self._provider_name} rationale repair did not cover every frozen "
                    "uncertainty "
                    "exactly once."
                )
            by_number = {
                item.uncertainty_number: item.rationale.strip() for item in focused.rationales
            }
            if any(not rationale for rationale in by_number.values()):
                raise RequirementAnalysisGenerationError(
                    f"{self._provider_name} rationale repair returned a blank rationale."
                )
            repaired_items = list(parsed.new_uncertainties)
            for number, (index, item) in enumerate(missing, start=1):
                repaired_items[index] = item.model_copy(update={"rationale": by_number[number]})
        except (StructuredOutputError, RequirementAnalysisGenerationError) as exc:
            self._debug_trace.record(
                "analysis.uncertainty_rationale_repair_invalid",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise RequirementAnalysisGenerationError(
                f"{self._provider_name} uncertainty rationale repair remained unusable after one "
                "focused attempt."
            ) from exc
        self._debug_trace.record(
            "analysis.uncertainty_rationale_repair_succeeded",
            uncertainty_count=len(missing),
        )
        return parsed.model_copy(update={"new_uncertainties": repaired_items})

    def _recover_evidence_citations(
        self,
        parsed: RequirementAnalysisSchema,
        candidate: RequirementAnalysisCandidate,
        documents: Sequence[AnalysisDocumentContext],
        images: Sequence[tuple[str, bytes]],
        original_error: RequirementAnalysisGenerationError,
        clarifications: Sequence[HumanClarification],
        business_context: str,
    ) -> RequirementAnalysisCandidate:
        outputs = analysis_evidence_subjects(candidate)
        blocks = tuple(
            block for document in documents for block in document.get("evidence_blocks", [])
        )
        try:
            schema = citation_recovery_schema(len(outputs), len(blocks), len(clarifications))
        except ValueError as exc:
            raise RequirementAnalysisGenerationError(
                "Citation recovery cannot represent the supplied packet."
            ) from exc
        answers = tuple((item.subject, item.answer) for item in clarifications)
        rationales = {
            **{
                ("open_question", q["question"]): q["rationale"]
                for q in candidate["open_questions"]
            },
            **{("ambiguity", q["statement"]): q["reason"] for q in candidate["ambiguities"]},
        }
        base_prompt = build_citation_recovery_prompt(
            outputs,
            documents,
            answers,
            business_context=business_context,
            uncertainty_rationales=rationales,
        )
        prompt = base_prompt
        started = time.monotonic()
        self._debug_trace.record(
            "analysis.citation_repair_started",
            output_count=len(outputs),
            evidence_block_count=len(blocks),
            initial_error=str(original_error),
        )
        for attempt in (1, 2):
            attempt_started = time.monotonic()
            try:
                focused = self._client.parse(
                    system_prompt=CITATION_RECOVERY_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    schema_type=schema,
                    images=images,
                )
                unsupported_numbers = sorted(
                    item.output_number for item in focused.decisions if not item.supported
                )
                if unsupported_numbers:
                    self._debug_trace.record(
                        "analysis.citation_repair_unsupported",
                        unsupported_output_numbers=unsupported_numbers,
                    )
                    raise StructuredResponseValidationError(
                        "The model reported unsupported analysis content.", unsupported=True
                    )
                # Revalidate clients/fakes that return a base schema instance.
                try:
                    focused = schema.model_validate(focused.model_dump(), strict=True)
                except ValidationError as exc:
                    raise response_validation_error(exc, focused.model_dump_json()) from exc
                decision_numbers = [item.output_number for item in focused.decisions]
                if len(decision_numbers) != len(set(decision_numbers)) or set(
                    decision_numbers
                ) != set(range(1, len(outputs) + 1)):
                    raise StructuredResponseValidationError(
                        "Return exactly one decision for every supplied output number; "
                        "do not repeat or omit output numbers."
                    )
                decisions = {item.output_number: item for item in focused.decisions}
                repaired_citations: list[AnalysisEvidenceCitationSchema] = []
                for number, (kind, subject) in enumerate(outputs, start=1):
                    block_numbers = decisions[number].block_numbers
                    answer_numbers = decisions[number].clarification_numbers
                    if (
                        (not block_numbers and not answer_numbers)
                        or len(block_numbers) != len(set(block_numbers))
                        or len(answer_numbers) != len(set(answer_numbers))
                    ):
                        raise StructuredResponseValidationError(
                            f"Output {number} requires unique supporting document block numbers "
                            f"within 1–{len(blocks)} or human answer numbers within "
                            f"1–{len(clarifications)}; at least one source is required."
                        )
                    repaired_citations.append(
                        AnalysisEvidenceCitationSchema(
                            kind=kind,
                            subject=subject,
                            block_ids=[blocks[index - 1]["block_id"] for index in block_numbers],
                            clarification_numbers=answer_numbers,
                        )
                    )
                repaired = parsed.model_copy(update={"evidence_citations": repaired_citations})
                result = attach_analysis_evidence(
                    repaired,
                    candidate,
                    documents=documents,
                    debug_trace=self._debug_trace,
                    clarification_count=len(clarifications),
                )
            except (
                StructuredOutputError,
                ModelTransportError,
                RequirementAnalysisGenerationError,
            ) as exc:
                validation = (
                    exc if isinstance(exc, StructuredResponseValidationError) else exc.__cause__
                )
                malformed = isinstance(validation, StructuredResponseValidationError)
                unsupported = (
                    isinstance(validation, StructuredResponseValidationError)
                    and validation.unsupported
                )
                category = (
                    "unsupported" if unsupported else "malformed" if malformed else "provider"
                )
                self._debug_trace.record(
                    "analysis.citation_repair_attempt_failed",
                    attempt=attempt,
                    validation_category=category,
                    duration_ms=(time.monotonic() - attempt_started) * 1000,
                )
                if malformed and not unsupported and attempt == 1:
                    prompt = base_prompt + (
                        "\nAPPLICATION VALIDATION FEEDBACK: "
                        + str(validation)
                        + f" There are {len(outputs)} outputs and {len(blocks)} evidence blocks."
                        + " Return one complete corrected mapping for the SAME frozen outputs. "
                        + "Do not rewrite, drop, guess support, or add analysis content.\n"
                    )
                    self._debug_trace.record(
                        "analysis.citation_repair_correction_started", attempt=2
                    )
                    continue
                self._debug_trace.record(
                    "analysis.citation_repair_invalid",
                    error_type=type(exc).__name__,
                    error=str(exc),
                    attempt_count=attempt,
                    validation_category=category,
                    duration_ms=(time.monotonic() - started) * 1000,
                )
                safe_error: BaseException
                if malformed:
                    safe_error = ModelTransportError("invalid_citations")
                    safe_error.__cause__ = exc
                else:
                    safe_error = exc
                raise RequirementAnalysisGenerationError(
                    f"{self._provider_name} citation repair remained unusable after "
                    f"{attempt} focused attempt(s). Analysis was not saved."
                ) from safe_error
            self._debug_trace.record(
                "analysis.citation_repair_succeeded",
                output_count=len(outputs),
                citation_count=len(repaired_citations),
                attempt_count=attempt,
                duration_ms=(time.monotonic() - started) * 1000,
            )
            return result
        raise AssertionError("Bounded citation recovery exhausted without returning or failing.")

    def _add_focused_questions(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        active_questions: Sequence[ActiveQuestionContext],
        candidate: RequirementAnalysisCandidate,
    ) -> RequirementAnalysisCandidate:
        unresolved = (
            candidate["assumptions"],
            candidate["open_questions"],
            candidate["ambiguities"],
            candidate["potential_dependencies"],
        )
        terms = vague_terms(requirement.description.value)
        if clarifications or active_questions or any(unresolved) or not terms:
            return candidate

        logger.info(
            "%s model %s found no uncertainty for vague terms; running focused review.",
            self._provider_name,
            self._client.model,
        )
        try:
            parsed = self._client.parse(
                system_prompt=CLARIFICATION_REVIEW_SYSTEM_PROMPT,
                user_prompt=build_clarification_review_prompt(
                    requirement.title.value,
                    requirement.description.value,
                    terms,
                ),
                schema_type=ClarificationReviewSchema,
            )
        except StructuredOutputError as exc:
            raise RequirementAnalysisGenerationError(
                f"{self._provider_name} clarification review failed: {exc}"
            ) from exc
        candidate["open_questions"] = to_clarification_questions(parsed)
        candidate["new_uncertainties"] = [
            {
                "kind": ClarificationKind.OPEN_QUESTION,
                "subject": item["question"],
                "rationale": item["rationale"],
            }
            for item in candidate["open_questions"]
        ]
        return candidate

    def _retry_complete_analysis(
        self,
        user_prompt: str,
        source_text: str,
        active_questions: Sequence[ActiveQuestionContext],
        documents: Sequence[AnalysisDocumentContext],
        intent_decisions: Sequence[IntentProposal],
        has_source_outcome: bool,
    ) -> RequirementAnalysisCandidate:
        try:
            parsed = self._client.parse(
                system_prompt=(
                    REQUIREMENT_ANALYSIS_SYSTEM_PROMPT + "\n" + COMPLETE_ANALYSIS_RETRY_INSTRUCTION
                ),
                user_prompt=user_prompt,
                schema_type=RequirementAnalysisSchema,
            )
        except StructuredOutputError as exc:
            raise RequirementAnalysisGenerationError(
                f"{self._provider_name} analysis retry failed: {exc}"
            ) from exc

        try:
            parsed = normalize_analysis_intent(
                parsed,
                intent_decisions,
                has_source_outcome=has_source_outcome,
                debug_trace=self._debug_trace,
            )
            parsed = self._discard_unsuppliable_citations(parsed, 0)
            return to_analysis_candidate(
                parsed,
                model=self._client.model,
                prompt_version=PROMPT_VERSION,
                source_text=source_text,
                active_questions=active_questions,
                documents=documents,
                debug_trace=self._debug_trace,
            )
        except RequirementAnalysisGenerationError as exc:
            raise RequirementAnalysisGenerationError(
                f"{self._provider_name} returned no usable analysis after one completeness retry."
            ) from exc


class LocalRequirementAnalyzer(StructuredRequirementAnalyzerAdapter):
    """Analyze requirements through an unauthenticated local model server."""

    def __init__(
        self,
        *,
        base_url: str,
        http_client: httpx.Client,
        model: str,
        timeout_seconds: float,
        reasoning_effort: str | None,
        vision_enabled: bool,
        context_window_tokens: int = 8192,
        max_output_tokens: int = 4096,
        debug_trace: DebugTrace | None = None,
    ) -> None:
        resolved_trace = debug_trace if debug_trace is not None else NullDebugTrace()
        super().__init__(
            client=LocalStructuredOutputClient(
                base_url=base_url,
                http_client=http_client,
                model=model,
                timeout_seconds=timeout_seconds,
                reasoning_effort=reasoning_effort,
                context_window_tokens=context_window_tokens,
                max_output_tokens=max_output_tokens,
                debug_trace=resolved_trace,
            ),
            provider_name="Local LLM",
            vision_enabled=vision_enabled,
            vision_error=(
                "The selected BRD contains meaningful images, but local vision is disabled. "
                "Use a vision-capable LOCAL_LLM_MODEL and set LOCAL_LLM_VISION_ENABLED=true."
            ),
            debug_trace=resolved_trace,
        )
