"""Requirement aggregate root."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from smb_requirement_agent.domain.requirement.errors import DuplicateRequirementStateError
from smb_requirement_agent.domain.requirement.intake_limits import require_within_intake_limits
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
    RequirementVersion,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class AnalysisEligibility:
    """Explains whether source content is complete enough for analysis."""

    eligible: bool
    missing_fields: tuple[str, ...]


@dataclass(frozen=True)
class Requirement:
    """A business requirement submitted by a Business Owner.

    This is a draft business input that has not yet been analysed,
    decomposed into Epics, Features, or Stories.
    """

    id: RequirementId
    title: RequirementTitle
    description: RequirementDescription
    status: RequirementStatus
    desired_outcome: RequirementContext | None = None
    customer_context: RequirementContext | None = None
    channels: tuple[RequirementContext, ...] = ()
    systems: tuple[RequirementContext, ...] = ()
    business_rules: tuple[RequirementContext, ...] = ()
    constraints: tuple[RequirementContext, ...] = ()
    version: RequirementVersion = RequirementVersion(1)
    updated_at: datetime | None = None
    duplicate_of_requirement_id: RequirementId | None = None

    def __post_init__(self) -> None:
        if self.status is RequirementStatus.DUPLICATE:
            if self.duplicate_of_requirement_id is None:
                raise DuplicateRequirementStateError(
                    "A duplicate Requirement must link to its canonical Requirement."
                )
            if self.duplicate_of_requirement_id == self.id:
                raise DuplicateRequirementStateError(
                    "A Requirement cannot be a duplicate of itself."
                )
        elif self.duplicate_of_requirement_id is not None:
            raise DuplicateRequirementStateError(
                "Only a duplicate Requirement may carry a canonical link."
            )

    @property
    def analysis_eligibility(self) -> AnalysisEligibility:
        if self.status is RequirementStatus.DUPLICATE:
            return AnalysisEligibility(False, ("duplicate_requirement",))
        missing = () if self.description.value else ("description",)
        return AnalysisEligibility(not missing, missing)

    def close_as_duplicate(self, canonical_id: RequirementId, at: datetime) -> Requirement:
        if canonical_id == self.id:
            raise DuplicateRequirementStateError("A Requirement cannot be a duplicate of itself.")
        return Requirement(
            id=self.id,
            title=self.title,
            description=self.description,
            status=RequirementStatus.DUPLICATE,
            desired_outcome=self.desired_outcome,
            customer_context=self.customer_context,
            channels=self.channels,
            systems=self.systems,
            business_rules=self.business_rules,
            constraints=self.constraints,
            version=self.version.next(),
            updated_at=at,
            duplicate_of_requirement_id=canonical_id,
        )

    def require_active(self) -> None:
        if self.status is RequirementStatus.DUPLICATE:
            raise DuplicateRequirementStateError(
                "This Requirement is closed as a duplicate; use its canonical Requirement."
            )

    def update(
        self,
        title: RequirementTitle,
        description: RequirementDescription,
        desired_outcome: RequirementContext | None = None,
        customer_context: RequirementContext | None = None,
        channels: tuple[RequirementContext, ...] = (),
        systems: tuple[RequirementContext, ...] = (),
        business_rules: tuple[RequirementContext, ...] = (),
        constraints: tuple[RequirementContext, ...] = (),
        updated_at: datetime | None = None,
    ) -> Requirement:
        """Return a new Requirement with updated title and description.

        The requirement ID and status are preserved. Invariants are enforced by
        the value objects supplied, and the edited content by the intake limits.
        """
        require_within_intake_limits(
            title=title.value,
            description=description.value,
            desired_outcome=desired_outcome.value if desired_outcome else None,
            customer_context=customer_context.value if customer_context else None,
            lists={
                "channels": (item.value for item in channels),
                "systems": (item.value for item in systems),
                "business_rules": (item.value for item in business_rules),
                "constraints": (item.value for item in constraints),
            },
        )
        return Requirement(
            id=self.id,
            title=title,
            description=description,
            status=self.status,
            desired_outcome=desired_outcome,
            customer_context=customer_context,
            channels=channels,
            systems=systems,
            business_rules=business_rules,
            constraints=constraints,
            version=self.version.next(),
            updated_at=updated_at,
            duplicate_of_requirement_id=self.duplicate_of_requirement_id,
        )


@dataclass(frozen=True)
class RequirementDraft:
    """Resumable partial intake that cannot enter analysis directly."""

    id: RequirementId
    title: str
    description: str
    desired_outcome: str
    customer_context: str
    channels: tuple[str, ...]
    systems: tuple[str, ...]
    business_rules: tuple[str, ...]
    constraints: tuple[str, ...]
    version: RequirementVersion
    updated_at: datetime

    def __post_init__(self) -> None:
        for field in ("title", "description", "desired_outcome", "customer_context"):
            object.__setattr__(self, field, getattr(self, field).strip())
        for field in ("channels", "systems", "business_rules", "constraints"):
            values = tuple(item.strip() for item in getattr(self, field) if item.strip())
            object.__setattr__(self, field, values)

    @property
    def analysis_eligibility(self) -> AnalysisEligibility:
        missing = tuple(
            name
            for name, value in (
                ("title", self.title),
                ("description", self.description),
            )
            if not value
        )
        return AnalysisEligibility(not missing, missing)

    def revise(
        self,
        *,
        title: str,
        description: str,
        desired_outcome: str,
        customer_context: str,
        channels: tuple[str, ...],
        systems: tuple[str, ...],
        business_rules: tuple[str, ...],
        constraints: tuple[str, ...],
        updated_at: datetime,
    ) -> RequirementDraft:
        require_within_intake_limits(
            title=title,
            description=description,
            desired_outcome=desired_outcome,
            customer_context=customer_context,
            lists={
                "channels": channels,
                "systems": systems,
                "business_rules": business_rules,
                "constraints": constraints,
            },
        )
        return RequirementDraft(
            id=self.id,
            title=title,
            description=description,
            desired_outcome=desired_outcome,
            customer_context=customer_context,
            channels=channels,
            systems=systems,
            business_rules=business_rules,
            constraints=constraints,
            version=self.version.next(),
            updated_at=updated_at,
        )
