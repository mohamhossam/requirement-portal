"""Fake requirement analyzer for deterministic testing."""

from collections.abc import Sequence

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
    RequirementAnalyzerPort,
    UncertaintyCandidate,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_mapping import (
    analysis_evidence_key,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSource,
    HumanClarification,
    IntentProposal,
    IntentProposalKind,
    QuestionChangeAction,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement


class FakeRequirementAnalyzer(RequirementAnalyzerPort):
    """Deterministic analyzer that returns canned responses for testing."""

    def __init__(self) -> None:
        self.model = "fake-analysis"
        self.prompt_version = "fake-analysis-v4"
        self.candidate = RequirementAnalysisCandidate(
            known_facts=["This is a known fact."],
            constraints=["This is a constraint."],
            business_rules=["This is a business rule."],
            assumptions=["This is an assumption."],
            open_questions=[
                OpenQuestionCandidate(
                    question="Is this a question?", rationale="Because we need to know."
                )
            ],
            ambiguities=[
                AmbiguityCandidate(
                    statement="This is ambiguous.", reason="It could mean multiple things."
                )
            ],
            potential_dependencies=["This is a dependency."],
            intent_proposals=[],
            model=self.model,
            prompt_version=self.prompt_version,
        )
        self.should_fail = False
        self.received_clarifications: Sequence[HumanClarification] = ()
        self.received_documents: Sequence[AnalysisDocumentContext] = ()
        self.received_active_questions: Sequence[ActiveQuestionContext] = ()

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        self.received_clarifications = clarifications
        self.received_documents = documents
        self.received_active_questions = active_questions
        if self.should_fail:
            raise RequirementAnalysisGenerationError("Fake generation error")
        resolved = {item.subject.strip() for item in clarifications}
        proposals: list[IntentProposalCandidate] = [
            IntentProposalCandidate(**item) for item in self.candidate["intent_proposals"]
        ]
        if (
            requirement.desired_outcome is None
            and not any(item["kind"] is IntentProposalKind.DESIRED_OUTCOME for item in proposals)
            and not any(
                item.kind is IntentProposalKind.DESIRED_OUTCOME
                and item.effective_statement is not None
                for item in intent_decisions
            )
        ):
            proposals.insert(
                0,
                {
                    "kind": IntentProposalKind.DESIRED_OUTCOME,
                    "statement": "Customers achieve the requested business result.",
                    "rationale": (
                        "This candidate translates the submitted business need "
                        "into an observable result."
                    ),
                    "success_measures": ["The intended customer result can be observed."],
                },
            )
        current_uncertainties = _candidate_uncertainties(self.candidate, resolved)
        current_by_key = {
            (item["kind"], item["subject"].casefold()): item for item in current_uncertainties
        }
        reviews: list[QuestionReviewCandidate] = []
        matched_keys: set[tuple[ClarificationKind, str]] = set()
        protected_subjects = {
            item["subject"].casefold()
            for item in active_questions
            if item["source"] is ClarificationSource.HUMAN
        }
        for item in active_questions:
            if item["source"] is ClarificationSource.HUMAN:
                continue
            key = item["kind"], item["subject"].casefold()
            if key in current_by_key:
                matched_keys.add(key)
                reviews.append(
                    QuestionReviewCandidate(
                        question_id=item["question_id"],
                        action=QuestionChangeAction.RETAINED,
                        rationale="The uncertainty remains unresolved in the confirmed context.",
                        replacement=None,
                    )
                )
            else:
                reviews.append(
                    QuestionReviewCandidate(
                        question_id=item["question_id"],
                        action=QuestionChangeAction.RETIRED,
                        rationale="Confirmed context means this uncertainty is no longer required.",
                        replacement=None,
                    )
                )
        new_uncertainties = [
            item
            for item in current_uncertainties
            if (item["kind"], item["subject"].casefold()) not in matched_keys
            and item["subject"].casefold() not in protected_subjects
        ]
        return RequirementAnalysisCandidate(
            known_facts=list(self.candidate["known_facts"]),
            constraints=list(self.candidate["constraints"]),
            business_rules=list(self.candidate["business_rules"]),
            assumptions=[item for item in self.candidate["assumptions"] if item not in resolved],
            open_questions=[
                item
                for item in self.candidate["open_questions"]
                if item["question"] not in resolved
            ],
            ambiguities=[
                item for item in self.candidate["ambiguities"] if item["statement"] not in resolved
            ],
            potential_dependencies=[
                item for item in self.candidate["potential_dependencies"] if item not in resolved
            ],
            intent_proposals=proposals,
            model=self.candidate["model"],
            prompt_version=self.candidate["prompt_version"],
            question_reviews=reviews,
            new_uncertainties=new_uncertainties,
        )

    def analyze_evidence(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext],
        intent_decisions: Sequence[IntentProposal],
        active_questions: Sequence[ActiveQuestionContext],
    ) -> RequirementAnalysisCandidate:
        candidate = self.analyze(
            requirement, clarifications, documents, intent_decisions, active_questions
        )
        first_document = next((item for item in documents if item.get("evidence_blocks")), None)
        if first_document is None:
            return candidate
        first_block = first_document["evidence_blocks"][0]
        reference = AnalysisEvidenceReferenceCandidate(
            document_id=first_document["document_id"],
            version_id=first_document["version_id"],
            checksum_sha256=first_document["checksum_sha256"],
            block_id=first_block["block_id"],
            label=" → ".join((*first_block["section_path"], first_block["label"])),
        )
        evidence: dict[str, list[AnalysisEvidenceReferenceCandidate]] = {}
        for kind, subject in _candidate_items(candidate):
            evidence[analysis_evidence_key(kind, subject)] = [reference]
        candidate["evidence_references"] = evidence
        return candidate


def _candidate_uncertainties(
    candidate: RequirementAnalysisCandidate,
    resolved: set[str],
) -> list[UncertaintyCandidate]:
    return [
        *(
            UncertaintyCandidate(
                kind=ClarificationKind.ASSUMPTION,
                subject=item,
                rationale=None,
            )
            for item in candidate["assumptions"]
            if item not in resolved
        ),
        *(
            UncertaintyCandidate(
                kind=ClarificationKind.OPEN_QUESTION,
                subject=item["question"],
                rationale=item["rationale"],
            )
            for item in candidate["open_questions"]
            if item["question"] not in resolved
        ),
        *(
            UncertaintyCandidate(
                kind=ClarificationKind.AMBIGUITY,
                subject=item["statement"],
                rationale=item["reason"],
            )
            for item in candidate["ambiguities"]
            if item["statement"] not in resolved
        ),
        *(
            UncertaintyCandidate(
                kind=ClarificationKind.POTENTIAL_DEPENDENCY,
                subject=item,
                rationale=None,
            )
            for item in candidate["potential_dependencies"]
            if item not in resolved
        ),
    ]


def _candidate_items(candidate: RequirementAnalysisCandidate) -> list[tuple[str, str]]:
    return [
        *(("known_fact", item) for item in candidate["known_facts"]),
        *(("constraint", item) for item in candidate["constraints"]),
        *(("business_rule", item) for item in candidate["business_rules"]),
        *(("assumption", item) for item in candidate["assumptions"]),
        *(("open_question", item["question"]) for item in candidate["open_questions"]),
        *(("ambiguity", item["statement"]) for item in candidate["ambiguities"]),
        *(("potential_dependency", item) for item in candidate["potential_dependencies"]),
        *(("intent_proposal", item["statement"]) for item in candidate["intent_proposals"]),
    ]
