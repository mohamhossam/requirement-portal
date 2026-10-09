"""The context a person was shown, checked before model-backed work (ADR-0103 Amendment 1, F2).

Generation tokens digest every input visible to a model-backed action. The shared part is the
guard that binds provider work to the prepared context; it is shared technical code. Each context
that runs such actions owns a port extending it with the tokens it reads, because those take its
own types: analysis's `AnalysisContextPort`, breakdown's `BreakdownContextPort` (ADR-0103 PR 11).
Workflows' `GenerationContextTokens` implements them all.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Protocol

from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class ExpectedContextPort(Protocol):
    def guard(
        self,
        current: Callable[[], str],
        *,
        references_for: RequirementId | None = None,
        reference_targets: tuple[str, ...] = (),
    ) -> AbstractContextManager[None]:
        """Bind provider work to the prepared context and recheck it on resume.

        With `references_for`, the Requirement's cited references must also still be current.
        """
        ...
