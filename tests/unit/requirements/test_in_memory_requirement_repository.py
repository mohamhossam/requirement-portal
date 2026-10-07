"""Contract tests for InMemoryRequirementRepository.

Verifies that the adapter fulfils the RequirementRepositoryPort contract:
add/get round trip, save/get round trip, unknown-ID behaviour, and
duplicate-add rejection.
"""

import pytest

from smb_requirement_agent.application.errors import DuplicateRequirementError
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.requirements.infrastructure.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def _make_requirement(req_id: str = "req-1") -> Requirement:
    return Requirement(
        id=RequirementId(req_id),
        title=RequirementTitle("Test Requirement"),
        description=RequirementDescription("A description of the requirement."),
        status=RequirementStatus.DRAFT,
    )


class TestInMemoryRequirementRepository:
    def test_add_and_get_round_trip(self) -> None:
        repo = InMemoryRequirementRepository()
        req = _make_requirement()

        repo.add(req)

        retrieved = repo.get(RequirementId("req-1"))
        assert retrieved is not None
        assert retrieved.id.value == "req-1"
        assert retrieved.title.value == "Test Requirement"

    def test_get_unknown_id_returns_none(self) -> None:
        repo = InMemoryRequirementRepository()

        result = repo.get(RequirementId("not-there"))

        assert result is None

    def test_get_returns_none_for_empty_repository(self) -> None:
        repo = InMemoryRequirementRepository()

        result = repo.get(RequirementId("any-id"))

        assert result is None

    def test_save_updates_existing_requirement(self) -> None:
        repo = InMemoryRequirementRepository()
        req = _make_requirement()
        repo.add(req)

        updated = Requirement(
            id=req.id,
            title=RequirementTitle("Updated Title"),
            description=req.description,
            status=req.status,
        )
        repo.save(updated)

        retrieved = repo.get(req.id)
        assert retrieved is not None
        assert retrieved.title.value == "Updated Title"

    def test_duplicate_add_raises_error(self) -> None:
        repo = InMemoryRequirementRepository()
        req = _make_requirement()
        repo.add(req)

        with pytest.raises(DuplicateRequirementError):
            repo.add(req)

    def test_two_distinct_requirements_coexist(self) -> None:
        repo = InMemoryRequirementRepository()
        repo.add(_make_requirement("req-1"))
        repo.add(_make_requirement("req-2"))

        assert repo.get(RequirementId("req-1")) is not None
        assert repo.get(RequirementId("req-2")) is not None

    def test_list_all_is_empty_for_a_fresh_repository(self) -> None:
        assert InMemoryRequirementRepository().list_all() == []

    def test_list_all_returns_every_requirement_newest_first(self) -> None:
        repo = InMemoryRequirementRepository()
        repo.add(_make_requirement("req-1"))
        repo.add(_make_requirement("req-2"))

        listed = repo.list_all()

        assert [item.id.value for item in listed] == ["req-2", "req-1"]
