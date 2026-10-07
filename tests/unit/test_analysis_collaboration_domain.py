"""Domain rules for Slice 8B clarification questions and analysis rounds."""

from datetime import UTC, datetime

import pytest

from smb_requirement_agent.domain.analysis.entities import (
    AnalysisQuestionChange,
    AnalysisRound,
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.errors import (
    ClarificationVersionConflictError,
    InvalidClarificationTransitionError,
)
from smb_requirement_agent.domain.analysis.value_objects import (
    AnalysisId,
    ClarificationKind,
    ClarificationSeverity,
    ClarificationSource,
    ClarificationStatus,
    IntentProposal,
    IntentProposalId,
    IntentProposalKind,
    IntentProposalStatus,
    KnownFact,
    QuestionChangeAction,
    QuestionId,
)
from smb_requirement_agent.infrastructure.persistence.analysis_payloads import (
    analysis_from_payload,
    analysis_round_from_payload,
    analysis_round_to_payload,
    clarification_question_from_payload,
    clarification_question_to_payload,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import RequirementVersion
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
OWNER = ActorProfile(ActorId("owner"), "Owner", "owner@example.test")
REVIEWER = ActorProfile(ActorId("reviewer"), "Reviewer", "reviewer@example.test")


def question() -> ClarificationQuestion:
    return ClarificationQuestion(
        QuestionId("question-1"),
        RequirementId("requirement-1"),
        AnalysisId("analysis-1"),
        ClarificationKind.OPEN_QUESTION,
        "Who owns fallout?",
        "Ownership is missing.",
        ClarificationSeverity.MEDIUM,
        True,
        ClarificationSource.AI,
    )


def test_draft_assignment_resolution_and_optimistic_versions() -> None:
    assigned = question().assign(REVIEWER, OWNER, NOW, 1)
    assert assigned.version == 2
    assert assigned.assignment_history[0].changed_by == OWNER.snapshot()

    drafted = assigned.save_draft("Partial", REVIEWER, NOW, 2)
    assert drafted.status is ClarificationStatus.IN_PROGRESS
    assert drafted.draft_updated_by == REVIEWER.snapshot()

    cleared = drafted.save_draft(" ", REVIEWER, NOW, 3)
    assert cleared.status is ClarificationStatus.OPEN
    assert cleared.draft_answer is None
    with pytest.raises(ClarificationVersionConflictError):
        cleared.classify(ClarificationSeverity.LOW, False, OWNER, NOW, 3)

    resolved = cleared.resolve("Customer Operations", REVIEWER, NOW, 4)
    assert resolved.status is ClarificationStatus.RESOLVED
    assert resolved.answered_by == REVIEWER.snapshot()
    with pytest.raises(InvalidClarificationTransitionError):
        resolved.assign(None, OWNER, NOW, resolved.version)


def test_identified_round_carries_provenance_source_version_and_question_order() -> None:
    proposal = IntentProposal(
        IntentProposalId("proposal-1"),
        IntentProposalKind.DESIRED_OUTCOME,
        "Customers complete the journey.",
        "The need describes journey completion.",
    ).decide(IntentProposalStatus.ACCEPTED, OWNER.snapshot(), NOW, 1)
    analysis = RequirementAnalysis(
        RequirementId("requirement-1"),
        (KnownFact("Fact"),),
        (),
        (),
        (),
        (),
        (),
        (),
        id=AnalysisId("analysis-1"),
        round_number=2,
        provenance=Provenance(NOW, "provider-model", "analysis-v2"),
        source_requirement_version=RequirementVersion(4),
        intent_proposals=(proposal,),
        source_desired_outcome=None,
    )
    round_ = AnalysisRound(
        analysis,
        (QuestionId("question-2"), QuestionId("question-1")),
        (
            AnalysisQuestionChange(
                QuestionChangeAction.REPLACED,
                QuestionId("question-1"),
                "The wording needed to change.",
                QuestionId("question-2"),
            ),
        ),
    )

    assert round_.number == 2
    assert round_.analysis.provenance == Provenance(NOW, "provider-model", "analysis-v2")
    assert round_.analysis.source_requirement_version == RequirementVersion(4)
    assert [item.value for item in round_.question_ids] == ["question-2", "question-1"]
    assert round_.question_changes[0].replacement_question_id == QuestionId("question-2")

    assert analysis_round_from_payload(analysis_round_to_payload(round_)) == round_
    assert (
        clarification_question_from_payload(clarification_question_to_payload(question()))
        == question()
    )

    legacy_round = analysis_round_to_payload(round_)
    legacy_round.pop("question_changes")
    assert analysis_round_from_payload(legacy_round).question_changes == ()
    legacy_question = clarification_question_to_payload(question())
    legacy_question.pop("replaces_question_id")
    assert clarification_question_from_payload(legacy_question).replaces_question_id is None


def test_replacement_links_questions_inherits_metadata_and_archives_draft() -> None:
    original = (
        question()
        .assign(REVIEWER, OWNER, NOW, 1)
        .classify(ClarificationSeverity.HIGH, False, OWNER, NOW, 2)
        .save_draft("Unconfirmed detail", REVIEWER, NOW, 3)
    )
    replacement = original.replacement(
        QuestionId("question-2"),
        AnalysisId("analysis-2"),
        ClarificationKind.AMBIGUITY,
        "Which ownership boundary applies?",
        "The same gap now concerns the boundary definition.",
    )
    archived = original.supersede()

    assert archived.status is ClarificationStatus.SUPERSEDED
    assert archived.draft_answer == "Unconfirmed detail"
    assert replacement.replaces_question_id == original.id
    assert replacement.assignee == original.assignee
    assert replacement.severity is ClarificationSeverity.HIGH
    assert replacement.is_blocker is False
    assert replacement.draft_answer is None
    assert replacement.assignment_history == ()
    assert (
        clarification_question_from_payload(clarification_question_to_payload(replacement))
        == replacement
    )


def test_pre_8b_analysis_payload_loads_with_truthfully_unavailable_audit_metadata() -> None:
    legacy = analysis_from_payload(
        {
            "requirement_id": "legacy-requirement",
            "known_facts": ["Legacy fact"],
            "constraints": [],
            "business_rules": [],
            "assumptions": [],
            "open_questions": [],
            "ambiguities": [],
            "potential_dependencies": [],
            "clarifications": [
                {
                    "kind": "open_question",
                    "subject": "Who owns it?",
                    "answer": "Operations",
                }
            ],
            "confirmed_at": None,
            "confirmed_by": None,
        }
    )

    assert legacy.id is None
    assert legacy.provenance is None
    assert legacy.clarifications[0].question_id is None
    assert legacy.clarifications[0].answered_by is None
    assert legacy.intent_proposals == ()
