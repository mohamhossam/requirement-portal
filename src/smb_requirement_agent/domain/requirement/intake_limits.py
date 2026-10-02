"""How much source content one Requirement or draft may carry.

The whole source is stored, versioned, indexed and sent to a model on every
analysis, so an unbounded field is an unbounded cost. The limits are generous:
the description matches the default analysis document budget, so a limit is
reached only by content analysis could not use anyway.

They apply when content is submitted or edited, not when a stored Requirement
is read back, so records created before the limits existed stay readable.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from smb_requirement_agent.domain.requirement.errors import RequirementIntakeTooLargeError

MAX_TITLE_CHARACTERS = 300
MAX_DESCRIPTION_CHARACTERS = 60_000
MAX_CONTEXT_CHARACTERS = 10_000
MAX_LIST_ITEMS = 50
MAX_LIST_ITEM_CHARACTERS = 1_000

LIST_FIELDS = ("channels", "systems", "business_rules", "constraints")


def require_within_intake_limits(
    *,
    title: str,
    description: str,
    desired_outcome: str | None,
    customer_context: str | None,
    lists: Mapping[str, Iterable[str]],
) -> None:
    """Refuse source content beyond the intake limits, naming the first field over."""
    _limit("title", title, MAX_TITLE_CHARACTERS)
    _limit("description", description, MAX_DESCRIPTION_CHARACTERS)
    _limit("desired_outcome", desired_outcome or "", MAX_CONTEXT_CHARACTERS)
    _limit("customer_context", customer_context or "", MAX_CONTEXT_CHARACTERS)
    for name, raw_items in lists.items():
        items = tuple(raw_items)
        if len(items) > MAX_LIST_ITEMS:
            raise RequirementIntakeTooLargeError(
                f"{name} is limited to {MAX_LIST_ITEMS} entries; {len(items)} were supplied."
            )
        for item in items:
            _limit(f"each {name} entry", item, MAX_LIST_ITEM_CHARACTERS)


def _limit(name: str, value: str, maximum: int) -> None:
    length = len(value.strip())
    if length > maximum:
        raise RequirementIntakeTooLargeError(
            f"{name} is limited to {maximum:,} characters; {length:,} were supplied."
        )
