"""Business-versus-enabler typing for backlog items (SAFe enablers).

SAFe types every Feature and Story as business work or one of four enabler
kinds. Business work delivers customer value directly; an enabler builds the
runway it needs: exploration (discovery and spikes), architecture,
infrastructure, or compliance work.
"""

from __future__ import annotations

from enum import Enum


class WorkKind(Enum):
    BUSINESS = "business"
    EXPLORATION = "exploration"
    ARCHITECTURE = "architecture"
    INFRASTRUCTURE = "infrastructure"
    COMPLIANCE = "compliance"

    @property
    def is_enabler(self) -> bool:
        return self is not WorkKind.BUSINESS
