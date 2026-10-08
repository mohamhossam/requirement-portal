"""Isolated, resumable generations of derived search vectors."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.knowledge.application.ports.requirement_knowledge import (
    RequirementKnowledgeIndexPort,
)


@dataclass(frozen=True)
class IndexGeneration:
    id: str
    identity: str
    status: str


class KnowledgeIndexGenerationsPort(Protocol):
    def begin_rebuild(self, identity: str) -> IndexGeneration: ...
    def staging_index(self, generation_id: str) -> RequirementKnowledgeIndexPort: ...
    def active_index(self, identity: str) -> RequirementKnowledgeIndexPort: ...
    def activate(self, generation_id: str) -> None: ...
    def list_generations(self) -> tuple[IndexGeneration, ...]: ...
