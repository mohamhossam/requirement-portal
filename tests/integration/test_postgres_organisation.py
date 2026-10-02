"""The organisation catalogue survives restarts and serialises concurrent editors."""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from smb_requirement_agent.domain.organisation.catalogue import (
    OrganisationConflictError,
    Person,
    Squad,
    SquadSystemResource,
    ValueStream,
)
from smb_requirement_agent.infrastructure.persistence.migration_runner import run_migrations
from smb_requirement_agent.infrastructure.persistence.postgres_connector import (
    DirectPostgresConnector,
)
from smb_requirement_agent.infrastructure.persistence.postgres_organisation import (
    PostgresOrganisationRepository,
)
from smb_requirement_agent.infrastructure.time.fixed_clock import FixedClock

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_DATABASE_URL is not configured")
NOW = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)


def test_organisation_catalogue_round_trips_and_rejects_stale_revisions() -> None:
    assert DATABASE_URL is not None
    run_migrations(DATABASE_URL)
    repository = PostgresOrganisationRepository(
        DirectPostgresConnector(DATABASE_URL), FixedClock(NOW)
    )
    suffix = f"{datetime.now(UTC).timestamp():.0f}"
    person_id, stream_id, squad_id = f"p-{suffix}", f"vs-{suffix}", f"sq-{suffix}"

    repository.change(
        lambda current: (
            current.put_person(Person(person_id, "Layla"), None)
            .put_value_stream(ValueStream(stream_id, f"Retail {suffix}", person_id), None)
            .put_squad(
                Squad(
                    squad_id,
                    "Sales",
                    stream_id,
                    person_id,
                    (SquadSystemResource("bcrm", person_id),),
                ),
                None,
            )
        ),
        "amina",
        "seed",
        squad_id,
    )

    reloaded = PostgresOrganisationRepository(
        DirectPostgresConnector(DATABASE_URL), FixedClock(NOW)
    )
    squad = reloaded.load().squad(squad_id)
    assert squad.systems == (SquadSystemResource("bcrm", person_id),)
    assert reloaded.audit(1)[0].subject_id == squad_id
    with pytest.raises(OrganisationConflictError):
        reloaded.change(
            lambda current: current.put_squad(Squad(squad_id, "Stale", stream_id), 9),
            "amina",
            "save_squad",
            squad_id,
        )
    assert reloaded.load().squad(squad_id).name == "Sales"
