"""Unit tests for Requirement use cases.

Uses InMemoryRequirementRepository as a test double.
No live network, database, or LLM calls.
"""

import pytest
from smb_kernel.time.fixed import FixedClock

from smb_requirement_agent.identity.infrastructure.fake_identity import FAKE_ACTORS
from smb_requirement_agent.identity.infrastructure.in_memory_identity import (
    InMemoryAccessRepository,
)
from smb_requirement_agent.requirements.application.errors import RequirementNotFoundError
from smb_requirement_agent.requirements.application.use_cases.create_requirement import (
    CreateRequirement,
    CreateRequirementInput,
)
from smb_requirement_agent.requirements.application.use_cases.get_requirement import GetRequirement
from smb_requirement_agent.requirements.application.use_cases.update_requirement import (
    UpdateRequirement,
    UpdateRequirementInput,
)
from smb_requirement_agent.requirements.domain.requirement.errors import (
    InvalidRequirementDescriptionError,
    InvalidRequirementTitleError,
)
from smb_requirement_agent.requirements.infrastructure.in_memory_document_repository import (
    InMemoryDocumentRepository,
)
from smb_requirement_agent.requirements.infrastructure.in_memory_requirement_repository import (
    InMemoryRequirementRepository,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.conftest import TEST_NOW, make_event_publisher
from tests.unit.access_service import access_service_for
from tests.unit.owned_requirement_creator import OwnedRequirementCreator
from tests.unit.transaction_stub import NoOpTransactionManager


def _make_repo() -> InMemoryRequirementRepository:
    return InMemoryRequirementRepository()


class TestCreateRequirement:
    def test_valid_input_creates_and_returns_requirement(self) -> None:
        repo = _make_repo()
        use_case = CreateRequirement(repo)

        result = use_case.execute(
            CreateRequirementInput(
                title="High Speed Business Pro XGPON",
                description=(
                    "Bundles created with High Speed Internet shall be available for ordering."
                ),
            )
        )

        assert result.title.value == "High Speed Business Pro XGPON"
        assert result.status.value == "draft"
        assert result.id.value != ""

    def test_created_requirement_is_stored_in_repository(self) -> None:
        repo = _make_repo()
        use_case = CreateRequirement(repo)

        result = use_case.execute(CreateRequirementInput(title="Title", description="Description."))

        stored = repo.get(result.id)
        assert stored is not None
        assert stored.id == result.id

    def test_empty_title_raises_domain_error(self) -> None:
        repo = _make_repo()
        use_case = CreateRequirement(repo)

        with pytest.raises(InvalidRequirementTitleError):
            use_case.execute(CreateRequirementInput(title="", description="Valid."))

    def test_blank_description_raises_domain_error(self) -> None:
        repo = _make_repo()
        use_case = CreateRequirement(repo)

        with pytest.raises(InvalidRequirementDescriptionError):
            use_case.execute(CreateRequirementInput(title="Title", description="  "))


class TestGetRequirement:
    def test_existing_requirement_is_returned(self) -> None:
        repo = _make_repo()
        create = CreateRequirement(repo)
        get = GetRequirement(repo)

        created = create.execute(CreateRequirementInput(title="Title", description="Description."))

        retrieved = get.execute(created.id)
        assert retrieved.id == created.id
        assert retrieved.title.value == "Title"

    def test_unknown_id_raises_not_found_error(self) -> None:
        repo = _make_repo()
        use_case = GetRequirement(repo)

        with pytest.raises(RequirementNotFoundError):
            use_case.execute(RequirementId("nonexistent-id"))


class TestUpdateRequirement:
    def test_valid_update_persists_changes(self) -> None:
        repo = _make_repo()
        access = InMemoryAccessRepository()
        create = OwnedRequirementCreator(repo, access, FAKE_ACTORS[0], FixedClock(TEST_NOW))
        update = UpdateRequirement(
            repo,
            make_event_publisher(),
            FixedClock(TEST_NOW),
            NoOpTransactionManager(),
            authorization=access_service_for(repo, access),
            documents=InMemoryDocumentRepository(),
        )
        get = GetRequirement(repo)

        created = create.execute(
            CreateRequirementInput(title="Original Title", description="Original description.")
        )

        updated = update.execute(
            FAKE_ACTORS[0],
            created.id,
            UpdateRequirementInput(
                title="Updated Title", description="Updated description.", expected_version=1
            ),
        )

        assert updated.title.value == "Updated Title"
        assert updated.description.value == "Updated description."
        assert updated.id == created.id

        # Verify the repository reflects the update.
        retrieved = get.execute(created.id)
        assert retrieved.title.value == "Updated Title"

    def test_unknown_id_raises_not_found_error(self) -> None:
        repo = _make_repo()
        access = InMemoryAccessRepository()
        use_case = UpdateRequirement(
            repo,
            make_event_publisher(),
            FixedClock(TEST_NOW),
            NoOpTransactionManager(),
            authorization=access_service_for(repo, access),
            documents=InMemoryDocumentRepository(),
        )

        with pytest.raises(RequirementNotFoundError):
            use_case.execute(
                FAKE_ACTORS[0],
                RequirementId("nonexistent-id"),
                UpdateRequirementInput(
                    title="Title", description="Description.", expected_version=1
                ),
            )

    def test_update_with_empty_title_raises_domain_error(self) -> None:
        repo = _make_repo()
        access = InMemoryAccessRepository()
        create = OwnedRequirementCreator(repo, access, FAKE_ACTORS[0], FixedClock(TEST_NOW))
        update = UpdateRequirement(
            repo,
            make_event_publisher(),
            FixedClock(TEST_NOW),
            NoOpTransactionManager(),
            authorization=access_service_for(repo, access),
            documents=InMemoryDocumentRepository(),
        )

        created = create.execute(CreateRequirementInput(title="Title", description="Description."))

        with pytest.raises(InvalidRequirementTitleError):
            update.execute(
                FAKE_ACTORS[0],
                created.id,
                UpdateRequirementInput(
                    title="", description="Valid description.", expected_version=1
                ),
            )

    def test_update_with_blank_description_raises_domain_error(self) -> None:
        repo = _make_repo()
        access = InMemoryAccessRepository()
        create = OwnedRequirementCreator(repo, access, FAKE_ACTORS[0], FixedClock(TEST_NOW))
        update = UpdateRequirement(
            repo,
            make_event_publisher(),
            FixedClock(TEST_NOW),
            NoOpTransactionManager(),
            authorization=access_service_for(repo, access),
            documents=InMemoryDocumentRepository(),
        )

        created = create.execute(CreateRequirementInput(title="Title", description="Description."))

        with pytest.raises(InvalidRequirementDescriptionError):
            update.execute(
                FAKE_ACTORS[0],
                created.id,
                UpdateRequirementInput(title="Title", description="   ", expected_version=1),
            )
