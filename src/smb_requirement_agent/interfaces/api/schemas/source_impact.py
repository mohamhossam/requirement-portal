"""Request bodies for deciding how published-source changes affect requirement content."""

from pydantic import BaseModel, Field

from smb_requirement_agent.domain.document.lineage import ImpactDecisionKind


class ImpactDecisionRequest(BaseModel):
    publication_state: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=0)
    decision: ImpactDecisionKind
    reason: str = Field(min_length=1, max_length=2000)
