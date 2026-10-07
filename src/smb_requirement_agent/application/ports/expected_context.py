"""The context a person was shown, checked before model-backed work (ADR-0103 Amendment 1, F2).

Generation tokens digest every input visible to a model-backed action. The contexts that run
such actions check them through this port, which is shared technical code; workflows'
`GenerationContextTokens` implements it. Each context adds the methods it needs as it adopts the
port: analysis in PR 10, breakdown in PR 11.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class ExpectedContextPort(Protocol):
    def guard(self, current: Callable[[], str]) -> AbstractContextManager[None]:
        """Bind provider work to the prepared context and recheck it on resume."""
        ...

    def analysis(self, requirement_id: RequirementId) -> str:
        """The current token for this Requirement's analysis inputs."""
        ...
