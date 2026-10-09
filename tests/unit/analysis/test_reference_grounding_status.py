"""An analysis records what checking the reference library found (ADR-0104).

The knowledge portal is optional and can be down. Neither may cost the analysis its
primary result, and a reviewer must be able to tell "nothing applies" from "it could
not be checked".
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.analysis.application.ports.reference_analysis import (
    ReferenceProposalResult,
)
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.application.use_cases.reference_grounding import (
    ReferenceGrounding,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    IntentProposal,
    ReferenceGroundingStatus,
)
from smb_requirement_agent.analysis.infrastructure.analysis_payloads import (
    analysis_from_payload,
    analysis_to_payload,
)
from smb_requirement_agent.application.errors import ServiceUnavailableError
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.infrastructure.config.options import LLMProvider
from smb_requirement_agent.infrastructure.config.settings import Settings
from smb_requirement_agent.infrastructure.text.budget import Utf8BudgetCounter
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.interfaces.api.routes.knowledge_views import REFERENCE_LIBRARY_HEADER
from smb_requirement_agent.references.application.ports.reference_grounding import (
    ReferenceEvidence,
    ReferenceKnowledgePort,
)
from smb_requirement_agent.references.infrastructure.knowledge_client import (
    FakeReferenceKnowledge,
)
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from tests.characterisation import samples
from tests.knowledge_doubles import PublishedLibrary, container_with_library, sync
from tests.unit.workflow_helpers import drain_requirement_index

PRIMARY: RequirementAnalysisCandidate = {
    "known_facts": ["SMB customers order bundles through BCRM."],
    "constraints": [],
    "business_rules": ["Credit check before activation."],
    "assumptions": [],
    "open_questions": [],
    "ambiguities": [],
    "potential_dependencies": [],
    "intent_proposals": [],
    "model": "primary-model",
    "prompt_version": "primary-v1",
}


@dataclass
class UnreachableLibrary(PublishedLibrary):
    """A connected library whose service stops answering after `answers` calls."""

    answers: int = 0

    def _call(self) -> None:
        if self.answers <= 0:
            raise ServiceUnavailableError("The knowledge service could not be reached.")
        self.answers -= 1

    def has_published(self) -> bool:
        self._call()
        return super().has_published()

    def search_evidence(self, query: str) -> tuple[ReferenceEvidence, ...]:
        self._call()
        return super().search_evidence(query)

    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]:
        self._call()
        return super().retrieve(query)


class NoProposals:
    """A reference proposer that finds nothing applicable, and counts its calls."""

    def __init__(self) -> None:
        self.calls = 0

    def propose(
        self,
        requirement: Requirement,
        primary: RequirementAnalysisCandidate,
        evidence: tuple[ReferenceEvidence, ...],
        decisions: Sequence[IntentProposal],
    ) -> ReferenceProposalResult:
        self.calls += 1
        return ReferenceProposalResult((), "reference-model", "reference-v1")


def _grounding(knowledge: ReferenceKnowledgePort, proposer: NoProposals) -> ReferenceGrounding:
    return ReferenceGrounding(
        knowledge, proposer, Utf8BudgetCounter(), FixedClock(datetime(2026, 10, 9, tzinfo=UTC))
    )


def _published(library: PublishedLibrary) -> PublishedLibrary:
    library.publish("Credit policy", ("A credit check runs before activation of any bundle.",))
    return library


def test_without_a_portal_the_analysis_says_none_is_connected() -> None:
    proposer = NoProposals()

    result = _grounding(FakeReferenceKnowledge(), proposer).augment(
        samples.requirement(), PRIMARY, ()
    )

    assert result["reference_grounding"] is ReferenceGroundingStatus.NOT_CONNECTED
    assert result["intent_proposals"] == [] and proposer.calls == 0


def test_a_connected_library_with_nothing_published_finds_no_evidence() -> None:
    proposer = NoProposals()

    result = _grounding(PublishedLibrary(), proposer).augment(samples.requirement(), PRIMARY, ())

    assert result["reference_grounding"] is ReferenceGroundingStatus.NO_EVIDENCE
    assert proposer.calls == 0


def test_evidence_that_reached_the_proposer_is_grounded() -> None:
    proposer = NoProposals()

    result = _grounding(_published(PublishedLibrary()), proposer).augment(
        samples.requirement(), PRIMARY, ()
    )

    assert result["reference_grounding"] is ReferenceGroundingStatus.GROUNDED
    assert proposer.calls == 1
    assert result["stage_provenance"][-1]["stage"] == "reference_applicability"


@pytest.mark.parametrize("answers", [0, 1, 2], ids=["published", "first-search", "later-search"])
def test_an_unreachable_portal_keeps_the_primary_analysis(answers: int) -> None:
    """However far the library got, its failure leaves the paid-for analysis standing."""
    proposer = NoProposals()
    library = _published(UnreachableLibrary(answers=answers))

    result = _grounding(library, proposer).augment(samples.requirement(), PRIMARY, ())

    assert result == {**PRIMARY, "reference_grounding": ReferenceGroundingStatus.UNAVAILABLE}
    assert proposer.calls == 0


def test_analysis_with_the_portal_down_is_stored_and_shown_as_unchecked() -> None:
    library = UnreachableLibrary(owner_id=FAKE_ACTORS[0].id.value, answers=10_000)
    container, _ = container_with_library(Settings(llm_provider=LLMProvider.FAKE), library)
    try:
        library.publish("Credit policy", ("A credit check runs before bundle activation.",))
        sync(container)
        requirement = container.create_requirement.execute(
            CreateRequirementInput(
                title="Bundle activation",
                description="Activate SMB bundles after a credit check.",
                desired_outcome="Bundles activate the same day.",
            ),
            FAKE_ACTORS[0],
        )
        library.answers = 0

        analysis = container.analyze_requirement.execute(FAKE_ACTORS[0], requirement.id)

        assert analysis.reference_grounding is ReferenceGroundingStatus.UNAVAILABLE
        assert analysis.known_facts
        assert analysis_from_payload(analysis_to_payload(analysis)) == analysis
        with TestClient(create_app(lambda: container)) as client:
            shown = client.get(f"/requirements/{requirement.id.value}/analysis")
        assert shown.status_code == 200
        assert shown.json()["reference_grounding"] == "unavailable"
    finally:
        container.close_resources()


def test_an_analysis_from_before_grounding_was_recorded_reads_as_unrecorded() -> None:
    analysis = samples.analysis()
    payload = analysis_to_payload(analysis)

    assert "reference_grounding" not in payload
    assert analysis_from_payload(payload).reference_grounding is None


def test_unified_search_without_the_library_answers_with_requirements_and_says_so() -> None:
    library = UnreachableLibrary(owner_id=FAKE_ACTORS[0].id.value, answers=10_000)
    container, _ = container_with_library(Settings(llm_provider=LLMProvider.FAKE), library)
    try:
        sync(container)
        container.create_requirement.execute(
            CreateRequirementInput(
                "XGPON launch", "Order XGPON bundles through BCRM for SMB customers."
            ),
            FAKE_ACTORS[0],
        )
        drain_requirement_index(container)
        library.answers = 0

        result = container.unified_knowledge_search.execute("XGPON bundles")
        assert result.references_unavailable
        assert {hit.source_type for hit in result.hits} == {"requirement"}
        with TestClient(create_app(lambda: container)) as client:
            response = client.post("/knowledge/search/unified", json={"query": "XGPON bundles"})
        assert response.status_code == 200
        assert response.headers[REFERENCE_LIBRARY_HEADER] == "unavailable"
        assert {hit["source_type"] for hit in response.json()} == {"requirement"}
    finally:
        container.close_resources()
