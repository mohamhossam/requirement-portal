"""Rebuild derived knowledge without replacing the active generation prematurely."""

from smb_requirement_agent.knowledge.application.ports.knowledge_index_generations import (
    IndexGeneration,
    KnowledgeIndexGenerationsPort,
)
from smb_requirement_agent.knowledge.application.ports.requirement_knowledge import (
    KnowledgeEmbeddingPort,
)
from smb_requirement_agent.knowledge.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
)


class RebuildKnowledgeIndex:
    def __init__(
        self,
        corpus: RequirementKnowledgeCorpus,
        embeddings: KnowledgeEmbeddingPort,
        generations: KnowledgeIndexGenerationsPort,
        identity: str,
    ) -> None:
        self._corpus = corpus
        self._embeddings = embeddings
        self._generations = generations
        self._identity = identity

    def execute(self) -> IndexGeneration:
        generation = self._generations.begin_rebuild(self._identity)
        index = self._generations.staging_index(generation.id)
        while index.pending_sources(1):
            self._corpus.sync_index(index, self._embeddings, require_complete=False)
        self._generations.activate(generation.id)
        return IndexGeneration(generation.id, generation.identity, "active")
