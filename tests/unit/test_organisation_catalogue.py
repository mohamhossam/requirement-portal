"""Value streams own products and squads; squads staff architecture systems with people."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.application.ports.architecture_knowledge import ArchitectureQuery
from smb_requirement_agent.application.ports.identity import Actor
from smb_requirement_agent.application.use_cases.organisation_catalogue import (
    ManageOrganisationCatalogue,
)
from smb_requirement_agent.application.use_cases.resolve_architecture_knowledge import (
    ResolveArchitectureKnowledge,
)
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError
from smb_requirement_agent.domain.organisation.catalogue import (
    InvalidOrganisationError,
    OrganisationCatalogue,
    OrganisationConflictError,
    Person,
    Product,
    Squad,
    SquadSystemResource,
    ValueStream,
)
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import (
    InMemoryEvidenceIndex,
)
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.reasoning import FakeArchitectureReasoner
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.architecture.yaml_knowledge import (
    YamlArchitectureKnowledge,
    default_knowledge_path,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_organisation import (
    InMemoryOrganisationRepository,
)

MAINTAINER = Actor("amina", frozenset({"knowledge_maintainer"}))
READER = Actor("ravi", frozenset({"knowledge_reader"}))
OWNER_HEADERS = {"X-Fake-Actor-Id": "fake-owner"}
READER_HEADERS = {"X-Fake-Actor-Id": "fake-reviewer"}
NOW = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)


def _catalogue() -> OrganisationCatalogue:
    return (
        OrganisationCatalogue()
        .put_person(Person("layla", "Layla Lead", "layla@example.test", "Delivery"), None)
        .put_person(Person("sam", "Sam Scrum", team="Agile office"), None)
        .put_person(Person("bea", "Bea Backend", team="CRM team"), None)
        .put_value_stream(ValueStream("retail", "Retail", "layla"), None)
        .put_product(Product("ordering", "retail", "Ordering", system_ids=("bcrm",)), None)
        .put_squad(
            Squad(
                "sales",
                "Sales squad",
                "retail",
                "sam",
                (SquadSystemResource("bcrm", "bea"), SquadSystemResource("gis")),
            ),
            None,
        )
    )


def test_a_system_can_sit_in_several_squads_with_its_value_streams_and_products() -> None:
    catalogue = _catalogue().put_squad(
        Squad("care", "Care squad", "retail", None, (SquadSystemResource("bcrm", "bea"),)),
        None,
    )

    owned = catalogue.ownership("bcrm")

    assert [item.name for item in owned.squads] == ["Care squad", "Sales squad"]
    assert [item.name for item in owned.products] == ["Ordering"]
    assert [item.name for item in owned.value_streams] == ["Retail"]
    assert catalogue.ownership("unknown").squads == ()


def test_invariants_protect_references_names_and_people() -> None:
    catalogue = _catalogue()

    with pytest.raises(InvalidOrganisationError, match="Unknown value stream"):
        catalogue.put_squad(Squad("orphan", "Orphan", "missing"), None)
    with pytest.raises(InvalidOrganisationError, match="already used"):
        catalogue.put_squad(Squad("again", "sales SQUAD", "retail"), None)
    with pytest.raises(InvalidOrganisationError, match="each system once"):
        Squad("dup", "Dup", "retail", None, (SquadSystemResource("x"), SquadSystemResource("x")))
    with pytest.raises(InvalidOrganisationError, match="inactive"):
        catalogue.put_person(Person("bea", "Bea Backend", active=False), 1)
    with pytest.raises(InvalidOrganisationError, match="not a known person"):
        catalogue.put_value_stream(ValueStream("b2b", "B2B", "nobody"), None)
    with pytest.raises(InvalidOrganisationError, match="more than one person"):
        catalogue.put_person(Person("dupe", "Dupe", "LAYLA@example.test"), None)
    with pytest.raises(InvalidOrganisationError, match="products and squads first"):
        catalogue.remove_value_stream("retail", 1)


def test_records_are_revision_checked() -> None:
    catalogue = _catalogue()

    updated = catalogue.put_squad(Squad("sales", "Sales and service", "retail"), 1)

    assert updated.squad("sales").revision == 2
    with pytest.raises(OrganisationConflictError, match="changed"):
        updated.put_squad(Squad("sales", "Stale", "retail"), 1)
    with pytest.raises(OrganisationConflictError, match="already exists"):
        updated.put_squad(Squad("sales", "New", "retail"), None)
    assert updated.remove_squad("sales", 2).squads == ()


def _manage() -> ManageOrganisationCatalogue:
    return ManageOrganisationCatalogue(
        InMemoryOrganisationRepository(FixedClock(NOW)),
        InMemoryArchitectureKnowledgeRepository(seed_knowledge()),
    )


def test_links_must_name_active_catalogue_systems_and_readers_do_not_see_emails() -> None:
    manage = _manage()
    manage.save_person(Person("layla", "Layla Lead", "layla@example.test"), None, MAINTAINER)
    manage.save_value_stream(ValueStream("retail", "Retail", "layla"), None, MAINTAINER)

    with pytest.raises(InvalidOrganisationError, match="not in the active architecture"):
        manage.save_squad(
            Squad("sales", "Sales", "retail", None, (SquadSystemResource("made-up"),)),
            None,
            MAINTAINER,
        )
    with pytest.raises(AuthorizationDeniedError):
        manage.save_person(Person("x", "X"), None, READER)

    manage.save_squad(
        Squad("sales", "Sales", "retail", None, (SquadSystemResource("bcrm"),)), None, MAINTAINER
    )

    assert manage.view(READER).person("layla").email is None
    assert manage.view(MAINTAINER).person("layla").email == "layla@example.test"
    assert [event.action for event in manage.audit(MAINTAINER)] == [
        "save_squad",
        "save_value_stream",
        "save_person",
    ]


def test_mapping_records_squads_value_streams_and_products_from_the_organisation() -> None:
    releases = InMemoryArchitectureKnowledgeRepository(seed_knowledge())
    organisation = InMemoryOrganisationRepository(FixedClock(NOW))
    organisation.change(lambda _: _catalogue(), "amina", "seed", "all")
    resolver = ResolveArchitectureKnowledge(
        releases,
        InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer()),
        FakeArchitectureReasoner(),
        YamlArchitectureKnowledge(default_knowledge_path()),
        organisation,
    )

    result = resolver.match(
        ArchitectureQuery(text=("Update customers",), declared_systems=("BCRM", "CPP"))
    )

    by_id = {item.id: item for item in result.systems}
    assert [item.name for item in by_id["bcrm"].squads] == ["Sales squad"]
    assert [item.name for item in by_id["bcrm"].value_streams] == ["Retail"]
    assert [item.name for item in by_id["bcrm"].products] == ["Ordering"]
    declared = next(item for item in result.systems if not item.catalogued)
    assert declared.squads == ()


def test_organisation_api_round_trip_and_permissions(client: TestClient) -> None:
    person = client.post(
        "/organisation/people",
        json={"person": {"id": "layla", "name": "Layla Lead", "email": "layla@example.test"}},
        headers=OWNER_HEADERS,
    )
    assert person.status_code == 201
    stream = client.post(
        "/organisation/value-streams",
        json={"value_stream": {"id": "retail", "name": "Retail", "lead_person_id": "layla"}},
        headers=OWNER_HEADERS,
    )
    assert stream.status_code == 201
    squad = client.post(
        "/organisation/squads",
        json={
            "squad": {
                "id": "sales",
                "name": "Sales squad",
                "value_stream_id": "retail",
                "scrum_master_person_id": "layla",
                "systems": [{"system_id": "bcrm", "person_id": "layla"}],
            }
        },
        headers=OWNER_HEADERS,
    )
    assert squad.status_code == 201

    stale = client.put(
        "/organisation/squads/sales",
        json={
            "expected_revision": 7,
            "squad": {"id": "sales", "name": "Renamed", "value_stream_id": "retail"},
        },
        headers=OWNER_HEADERS,
    )
    assert stale.status_code == 409
    mismatched = client.put(
        "/organisation/squads/other",
        json={
            "expected_revision": 1,
            "squad": {"id": "sales", "name": "Renamed", "value_stream_id": "retail"},
        },
        headers=OWNER_HEADERS,
    )
    assert mismatched.status_code == 422

    read = client.get("/organisation", headers=READER_HEADERS)
    assert read.status_code == 200
    assert read.json()["people"][0]["email"] is None
    assert read.json()["squads"][0]["systems"] == [{"system_id": "bcrm", "person_id": "layla"}]
    ownership = client.get("/organisation/systems/bcrm/ownership", headers=READER_HEADERS)
    assert [item["name"] for item in ownership.json()["squads"]] == ["Sales squad"]
    assert (
        client.post(
            "/organisation/people",
            json={"person": {"id": "x", "name": "X"}},
            headers=READER_HEADERS,
        ).status_code
        == 403
    )
    removed = client.request(
        "DELETE",
        "/organisation/squads/sales",
        json={"expected_revision": 1},
        headers=OWNER_HEADERS,
    )
    assert removed.status_code == 200
    assert removed.json()["squads"] == []
