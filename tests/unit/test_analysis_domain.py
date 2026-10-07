"""Tests for analysis domain entities."""

from datetime import UTC, datetime

import pytest

from smb_requirement_agent.domain.analysis.entities import (
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.errors import (
    AnalysisConfirmationBlockedError,
    IntentProposalVersionConflictError,
    InvalidAnalysisContentError,
    InvalidClarificationError,
    InvalidIntentProposalTransitionError,
)
from smb_requirement_agent.domain.analysis.value_objects import (
    Ambiguity,
    Assumption,
    BusinessRule,
    ClarificationKind,
    Constraint,
    HumanClarification,
    IntentProposal,
    IntentProposalId,
    IntentProposalKind,
    IntentProposalStatus,
    KnownFact,
    OpenQuestion,
    PotentialDependency,
)
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def test_valid_analysis_creation() -> None:
    req_id = RequirementId("req-123")
    analysis = RequirementAnalysis(
        requirement_id=req_id,
        known_facts=(KnownFact("Fact 1"),),
        constraints=(Constraint("Constraint 1"),),
        business_rules=(BusinessRule("Rule 1"),),
        assumptions=(Assumption("Assumption 1"),),
        open_questions=(OpenQuestion("Question 1", "Rationale 1"),),
        ambiguities=(Ambiguity("Statement 1", "Reason 1"),),
        potential_dependencies=(PotentialDependency("Dependency 1"),),
    )

    assert analysis.requirement_id == req_id
    assert analysis.known_facts[0].statement == "Fact 1"
    assert analysis.assumptions[0].statement == "Assumption 1"
    assert analysis.clarifications == ()


def test_invalid_known_fact() -> None:
    with pytest.raises(InvalidAnalysisContentError):
        KnownFact("")
    with pytest.raises(InvalidAnalysisContentError):
        KnownFact("   ")


def test_invalid_open_question() -> None:
    with pytest.raises(InvalidAnalysisContentError):
        OpenQuestion("", "valid")
    with pytest.raises(InvalidAnalysisContentError):
        OpenQuestion("valid", "")


def test_analysis_exposes_stable_keys_for_every_unresolved_category() -> None:
    analysis = RequirementAnalysis(
        requirement_id=RequirementId("req-123"),
        known_facts=(),
        constraints=(),
        business_rules=(),
        assumptions=(Assumption("Assumption 1"),),
        open_questions=(OpenQuestion("Question 1", "Rationale 1"),),
        ambiguities=(Ambiguity("Ambiguity 1", "Reason 1"),),
        potential_dependencies=(PotentialDependency("Dependency 1"),),
    )

    assert analysis.unresolved_keys() == {
        (ClarificationKind.ASSUMPTION, "Assumption 1"),
        (ClarificationKind.OPEN_QUESTION, "Question 1"),
        (ClarificationKind.AMBIGUITY, "Ambiguity 1"),
        (ClarificationKind.POTENTIAL_DEPENDENCY, "Dependency 1"),
    }


def test_human_clarification_requires_subject_and_answer() -> None:
    with pytest.raises(InvalidClarificationError):
        HumanClarification(ClarificationKind.OPEN_QUESTION, "", "Answer")
    with pytest.raises(InvalidClarificationError):
        HumanClarification(ClarificationKind.OPEN_QUESTION, "Question", "   ")


def test_only_a_resolved_analysis_can_be_human_confirmed() -> None:
    unresolved = RequirementAnalysis(
        requirement_id=RequirementId("req-123"),
        known_facts=(KnownFact("Fact"),),
        constraints=(),
        business_rules=(),
        assumptions=(Assumption("Needs an answer"),),
        open_questions=(),
        ambiguities=(),
        potential_dependencies=(),
    )
    with pytest.raises(AnalysisConfirmationBlockedError):
        unresolved.confirm(datetime(2026, 1, 1, tzinfo=UTC), FAKE_ACTORS[0])

    resolved = RequirementAnalysis(
        requirement_id=RequirementId("req-123"),
        known_facts=(KnownFact("Fact"),),
        constraints=(),
        business_rules=(),
        assumptions=(),
        open_questions=(),
        ambiguities=(),
        potential_dependencies=(),
    )
    confirmed = resolved.confirm(datetime(2026, 1, 1, tzinfo=UTC), FAKE_ACTORS[0])
    assert confirmed.is_human_confirmed is True


def test_owner_can_revise_an_intent_decision_until_analysis_confirmation() -> None:
    proposal = IntentProposal(
        IntentProposalId("proposal-1"),
        IntentProposalKind.DESIRED_OUTCOME,
        "Customers complete the requested journey.",
        "The business need asks for a completed customer journey.",
        ("Completion can be observed.",),
    )
    analysis = RequirementAnalysis(
        requirement_id=RequirementId("req-123"),
        known_facts=(KnownFact("Fact"),),
        constraints=(),
        business_rules=(),
        assumptions=(),
        open_questions=(),
        ambiguities=(),
        potential_dependencies=(),
        intent_proposals=(proposal,),
    )
    decided = analysis.decide_intent_proposal(
        proposal.id,
        IntentProposalStatus.ACCEPTED,
        FAKE_ACTORS[0],
        datetime(2026, 1, 1, tzinfo=UTC),
        1,
    )
    assert decided.effective_desired_outcome() == proposal.statement
    revised = decided.decide_intent_proposal(
        proposal.id,
        IntentProposalStatus.EDITED,
        FAKE_ACTORS[0],
        datetime(2026, 1, 2, tzinfo=UTC),
        2,
        replacement_statement="Customers complete the journey without assisted support.",
        success_measures=("Completion is visible in the channel.",),
    )
    assert revised.intent_proposals[0].version == 3
    assert len(revised.intent_proposals[0].decisions) == 2
    with pytest.raises(IntentProposalVersionConflictError):
        revised.decide_intent_proposal(
            proposal.id,
            IntentProposalStatus.REJECTED,
            FAKE_ACTORS[0],
            datetime(2026, 1, 3, tzinfo=UTC),
            1,
        )
    confirmed = revised.confirm(
        datetime(2026, 1, 3, tzinfo=UTC),
        FAKE_ACTORS[0],
        has_effective_outcome=True,
    )
    with pytest.raises(InvalidIntentProposalTransitionError):
        confirmed.decide_intent_proposal(
            proposal.id,
            IntentProposalStatus.REJECTED,
            FAKE_ACTORS[0],
            datetime(2026, 1, 4, tzinfo=UTC),
            3,
        )


def test_confirmation_requires_all_proposals_decided_and_an_effective_outcome() -> None:
    proposal = IntentProposal(
        IntentProposalId("proposal-1"),
        IntentProposalKind.DESIRED_OUTCOME,
        "Customers achieve the requested result.",
        "Candidate outcome.",
    )
    analysis = RequirementAnalysis(
        RequirementId("req-123"),
        (KnownFact("Fact"),),
        (),
        (),
        (),
        (),
        (),
        (),
        intent_proposals=(proposal,),
    )
    with pytest.raises(AnalysisConfirmationBlockedError):
        analysis.confirm(
            datetime(2026, 1, 1, tzinfo=UTC),
            FAKE_ACTORS[0],
            has_effective_outcome=False,
        )
    rejected = analysis.decide_intent_proposal(
        proposal.id,
        IntentProposalStatus.REJECTED,
        FAKE_ACTORS[0],
        datetime(2026, 1, 1, tzinfo=UTC),
        1,
    )
    with pytest.raises(AnalysisConfirmationBlockedError):
        rejected.confirm(
            datetime(2026, 1, 2, tzinfo=UTC),
            FAKE_ACTORS[0],
            has_effective_outcome=False,
        )
