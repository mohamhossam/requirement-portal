"""Map schema-valid analysis output onto provider-independent analysis candidates.

Structured-output schemas guarantee shape, not usable content. Every analysis adapter applies
the same normalisation here before constructing domain value objects. Split from
`candidate_mappers.py` in ADR-0103 PR 11b.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from smb_kernel.diagnostics import DebugTrace

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    AmbiguityCandidate,
    AnalysisDocumentContext,
    AnalysisEvidenceReferenceCandidate,
    IntentProposalCandidate,
    OpenQuestionCandidate,
    QuestionReviewCandidate,
    RequirementAnalysisCandidate,
    UncertaintyCandidate,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSource,
    IntentProposal,
    IntentProposalKind,
    QuestionChangeAction,
    is_additional_intent_proposal,
)
from smb_requirement_agent.analysis.infrastructure.llm.response_sanitizer import (
    clean_pairs,
    clean_statements,
    require_any_content,
)
from smb_requirement_agent.analysis.infrastructure.llm.schemas.analysis_schema import (
    AnalysisEvidenceCitationSchema,
    AnalysisEvidenceKind,
    ClarificationReviewSchema,
    DesiredOutcomeProposalSchema,
    DesiredOutcomeReviewSchema,
    RequirementAnalysisSchema,
    UncertaintySchema,
)


def normalize_analysis_intent(
    parsed: RequirementAnalysisSchema,
    intent_decisions: Sequence[IntentProposal],
    *,
    has_source_outcome: bool,
    debug_trace: DebugTrace | None = None,
) -> RequirementAnalysisSchema:
    """Exclude governed intent echoes before validating genuinely generated content."""
    decided = tuple(intent_decisions)
    outcome = parsed.desired_outcome_proposal
    rules = parsed.business_rule_proposals
    constraints = parsed.constraint_proposals
    removed: set[str] = set()
    if isinstance(outcome, DesiredOutcomeProposalSchema) and not is_additional_intent_proposal(
        IntentProposalKind.DESIRED_OUTCOME,
        outcome.statement.strip(),
        decided,
        has_source_outcome=has_source_outcome,
    ):
        removed.add(outcome.statement.strip())
        outcome = None
    for kind, items in (
        (IntentProposalKind.BUSINESS_RULE, rules),
        (IntentProposalKind.CONSTRAINT, constraints),
    ):
        removed.update(
            p.statement.strip()
            for p in items
            if not is_additional_intent_proposal(
                kind, p.statement.strip(), decided, has_source_outcome=has_source_outcome
            )
        )
    kept_rules = [
        p
        for p in rules
        if is_additional_intent_proposal(
            IntentProposalKind.BUSINESS_RULE,
            p.statement.strip(),
            decided,
            has_source_outcome=has_source_outcome,
        )
    ]
    kept_constraints = [
        p
        for p in constraints
        if is_additional_intent_proposal(
            IntentProposalKind.CONSTRAINT,
            p.statement.strip(),
            decided,
            has_source_outcome=has_source_outcome,
        )
    ]
    if not removed:
        return parsed
    remaining = {
        " ".join(p.statement.casefold().split())
        for p in (*kept_rules, *kept_constraints, *((outcome,) if outcome is not None else ()))
    }
    excluded = {" ".join(s.casefold().split()) for s in removed} - remaining
    citations = [
        c
        for c in parsed.evidence_citations
        if c.kind != "intent_proposal" or " ".join(c.subject.casefold().split()) not in excluded
    ]
    if debug_trace is not None:
        debug_trace.record("analysis.governed_intent_excluded", proposal_count=len(removed))
    return parsed.model_copy(
        update={
            "desired_outcome_proposal": outcome,
            "business_rule_proposals": kept_rules,
            "constraint_proposals": kept_constraints,
            "evidence_citations": citations,
        }
    )


def to_analysis_candidate(
    parsed: RequirementAnalysisSchema,
    *,
    model: str,
    prompt_version: str,
    source_text: str = "",
    active_questions: Iterable[ActiveQuestionContext] = (),
    documents: Iterable[AnalysisDocumentContext] = (),
    debug_trace: DebugTrace | None = None,
    clarification_count: int = 0,
) -> RequirementAnalysisCandidate:
    """Clean and map a typed analysis response."""
    result = to_analysis_content_candidate(
        parsed,
        model=model,
        prompt_version=prompt_version,
        source_text=source_text,
        active_questions=active_questions,
        debug_trace=debug_trace,
    )
    return attach_analysis_evidence(
        parsed,
        result,
        documents=documents,
        debug_trace=debug_trace,
        clarification_count=clarification_count,
    )


def to_analysis_content_candidate(
    parsed: RequirementAnalysisSchema,
    *,
    model: str,
    prompt_version: str,
    source_text: str = "",
    active_questions: Iterable[ActiveQuestionContext] = (),
    debug_trace: DebugTrace | None = None,
) -> RequirementAnalysisCandidate:
    """Clean analysis content without interpreting provider evidence citations."""
    known_facts = clean_statements(parsed.known_facts)
    constraints = clean_statements(parsed.constraints)
    business_rules = clean_statements(parsed.business_rules)
    uncertainties, question_reviews, new_uncertainties = _reconcile_uncertainties(
        parsed, tuple(active_questions)
    )
    assumptions = [
        item["subject"] for item in uncertainties if item["kind"] is ClarificationKind.ASSUMPTION
    ]
    open_questions = [
        (item["subject"], item["rationale"] or "")
        for item in uncertainties
        if item["kind"] is ClarificationKind.OPEN_QUESTION
    ]
    ambiguities = [
        (item["subject"], item["rationale"] or "")
        for item in uncertainties
        if item["kind"] is ClarificationKind.AMBIGUITY
    ]
    potential_dependencies = [
        item["subject"]
        for item in uncertainties
        if item["kind"] is ClarificationKind.POTENTIAL_DEPENDENCY
    ]
    proposals: list[IntentProposalCandidate] = []
    outcome = parsed.desired_outcome_proposal
    if isinstance(outcome, DesiredOutcomeProposalSchema):
        statement, rationale = outcome.statement.strip(), outcome.rationale.strip()
        if statement and rationale:
            proposals.append(
                IntentProposalCandidate(
                    kind=IntentProposalKind.DESIRED_OUTCOME,
                    statement=statement,
                    rationale=rationale,
                    success_measures=clean_statements(outcome.success_measures),
                )
            )
    proposals.extend(
        _intent_statement_proposals(
            IntentProposalKind.BUSINESS_RULE,
            ((item.statement, item.rationale) for item in parsed.business_rule_proposals),
        )
    )
    proposals.extend(
        _intent_statement_proposals(
            IntentProposalKind.CONSTRAINT,
            ((item.statement, item.rationale) for item in parsed.constraint_proposals),
        )
    )
    proposals = _deduplicate_proposals(proposals, business_rules, constraints)
    _reject_invented_numeric_targets(proposals, source_text)

    require_any_content(
        known_facts,
        constraints,
        business_rules,
        assumptions,
        open_questions,
        ambiguities,
        potential_dependencies,
        [item["statement"] for item in proposals],
    )

    result = RequirementAnalysisCandidate(
        known_facts=known_facts,
        constraints=constraints,
        business_rules=business_rules,
        assumptions=assumptions,
        open_questions=[
            OpenQuestionCandidate(question=question, rationale=rationale)
            for question, rationale in open_questions
        ],
        ambiguities=[
            AmbiguityCandidate(statement=statement, reason=reason)
            for statement, reason in ambiguities
        ],
        potential_dependencies=potential_dependencies,
        intent_proposals=proposals,
        model=model,
        prompt_version=prompt_version,
        question_reviews=question_reviews,
        new_uncertainties=new_uncertainties,
    )
    if debug_trace is not None:
        debug_trace.record("analysis_mapper.normalized_candidate", candidate=result)
    return result


def attach_analysis_evidence(
    parsed: RequirementAnalysisSchema,
    candidate: RequirementAnalysisCandidate,
    *,
    documents: Iterable[AnalysisDocumentContext] = (),
    debug_trace: DebugTrace | None = None,
    clarification_count: int = 0,
) -> RequirementAnalysisCandidate:
    """Validate citations and attach provider-independent evidence references."""
    evidence = _validated_evidence(
        parsed, candidate, tuple(documents), debug_trace, clarification_count
    )
    if evidence:
        candidate["evidence_references"] = evidence
    return candidate


def salvage_human_citations(
    parsed: RequirementAnalysisSchema,
    candidate: RequirementAnalysisCandidate,
    clarification_count: int,
) -> tuple[RequirementAnalysisSchema, int]:
    """Keep only well-formed human-answer citations when no document blocks exist.

    Without documents a citation can only point at a human answer, and citing is optional.
    A citation naming a paraphrased, retired, or duplicate subject, or an unknown answer
    number, is dropped rather than failing the round; stray block IDs are removed.
    """
    expected = _candidate_evidence_keys(candidate)
    kept: list[AnalysisEvidenceCitationSchema] = []
    seen: set[str] = set()
    for citation in parsed.evidence_citations:
        key = f"{citation.kind.strip()}:{' '.join(citation.subject.casefold().split())}"
        numbers = citation.clarification_numbers
        if (
            key not in expected
            or key in seen
            or not numbers
            or len(numbers) != len(set(numbers))
            or any(number < 1 or number > clarification_count for number in numbers)
        ):
            continue
        seen.add(key)
        kept.append(
            citation.model_copy(update={"block_ids": []}) if citation.block_ids else citation
        )
    dropped = len(parsed.evidence_citations) - len(kept)
    return parsed.model_copy(update={"evidence_citations": kept}), dropped


def _validated_evidence(
    parsed: RequirementAnalysisSchema,
    candidate: RequirementAnalysisCandidate,
    documents: tuple[AnalysisDocumentContext, ...],
    debug_trace: DebugTrace | None,
    clarification_count: int,
) -> dict[str, list[AnalysisEvidenceReferenceCandidate]]:
    blocks: dict[str, AnalysisEvidenceReferenceCandidate] = {}
    structured = False
    for document in documents:
        for block in document.get("evidence_blocks", []):
            structured = True
            block_id = block["block_id"].strip()
            if not block_id or block_id in blocks:
                raise RequirementAnalysisGenerationError(
                    "Evidence context contains blank or duplicate block IDs."
                )
            blocks[block_id] = AnalysisEvidenceReferenceCandidate(
                document_id=document["document_id"],
                version_id=document["version_id"],
                checksum_sha256=document["checksum_sha256"],
                block_id=block_id,
                label=" → ".join((*block["section_path"], block["label"])),
            )
    raw_citations = parsed.evidence_citations
    citations_input = raw_citations if isinstance(raw_citations, list) else []
    if not structured:
        if citations_input and not clarification_count:
            raise RequirementAnalysisGenerationError(
                "Provider cited evidence blocks that were not supplied."
            )
        if not citations_input:
            return {}

    expected = _candidate_evidence_keys(candidate)
    returned = {
        f"{citation.kind.strip()}:{' '.join(citation.subject.strip().casefold().split())}"
        for citation in citations_input
        if citation.kind.strip() and citation.subject.strip()
    }
    if debug_trace is not None:
        debug_trace.record(
            "analysis_mapper.citation_comparison",
            expected_keys=sorted(expected),
            returned_keys=sorted(returned),
            missing_keys=sorted(expected - returned),
            unexpected_keys=sorted(returned - expected),
            evidence_block_ids=sorted(blocks),
        )
    citations: dict[str, list[AnalysisEvidenceReferenceCandidate]] = {}
    clarification_references: dict[str, list[int]] = {}
    for citation in citations_input:
        kind = citation.kind.strip()
        subject = citation.subject.strip()
        key = f"{kind}:{' '.join(subject.casefold().split())}"
        if not kind or not subject or key not in expected:
            raise RequirementAnalysisGenerationError(
                "Provider returned a blank, unknown, or stale evidence citation."
            )
        if key in citations:
            raise RequirementAnalysisGenerationError(
                "Provider returned duplicate evidence citation records."
            )
        seen: set[str] = set()
        references: list[AnalysisEvidenceReferenceCandidate] = []
        for raw_block_id in citation.block_ids:
            block_id = raw_block_id.strip()
            if not block_id or block_id in seen or block_id not in blocks:
                raise RequirementAnalysisGenerationError(
                    "Provider returned blank, duplicate, or out-of-packet evidence block IDs."
                )
            seen.add(block_id)
            references.append(blocks[block_id])
        numbers = citation.clarification_numbers
        if len(numbers) != len(set(numbers)) or any(
            number < 1 or number > clarification_count for number in numbers
        ):
            raise RequirementAnalysisGenerationError(
                "Provider returned duplicate or unknown human clarification references."
            )
        if not references and not numbers:
            raise RequirementAnalysisGenerationError(
                "Provider returned an analysis item without document or human support."
            )
        if numbers:
            clarification_references[key] = list(numbers)
        citations[key] = references
    if structured and set(citations) != expected:
        raise RequirementAnalysisGenerationError(
            "Provider did not cite every generated analysis item."
        )
    if clarification_references:
        candidate["clarification_references"] = clarification_references
    return citations


def analysis_evidence_subjects(
    candidate: RequirementAnalysisCandidate,
) -> tuple[tuple[AnalysisEvidenceKind, str], ...]:
    """Return every output that requires evidence in stable prompt order."""
    values: list[tuple[AnalysisEvidenceKind, str]] = [
        *(("known_fact", item) for item in candidate["known_facts"]),
        *(("constraint", item) for item in candidate["constraints"]),
        *(("business_rule", item) for item in candidate["business_rules"]),
        *(("assumption", item) for item in candidate["assumptions"]),
        *(("open_question", item["question"]) for item in candidate["open_questions"]),
        *(("ambiguity", item["statement"]) for item in candidate["ambiguities"]),
        *(("potential_dependency", item) for item in candidate["potential_dependencies"]),
        *(("intent_proposal", item["statement"]) for item in candidate["intent_proposals"]),
    ]
    return tuple(values)


def _candidate_evidence_keys(candidate: RequirementAnalysisCandidate) -> set[str]:
    return {
        f"{kind}:{' '.join(subject.casefold().split())}"
        for kind, subject in analysis_evidence_subjects(candidate)
    }


def _reconcile_uncertainties(
    parsed: RequirementAnalysisSchema,
    active_questions: tuple[ActiveQuestionContext, ...],
) -> tuple[
    list[UncertaintyCandidate],
    list[QuestionReviewCandidate],
    list[UncertaintyCandidate],
]:
    active_by_id = {item["question_id"]: item for item in active_questions}
    if len(active_by_id) != len(active_questions):
        raise RequirementAnalysisGenerationError("Active question context contains duplicate IDs.")
    ai_ids = {
        item["question_id"] for item in active_questions if item["source"] is ClarificationSource.AI
    }
    protected_subjects = {
        item["subject"].strip().casefold()
        for item in active_questions
        if item["source"] is ClarificationSource.HUMAN
    }
    current: list[UncertaintyCandidate] = []
    reviews: list[QuestionReviewCandidate] = []
    reviewed_ids: set[str] = set()
    actions = {
        "retain": QuestionChangeAction.RETAINED,
        "retire": QuestionChangeAction.RETIRED,
        "replace": QuestionChangeAction.REPLACED,
    }
    for review in parsed.active_question_reviews:
        question_id = review.question_id.strip()
        rationale = review.rationale.strip()
        if not question_id or not rationale:
            raise RequirementAnalysisGenerationError(
                "Provider returned a blank question review ID or rationale."
            )
        if question_id in reviewed_ids:
            raise RequirementAnalysisGenerationError(
                "Provider reviewed the same active question more than once."
            )
        context = active_by_id.get(question_id)
        if context is None or question_id not in ai_ids:
            raise RequirementAnalysisGenerationError(
                "Provider reviewed an unknown or protected human question."
            )
        reviewed_ids.add(question_id)
        action = actions[review.action]
        replacement = (
            _clean_uncertainty(review.replacement) if review.replacement is not None else None
        )
        if action is QuestionChangeAction.RETAINED:
            if replacement is not None:
                raise RequirementAnalysisGenerationError(
                    "A retained question cannot include replacement content."
                )
            current.append(
                UncertaintyCandidate(
                    kind=context["kind"],
                    subject=context["subject"].strip(),
                    rationale=(context["rationale"] or "").strip() or None,
                )
            )
        elif action is QuestionChangeAction.RETIRED:
            if replacement is not None:
                raise RequirementAnalysisGenerationError(
                    "A retired question cannot include replacement content."
                )
        else:
            if replacement is None:
                raise RequirementAnalysisGenerationError(
                    "A replaced question requires replacement content."
                )
            old_key = context["kind"], context["subject"].strip().casefold()
            replacement_key = replacement["kind"], replacement["subject"].casefold()
            if old_key == replacement_key:
                raise RequirementAnalysisGenerationError(
                    "An unchanged question must be retained rather than replaced."
                )
            current.append(replacement)
        reviews.append(
            QuestionReviewCandidate(
                question_id=question_id,
                action=action,
                rationale=rationale,
                replacement=replacement,
            )
        )

    if reviewed_ids != ai_ids:
        raise RequirementAnalysisGenerationError(
            "Provider did not review every active AI clarification question."
        )

    new_uncertainties = _deduplicate_new_uncertainties(parsed.new_uncertainties)
    current.extend(new_uncertainties)
    seen_subjects: set[str] = set()
    for item in current:
        subject_key = item["subject"].casefold()
        if subject_key in protected_subjects:
            raise RequirementAnalysisGenerationError(
                "Provider duplicated a protected human-authored clarification question."
            )
        if subject_key in seen_subjects:
            raise RequirementAnalysisGenerationError(
                "Provider returned duplicate current uncertainties."
            )
        seen_subjects.add(subject_key)
    if len(current) > 12:
        raise RequirementAnalysisGenerationError(
            "Provider returned more than 12 current AI uncertainties."
        )
    return current, reviews, new_uncertainties


def _clean_uncertainty(value: UncertaintySchema) -> UncertaintyCandidate:
    kind = value.kind
    subject = str(value.subject).strip()
    raw_rationale = value.rationale
    rationale = str(raw_rationale).strip() if raw_rationale is not None else None
    if not subject:
        raise RequirementAnalysisGenerationError("Provider returned a blank uncertainty subject.")
    if kind in (ClarificationKind.OPEN_QUESTION, ClarificationKind.AMBIGUITY) and not rationale:
        raise RequirementAnalysisGenerationError(
            "Provider returned a question or ambiguity without a rationale."
        )
    return UncertaintyCandidate(kind=kind, subject=subject, rationale=rationale or None)


def _deduplicate_new_uncertainties(
    values: Iterable[UncertaintySchema],
) -> list[UncertaintyCandidate]:
    """Collapse repeated provider items without hiding classification conflicts."""
    result: list[UncertaintyCandidate] = []
    positions: dict[str, int] = {}
    for value in values:
        candidate = _clean_uncertainty(value)
        subject_key = candidate["subject"].casefold()
        position = positions.get(subject_key)
        if position is None:
            positions[subject_key] = len(result)
            result.append(candidate)
            continue

        existing = result[position]
        if existing["kind"] is not candidate["kind"]:
            raise RequirementAnalysisGenerationError(
                "Provider returned the same uncertainty with conflicting classifications."
            )
        existing_rationale = existing["rationale"] or ""
        candidate_rationale = candidate["rationale"] or ""
        if len(candidate_rationale) > len(existing_rationale):
            result[position] = UncertaintyCandidate(
                kind=existing["kind"],
                subject=existing["subject"],
                rationale=candidate["rationale"],
            )
    return result


def _intent_statement_proposals(
    kind: IntentProposalKind, values: Iterable[tuple[str, str]]
) -> list[IntentProposalCandidate]:
    pairs = clean_pairs(values)
    return [
        IntentProposalCandidate(
            kind=kind,
            statement=statement,
            rationale=rationale,
            success_measures=[],
        )
        for statement, rationale in pairs
    ]


def _deduplicate_proposals(
    proposals: list[IntentProposalCandidate],
    business_rules: list[str],
    constraints: list[str],
) -> list[IntentProposalCandidate]:
    source = {(IntentProposalKind.BUSINESS_RULE, item.casefold()) for item in business_rules} | {
        (IntentProposalKind.CONSTRAINT, item.casefold()) for item in constraints
    }
    seen: set[tuple[IntentProposalKind, str]] = set()
    result: list[IntentProposalCandidate] = []
    for proposal in proposals:
        key = proposal["kind"], proposal["statement"].casefold()
        if key in source or key in seen:
            continue
        seen.add(key)
        result.append(proposal)
    return result


_NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?%?")


def _reject_invented_numeric_targets(
    proposals: list[IntentProposalCandidate], source_text: str
) -> None:
    supported = set(_NUMBER_PATTERN.findall(source_text))
    for proposal in proposals:
        content = " ".join(
            (proposal["statement"], proposal["rationale"], *proposal["success_measures"])
        )
        invented = set(_NUMBER_PATTERN.findall(content)) - supported
        if invented:
            raise RequirementAnalysisGenerationError(
                "Provider invented a numeric target in an AI intent proposal."
            )


def to_desired_outcome_review(
    parsed: DesiredOutcomeReviewSchema,
    *,
    source_text: str,
) -> tuple[IntentProposalCandidate | None, OpenQuestionCandidate | None]:
    """Normalize exactly one focused outcome proposal or blocker question."""
    if parsed.can_infer:
        statement = parsed.statement.strip()
        rationale = parsed.rationale.strip()
        if not statement or not rationale:
            raise RequirementAnalysisGenerationError(
                "Provider returned an incomplete desired-outcome proposal."
            )
        proposal = IntentProposalCandidate(
            kind=IntentProposalKind.DESIRED_OUTCOME,
            statement=statement,
            rationale=rationale,
            success_measures=clean_statements(parsed.success_measures),
        )
        _reject_invented_numeric_targets([proposal], source_text)
        return proposal, None

    question = parsed.blocker_question.strip()
    rationale = parsed.blocker_rationale.strip()
    if not question or not rationale:
        raise RequirementAnalysisGenerationError(
            "Provider returned neither a desired outcome nor an outcome blocker question."
        )
    return None, OpenQuestionCandidate(question=question, rationale=rationale)


def to_clarification_questions(
    parsed: ClarificationReviewSchema,
) -> list[OpenQuestionCandidate]:
    """Clean a focused clarification review before merging it into an analysis."""
    questions = clean_pairs((item.question, item.rationale) for item in parsed.open_questions)
    if not questions:
        raise RequirementAnalysisGenerationError(
            "Provider returned no usable questions from the clarification review."
        )
    return [
        OpenQuestionCandidate(question=question, rationale=rationale)
        for question, rationale in questions
    ]
