"""Unit tests for the Requirement domain model.

Pure, fast, no I/O.  Tests cover value-object validation, entity creation,
and the update behaviour on the aggregate.
"""

import pytest

from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.requirements.domain.requirement.errors import (
    InvalidRequirementDescriptionError,
    InvalidRequirementTitleError,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


def _valid_requirement() -> Requirement:
    return Requirement(
        id=RequirementId("test-id"),
        title=RequirementTitle("High Speed Business Pro XGPON"),
        description=RequirementDescription(
            "The new bundles created with High Speed Internet "
            "shall be available in channel for ordering."
        ),
        status=RequirementStatus.DRAFT,
    )


class TestRequirementTitle:
    def test_empty_string_is_rejected(self) -> None:
        with pytest.raises(InvalidRequirementTitleError):
            RequirementTitle("")

    def test_blank_string_is_rejected(self) -> None:
        with pytest.raises(InvalidRequirementTitleError):
            RequirementTitle("   ")

    def test_valid_title_is_accepted(self) -> None:
        title = RequirementTitle("High Speed Business Pro XGPON")
        assert title.value == "High Speed Business Pro XGPON"

    def test_surrounding_whitespace_is_stripped(self) -> None:
        title = RequirementTitle("  My Requirement  ")
        assert title.value == "My Requirement"


class TestRequirementDescription:
    def test_empty_string_is_rejected(self) -> None:
        with pytest.raises(InvalidRequirementDescriptionError):
            RequirementDescription("")

    def test_blank_string_is_rejected(self) -> None:
        with pytest.raises(InvalidRequirementDescriptionError):
            RequirementDescription("   ")

    def test_valid_description_is_accepted(self) -> None:
        desc = RequirementDescription("Detailed requirement text.")
        assert desc.value == "Detailed requirement text."

    def test_surrounding_whitespace_is_stripped(self) -> None:
        desc = RequirementDescription("  Some description.  ")
        assert desc.value == "Some description."


class TestRequirement:
    def test_valid_requirement_is_created_with_draft_status(self) -> None:
        req = _valid_requirement()
        assert req.status == RequirementStatus.DRAFT

    def test_update_returns_new_requirement_with_updated_fields(self) -> None:
        req = _valid_requirement()
        updated = req.update(
            title=RequirementTitle("Updated Title"),
            description=RequirementDescription("Updated description text."),
        )
        assert updated.title.value == "Updated Title"
        assert updated.description.value == "Updated description text."

    def test_update_preserves_id_and_status(self) -> None:
        req = _valid_requirement()
        updated = req.update(
            title=RequirementTitle("New Title"),
            description=RequirementDescription("New description."),
        )
        assert updated.id == req.id
        assert updated.status == req.status

    def test_update_does_not_mutate_original(self) -> None:
        req = _valid_requirement()
        req.update(
            title=RequirementTitle("Updated Title"),
            description=RequirementDescription("Updated description text."),
        )
        assert req.title.value == "High Speed Business Pro XGPON"

    def test_update_rejects_empty_title(self) -> None:
        req = _valid_requirement()
        with pytest.raises(InvalidRequirementTitleError):
            req.update(
                title=RequirementTitle(""),
                description=RequirementDescription("Valid description."),
            )

    def test_update_rejects_blank_description(self) -> None:
        req = _valid_requirement()
        with pytest.raises(InvalidRequirementDescriptionError):
            req.update(
                title=RequirementTitle("Valid Title"),
                description=RequirementDescription("   "),
            )
