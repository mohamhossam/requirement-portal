"""Published reference applicability stays attributable and revocable."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from smb_kernel.llm.structured_output import StructuredOutputError

from smb_requirement_agent.analysis.domain.errors import InvalidIntentProposalDecisionError
from smb_requirement_agent.analysis.domain.value_objects import IntentProposalStatus
from smb_requirement_agent.analysis.infrastructure.analysis_payloads import (
    analysis_from_payload,
    analysis_to_payload,
)
from smb_requirement_agent.application.errors import (
    RequirementAnalysisConflictError,
    RequirementAnalysisGenerationError,
)
from smb_requirement_agent.identity.domain.errors import AuthorizationDeniedError
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.llm.reference_proposals import (
    ProposalOutput,
    ReferenceOutput,
    StructuredReferenceProposer,
)
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.application.use_cases.requirement_drafts import (
    RequirementDraftInput,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from tests.knowledge_doubles import PublishedLibrary, container_with_library, sync
from tests.unit.workflow_helpers import drain_requirement_index


@dataclass(frozen=True)
class Grounded:
    """A container whose library has one published policy, and that policy's citation."""

    container: Container
    library: PublishedLibrary
    citation: PublishedReference

    def withdraw(self) -> None:
        """Withdraw the policy in the library, and let requirement work learn of it."""
        self.library.withdraw(self.citation.document_id)
        sync(self.container)


@pytest.fixture
def grounded() -> Iterator[Grounded]:
    # The policy's owner is the first fake actor, who also owns the Requirements below.
    container, library = container_with_library(
        Settings(llm_provider=LLMProvider.FAKE), PublishedLibrary(owner_id=FAKE_ACTORS[0].id.value)
    )
    (citation,) = library.publish(
        "XGPON policy", ("High-speed bundles require XGPON coverage at the customer address.",)
    )
    sync(container)
    yield Grounded(container, library, citation)
    container.close_resources()


def test_unified_search_balances_sources_across_the_workspace(
    grounded: Grounded,
) -> None:
    """Search sees what reading sees (ADR-0075): anyone's submitted work, no drafts."""
    container = grounded.container
    owned = container.create_requirement.execute(
        CreateRequirementInput("XGPON launch", "Order bundles through BCRM."), FAKE_ACTORS[0]
    )
    colleague = container.create_requirement.execute(
        CreateRequirementInput("Colleague XGPON", "XGPON bundles for a colleague."), FAKE_ACTORS[1]
    )
    draft = container.create_requirement_draft.execute(
        RequirementDraftInput("Draft XGPON", "XGPON bundles still being written."), FAKE_ACTORS[1]
    )
    drain_requirement_index(container)
    hits = container.unified_knowledge_search.execute("XGPON bundles")
    assert {h.source_type for h in hits} == {"requirement", "published_document"}
    assert any(h.source_id == owned.id.value for h in hits)
    assert any(h.source_id == colleague.id.value for h in hits)
    assert all(h.source_id != draft.id.value for h in hits)
    assert len([h for h in hits if h.source_id == owned.id.value]) <= 3
    with TestClient(create_app(lambda: container)) as client:
        response = client.post("/knowledge/search/unified", json={"query": "XGPON bundles"})
        assert response.status_code == 200
        assert {h["source_type"] for h in response.json()} == {"requirement", "published_document"}
        assert client.post("/knowledge/search/unified", json={"query": "   "}).status_code == 422
        grounded.withdraw()
        response = client.post("/knowledge/search/unified", json={"query": "XGPON bundles"})
        assert all(h["source_type"] == "requirement" for h in response.json())


def test_document_answer_preserves_citation_and_hides_after_withdrawal(
    grounded: Grounded,
) -> None:
    from smb_requirement_agent.application.errors import AnswerSuggestionNotFoundError
    from smb_requirement_agent.domain.knowledge.entities import AnswerSuggestionSource
    from smb_requirement_agent.interfaces.api.routes.knowledge import suggestion_response

    container = grounded.container
    requirement = container.create_requirement.execute(
        CreateRequirementInput("XGPON bundle", "Order a high-speed bundle."), FAKE_ACTORS[0]
    )
    container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    question = container.analysis_audit_repository.list_questions(requirement.id)[0]
    drain_requirement_index(container)
    result = container.suggest_clarification_answers.execute(
        requirement.id, question.id, question.version, FAKE_ACTORS[0]
    )
    cited = next(s for s in result.suggestions if s.reference_evidence)
    assert cited.source_for(requirement.id) is AnswerSuggestionSource.PUBLISHED_REFERENCE
    assert cited.reference_evidence[0].document_id == grounded.citation.document_id
    assert suggestion_response(result).suggestions[0].reference_evidence
    assert (
        container.knowledge_repository.latest_suggestion_set(requirement.id, question.id.value)
        == result
    )
    grounded.withdraw()
    assert container.suggest_clarification_answers.get_current(requirement.id, question.id) is None
    with pytest.raises(AnswerSuggestionNotFoundError):
        container.suggest_clarification_answers.require_suggestion(
            requirement.id, question.id, cited.id.value
        )
    # Historical evidence survives even though it can no longer be selected.
    assert (
        container.knowledge_repository.latest_suggestion_set(requirement.id, question.id.value)
        == result
    )


def test_document_withdrawn_during_answer_generation_cannot_persist(
    grounded: Grounded,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from smb_requirement_agent.application.ports.requirement_knowledge import (
        AnswerSuggestionCandidate,
    )
    from smb_requirement_agent.infrastructure.llm.fake_requirement_knowledge import (
        FakeClarificationAnswerSuggester,
    )

    container = grounded.container
    requirement = container.create_requirement.execute(
        CreateRequirementInput("XGPON bundle", "Order high-speed bundles."), FAKE_ACTORS[0]
    )
    container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    question = container.analysis_audit_repository.list_questions(requirement.id)[0]
    drain_requirement_index(container)

    def withdrawing(*args: object, **kwargs: object) -> tuple[AnswerSuggestionCandidate, ...]:
        grounded.withdraw()
        return (
            AnswerSuggestionCandidate(
                "Coverage required", "The cited policy supports it", ("reference:0",)
            ),
        )

    monkeypatch.setattr(FakeClarificationAnswerSuggester, "suggest", withdrawing)
    with pytest.raises(RequirementAnalysisConflictError):
        container.suggest_clarification_answers.execute(
            requirement.id, question.id, question.version, FAKE_ACTORS[0]
        )
    assert (
        container.knowledge_repository.latest_suggestion_set(requirement.id, question.id.value)
        is None
    )


def test_reference_conflict_requires_owner_review_in_screening(
    grounded: Grounded,
) -> None:
    container = grounded.container
    requirement = container.create_requirement.execute(
        CreateRequirementInput("XGPON bundle", "Order high-speed bundles."), FAKE_ACTORS[0]
    )
    analysis = container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    proposal = next(p for p in analysis.intent_proposals if p.reference_evidence)
    container.analysis_repository.save(
        replace(
            analysis,
            intent_proposals=(replace(proposal, reference_conflict=True),),
            version=analysis.version + 1,
        )
    )
    drain_requirement_index(container)
    review = container.screen_requirement_knowledge.execute(
        FAKE_ACTORS[0],
        requirement.id,
        container.get_knowledge_review.execute(requirement.id).current_fingerprint,
    )
    assert review.reference_conflict_ids == (proposal.id.value,)
    assert not review.ready


def test_reference_withdrawal_during_answer_reanalysis_cannot_commit(
    grounded: Grounded,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
        RequirementAnalysisCandidate,
    )
    from smb_requirement_agent.application.errors import ArtifactVersionConflictError
    from smb_requirement_agent.infrastructure.llm.fake_requirement_analyzer import (
        FakeRequirementAnalyzer,
    )

    container = grounded.container
    requirement = container.create_requirement.execute(
        CreateRequirementInput("XGPON bundle", "Order high-speed bundles."), FAKE_ACTORS[0]
    )
    analysis = container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    question = container.analysis_audit_repository.list_questions(requirement.id)[0]
    drain_requirement_index(container)
    suggestions = container.suggest_clarification_answers.execute(
        requirement.id, question.id, question.version, FAKE_ACTORS[0]
    )
    suggestion = next(s for s in suggestions.suggestions if s.reference_evidence)
    original = FakeRequirementAnalyzer.analyze

    def withdrawing(*args: object, **kwargs: object) -> RequirementAnalysisCandidate:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        grounded.withdraw()
        return result

    monkeypatch.setattr(FakeRequirementAnalyzer, "analyze", withdrawing)
    with pytest.raises(ArtifactVersionConflictError):
        container.analysis_collaboration.resolve(
            requirement.id,
            question.id,
            suggestion.answer,
            question.version,
            FAKE_ACTORS[0],
            source_suggestion_id=suggestion.id.value,
        )
    assert container.analysis_repository.get_by_requirement_id(requirement.id) == analysis
    assert container.analysis_audit_repository.get_question(requirement.id, question.id) == question


def test_owner_applicability_roundtrip_and_withdrawal(
    grounded: Grounded,
) -> None:
    container = grounded.container
    requirement = container.create_requirement.execute(
        CreateRequirementInput(
            title="High-speed bundles",
            description="Allow SMB customers to order high-speed bundles through BCRM.",
            desired_outcome="Customers can order eligible bundles.",
        ),
        FAKE_ACTORS[0],
    )
    analysis = container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    proposal = next(p for p in analysis.intent_proposals if p.reference_evidence)
    assert proposal.statement not in [r.statement for r in analysis.business_rules]
    assert proposal.effective_statement is None
    assert analysis_from_payload(analysis_to_payload(analysis)) == analysis
    with pytest.raises(InvalidIntentProposalDecisionError):
        container.analysis_collaboration.decide_intent_proposal(
            requirement.id,
            proposal.id,
            IntentProposalStatus.ACCEPTED,
            proposal.version,
            FAKE_ACTORS[0],
        )
    with pytest.raises(AuthorizationDeniedError):
        container.analysis_collaboration.decide_intent_proposal(
            requirement.id,
            proposal.id,
            IntentProposalStatus.ACCEPTED,
            proposal.version,
            FAKE_ACTORS[1],
            rationale="Applies",
        )
    workspace = container.analysis_collaboration.decide_intent_proposal(
        requirement.id,
        proposal.id,
        IntentProposalStatus.EDITED,
        proposal.version,
        FAKE_ACTORS[0],
        replacement_statement="Check XGPON coverage before ordering high-speed bundles.",
        rationale="This offer uses the policy's covered access network.",
    )
    decided = next(p for p in workspace.analysis.intent_proposals if p.id == proposal.id)
    assert decided.reference_evidence == proposal.reference_evidence
    assert decided.decisions[-1].rationale
    assert analysis_from_payload(analysis_to_payload(workspace.analysis)) == workspace.analysis
    grounded.withdraw()
    current = container.analysis_collaboration.workspace(requirement.id)
    assert proposal.id.value in current.stale_reference_proposal_ids
    assert current.analysis.intent_proposals == workspace.analysis.intent_proposals
    with pytest.raises(RequirementAnalysisConflictError):
        container.generate_epic.execute(FAKE_ACTORS[0], requirement.id)
    with TestClient(create_app(lambda: container)) as client:
        response = client.get(f"/requirements/{requirement.id.value}/analysis")
        assert response.status_code == 200
        assert proposal.id.value in response.json()["stale_reference_proposal_ids"]
        rejected = client.patch(
            f"/requirements/{requirement.id.value}/analysis/proposals/{proposal.id.value}",
            json={
                "decision": "rejected",
                "expected_version": decided.version,
                "rationale": "The policy was withdrawn; do not apply it.",
            },
        )
        assert rejected.status_code == 200, rejected.text
        assert rejected.json()["stale_reference_proposal_ids"] == []


@pytest.mark.parametrize("bad", ["blank", "citation", "empty", "provider"])
def test_reference_adapter_rejects_unusable_output(grounded: Grounded, bad: str) -> None:
    container = grounded.container
    requirement = container.create_requirement.execute(
        CreateRequirementInput("Bundles", "Order high-speed bundles."), FAKE_ACTORS[0]
    )
    evidence = grounded.library.search_evidence("XGPON")
    assert evidence
    transport = Mock()
    transport.model = "test"
    transport.parse.return_value = ReferenceOutput(
        proposals=[
            ProposalOutput(
                kind="business_rule",
                statement=" " if bad == "blank" else "Coverage required",
                rationale="Potential applicability",
                evidence_numbers=[999 if bad == "citation" else 1],
                conflict=False,
            )
        ],
        no_applicability_reason=None,
    )
    if bad == "empty":
        transport.parse.return_value = ReferenceOutput(proposals=[], no_applicability_reason=" ")
    if bad == "provider":
        transport.parse.side_effect = StructuredOutputError("offline")
    from smb_requirement_agent.infrastructure.llm.fake_requirement_analyzer import (
        FakeRequirementAnalyzer,
    )

    primary = FakeRequirementAnalyzer().analyze(requirement, ())
    with pytest.raises(RequirementAnalysisGenerationError):
        StructuredReferenceProposer(transport).propose(requirement, primary, evidence, ())
    transport.parse.side_effect = None
    transport.parse.return_value = ReferenceOutput(
        proposals=[], no_applicability_reason="Different offer scope"
    )
    result = StructuredReferenceProposer(transport).propose(requirement, primary, evidence, ())
    assert result.proposals == ()
    assert result.prompt_version == "reference-applicability-v2"
    assert "surrounding_approved_context" in transport.parse.call_args.kwargs["user_prompt"]


def test_tampered_citation_is_not_current(grounded: Grounded) -> None:
    container = grounded.container
    citation = grounded.library.search_evidence("XGPON")[0].citation
    container.reference_currency.require_current((citation,))
    with pytest.raises(RequirementAnalysisConflictError):
        container.reference_currency.require_current(
            (replace(citation, excerpt="X" * len(citation.excerpt)),)
        )


def test_withdrawal_during_reference_generation_cannot_persist(
    grounded: Grounded,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from smb_requirement_agent.analysis.application.ports.reference_analysis import (
        ReferenceProposalResult,
    )
    from smb_requirement_agent.infrastructure.llm.reference_proposals import FakeReferenceProposer

    container = grounded.container
    requirement = container.create_requirement.execute(
        CreateRequirementInput("High-speed bundles", "Order high-speed bundles through BCRM."),
        FAKE_ACTORS[0],
    )
    original = FakeReferenceProposer.propose

    def withdrawing(*args: object, **kwargs: object) -> ReferenceProposalResult:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        grounded.withdraw()
        return result

    monkeypatch.setattr(FakeReferenceProposer, "propose", withdrawing)
    with pytest.raises(RequirementAnalysisConflictError):
        container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    assert container.analysis_repository.get_by_requirement_id(requirement.id) is None
    assert not container.analysis_audit_repository.list_rounds(requirement.id)


def test_confirmed_reference_withdrawal_blocks_generation_and_preserves_history(
    grounded: Grounded,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from smb_requirement_agent.application.ports.epic_generator import EpicCandidate
    from smb_requirement_agent.infrastructure.llm.fake_epic_generator import FakeEpicGenerator

    container = grounded.container
    requirement = container.create_requirement.execute(
        CreateRequirementInput(
            "High-speed bundles", "Order high-speed bundles.", desired_outcome="Eligible ordering"
        ),
        FAKE_ACTORS[0],
    )
    analysis = container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)
    proposal = next(p for p in analysis.intent_proposals if p.reference_evidence)
    decided = container.analysis_collaboration.decide_intent_proposal(
        requirement.id,
        proposal.id,
        IntentProposalStatus.ACCEPTED,
        1,
        FAKE_ACTORS[0],
        rationale="Network coverage applies",
    ).analysis
    confirmed = replace(
        decided,
        confirmed_at=container.clock.now(),
        confirmed_by=FAKE_ACTORS[0].snapshot(),
        version=decided.version + 1,
    )
    container.analysis_repository.save(confirmed)
    original = FakeEpicGenerator.generate

    def withdrawing(*args: object, **kwargs: object) -> EpicCandidate:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        grounded.withdraw()
        return result

    monkeypatch.setattr(FakeEpicGenerator, "generate", withdrawing)
    with pytest.raises(RequirementAnalysisConflictError):
        container.generate_epic.execute(FAKE_ACTORS[0], requirement.id)
    assert container.epic_repository.get_by_requirement_id(requirement.id) is None
    assert container.analysis_repository.get_by_requirement_id(requirement.id) == confirmed
    reopened = container.analysis_collaboration.generate(FAKE_ACTORS[0], requirement.id, force=True)
    assert not reopened.analysis.is_human_confirmed
    assert proposal.id.value in reopened.stale_reference_proposal_ids
    assert (
        next(p for p in reopened.analysis.intent_proposals if p.id == proposal.id).decisions
        == next(p for p in confirmed.intent_proposals if p.id == proposal.id).decisions
    )
