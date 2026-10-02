"""Reviewed passages, incremental embeddings and source-balanced hybrid retrieval."""

from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import timedelta

from smb_kernel.embeddings import Embedding
from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.application.errors import (
    DocumentNotFoundError,
    DocumentVersionConflictError,
    KnowledgeGenerationError,
    ModelTransportError,
    RequirementAnalysisConflictError,
    UnsupportedDocumentError,
)
from smb_requirement_agent.application.ports.document_library import DocumentLibraryPort
from smb_requirement_agent.application.ports.embedding import (
    KnowledgeEmbeddingPort,
    TokenCounterPort,
)
from smb_requirement_agent.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.application.ports.reference_index import (
    ReferenceChunk,
    ReferenceIndexPort,
)
from smb_requirement_agent.application.ports.transaction_manager import TransactionManagerPort
from smb_requirement_agent.application.use_cases.document_library import (
    CHUNKING_POLICY,
    TABLE_CHUNKING_POLICY,
)
from smb_requirement_agent.application.use_cases.source_lineage import analysis_lineage
from smb_requirement_agent.domain.analysis.entities import RequirementAnalysis
from smb_requirement_agent.domain.analysis.value_objects import IntentProposal, IntentProposalStatus
from smb_requirement_agent.domain.document.library import LibraryDocument, Publication
from smb_requirement_agent.domain.document.reference import (
    PublishedReference,
    normalize_search,
)
from smb_requirement_agent.domain.document.value_objects import EvidenceBlockKind
from smb_requirement_agent.domain.identity.entities import ActorProfile
from smb_requirement_agent.domain.identity.errors import AuthorizationDeniedError

CONTEXT_MAX_BUDGET = 1536


@dataclass(frozen=True)
class CorpusBuildPreview:
    document_version: int
    fingerprint: str
    index_identity: str
    chunking_policy: str
    chunks: tuple[ReferenceChunk, ...]


def chunk_manifest(pairs: tuple[tuple[str, str], ...]) -> str:
    return hashlib.sha256(json.dumps(sorted(pairs), separators=(",", ":")).encode()).hexdigest()


class StructureAwareChunks:
    def __init__(self, tokens: TokenCounterPort) -> None:
        self._tokens = tokens

    @property
    def identity(self) -> str:
        return self.policy_identity(CHUNKING_POLICY)

    def policy_identity(self, policy: str) -> str:
        if policy not in (CHUNKING_POLICY, TABLE_CHUNKING_POLICY):
            raise KnowledgeGenerationError(
                "Unsupported chunking policy; restore its implementation."
            )
        return f"{policy}:{self._tokens.identity}:normalize-ar-v1"

    def build(
        self, document: LibraryDocument, publication: Publication
    ) -> tuple[ReferenceChunk, ...]:
        version = document.file_version(publication.version_id)
        revision = next(r for r in version.revisions if r.id == publication.revision_id)
        blocks = {b.id: b for b in version.blocks}
        identity = self.policy_identity(publication.chunking_policy)
        result: list[ReferenceChunk] = []
        for passage in revision.passages:
            if not passage.included:
                continue
            block = blocks[passage.block_id]
            label = " / ".join((document.title, *block.section_path, block.label))
            if self._tokens.count(label) >= 256:
                raise KnowledgeGenerationError(
                    "Source labels exceed the chunk budget. "
                    "Shorten the document title or review its structure."
                )
            parent = hashlib.sha256(
                f"{version.id}:{revision.id}:{block.section_path}".encode()
            ).hexdigest()
            # Each approved block remains isolated. Sentence boundaries are preferred; a very long
            # sentence is explicitly split without dropping any characters or crossing a source.
            table = publication.chunking_policy == TABLE_CHUNKING_POLICY and block.kind in (
                EvidenceBlockKind.TABLE_ROW,
                EvidenceBlockKind.WORKSHEET_RANGE,
            )
            spans = (
                self._table_spans(passage.text, label)
                if table
                else tuple((start, end, "") for start, end in self._spans(passage.text, label))
            )
            for start, end, field in spans:
                original = passage.text[start:end]
                child_label = f"{label}\n{field}" if field else label
                search = normalize_search(f"{child_label}\n{original}")
                digest = hashlib.sha256(search.encode()).hexdigest()
                chunk_id = hashlib.sha256(
                    f"{publication.id}:{block.id}:{start}:{end}:{identity}".encode()
                ).hexdigest()
                result.append(
                    ReferenceChunk(
                        chunk_id,
                        document.id,
                        document.title,
                        version.id,
                        version.number,
                        revision.id,
                        publication.id,
                        publication.fingerprint,
                        parent,
                        block.id,
                        block.section_path,
                        block.label,
                        original,
                        search,
                        digest,
                        "ar" if re.search(r"[\u0600-\u06ff]", original) else "en",
                        self._tokens.count(f"{child_label}\n{original}"),
                        identity,
                        start,
                        end,
                        child_strategy="table_field_fragment"
                        if field
                        else "table_row"
                        if table
                        else "passage",
                        field_context=field,
                    )
                )
        return self._with_context(tuple(result))

    def _table_spans(self, text: str, label: str) -> tuple[tuple[int, int, str], ...]:
        """Pack rendered fields without losing characters; isolate oversized cells.

        Delimiters are layout hints only. Exact offsets always refer to approved text,
        including when a reviewer or a cell value contains a delimiter itself.
        """
        boundaries = [0, *(m.end() for m in re.finditer(r" \| ", text)), len(text)]
        result: list[tuple[int, int, str]] = []
        start = end = 0
        for left, right in zip(boundaries, boundaries[1:], strict=False):
            if self._tokens.count(f"{label}\n{text[start:right]}") <= 768:
                end = right
                continue
            if end > start:
                result.append((start, end, ""))
            start = left
            field = text[left:right]
            if self._tokens.count(f"{label}\n{field}") <= 768:
                end = right
                continue
            match = re.match(r"([^:=\n|]{1,80}[:=])", field)
            heading = match.group(1) if match else ""
            if self._tokens.count(heading) > 160:
                heading = ""
            child_label = f"{label}\n{heading}" if heading else label
            result.extend((left + a, left + b, heading) for a, b in self._spans(field, child_label))
            start = end = right
        if end > start:
            result.append((start, end, ""))
        return tuple(result)

    def _with_context(self, chunks: tuple[ReferenceChunk, ...]) -> tuple[ReferenceChunk, ...]:
        """Attach a bounded same-section window without changing the indexed child text."""

        groups: dict[str, list[int]] = {}
        for index, chunk in enumerate(chunks):
            groups.setdefault(chunk.parent_id, []).append(index)
        enriched = list(chunks)
        for indexes in groups.values():
            for position, chunk_index in enumerate(indexes):
                target = chunks[chunk_index]
                selected = {position}
                candidates = sorted(
                    (candidate for candidate in range(len(indexes)) if candidate != position),
                    key=lambda candidate: (
                        abs(candidate - position),
                        0 if candidate < position else 1,
                    ),
                )
                for candidate in candidates:
                    trial = sorted((*selected, candidate))
                    context = self._render_context(tuple(chunks[indexes[item]] for item in trial))
                    header = " / ".join((target.document_title, *target.heading_path))
                    if self._tokens.count(f"{header}\n{context}") <= CONTEXT_MAX_BUDGET:
                        selected.add(candidate)
                window = tuple(chunks[indexes[item]] for item in sorted(selected))
                context = self._render_context(window)
                header = " / ".join((target.document_title, *target.heading_path))
                enriched[chunk_index] = replace(
                    target,
                    context_text=context,
                    context_locations=tuple(item.location for item in window),
                    context_token_count=self._tokens.count(f"{header}\n{context}"),
                )
        return tuple(enriched)

    @staticmethod
    def _render_context(chunks: tuple[ReferenceChunk, ...]) -> str:
        return "\n\n".join(
            f"{chunk.location}\n{chunk.field_context}\n{chunk.original_text}"
            if chunk.field_context
            else f"{chunk.location}\n{chunk.original_text}"
            for chunk in chunks
        )

    def _spans(self, text: str, label: str) -> tuple[tuple[int, int], ...]:
        result: list[tuple[int, int]] = []
        start = 0
        while start < len(text):
            low, high = start + 1, len(text)
            end = start
            while low <= high:
                mid = (low + high) // 2
                if self._tokens.count(f"{label}\n{text[start:mid]}") <= 768:
                    end, low = mid, mid + 1
                else:
                    high = mid - 1
            if end == start:
                raise KnowledgeGenerationError("A source cannot fit the chunk budget.")
            if end < len(text):
                boundaries = [
                    m.end() + start for m in re.finditer(r"[.!?\u061f]\s+|\n+", text[start:end])
                ]
                preferred = [
                    b for b in boundaries if self._tokens.count(f"{label}\n{text[start:b]}") >= 384
                ]
                if preferred:
                    end = min(
                        preferred,
                        key=lambda b: abs(self._tokens.count(f"{label}\n{text[start:b]}") - 512),
                    )
            result.append((start, end))
            start = end
        return tuple(result)


class ReferenceKnowledge:
    def retrieve(self, query: str) -> tuple[ReferenceEvidence, ...]:
        if not self.has_published():
            return ()
        result: list[ReferenceEvidence] = []
        budget = 0
        for chunk in self.search(query[:2000]):
            context = chunk.context_text or chunk.original_text
            cost = len(context.encode("utf-8"))
            if budget + cost > 8000 or len(result) >= 10:
                continue
            result.append(ReferenceEvidence(self.citation(chunk), context, chunk.context_locations))
            budget += cost
        return tuple(result)

    def has_published(self) -> bool:
        return self._documents.has_published()

    def search_evidence(self, query: str) -> tuple[ReferenceEvidence, ...]:
        evidence: list[ReferenceEvidence] = []
        for chunk in self.search(query):
            citation = self.citation(chunk)
            evidence.append(
                ReferenceEvidence(
                    citation,
                    chunk.context_text or f"{citation.location}\n{citation.excerpt}",
                    chunk.context_locations or (chunk.location,),
                )
            )
        return tuple(evidence)

    @staticmethod
    def citation(chunk: ReferenceChunk) -> PublishedReference:
        return PublishedReference(
            chunk.document_id,
            chunk.document_title,
            chunk.version_id,
            chunk.version_number,
            chunk.revision_id,
            chunk.publication_id,
            chunk.approval_fingerprint,
            chunk.block_id,
            chunk.location,
            chunk.original_text,
            chunk.start_offset,
            chunk.end_offset,
            hashlib.sha256(normalize_search(chunk.original_text).encode()).hexdigest(),
        )

    def _citation_current(self, citation: PublishedReference) -> bool:
        document = self._documents.get(citation.document_id)
        if document is None or document.published_id != citation.publication_id:
            return False
        publication = next(
            (
                p
                for p in document.publications
                if p.id == citation.publication_id and p.withdrawn_at is None
            ),
            None,
        )
        if (
            publication is None
            or publication.fingerprint != citation.approval_fingerprint
            or publication.version_id != citation.version_id
            or publication.revision_id != citation.revision_id
        ):
            return False
        source = document.file_version(citation.version_id)
        revision = next((r for r in source.revisions if r.id == citation.revision_id), None)
        passage = (
            next(
                (p for p in revision.passages if p.block_id == citation.block_id and p.included),
                None,
            )
            if revision
            else None
        )
        return (
            passage is not None
            and document.title == citation.title
            and source.number == citation.version_number
            and any(
                b.id == citation.block_id and b.label == citation.location for b in source.blocks
            )
            and hashlib.sha256(normalize_search(citation.excerpt).encode()).hexdigest()
            == citation.lineage_hash
            and passage.text[citation.start_offset : citation.end_offset] == citation.excerpt
        )

    def require_current(self, evidence: Sequence[PublishedReference]) -> None:
        with self._transactions.transaction():
            self._documents.lock_publications(tuple(sorted({c.document_id for c in evidence})))
            if any(not self._citation_current(c) for c in evidence):
                raise RequirementAnalysisConflictError(
                    "A cited reference was withdrawn or replaced. "
                    "Re-analyse and reconcile its applicability before continuing."
                )

    def stale_analysis(
        self, analysis: RequirementAnalysis, *, target_ids: Sequence[str] | None = None
    ) -> tuple[str, ...]:
        with self._transactions.transaction():
            origins = analysis_lineage(analysis)
            self._documents.lock_publications(
                tuple(sorted({item.citation.document_id for item in origins}))
            )
            return (
                *self.stale_proposals(analysis.intent_proposals),
                *(
                    item.citation.publication_id
                    for item in origins
                    if not self._citation_current(item.citation)
                ),
            )

    def stale_proposals(self, proposals: Sequence[IntentProposal]) -> tuple[str, ...]:
        with self._transactions.transaction():
            self._documents.lock_publications(
                tuple(
                    sorted(
                        {
                            c.document_id
                            for p in proposals
                            if p.status is not IntentProposalStatus.REJECTED
                            for c in p.reference_evidence
                        }
                    )
                )
            )
            return tuple(
                p.id.value
                for p in proposals
                if p.status is not IntentProposalStatus.REJECTED
                and any(not self._citation_current(c) for c in p.reference_evidence)
            )

    def __init__(
        self,
        documents: DocumentLibraryPort,
        index: ReferenceIndexPort,
        embeddings: KnowledgeEmbeddingPort,
        chunks: StructureAwareChunks,
        transactions: TransactionManagerPort,
        clock: ClockPort,
        embedding_identity: str,
    ) -> None:
        self._documents, self._index, self._embeddings = documents, index, embeddings
        self._chunks, self._transactions, self._clock = chunks, transactions, clock
        self._embedding_identity = embedding_identity
        self.identity = f"{embedding_identity}:{chunks.identity}"

    def _index_identity(self, policy: str) -> str:
        return (
            self.identity
            if policy == CHUNKING_POLICY
            else (f"{self._embedding_identity}:{self._chunks.policy_identity(policy)}")
        )

    def _owned(
        self, document_id: str, actor: ActorProfile, expected: int | None = None
    ) -> LibraryDocument:
        document = self._documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError("Library document was not found.")
        if document.owner.id != actor.id:
            raise AuthorizationDeniedError("Only the owner can manage corpus builds.")
        if expected is not None and document.version != expected:
            raise DocumentVersionConflictError("Document changed. Reload before retrying.")
        return document

    def preview_build(self, document_id: str, actor: ActorProfile) -> CorpusBuildPreview:
        document = self._owned(document_id, actor)
        source = document.versions[-1]
        if not source.revisions:
            raise DocumentVersionConflictError("Save an extraction review before building.")
        revision = source.revisions[-1]
        fingerprint = revision.fingerprint(source.id, TABLE_CHUNKING_POLICY)
        publication = Publication(
            "preview",
            source.id,
            revision.id,
            fingerprint,
            TABLE_CHUNKING_POLICY,
            actor.snapshot(),
            self._clock.now(),
        )
        return CorpusBuildPreview(
            document.version,
            fingerprint,
            self._index_identity(TABLE_CHUNKING_POLICY),
            TABLE_CHUNKING_POLICY,
            self._chunks.build(document, publication),
        )

    def build_review(
        self,
        document_id: str,
        actor: ActorProfile,
        expected: int,
        fingerprint: str,
        index_identity: str,
    ) -> LibraryDocument:
        with self._transactions.transaction():
            document = self._owned(document_id, actor, expected)
            if index_identity != self._index_identity(TABLE_CHUNKING_POLICY):
                raise DocumentVersionConflictError("Index configuration changed. Preview again.")
            if any(
                p.withdrawn_at is None and p.activated_at is None for p in document.publications
            ):
                raise DocumentVersionConflictError("Finish or discard the pending build first.")
            source = document.versions[-1]
            if not source.revisions:
                raise DocumentVersionConflictError("Save an extraction review before building.")
            publication = Publication(
                str(uuid.uuid4()),
                source.id,
                source.revisions[-1].id,
                fingerprint,
                TABLE_CHUNKING_POLICY,
                actor.snapshot(),
                self._clock.now(),
                requires_activation=True,
                index_identity=index_identity,
                replaces_publication_id=document.published_id,
            )
            updated = document.approve(publication)
            self._documents.save(updated, expected)
            return updated

    def activate_build(
        self,
        document_id: str,
        publication_id: str,
        actor: ActorProfile,
        expected: int,
        manifest: str,
    ) -> LibraryDocument:
        with self._transactions.transaction():
            document = self._owned(document_id, actor, expected)
            publication = next((p for p in document.publications if p.id == publication_id), None)
            if (
                publication is None
                or not publication.requires_activation
                or publication.withdrawn_at is not None
                or publication.built_at is None
                or publication.chunk_manifest != manifest
                or publication.index_identity != self._index_identity(publication.chunking_policy)
                or document.publications[-1].id != publication.id
                or document.versions[-1].id != publication.version_id
                or document.versions[-1].revisions[-1].id != publication.revision_id
                or document.published_id != publication.replaces_publication_id
                or publication.activated_at is not None
            ):
                raise DocumentVersionConflictError(
                    "Build or source changed. Reload and rebuild before activation."
                )
            self._verify_manifest(publication, self._chunks.build(document, publication))
            updated = document.activate(publication.id, self._clock.now())
            self._documents.save(updated, expected)
            return updated

    def discard_build(
        self,
        document_id: str,
        publication_id: str,
        actor: ActorProfile,
        expected: int,
    ) -> LibraryDocument:
        with self._transactions.transaction():
            document = self._owned(document_id, actor, expected)
            publication = next((p for p in document.publications if p.id == publication_id), None)
            if (
                publication is None
                or not publication.requires_activation
                or publication.activated_at is not None
                or publication.withdrawn_at is not None
            ):
                raise DocumentVersionConflictError("Only a pending build can be discarded.")
            updated = replace(
                document,
                version=document.version + 1,
                publications=tuple(
                    replace(
                        p,
                        withdrawn_at=self._clock.now(),
                        withdrawal_reason="Owner discarded corpus build.",
                        index_lease_until=None,
                    )
                    if p.id == publication_id
                    else p
                    for p in document.publications
                ),
            )
            self._documents.save(updated, expected)
            return updated

    def _verify_manifest(self, publication: Publication, chunks: tuple[ReferenceChunk, ...]) -> str:
        expected = tuple(sorted((c.id, c.content_hash) for c in chunks))
        actual = self._index.manifest(
            self._index_identity(publication.chunking_policy), publication.id
        )
        digest = chunk_manifest(expected)
        if (
            not chunks
            or actual != expected
            or (
                publication.built_at is not None
                and (publication.chunk_count != len(chunks) or publication.chunk_manifest != digest)
            )
        ):
            raise KnowledgeGenerationError(
                "Corpus build is incomplete or its manifest changed. Discard and rebuild."
            )
        return digest

    def preview(
        self, document: LibraryDocument, publication: Publication
    ) -> tuple[ReferenceChunk, ...]:
        return self._chunks.build(document, publication)

    def preview_review(self, document_id: str, actor: ActorProfile) -> tuple[ReferenceChunk, ...]:
        document = self._documents.get(document_id)
        if document is None:
            raise DocumentNotFoundError("Library document was not found.")
        if document.owner.id != actor.id:
            raise AuthorizationDeniedError("Only the owner can preview unpublished chunks.")
        source = document.versions[-1]
        if not source.revisions:
            raise DocumentVersionConflictError(
                "Save an extraction review before previewing chunks."
            )
        revision = source.revisions[-1]
        publication = Publication(
            "preview",
            source.id,
            revision.id,
            revision.fingerprint(source.id, CHUNKING_POLICY),
            CHUNKING_POLICY,
            actor.snapshot(),
            self._clock.now(),
        )
        return self._chunks.build(document, publication)

    def index_next(self) -> bool:
        document = self._documents.pending_publication(self._clock.now())
        if document is None:
            return False
        publication = next(
            p
            for p in reversed(document.publications)
            if p.withdrawn_at is None and p.activated_at is None
        )
        with self._transactions.transaction():
            reserved = replace(
                publication,
                indexing_attempts=publication.indexing_attempts + 1,
                indexing_error="Indexing in progress; retry explicitly if processing stops.",
                index_lease_until=self._clock.now() + timedelta(seconds=660),
            )
            document = replace(
                document,
                version=document.version + 1,
                publications=tuple(
                    reserved if p.id == publication.id else p for p in document.publications
                ),
            )
            self._documents.save(document, document.version - 1)
        try:
            return self._index_document(document, reserved)
        except (KnowledgeGenerationError, ModelTransportError) as exc:
            with self._transactions.transaction():
                current = self._documents.get(document.id)
                if current is not None and current.version == document.version:
                    failed = replace(
                        reserved,
                        indexing_error=type(exc).__name__,
                        index_lease_until=self._clock.now()
                        + timedelta(seconds=30 * reserved.indexing_attempts),
                    )
                    updated = replace(
                        current,
                        version=current.version + 1,
                        publications=tuple(
                            failed if p.id == failed.id else p for p in current.publications
                        ),
                    )
                    self._documents.save(updated, current.version)
            raise

    def _index_document(self, document: LibraryDocument, publication: Publication) -> bool:
        identity = self._index_identity(publication.chunking_policy)
        if publication.index_identity is not None and publication.index_identity != identity:
            raise KnowledgeGenerationError(
                "Build configuration changed. Restore it or discard and rebuild."
            )
        chunks = self._chunks.build(document, publication)
        if not chunks:
            raise KnowledgeGenerationError("Approved publication contains no usable chunks.")
        # Durable batches are invisible until the publication pointer activates. A crash can
        # reuse completed embeddings without re-sending the whole document to the provider.
        for start in range(0, len(chunks), 16):
            batch = chunks[start : start + 16]
            cached: dict[str, Embedding] = {}
            missing: dict[str, str] = {}
            for chunk in batch:
                vector = self._index.cached(identity, chunk.content_hash)
                if vector is None:
                    missing[chunk.content_hash] = chunk.search_text
                else:
                    cached[chunk.content_hash] = vector
            if missing:
                generated = self._embeddings.embed(tuple(missing.values()))
                if len(generated) != len(missing):
                    raise KnowledgeGenerationError(
                        "Embedding provider returned the wrong number of vectors."
                    )
                cached.update(zip(missing, generated, strict=True))
            vectors = tuple(cached[chunk.content_hash] for chunk in batch)
            for vector in vectors:
                self._validate_vector(vector)
            with self._transactions.transaction():
                current = self._documents.get(document.id)
                if current is None or current.version != document.version:
                    raise DocumentVersionConflictError(
                        "Document changed while indexing. Retry against the current state."
                    )
                if (
                    publication.index_lease_until is None
                    or publication.index_lease_until <= self._clock.now()
                ):
                    raise DocumentVersionConflictError(
                        "Indexing lease expired. This result cannot publish."
                    )
                self._index.stage(identity, batch, vectors)
        with self._transactions.transaction():
            current = self._documents.get(document.id)
            if current is None or current.version != document.version:
                raise DocumentVersionConflictError(
                    "Document changed while indexing. The new state will be retried."
                )
            if (
                publication.index_lease_until is None
                or publication.index_lease_until <= self._clock.now()
            ):
                raise DocumentVersionConflictError(
                    "Indexing lease expired. This result cannot publish."
                )
            manifest = self._verify_manifest(publication, chunks)
            updated = (
                replace(current, version=current.version + 1)
                if publication.requires_activation
                else current.activate(publication.id, self._clock.now())
            )
            updated = replace(
                updated,
                publications=tuple(
                    replace(
                        p,
                        indexing_error=None,
                        index_identity=identity,
                        index_lease_until=None,
                        built_at=self._clock.now(),
                        chunk_count=len(chunks),
                        chunk_manifest=manifest,
                    )
                    if p.id == publication.id
                    else p
                    for p in updated.publications
                ),
            )
            self._documents.save(updated, current.version)
        return True

    @staticmethod
    def _validate_vector(vector: Embedding) -> None:
        if len(vector) != 768 or not all(math.isfinite(v) for v in vector) or not any(vector):
            raise KnowledgeGenerationError(
                "Embedding provider returned an invalid 768-dimensional vector."
            )

    def search(self, query: str) -> tuple[ReferenceChunk, ...]:
        query = normalize_search(query)
        if not query or len(query) > 2000:
            raise UnsupportedDocumentError("Search requires 1 to 2,000 characters.")
        identities = (self.identity, self._index_identity(TABLE_CHUNKING_POLICY))
        if self._documents.has_incompatible_publication(identities):
            raise KnowledgeGenerationError(
                "Published references use another index generation. "
                "Restore the compatible model configuration before searching."
            )
        generated = self._embeddings.embed((query,))
        if len(generated) != 1:
            raise KnowledgeGenerationError(
                "Embedding provider returned the wrong number of query vectors."
            )
        self._validate_vector(generated[0])
        branches = [
            self._index.search(identity, query, generated[0], 100) for identity in identities
        ]
        # Interleave compatible policy generations fairly; vectors never cross model identities.
        candidates = tuple(
            c
            for rank in range(max(map(len, branches), default=0))
            for branch in branches
            for c in branch[rank : rank + 1]
        )
        selected: list[ReferenceChunk] = []
        counts: dict[str, int] = {}
        hashes: set[str] = set()
        expanded: dict[tuple[str, str], dict[str, ReferenceChunk]] = {}
        for chunk in candidates:
            document = self._documents.get(chunk.document_id)
            if document is None or document.published_id != chunk.publication_id:
                continue
            publication = next(
                (
                    p
                    for p in document.publications
                    if p.id == chunk.publication_id
                    and p.withdrawn_at is None
                    and p.fingerprint == chunk.approval_fingerprint
                ),
                None,
            )
            if publication is None:
                continue
            publication_key = (document.id, publication.id)
            if publication_key not in expanded:
                expanded[publication_key] = {
                    current.id: current for current in self._chunks.build(document, publication)
                }
            current_chunk = expanded[publication_key].get(chunk.id)
            if current_chunk is None:
                raise KnowledgeGenerationError(
                    "Indexed chunk no longer matches the approved chunking policy."
                )
            chunk = current_chunk
            version = document.file_version(chunk.version_id)
            revision = next((r for r in version.revisions if r.id == chunk.revision_id), None)
            passage = (
                next(
                    (p for p in revision.passages if p.block_id == chunk.block_id and p.included),
                    None,
                )
                if revision
                else None
            )
            if (
                passage is None
                or passage.text[chunk.start_offset : chunk.end_offset] != chunk.original_text
            ):
                raise KnowledgeGenerationError(
                    "Indexed citation no longer matches approved source text."
                )
            if chunk.content_hash in hashes or counts.get(document.id, 0) >= 3:
                continue
            if document.id not in counts and len(counts) >= 10:
                continue
            selected.append(chunk)
            counts[document.id] = counts.get(document.id, 0) + 1
            hashes.add(chunk.content_hash)
        return tuple(selected)
