"""What a browser may report about its own failures (production hardening PR 12)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ClientErrorKind = Literal["render", "chunk_load", "uncaught_error", "unhandled_rejection"]


class ClientErrorReport(BaseModel):
    """Only the kind of failure: never a message, stack or URL, which could carry content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ClientErrorKind
