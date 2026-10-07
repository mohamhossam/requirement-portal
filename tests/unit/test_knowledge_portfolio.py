"""The corpus browser, portfolio findings and nudges for the Knowledge Center (B2).

Requirement work answers knowledge-portal over three service-token routes: the corpus row by
row, the findings still in force, and a nudge that asks both Requirements' owners to decide a
finding. Rows carry identity and state, plus a finding's one-line rationale; never an email, a
description, a passage or an evidence excerpt (ADR-0099 Amendment 1).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.errors import KnowledgeFindingNotFoundError
from smb_requirement_agent.application.ports.knowledge_portfolio import (
    FindingAge,
    IndexState,
    PersonName,
)
from smb_requirement_agent.application.use_cases.create_requirement import CreateRequirementInput
from smb_requirement_agent.domain.knowledge.entities import KnowledgeRelationshipKind
from smb_requirement_agent.domain.knowledge.errors import KnowledgeFindingConflictError
from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.interfaces.api.container import Container, build_container
from smb_requirement_agent.interfaces.api.main import create_app
from smb_requirement_agent.jobs.domain.entities import NotificationKind
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.conftest import FAKE_PROVIDER_SETTINGS
from tests.unit.workflow_helpers import drain_requirement_index

TOKEN = "k" * 40
SERVICE = {"Authorization": f"Bearer {TOKEN}"}
START = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)
AMINA, RAVI, OMAR = FAKE_ACTORS
XGPON = "Business customers order XGPON bundles via BCRM."


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(START)


@pytest.fixture
def timed(clock: FixedClock) -> Container:
    return build_container(FAKE_PROVIDER_SETTINGS, clock=clock)


def _requirement(
    container: Container, title: str, description: str, owner: ActorProfile = AMINA
) -> RequirementId:
    return container.create_requirement.execute(
        CreateRequirementInput(title=title, description=description), owner
    ).id


def _screen(container: Container, requirement_id: RequirementId) -> None:
    fingerprint = container.get_knowledge_review.execute(requirement_id).current_fingerprint
    drain_requirement_index(container)
    container.screen_requirement_knowledge.execute(AMINA, requirement_id, fingerprint)


def _duplicates(container: Container) -> tuple[RequirementId, RequirementId, str]:
    """Two owners' Requirements screened as possible duplicates; the finding's id."""
    canonical = _requirement(container, "XGPON bundles", XGPON, RAVI)
    candidate = _requirement(container, "XGPON bundles for offices", XGPON, AMINA)
    _screen(container, candidate)
    finding = container.get_knowledge_review.execute(candidate).findings[0]
    return canonical, candidate, finding.id.value


def _nudge(container: Container, finding_id: str) -> object:
    return container.nudge_finding_owners.execute(finding_id, OMAR.id.value, OMAR.display_name)


def _corpus(container: Container, **filters: object) -> list[str]:
    arguments: dict[str, object] = {
        "index_state": None,
        "owner_id": None,
        "text": "",
        "open_findings_only": False,
        "not_screened_for_days": None,
        "offset": 0,
        "limit": 50,
    }
    arguments.update(filters)
    page = container.knowledge_portfolio.corpus(**arguments)  # type: ignore[arg-type]
    return [item.title for item in page.items]


def test_each_requirement_is_a_row_of_identity_and_state(timed: Container) -> None:
    canonical, candidate, _ = _duplicates(timed)
    _requirement(timed, "Archive", "Old records.", RAVI)

    page = timed.knowledge_portfolio.corpus(
        index_state=None,
        owner_id=None,
        text="",
        open_findings_only=False,
        not_screened_for_days=None,
        offset=0,
        limit=50,
    )

    assert [item.title for item in page.items] == [
        "Archive",
        "XGPON bundles",
        "XGPON bundles for offices",
    ]
    archive, first, second = page.items
    assert archive.index_state is IndexState.WAITING
    assert first.index_state is second.index_state is IndexState.CURRENT
    assert first.owner == PersonName(RAVI.id.value, RAVI.display_name)
    assert second.owner == PersonName(AMINA.id.value, AMINA.display_name)
    assert (first.open_findings, second.open_findings) == (1, 1)
    assert second.last_screened_at == START
    assert first.last_screened_at is None
    assert page.next_offset is None
    assert {item.requirement_id for item in page.items} >= {canonical.value, candidate.value}


def test_the_corpus_filters_and_pages(timed: Container, clock: FixedClock) -> None:
    _duplicates(timed)
    _requirement(timed, "Archive", "Old records.", RAVI)

    assert _corpus(timed, owner_id=RAVI.id.value) == ["Archive", "XGPON bundles"]
    assert _corpus(timed, text="  offices ") == ["XGPON bundles for offices"]
    assert _corpus(timed, text="%") == []
    assert _corpus(timed, open_findings_only=True) == [
        "XGPON bundles",
        "XGPON bundles for offices",
    ]
    assert _corpus(timed, index_state=IndexState.WAITING) == ["Archive"]
    assert _corpus(timed, index_state=IndexState.CURRENT) == [
        "XGPON bundles",
        "XGPON bundles for offices",
    ]
    assert _corpus(timed, index_state=IndexState.FAILED) == []
    assert _corpus(timed, index_state=IndexState.REBUILD_REQUIRED) == []

    clock.set(START + timedelta(days=10))
    # Never screened, or screened before the cut-off.
    assert _corpus(timed, not_screened_for_days=30) == ["Archive", "XGPON bundles"]
    assert _corpus(timed, not_screened_for_days=7) == [
        "Archive",
        "XGPON bundles",
        "XGPON bundles for offices",
    ]

    first = timed.knowledge_portfolio.corpus(
        index_state=None,
        owner_id=None,
        text="",
        open_findings_only=False,
        not_screened_for_days=None,
        offset=0,
        limit=2,
    )
    rest = timed.knowledge_portfolio.corpus(
        index_state=None,
        owner_id=None,
        text="",
        open_findings_only=False,
        not_screened_for_days=None,
        offset=2,
        limit=2,
    )
    assert (len(first.items), first.next_offset) == (2, 2)
    assert ([item.title for item in rest.items], rest.next_offset) == (
        ["XGPON bundles for offices"],
        None,
    )


def test_a_finding_row_names_both_sides_and_the_judges_rationale(timed: Container) -> None:
    canonical, candidate, finding_id = _duplicates(timed)
    stored = timed.knowledge_repository.get_finding(
        timed.get_knowledge_review.execute(candidate).findings[0].id
    )
    assert stored is not None

    page = timed.knowledge_portfolio.findings(
        kind=None, age=None, owner_id=None, offset=0, limit=50
    )

    (row,) = page.items
    assert row.finding_id == finding_id
    assert row.kind is KnowledgeRelationshipKind.POSSIBLE_DUPLICATE
    assert row.rationale == stored.rationale
    assert (row.raised_at, row.age) == (START, FindingAge.UNDER_7_DAYS)
    assert (row.subject.requirement_id, row.related.requirement_id) == (
        candidate.value,
        canonical.value,
    )
    assert row.subject.owner == PersonName(AMINA.id.value, AMINA.display_name)
    assert row.related.owner == PersonName(RAVI.id.value, RAVI.display_name)
    assert (row.last_nudge, row.next_nudge_at) == (None, None)


def test_findings_filter_by_kind_age_and_either_owner(timed: Container, clock: FixedClock) -> None:
    _duplicates(timed)

    def ids(**filters: object) -> int:
        arguments: dict[str, object] = {"kind": None, "age": None, "owner_id": None}
        arguments.update(filters)
        return len(
            timed.knowledge_portfolio.findings(
                offset=0,
                limit=50,
                **arguments,  # type: ignore[arg-type]
            ).items
        )

    assert ids(kind=KnowledgeRelationshipKind.POSSIBLE_DUPLICATE) == 1
    assert ids(kind=KnowledgeRelationshipKind.POSSIBLE_CONTRADICTION) == 0
    assert ids(owner_id=AMINA.id.value) == ids(owner_id=RAVI.id.value) == 1
    assert ids(owner_id=OMAR.id.value) == 0
    assert ids(age=FindingAge.UNDER_7_DAYS) == 1

    clock.set(START + timedelta(days=31))
    assert ids(age=FindingAge.UNDER_7_DAYS) == ids(age=FindingAge.FROM_7_TO_30_DAYS) == 0
    assert ids(age=FindingAge.OVER_30_DAYS) == 1
    (row,) = timed.knowledge_portfolio.findings(
        kind=None, age=None, owner_id=None, offset=0, limit=50
    ).items
    assert row.age is FindingAge.OVER_30_DAYS


def test_a_decided_or_outdated_finding_is_not_listed(timed: Container) -> None:
    canonical, candidate, _ = _duplicates(timed)
    stored = timed.requirement_repository.get(canonical)
    assert stored is not None

    timed.requirement_repository.save(
        stored.update(stored.title, stored.description, updated_at=START + timedelta(hours=1))
    )

    assert not timed.knowledge_portfolio.findings(
        kind=None, age=None, owner_id=None, offset=0, limit=50
    ).items
    assert _corpus(timed, open_findings_only=True) == []


def test_a_nudge_notifies_both_owners_without_an_ai_job(timed: Container) -> None:
    canonical, candidate, finding_id = _duplicates(timed)

    result = timed.nudge_finding_owners.execute(finding_id, OMAR.id.value, OMAR.display_name)

    assert result.nudged_at == START
    assert result.next_nudge_at == START + timedelta(days=7)
    assert set(result.recipients) == {AMINA.display_name, RAVI.display_name}
    for owner, requirement in ((AMINA, candidate), (RAVI, canonical)):
        (notification,) = [
            item
            for item in timed.notification_repository.list_for_actor(owner.id)
            if item.kind is NotificationKind.KNOWLEDGE_FINDINGS_NUDGE
        ]
        assert notification.job_id is None
        assert notification.resource_path == f"/requirements/{requirement.value}/knowledge"
        assert notification.message.startswith("Omar Observer asks you to decide a possible")
    (row,) = timed.knowledge_portfolio.findings(
        kind=None, age=None, owner_id=None, offset=0, limit=50
    ).items
    assert row.last_nudge is not None
    assert (row.last_nudge.at, row.last_nudge.by) == (START, OMAR.display_name)
    assert row.next_nudge_at == START + timedelta(days=7)


def test_a_finding_is_nudged_at_most_once_a_week(timed: Container, clock: FixedClock) -> None:
    _, _, finding_id = _duplicates(timed)
    _nudge(timed, finding_id)

    clock.set(START + timedelta(days=6, hours=23))
    with pytest.raises(KnowledgeFindingConflictError, match="again from 13 Oct 2026"):
        _nudge(timed, finding_id)

    clock.set(START + timedelta(days=7))
    _nudge(timed, finding_id)
    nudges = [
        item
        for item in timed.notification_repository.list_for_actor(AMINA.id)
        if item.kind is NotificationKind.KNOWLEDGE_FINDINGS_NUDGE
    ]
    assert len(nudges) == 2


def test_one_owner_of_both_requirements_is_notified_once(timed: Container) -> None:
    _requirement(timed, "XGPON bundles", XGPON)
    candidate = _requirement(timed, "XGPON bundles for offices", XGPON)
    _screen(timed, candidate)
    finding = timed.get_knowledge_review.execute(candidate).findings[0]

    result = timed.nudge_finding_owners.execute(finding.id.value, OMAR.id.value, OMAR.display_name)

    assert result.recipients == (AMINA.display_name,)


def test_a_decided_or_missing_finding_cannot_be_nudged(timed: Container) -> None:
    _, candidate, finding_id = _duplicates(timed)
    finding = timed.get_knowledge_review.execute(candidate).findings[0]
    timed.decide_knowledge_finding.execute(
        candidate, finding.id, "duplicate", finding.version, AMINA
    )

    with pytest.raises(KnowledgeFindingConflictError, match="no longer open"):
        _nudge(timed, finding_id)
    with pytest.raises(KnowledgeFindingNotFoundError):
        _nudge(timed, "missing")
    assert not [
        item
        for item in timed.notification_repository.list_for_actor(ActorId(RAVI.id.value))
        if item.kind is NotificationKind.KNOWLEDGE_FINDINGS_NUDGE
    ]


def test_the_routes_need_the_service_token_and_never_carry_an_email(timed: Container) -> None:
    _, _, finding_id = _duplicates(timed)
    serving = replace(timed, settings=replace(timed.settings, knowledge_service_token=TOKEN))
    nudge = f"/internal/knowledge/findings/{finding_id}/nudge"
    body = {"actor_id": OMAR.id.value, "actor_name": OMAR.display_name}

    with TestClient(create_app(lambda: serving)) as client:
        refused = [
            client.get("/internal/knowledge/corpus").status_code,
            client.get("/internal/knowledge/findings").status_code,
            client.post(nudge, json=body).status_code,
        ]
        corpus = client.get("/internal/knowledge/corpus", params={"q": "xgpon"}, headers=SERVICE)
        findings = client.get(
            "/internal/knowledge/findings", params={"age": "under_7_days"}, headers=SERVICE
        )
        nudged = client.post(nudge, json=body, headers=SERVICE)
        again = client.post(nudge, json=body, headers=SERVICE)
        missing = client.post(
            "/internal/knowledge/findings/missing/nudge", json=body, headers=SERVICE
        )
        invalid = client.get("/internal/knowledge/corpus", params={"limit": 101}, headers=SERVICE)

    assert refused == [401, 401, 401]
    assert corpus.status_code == findings.status_code == nudged.status_code == 200
    assert len(corpus.json()["items"]) == 2
    assert findings.json()["items"][0]["rationale"]
    assert set(findings.json()["items"][0]["subject"]) == {"requirement_id", "title", "owner"}
    assert set(nudged.json()["recipients"]) == {AMINA.display_name, RAVI.display_name}
    assert again.status_code == 409
    assert "again from" in again.json()["message"]
    assert missing.status_code == 404
    assert invalid.status_code == 422
    for response in (corpus, findings, nudged):
        assert "@" not in response.text
        assert XGPON not in response.text
