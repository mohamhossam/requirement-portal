"""The analysis context token a person was shown (ADR-0103 Amendment 1, F2)."""

from __future__ import annotations

from typing import Protocol

from smb_requirement_agent.application.ports.expected_context import ExpectedContextPort
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class AnalysisContextPort(ExpectedContextPort, Protocol):
    def analysis(self, requirement_id: RequirementId) -> str:
        """The current token for this Requirement's analysis inputs."""
        ...
