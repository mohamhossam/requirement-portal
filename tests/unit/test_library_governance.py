"""Ownership access changes and read-only dependency lineage across analysis rounds."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from pydantic import TypeAdapter

from smb_requirement_agent.application.errors import (
    DocumentNotFoundError,
    DocumentVersionConflictError,
)
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.application.use_cases.document_library import LibraryView
from smb_requirement_agent.application.use_cases.documents import UploadDocumentInput
from smb_requirement_agent.domain.analysis.value_objects import AnalysisId, IntentProposalStatus
from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.document.library import LibraryDocument, OwnershipTransfer
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.infrastructure.identity.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.container import Container
from smb_requirement_agent.interfaces.api.main import create_app
from tests.unit import test_reference_grounding

grounded = test_reference_grounding.grounded


def test_transfer_preserves_sources_and_changes_private_access(
    grounded: tuple[Container, LibraryView],
) -> None:
    container, before = grounded
    owner, target, observer = FAKE_ACTORS
    service = container.library_governance
    receipt = service.transfer(
        before.id, owner, target.id, before.version, " New policy custodian "
    )
    after = container.document_library.get(before.id, target)
    assert after.can_edit and after.owner == target.snapshot()
    assert after.versions == before.versions
    assert after.publications == before.publications
    assert after.published_id == before.published_id
    assert receipt.reason == "New policy custodian"
    assert service.history(before.id, target) == (receipt,)
    assert receipt.previous_owner == owner.snapshot() and receipt.performed_by == owner.snapshot()
    assert not container.document_library.get(before.id, owner).can_edit
    for actor in (owner, observer):
        with pytest.raises(AuthorizationDeniedError):
            container.document_library.original(before.id, before.versions[0].id, actor)
        with pytest.raises(AuthorizationDeniedError):
            service.history(before.id, actor)
        with pytest.raises(AuthorizationDeniedError):
            service.transfer(before.id, actor, owner.id, after.version, "Unauthorized")
    with pytest.raises(DocumentVersionConflictError):
        service.transfer(before.id, target, owner.id, before.version, "Old form")
    source = before.versions[0]
    with pytest.raises(AuthorizationDeniedError):
        container.document_library.submit(
            before.title,
            UploadDocumentInput(source.filename, source.mime_type, b"retry"),
            source.idempotency_key,
            owner,
        )
    # A new owner's equal key is a distinct submission; uploader provenance remains unchanged.
    replacement = container.document_library.submit(
        before.title,
        UploadDocumentInput("new.txt", "text/plain", b"Replacement policy"),
        source.idempotency_key,
        target,
        before.id,
        after.version,
    )
    assert replacement.versions[-1].uploaded_by == target.snapshot()
    assert replacement.versions[0].uploaded_by == owner.snapshot()
    codec = TypeAdapter(LibraryDocument)
    assert codec.validate_json(codec.dump_json(replacement)) == replacement
    container.document_library.withdraw(before.id, replacement.version, target, "Retired")
    with pytest.raises(DocumentNotFoundError):
        container.document_library.get(before.id, owner)
    assert any(d.id == before.id for d in container.document_library.list(target))
    assert not any(d.id == before.id for d in container.document_library.list(owner))


@pytest.mark.parametrize("reason,target_index", [(" ", 1), ("Custodian", 0)])
def test_invalid_handover_is_atomic(
    grounded: tuple[Container, LibraryView], reason: str, target_index: int
) -> None:
    container, document = grounded
    with pytest.raises(InvalidDocumentError):
        container.library_governance.transfer(
            document.id, FAKE_ACTORS[0], FAKE_ACTORS[target_index].id, document.version, reason
        )
    assert container.document_library.get(document.id, FAKE_ACTORS[0]).version == document.version
    assert container.library_governance.history(document.id, FAKE_ACTORS[0]) == ()


def test_transfer_api_statuses_and_receipt(grounded: tuple[Container, LibraryView]) -> None:
    container, document = grounded
    path = f"/library/documents/{document.id}"
    body = {
        "expected_version": document.version,
        "actor_id": "fake-reviewer",
        "reason": "Policy team handover",
    }
    with TestClient(create_app(lambda: container)) as client:
        assert (
            client.post(f"{path}/ownership", json={**body, "actor_id": "unknown"}).status_code
            == 404
        )
        assert client.post(f"{path}/ownership", json={**body, "reason": " "}).status_code == 422
        assert (
            client.post(f"{path}/ownership", json={**body, "actor_id": "fake-owner"}).status_code
            == 422
        )
        assert (
            client.post(f"{path}/ownership", json={**body, "expected_version": 999}).status_code
            == 409
        )
        stranger = {"X-Fake-Actor-Id": "fake-observer"}
        assert client.post(f"{path}/ownership", json=body, headers=stranger).status_code == 403
        assert client.get(f"{path}/dependencies", headers=stranger).status_code == 403
        assert client.get(f"{path}/dependencies?limit=101").status_code == 422
        assert client.get("/library/documents/missing/dependencies").status_code == 404
        response = client.post(f"{path}/ownership", json=body)
        assert response.status_code == 200 and "versions" not in response.json()
        assert client.get(f"{path}/ownership/history").status_code == 403
        new_owner = {"X-Fake-Actor-Id": "fake-reviewer"}
        assert client.get(f"{path}/ownership/history", headers=new_owner).json() == [
            response.json()
        ]


def test_dependencies_decisions_history_pagination_and_privacy(
    grounded: tuple[Container, LibraryView],
) -> None:
    container, document = grounded
    owner = FAKE_ACTORS[0]
    requirements = [
        container.create_requirement.execute(
            CreateRequirementInput(
                title=f"High-speed bundles {n}", description="Order XGPON bundles through BCRM."
            ),
            actor,
        )
        for n, actor in enumerate((owner, FAKE_ACTORS[1]))
    ]
    for requirement, actor in zip(requirements, FAKE_ACTORS, strict=False):
        container.analyze_requirement.execute(actor, requirement.id)
    requirement = requirements[0]
    analysis = container.analysis_repository.get_by_requirement_id(requirement.id)
    assert analysis is not None
    proposal = next(p for p in analysis.intent_proposals if p.reference_evidence)
    container.analysis_collaboration.decide_intent_proposal(
        requirement.id,
        proposal.id,
        IntentProposalStatus.ACCEPTED,
        proposal.version,
        owner,
        rationale="Policy applies",
    )
    page = container.library_governance.dependencies(document.id, owner, limit=1)
    assert len(page.items) == 1
    row = page.items[0]
    assert row.requirement_id == requirement.id.value
    assert (
        row.current_analysis
        and row.publication_current
        and row.status == IntentProposalStatus.ACCEPTED
    )
    assert row.citation == proposal.reference_evidence[0]
    assert all(
        d.requirement_id != requirements[1].id.value
        for d in container.library_governance.dependencies(document.id, owner).items
    )
    # A later analysis drops the reference; the immutable previous round still appears.
    updated = container.analysis_repository.get_by_requirement_id(requirement.id)
    assert updated is not None
    later = replace(
        updated,
        id=AnalysisId("later-round"),
        round_number=2,
        intent_proposals=(),
        version=updated.version + 1,
    )
    container.analysis_repository.save(later)
    history = container.library_governance.dependencies(document.id, owner)
    assert history.items and all(not row.current_analysis for row in history.items)
    container.document_library.withdraw(document.id, document.version, owner, "Policy retired")
    assert all(
        not row.publication_current
        for row in container.library_governance.dependencies(document.id, owner).items
    )
    assert container.library_governance.dependencies(document.id, owner, offset=999).items == ()


def test_transfer_domain_requires_current_actor(grounded: tuple[Container, LibraryView]) -> None:
    container, _ = grounded
    with pytest.raises(InvalidDocumentError):
        OwnershipTransfer(
            FAKE_ACTORS[0].snapshot(),
            FAKE_ACTORS[1].snapshot(),
            FAKE_ACTORS[2].snapshot(),
            container.clock.now(),
            "Invalid actor",
        )


def test_dependency_pages_and_rejected_current_decisions(
    grounded: tuple[Container, LibraryView],
) -> None:
    container, document = grounded
    owner = FAKE_ACTORS[0]
    for number in range(2):
        requirement = container.create_requirement.execute(
            CreateRequirementInput(
                title=f"Coverage {number}", description="Order XGPON bundles through BCRM."
            ),
            owner,
        )
        analysis = container.analyze_requirement.execute(owner, requirement.id)
        proposal = next(p for p in analysis.intent_proposals if p.reference_evidence)
        container.analysis_collaboration.decide_intent_proposal(
            requirement.id,
            proposal.id,
            IntentProposalStatus.REJECTED,
            proposal.version,
            owner,
            rationale="This policy does not apply to the offer.",
        )
    first = container.library_governance.dependencies(document.id, owner, limit=1)
    assert len(first.items) == 1 and first.next_offset == 1
    second = container.library_governance.dependencies(document.id, owner, offset=1, limit=1)
    assert len(second.items) == 1 and second.next_offset == 2
    # Prior pending states are now indexed historical records, not erased by a decision.
    assert first.items[0].requirement_id != second.items[0].requirement_id
    assert all(
        row.status == IntentProposalStatus.REJECTED and row.current_analysis
        for row in (*first.items, *second.items)
    )


def test_legacy_history_defaults_and_broken_chain_is_rejected(
    grounded: tuple[Container, LibraryView],
) -> None:
    container, document = grounded
    source = LibraryDocument(document.id, document.title, document.owner, document.versions)
    codec = TypeAdapter(LibraryDocument)
    payload = codec.dump_python(source, mode="json")
    payload.pop("ownership_history")
    assert codec.validate_python(payload).ownership_history == ()
    transfer = OwnershipTransfer(
        document.owner, FAKE_ACTORS[1].snapshot(), document.owner, container.clock.now(), "Handover"
    )
    with pytest.raises(InvalidDocumentError):
        replace(source, ownership_history=(transfer,))
