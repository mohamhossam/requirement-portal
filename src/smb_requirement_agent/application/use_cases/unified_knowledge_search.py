"""Source-balanced search across the workspace without mixing vector spaces.

Search sees what reading sees (ADR-0075): every submitted Requirement, whoever
owns it. Drafts are never indexed, so they cannot appear. A hit is still
dropped when its Requirement no longer exists or its evidence is stale.
"""

from dataclasses import dataclass
from typing import Literal

from smb_requirement_agent.application.errors import (
    KnowledgeGenerationError,
    RequirementAnalysisConflictError,
    UnsupportedDocumentError,
)
from smb_requirement_agent.application.ports.reference_grounding import ReferenceSearchPort
from smb_requirement_agent.application.ports.requirement_knowledge import (
    KnowledgeEmbeddingPort,
    RequirementKnowledgeIndexPort,
)
from smb_requirement_agent.application.use_cases.requirement_knowledge import (
    RequirementKnowledgeCorpus,
    require_index_current,
)
from smb_requirement_agent.domain.knowledge.bounded_text import bounded_knowledge_text
from smb_requirement_agent.domain.knowledge.entities import RelationshipEvidence
from smb_requirement_agent.identity.application.ports.access_repository import AccessRepositoryPort
from smb_requirement_agent.shared_kernel.citation import (
    PublishedReference,
    normalize_search,
)


@dataclass(frozen=True)
class UnifiedSearchHit:
    source_type: Literal["requirement", "published_document"]
    source_id: str
    title: str
    excerpt: str
    evidence_path: str
    requirement_evidence: RelationshipEvidence | None = None
    reference_evidence: PublishedReference | None = None


class UnifiedKnowledgeSearch:
    def __init__(
        self,
        corpus: RequirementKnowledgeCorpus,
        index: RequirementKnowledgeIndexPort,
        embeddings: KnowledgeEmbeddingPort,
        references: ReferenceSearchPort,
        access: AccessRepositoryPort,
    ) -> None:
        self._corpus, self._index, self._embeddings = corpus, index, embeddings
        self._references, self._access = references, access

    def execute(self, query: str) -> tuple[UnifiedSearchHit, ...]:
        query = normalize_search(query)
        if not query or len(query) > 2000:
            raise UnsupportedDocumentError("Search requires 1 to 2,000 characters.")
        require_index_current(self._index)
        vectors = self._embeddings.embed((bounded_knowledge_text(query)[0],))
        if len(vectors) != 1:
            raise KnowledgeGenerationError("Search returned no query embedding.")
        matches = self._index.search(query, vectors[0], None, 100)
        requirements: list[UnifiedSearchHit] = []
        for match in matches:
            c = match.chunk
            if self._access.get_requirement(c.requirement_id) is None:
                continue
            evidence = RelationshipEvidence(
                c.id,
                c.requirement_id,
                c.field,
                c.text,
                c.evidence_path,
                c.fingerprint,
                c.source_lineage,
            )
            if not self._corpus.citations_current((evidence,)):
                continue
            try:
                self._references.require_current(tuple(o.citation for o in c.source_lineage))
            except RequirementAnalysisConflictError:
                # Historical copies remain in dependency review, not fresh evidence search.
                continue
            requirements.append(
                UnifiedSearchHit(
                    "requirement",
                    c.requirement_id.value,
                    self._corpus.title(c.requirement_id),
                    c.text,
                    c.evidence_path,
                    evidence,
                )
            )
        references = self._references.retrieve(query)
        self._references.require_current(tuple(item.citation for item in references))
        documents = [
            UnifiedSearchHit(
                "published_document",
                item.citation.document_id,
                item.citation.title,
                item.citation.excerpt,
                "",
                reference_evidence=item.citation,
            )
            for item in references
        ]
        # A Requirement copy is searchable but cannot count as another source.
        # Prefer the original published passage when that origin is retrieved.
        original_ids = {hit.source_id for hit in documents}
        requirements = [
            hit
            for hit in requirements
            if hit.requirement_evidence is not None
            and not any(
                o.citation.document_id in original_ids
                for o in hit.requirement_evidence.source_lineage
            )
        ]
        selected: list[UnifiedSearchHit] = []
        seen: set[str] = set()
        seen_origins: set[str] = set()
        counts: dict[tuple[str, str], int] = {}
        for rank in range(max(len(requirements), len(documents))):
            for branch in (requirements, documents):
                for hit in branch[rank : rank + 1]:
                    if hit.requirement_evidence is not None:
                        evidence = hit.requirement_evidence
                        if self._access.get_requirement(
                            evidence.requirement_id
                        ) is None or not self._corpus.citations_current((evidence,)):
                            continue
                        try:
                            self._references.require_current(
                                tuple(o.citation for o in evidence.source_lineage)
                            )
                        except RequirementAnalysisConflictError:
                            continue
                    key = normalize_search(hit.excerpt)
                    origins = (
                        {o.citation.document_id for o in hit.requirement_evidence.source_lineage}
                        if hit.requirement_evidence
                        else {hit.source_id}
                    )
                    if hit.requirement_evidence and origins & seen_origins:
                        continue
                    source = (hit.source_type, hit.source_id)
                    if key in seen or counts.get(source, 0) >= 3:
                        continue
                    selected.append(hit)
                    seen_origins.update(origins)
                    seen.add(key)
                    counts[source] = counts.get(source, 0) + 1
                    if len(selected) == 20:
                        return tuple(selected)
        return tuple(selected)
