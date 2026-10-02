"""Immutable, validated source versions for architecture releases."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from smb_kernel.documents.ports import DocumentExtractorPort, DocumentStoragePort

from smb_requirement_agent.application.document_upload_validation import (
    SUPPORTED_EXTENSIONS,
    validate_document_upload,
)
from smb_requirement_agent.application.errors import PersistenceError
from smb_requirement_agent.application.ports.architecture_knowledge_repository import (
    ArchitectureKnowledgeRepositoryPort,
)
from smb_requirement_agent.application.ports.identity import Actor, require_maintainer
from smb_requirement_agent.application.ports.located_document_extractor import (
    LocatedDocumentExtractorPort,
    LocatedText,
)
from smb_requirement_agent.application.use_cases.architecture_knowledge import (
    KnowledgeNotFoundError,
    ManageArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    InvalidKnowledgeError,
    KnowledgeConflictError,
    KnowledgeDocumentVersion,
    KnowledgeReleaseStatus,
)
from smb_requirement_agent.domain.document.value_objects import DocumentVersionId

# Architecture sources may also be Markdown, read as plain text, spreadsheets, read
# row by row, and images (diagrams, screenshots) read by a vision model.
ARCHITECTURE_EXTENSIONS = {
    **SUPPORTED_EXTENSIONS,
    "text/markdown": ".md,.markdown",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "text/csv": ".csv",
    "text/tab-separated-values": ".tsv",
    "image/png": ".png",
    "image/jpeg": ".jpg,.jpeg",
}

_MARKDOWN_SUFFIXES = (".md", ".markdown")
_UNTYPED_MARKDOWN = {"", "application/octet-stream", "text/plain", "text/x-markdown"}


def _markdown_type(filename: str, mime_type: str) -> str:
    """Browsers often send Markdown untyped or as plain text; its name decides."""
    declared = mime_type.split(";", 1)[0].strip().lower()
    if filename.strip().lower().endswith(_MARKDOWN_SUFFIXES) and declared in _UNTYPED_MARKDOWN:
        return "text/markdown"
    return mime_type


class UploadKnowledgeDocument:
    def __init__(
        self,
        knowledge: ManageArchitectureKnowledge,
        repository: ArchitectureKnowledgeRepositoryPort,
        storage: DocumentStoragePort,
        extractor: DocumentExtractorPort,
        max_bytes: int,
    ) -> None:
        self._knowledge = knowledge
        self._repository = repository
        self._storage = storage
        self._extractor = extractor
        self._max_bytes = max_bytes

    @property
    def max_bytes(self) -> int:
        """The upload limit the transport must enforce while reading the body."""
        return self._max_bytes

    def execute(
        self,
        release_id: str,
        expected_revision: int,
        title: str,
        filename: str,
        mime_type: str,
        language: str,
        content: bytes,
        actor: Actor,
        uploaded_at: datetime,
    ) -> ArchitectureKnowledge:
        require_maintainer(actor)
        current = self._knowledge.get(release_id)
        if (
            current.status is not KnowledgeReleaseStatus.DRAFT
            or current.revision != expected_revision
        ):
            raise KnowledgeConflictError("The draft changed; reload before uploading.")
        if not title.strip():
            raise InvalidKnowledgeError("Document title is required.")
        filename, mime_type = validate_document_upload(
            filename,
            _markdown_type(filename, mime_type),
            content,
            self._max_bytes,
            ARCHITECTURE_EXTENSIONS,
        )
        # The existing extractor checks signatures, unsafe archives, macros and blank text.
        self._extractor.extract(mime_type, content)
        checksum = hashlib.sha256(content).hexdigest()
        if any(version.checksum == checksum for version in current.documents):
            raise InvalidKnowledgeError("This document content is already in the draft.")
        version_id = uuid4().hex
        version = KnowledgeDocumentVersion(
            id=version_id,
            title=title.strip(),
            filename=filename.strip(),
            mime_type=mime_type,
            language=language,
            checksum=checksum,
            storage_key=version_id,
            uploaded_by=actor.id,
            uploaded_at=uploaded_at,
        )
        updated = current.updated(documents=(*current.documents, version))
        blob_id = DocumentVersionId(version_id)
        self._storage.put(blob_id, content)
        try:
            self._repository.save(updated, expected_revision, actor.id, "upload_document")
        except (KnowledgeConflictError, PersistenceError):
            self._storage.delete(blob_id)
            raise
        return updated


@dataclass(frozen=True)
class DocumentPassage:
    """A cited passage with the passages around it, as the document reads."""

    mime_type: str
    passage: LocatedText
    before: tuple[LocatedText, ...]
    after: tuple[LocatedText, ...]


_PART = re.compile(r" \(part \d+ of \d+\)$")
_IMAGES = frozenset({"image/png", "image/jpeg"})
_LINE_RANGE = re.compile(r"^lines? (?P<start>\d+)(?:-(?P<end>\d+))?$")


def _line_range(location: str) -> tuple[int, int] | None:
    """The first and last line of a "line N" or "lines A-B" location."""
    match = _LINE_RANGE.match(location)
    if match is None:
        return None
    start = int(match["start"])
    return start, int(match["end"] or start)


class ReadKnowledgeDocument:
    """The original bytes of a document version the actor may read."""

    def __init__(
        self,
        knowledge: ManageArchitectureKnowledge,
        storage: DocumentStoragePort,
        located: LocatedDocumentExtractorPort,
    ) -> None:
        self._knowledge = knowledge
        self._storage = storage
        self._located = located

    def passage(
        self, release_id: str, version_id: str, location: str, actor: Actor, context: int = 2
    ) -> DocumentPassage:
        """The passage a suggestion cites, re-read from the stored document.

        A long passage read in parts is cited as "page 3 (part 2 of 3)"; the
        whole passage is returned, since the quote is somewhere inside it.
        """
        require_maintainer(actor)
        release = self._knowledge.get(release_id)
        version = next((item for item in release.documents if item.id == version_id), None)
        if version is None:
            raise KnowledgeNotFoundError("This document is not part of the version.")
        if version.mime_type in _IMAGES:
            raise InvalidKnowledgeError("Images have no text passages to show.")
        segments = self._located.extract(
            version.mime_type, self._storage.get(DocumentVersionId(version.storage_key))
        )
        wanted = _PART.sub("", location.strip())
        index = next((i for i, item in enumerate(segments) if item.location == wanted), None)
        if index is None and (lines := _line_range(wanted)) is not None:
            # Suggestions read before a document's passages changed shape cite line
            # windows ("lines 1-40"); the first passage on those lines stands in.
            index = next(
                (
                    i
                    for i, item in enumerate(segments)
                    if (span := _line_range(item.location)) is not None
                    and span[0] <= lines[1]
                    and lines[0] <= span[1]
                ),
                None,
            )
        if index is None:
            raise KnowledgeNotFoundError("That passage was not found in the document.")
        return DocumentPassage(
            version.mime_type,
            segments[index],
            segments[max(0, index - context) : index],
            segments[index + 1 : index + 1 + context],
        )

    def execute(self, version_id: str, actor: Actor) -> tuple[KnowledgeDocumentVersion, bytes]:
        version = self._knowledge.document_version(version_id, actor)
        return version, self._storage.get(DocumentVersionId(version.storage_key))
