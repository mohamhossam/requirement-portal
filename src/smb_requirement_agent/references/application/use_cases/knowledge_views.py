"""Read-only views of knowledge a Requirement relies on (ADR-0099)."""

from smb_requirement_agent.application.errors import KnowledgeViewUnavailableError
from smb_requirement_agent.references.application.ports.knowledge_views import (
    ArchitectureEvidence,
    CitedPassage,
    KnowledgeViewsPort,
    PassageCitation,
)


class KnowledgeViews:
    def __init__(self, views: KnowledgeViewsPort) -> None:
        self._views = views

    def passage(self, citation: PassageCitation) -> CitedPassage:
        found = self._views.passage(citation)
        if found is None:
            raise KnowledgeViewUnavailableError(
                "This exact citation is no longer published or cannot be resolved. "
                "Search again for current evidence."
            )
        return found

    def evidence(self, release_id: str, chunk_id: str) -> ArchitectureEvidence:
        found = self._views.evidence(release_id, chunk_id)
        if found is None:
            raise KnowledgeViewUnavailableError("This architecture evidence is not available.")
        return found
