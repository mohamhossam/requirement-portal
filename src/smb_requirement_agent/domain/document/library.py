"""Reviewed shared evidence; publication never implies universal applicability."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime

from smb_requirement_agent.domain.document.entities import (
    DocumentAsset,
    DocumentEvidenceBlock,
    DocumentExtractionWarning,
)
from smb_requirement_agent.domain.document.errors import InvalidDocumentError
from smb_requirement_agent.domain.document.ingestion import IngestionStage as IngestionStage
from smb_requirement_agent.domain.document.value_objects import ExtractionWarningSeverity
from smb_requirement_agent.domain.identity.entities import ActorSnapshot
from smb_requirement_agent.domain.shared.staleness import require_aware

# They bound what one review submission can carry. They are checked when a
# review is submitted, not when a stored one is loaded, so no stored review
# can fail to read back.
MAX_PASSAGE_BLOCK_ID_CHARACTERS = 1_000
MAX_PASSAGE_TEXT_CHARACTERS = 200_000
MAX_PASSAGE_EXCLUSION_REASON_CHARACTERS = 10_000


@dataclass(frozen=True)
class ReviewedPassage:
    block_id: str
    text: str
    included: bool
    exclusion_reason: str = ""

    def __post_init__(self) -> None:
        if not self.block_id.strip() or not self.text.strip():
            raise InvalidDocumentError("A reviewed passage requires an identity and text.")
        if not self.included and not self.exclusion_reason.strip():
            raise InvalidDocumentError("Excluded passages require an explanation.")


def require_submittable_passages(passages: tuple[ReviewedPassage, ...]) -> None:
    """Refuse a review submission whose passages exceed the per-passage limits."""
    for passage in passages:
        if (
            len(passage.block_id) > MAX_PASSAGE_BLOCK_ID_CHARACTERS
            or len(passage.text) > MAX_PASSAGE_TEXT_CHARACTERS
            or len(passage.exclusion_reason) > MAX_PASSAGE_EXCLUSION_REASON_CHARACTERS
        ):
            raise InvalidDocumentError(
                "A reviewed passage is limited to a "
                f"{MAX_PASSAGE_BLOCK_ID_CHARACTERS:,}-character identity, "
                f"{MAX_PASSAGE_TEXT_CHARACTERS:,} characters of text and a "
                f"{MAX_PASSAGE_EXCLUSION_REASON_CHARACTERS:,}-character exclusion reason."
            )


@dataclass(frozen=True)
class ExtractionRevision:
    id: str
    created_at: datetime
    created_by: ActorSnapshot
    passages: tuple[ReviewedPassage, ...]
    explanation: str

    def __post_init__(self) -> None:
        require_aware(self.created_at, "extraction revision time")
        if not self.id or not self.explanation.strip() or not self.passages:
            raise InvalidDocumentError("An extraction revision requires content and rationale.")
        ids = [item.block_id for item in self.passages]
        if len(ids) != len(set(ids)):
            raise InvalidDocumentError("An extraction revision cannot repeat a passage.")

    def fingerprint(self, version_id: str, policy: str) -> str:
        content = [
            version_id,
            self.id,
            policy,
            [[p.block_id, p.text, p.included, p.exclusion_reason] for p in self.passages],
        ]
        return hashlib.sha256(json.dumps(content, ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class LibraryVersion:
    id: str
    number: int
    filename: str
    mime_type: str
    size_bytes: int
    checksum: str
    uploaded_at: datetime
    uploaded_by: ActorSnapshot
    idempotency_key: str
    stage: IngestionStage = IngestionStage.QUEUED
    attempt: int = 0
    lease_token: str | None = None
    lease_until: datetime | None = None
    error: str | None = None
    extraction_version: str | None = None
    blocks: tuple[DocumentEvidenceBlock, ...] = ()
    warnings: tuple[str, ...] = ()
    blocking_warnings: tuple[str, ...] = ()
    revisions: tuple[ExtractionRevision, ...] = ()
    assets: tuple[DocumentAsset, ...] = ()
    warning_details: tuple[DocumentExtractionWarning, ...] = ()

    @property
    def unresolved_blocking_warnings(self) -> tuple[str, ...]:
        # Legacy warnings have no trustworthy scope and must remain blocking.
        if not self.warning_details:
            return self.blocking_warnings
        excluded = (
            {p.block_id for p in self.revisions[-1].passages if not p.included}
            if self.revisions
            else set()
        )
        known = {b.id for b in self.blocks}
        scoped_messages = {
            w.message
            for w in self.warning_details
            if w.severity is ExtractionWarningSeverity.BLOCKING
        }
        return tuple(w for w in self.blocking_warnings if w not in scoped_messages) + tuple(
            w.message
            for w in self.warning_details
            if w.severity is ExtractionWarningSeverity.BLOCKING
            and (w.block_id not in known or w.block_id not in excluded)
        )

    def __post_init__(self) -> None:
        require_aware(self.uploaded_at, "library upload time")
        if not self.id or self.number < 1 or self.size_bytes < 1 or not self.filename.strip():
            raise InvalidDocumentError("Library version metadata is incomplete.")
        if len(self.checksum) != 64 or any(c not in "0123456789abcdef" for c in self.checksum):
            raise InvalidDocumentError("Library upload requires a SHA-256 checksum.")
        if self.stage is IngestionStage.READY and not self.blocks:
            raise InvalidDocumentError("Ready evidence must contain extracted blocks.")


@dataclass(frozen=True)
class Publication:
    id: str
    version_id: str
    revision_id: str
    fingerprint: str
    chunking_policy: str
    approved_by: ActorSnapshot
    approved_at: datetime
    activated_at: datetime | None = None
    withdrawn_at: datetime | None = None
    withdrawal_reason: str | None = None
    indexing_attempts: int = 0
    indexing_error: str | None = None
    index_identity: str | None = None
    index_lease_until: datetime | None = None
    # A generation is an immutable, owner-approved corpus member. Legacy approvals
    # retain automatic activation; explicit rebuilds stop at ready for activation.
    requires_activation: bool = False
    built_at: datetime | None = None
    chunk_count: int = 0
    chunk_manifest: str | None = None
    replaces_publication_id: str | None = None

    def __post_init__(self) -> None:
        if not all((self.id, self.version_id, self.revision_id, self.chunking_policy)):
            raise InvalidDocumentError("Publication identity and policy are required.")
        if len(self.fingerprint) != 64 or any(
            c not in "0123456789abcdef" for c in self.fingerprint
        ):
            raise InvalidDocumentError(
                "Publication requires an exact SHA-256 approval fingerprint."
            )
        if self.indexing_attempts < 0:
            raise InvalidDocumentError("Indexing attempt count cannot be negative.")
        require_aware(self.approved_at, "publication approval time")
        for timestamp in (
            self.activated_at,
            self.withdrawn_at,
            self.index_lease_until,
            self.built_at,
        ):
            if timestamp is not None:
                require_aware(timestamp, "publication lifecycle time")
        if self.withdrawn_at is not None and not (self.withdrawal_reason or "").strip():
            raise InvalidDocumentError("Withdrawn publication requires a rationale.")
        if self.chunk_count < 0:
            raise InvalidDocumentError("Chunk count cannot be negative.")
        if self.built_at is not None and (
            self.chunk_count < 1
            or not self.index_identity
            or not self.chunk_manifest
            or len(self.chunk_manifest) != 64
        ):
            raise InvalidDocumentError(
                "A built generation requires an index and complete manifest."
            )


@dataclass(frozen=True)
class OwnershipTransfer:
    previous_owner: ActorSnapshot
    new_owner: ActorSnapshot
    performed_by: ActorSnapshot
    recorded_at: datetime
    reason: str

    def __post_init__(self) -> None:
        require_aware(self.recorded_at, "ownership transfer time")
        if not self.reason.strip() or len(self.reason) > 2000:
            raise InvalidDocumentError(
                "Ownership transfer requires a rationale up to 2000 characters."
            )
        if self.previous_owner.id == self.new_owner.id:
            raise InvalidDocumentError("Choose a different document owner.")
        if self.performed_by.id != self.previous_owner.id:
            raise InvalidDocumentError("Only the current owner can transfer ownership.")


@dataclass(frozen=True)
class LibraryDocument:
    id: str
    title: str
    owner: ActorSnapshot
    versions: tuple[LibraryVersion, ...]
    version: int = 1
    publications: tuple[Publication, ...] = ()
    published_id: str | None = None
    ownership_history: tuple[OwnershipTransfer, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.title.strip() or self.version < 1 or not self.versions:
            raise InvalidDocumentError("Library document identity and title are required.")
        if tuple(v.number for v in self.versions) != tuple(range(1, len(self.versions) + 1)):
            raise InvalidDocumentError("Library version numbers must be contiguous.")
        if len({v.id for v in self.versions}) != len(self.versions):
            raise InvalidDocumentError("Library version identities must be unique.")
        if len({p.id for p in self.publications}) != len(self.publications):
            raise InvalidDocumentError("Publication identities must be unique.")
        if self.ownership_history and (
            self.ownership_history[-1].new_owner != self.owner
            or any(
                later.previous_owner != earlier.new_owner
                for earlier, later in zip(
                    self.ownership_history, self.ownership_history[1:], strict=False
                )
            )
        ):
            raise InvalidDocumentError(
                "Ownership history must form an unbroken chain to the current owner."
            )
        if self.published_id is not None and not any(
            p.id == self.published_id and p.activated_at is not None and p.withdrawn_at is None
            for p in self.publications
        ):
            raise InvalidDocumentError(
                "Searchable publication must be activated and not withdrawn."
            )

    def file_version(self, version_id: str) -> LibraryVersion:
        for item in self.versions:
            if item.id == version_id:
                return item
        raise InvalidDocumentError("Version does not belong to this document.")

    def transfer(self, change: OwnershipTransfer) -> LibraryDocument:
        if change.previous_owner != self.owner:
            raise InvalidDocumentError("Document owner changed; reload before transferring.")
        return replace(
            self,
            owner=change.new_owner,
            ownership_history=(*self.ownership_history, change),
            version=self.version + 1,
        )

    def update_file(self, value: LibraryVersion) -> LibraryDocument:
        original = self.file_version(value.id)
        if (
            original.number,
            original.checksum,
            original.filename,
            original.mime_type,
            original.size_bytes,
            original.uploaded_at,
            original.uploaded_by,
            original.idempotency_key,
        ) != (
            value.number,
            value.checksum,
            value.filename,
            value.mime_type,
            value.size_bytes,
            value.uploaded_at,
            value.uploaded_by,
            value.idempotency_key,
        ):
            raise InvalidDocumentError("Original upload metadata is immutable.")
        return replace(
            self,
            versions=tuple(value if v.id == value.id else v for v in self.versions),
            version=self.version + 1,
        )

    def review(self, version_id: str, revision: ExtractionRevision) -> LibraryDocument:
        source = self.file_version(version_id)
        if source.stage is not IngestionStage.READY:
            raise InvalidDocumentError("Only successfully extracted evidence can be reviewed.")
        text_ids = {b.id for b in source.blocks}
        if {p.block_id for p in revision.passages} != text_ids:
            raise InvalidDocumentError(
                "Review must explicitly include or exclude every block, including images."
            )
        return self.update_file(replace(source, revisions=(*source.revisions, revision)))

    def approve(self, publication: Publication) -> LibraryDocument:
        source = self.file_version(publication.version_id)
        if source.stage is not IngestionStage.READY or source.unresolved_blocking_warnings:
            raise InvalidDocumentError("Blocking extraction problems prevent publication.")
        if not source.revisions or source.revisions[-1].id != publication.revision_id:
            raise InvalidDocumentError(
                "Approve the current extraction revision, not an old revision."
            )
        revision = source.revisions[-1]
        if not any(p.included for p in revision.passages):
            raise InvalidDocumentError("Publication requires at least one selected passage.")
        if publication.fingerprint != revision.fingerprint(source.id, publication.chunking_policy):
            raise InvalidDocumentError(
                "Publication fingerprint does not match the reviewed content."
            )
        if publication.approved_by.id != self.owner.id:
            raise InvalidDocumentError("Publication must be approved by the document owner.")
        if not publication.requires_activation and any(
            p.fingerprint == publication.fingerprint and p.withdrawn_at is None
            for p in self.publications
        ):
            raise InvalidDocumentError("This exact revision is already approved.")
        return replace(
            self, publications=(*self.publications, publication), version=self.version + 1
        )

    def activate(self, publication_id: str, at: datetime) -> LibraryDocument:
        candidates = [p for p in self.publications if p.withdrawn_at is None]
        if not candidates or candidates[-1].id != publication_id:
            raise InvalidDocumentError("Only the latest eligible approval can be activated.")
        publication = candidates[-1]
        if publication.requires_activation:
            source = self.file_version(publication.version_id)
            if (
                publication.built_at is None
                or publication.activated_at is not None
                or self.published_id != publication.replaces_publication_id
                or source.id != self.versions[-1].id
                or source.revisions[-1].id != publication.revision_id
            ):
                raise InvalidDocumentError("Build or source changed; rebuild before activation.")
        return replace(
            self,
            published_id=publication_id,
            version=self.version + 1,
            publications=tuple(
                replace(p, activated_at=at) if p.id == publication_id else p
                for p in self.publications
            ),
        )

    def withdraw(self, at: datetime, reason: str) -> LibraryDocument:
        if not reason.strip():
            raise InvalidDocumentError("Withdrawal requires a rationale.")
        return replace(
            self,
            published_id=None,
            version=self.version + 1,
            publications=tuple(
                replace(p, withdrawn_at=at, withdrawal_reason=reason)
                if p.withdrawn_at is None
                else p
                for p in self.publications
            ),
        )
