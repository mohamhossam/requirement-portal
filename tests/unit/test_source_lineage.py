"""Reuse, derived origins, private dependency pages and explicit source reconciliation."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisConflictError
from smb_requirement_agent.analysis.domain.value_objects import IntentProposalStatus
from smb_requirement_agent.analysis.infrastructure.analysis_payloads import (
    analysis_from_payload,
    analysis_to_payload,
)
from smb_requirement_agent.application.errors import ArtifactVersionConflictError
from smb_requirement_agent.breakdown.infrastructure.backlog_payloads import (
    epic_from_payload,
    epic_to_payload,
    feature_from_payload,
    feature_to_payload,
    story_from_payload,
    story_to_payload,
)
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.knowledge.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
)
from smb_requirement_agent.knowledge.domain.lineage import ImpactDecisionKind
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirementInput,
)
from tests.unit.analysis import test_reference_grounding
from tests.unit.analysis.test_reference_grounding import Grounded
from tests.unit.workflow_helpers import drain_requirement_index

grounded = test_reference_grounding.grounded
TOKEN = "k" * 40
SERVICE = {"Authorization": f"Bearer {TOKEN}"}


def test_answer_origin_survives_reanalysis_and_is_not_independent(
    grounded: Grounded,
) -> None:
    container = grounded.container
    document_id = grounded.citation.document_id
    owner = FAKE_ACTORS[0]
    requirement = container.create_requirement.execute(
        CreateRequirementInput("XGPON order", "Order bundles through BCRM."), owner
    )
    container.analyze_requirement.execute(owner, requirement.id)
    question = container.analysis_audit_repository.list_questions(requirement.id)[0]
    drain_requirement_index(container)
    suggestions = container.suggest_clarification_answers.execute(
        requirement.id, question.id, question.version, owner
    )
    suggestion = next(item for item in suggestions.suggestions if item.reference_evidence)
    workspace = container.analysis_collaboration.resolve(
        requirement.id,
        question.id,
        suggestion.answer,
        question.version,
        owner,
        source_suggestion_id=suggestion.id.value,
    )
    answer = workspace.analysis.clarifications[-1]
    assert answer.source_lineage[0].citation == suggestion.reference_evidence[0]
    assert analysis_from_payload(analysis_to_payload(workspace.analysis)) == workspace.analysis
    rows = container.source_impact.page(
        owner, document_id=document_id, active_only=True, limit=100
    ).items
    assert {item.dependency.target_kind for item in rows} >= {
        "clarification",
        "analysis",
        "requirement",
    }
    assert any(item.dependency.lineage.via for item in rows)
    corpus = RequirementKnowledgeCorpus(
        container.requirement_repository,
        container.analysis_repository,
        container.analysis_audit_repository,
        container.access_repository,
        container.knowledge_repository,
        container.document_repository,
    )
    copies = [chunk for chunk in corpus.chunks(requirement) if chunk.source_lineage]
    assert copies and all(c.source_lineage[0].citation.document_id == document_id for c in copies)
    drain_requirement_index(container)
    hits = container.unified_knowledge_search.execute("XGPON coverage").hits
    assert any(hit.reference_evidence for hit in hits)
    assert not any(
        hit.requirement_evidence and hit.requirement_evidence.source_lineage for hit in hits
    )


def test_derived_backlog_lineage_and_content_bound_review(grounded: Grounded) -> None:
    container = grounded.container
    owner = FAKE_ACTORS[0]
    requirement = container.create_requirement.execute(
        CreateRequirementInput("XGPON order", "Order bundles through BCRM."), owner
    )
    analysis = container.analyze_requirement.execute(owner, requirement.id)
    proposal = next(item for item in analysis.intent_proposals if item.reference_evidence)
    workspace = container.analysis_collaboration.decide_intent_proposal(
        requirement.id,
        proposal.id,
        IntentProposalStatus.ACCEPTED,
        proposal.version,
        owner,
        rationale="Policy applies",
    )
    assert proposal.reference_provenance is not None
    confirmed = replace(
        workspace.analysis,
        version=workspace.analysis.version + 1,
        confirmed_by=owner.snapshot(),
        confirmed_at=proposal.reference_provenance.generated_at,
    )
    container.analysis_repository.save(confirmed)
    epic = container.generate_epic.execute(owner, requirement.id).epic
    container.epic_repository.save(replace(epic.approve(), version=epic.version + 1))
    features = container.generate_features.execute(owner, requirement.id).features
    feature = features[0]
    container.feature_repository.save(replace(feature.approve(), version=feature.version + 1))
    stories = container.generate_stories.execute(owner, requirement.id, feature.id)
    for artifact in (epic, *features, *stories):
        assert artifact.source_lineage and all(
            origin.citation == proposal.reference_evidence[0] for origin in artifact.source_lineage
        )
    assert epic_from_payload(epic_to_payload(epic)) == epic
    assert feature_from_payload(feature_to_payload(feature)) == feature
    assert story_from_payload(story_to_payload(stories[0])) == stories[0]
    before = container.breakdown_repository.list_breakdown_revisions(requirement.id)
    grounded.withdraw()
    rows = container.source_impact.page(
        owner, requirement_id=requirement.id.value, active_only=True, limit=100
    ).items
    assert {item.dependency.target_kind for item in rows} >= {
        "requirement",
        "analysis",
        "epic",
        "feature",
        "story",
    }
    assert all(item.needs_review for item in rows)
    with pytest.raises(RequirementAnalysisConflictError):
        container.generate_epic.execute(owner, requirement.id, force=True)
    for item in rows:
        container.source_impact.decide(
            item.dependency.id,
            owner,
            item.publication_state,
            0,
            ImpactDecisionKind.RETAIN,
            "This rollout intentionally retains the reviewed historical rule.",
            requirement_id=item.dependency.requirement_id,
        )
    assert not container.source_impact.stale_analysis(confirmed)
    assert container.breakdown_repository.list_breakdown_revisions(requirement.id) == before
    selected = rows[0]
    with pytest.raises(ArtifactVersionConflictError):
        container.source_impact.decide(
            selected.dependency.id,
            owner,
            selected.publication_state,
            0,
            ImpactDecisionKind.RETAIN,
            "Stale form",
            requirement_id=selected.dependency.requirement_id,
        )
    # Content change invalidates its prior reconciliation without deleting that decision.
    container.epic_repository.save(
        replace(epic, version=epic.version + 1).edit(
            epic.name, epic.outcome, type(epic.business_case)("Changed case")
        )
    )
    refreshed = container.source_impact.page(
        owner, requirement_id=requirement.id.value, limit=100
    ).items
    assert any(item.needs_review and item.dependency.target_kind == "epic" for item in refreshed)
    assert any(item.decisions and not item.dependency.current for item in refreshed)
    # Revise has a usable recovery path: reject the old proposal, re-analyse,
    # then replace descendants without first accepting their old sources.
    affected = next(
        item for item in refreshed if item.needs_review and item.dependency.target_kind == "epic"
    )
    container.source_impact.decide(
        affected.dependency.id,
        owner,
        affected.publication_state,
        0,
        ImpactDecisionKind.REVISE,
        "Replace the old policy inputs and regenerate.",
        requirement_id=affected.dependency.requirement_id,
    )
    current = container.analyze_requirement.execute(owner, requirement.id, force=True)
    old_proposal = next(p for p in current.intent_proposals if p.id == proposal.id)
    container.analysis_collaboration.decide_intent_proposal(
        requirement.id,
        old_proposal.id,
        IntentProposalStatus.REJECTED,
        old_proposal.version,
        owner,
        rationale="Withdrawn policy no longer applies",
    )
    renewed = container.analyze_requirement.execute(owner, requirement.id, force=True)
    assert not renewed.source_lineage
    container.analysis_repository.save(
        replace(
            renewed,
            version=renewed.version + 1,
            confirmed_by=owner.snapshot(),
            confirmed_at=proposal.reference_provenance.generated_at,
        )
    )
    replacement = container.generate_epic.execute(owner, requirement.id, force=True).epic
    assert not replacement.source_lineage
    remaining = container.source_impact.page(
        owner, requirement_id=requirement.id.value, active_only=True, limit=100
    ).items
    assert not any(
        item.needs_review and item.dependency.target_kind == "epic" for item in remaining
    )
    history = container.source_impact.page(
        owner, requirement_id=requirement.id.value, limit=100
    ).items
    assert any(item.decisions and not item.dependency.current for item in history)


def test_source_impact_api_permissions_cas_and_private_counts(
    grounded: Grounded,
) -> None:
    container = grounded.container
    document_id = grounded.citation.document_id
    owner = FAKE_ACTORS[0]
    for actor in FAKE_ACTORS[:2]:
        requirement = container.create_requirement.execute(
            CreateRequirementInput("Private name " + actor.id.value, "XGPON coverage for bundles."),
            actor,
        )
        container.analyze_requirement.execute(actor, requirement.id)
    grounded.withdraw()
    # The owner's view of a document's dependents is served to the knowledge service.
    serving = replace(
        container, settings=replace(container.settings, knowledge_service_token=TOKEN)
    )
    with TestClient(create_app(lambda: serving)) as client:
        path = f"/internal/references/{document_id}/impact"
        page = client.get(
            path,
            params={"actor_id": owner.id.value, "active_only": True, "limit": 100},
            headers=SERVICE,
        )
        assert page.status_code == 200 and "fake-reviewer" not in page.text
        assert "total" not in page.json() and page.json()["next_offset"] is None
        observer = client.get(path, params={"actor_id": "fake-observer"}, headers=SERVICE)
        assert observer.status_code == 403
        too_many = client.get(
            path, params={"actor_id": owner.id.value, "limit": 101}, headers=SERVICE
        )
        assert too_many.status_code == 422
        item = page.json()["items"][0]
        decision_path = (
            f"/requirements/{item['dependency']['requirement_id']}"
            f"/source-impact/{item['dependency']['id']}/decisions"
        )
        body = dict(
            publication_state=item["publication_state"],
            expected_version=0,
            decision="retain_historical",
            reason="Reviewed retained historical applicability",
        )
        assert (
            client.post(
                decision_path, json=body, headers={"X-Fake-Actor-Id": "fake-reviewer"}
            ).status_code
            == 403
        )
        assert client.post(decision_path, json={**body, "reason": " "}).status_code == 422
        assert (
            client.post(decision_path, json={**body, "publication_state": "changed"}).status_code
            == 409
        )
        assert client.post(decision_path, json=body).status_code == 200
        assert client.post(decision_path, json=body).status_code == 409


def test_source_impact_lives_under_the_requirement_and_the_library_paths_are_gone(
    grounded: Grounded,
) -> None:
    """Source impact is requirement work (ADR-0099); the old library paths no longer answer."""
    container = grounded.container
    owner = FAKE_ACTORS[0]
    mine = container.create_requirement.execute(
        CreateRequirementInput("Mine", "XGPON coverage for bundles."), owner
    )
    container.analyze_requirement.execute(owner, mine.id)
    other = container.create_requirement.execute(
        CreateRequirementInput("Other", "Unrelated wording."), owner
    )
    grounded.withdraw()
    with TestClient(create_app(lambda: container)) as client:
        path = f"/requirements/{mine.id.value}/source-impact?active_only=true&limit=100"
        page = client.get(path)
        assert page.status_code == 200
        assert page.headers["Cache-Control"] == "private, no-store"
        legacy = client.get(f"/library/requirements/{mine.id.value}/source-impact")
        assert legacy.status_code == 404

        item = page.json()["items"][0]
        dependency = item["dependency"]["id"]
        body = dict(
            publication_state=item["publication_state"],
            expected_version=0,
            decision="retain_historical",
            reason="Reviewed retained historical applicability",
        )
        elsewhere = f"/requirements/{other.id.value}/source-impact/{dependency}/decisions"
        assert client.post(elsewhere, json=body).status_code == 404
        here = f"/requirements/{mine.id.value}/source-impact/{dependency}/decisions"
        decided = client.post(here, json=body)
        assert decided.status_code == 200
        assert decided.json()["decisions"][-1]["decision"] == "retain_historical"
        assert (
            client.post(f"/library/source-impact/{dependency}/decisions", json=body).status_code
            == 404
        )

        operations = client.get("/openapi.json").json()["paths"]
        assert not [path for path in operations if path.startswith("/library/")]
        assert "deprecated" not in operations["/requirements/{requirement_id}/source-impact"]["get"]
