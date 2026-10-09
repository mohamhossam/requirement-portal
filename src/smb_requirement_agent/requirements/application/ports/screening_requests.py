"""Asking for a knowledge screen, as the Requirement context sees it (ADR-0103 Amendment 1).

Requirements sit upstream of the knowledge screen, so they ask for one through this port they
own. The composition root implements it with the screening context's scheduler. Analysis, also
upstream of the screen, asks through the same port (ADR-0103 PR 10).
"""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class ScreeningRequestPort(Protocol):
    def schedule(self, requirement_id: RequirementId) -> None:
        """Ask for this Requirement, and those related to it, to be screened again."""
        ...
