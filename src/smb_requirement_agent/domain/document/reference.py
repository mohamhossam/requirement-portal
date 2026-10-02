"""Immutable published-reference evidence; applicability is a separate human decision."""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass

from smb_requirement_agent.domain.document.errors import InvalidDocumentError


def normalize_search(text: str) -> str:
    """The normal form a citation's `lineage_hash` and reference search are computed over.

    It is part of the citation contract both contexts share (ADR-0099).
    """
    # Preserve original citation text. Search normalization removes Arabic tatweel/diacritics.
    return " ".join(
        "".join(
            c
            for c in unicodedata.normalize("NFKC", text).casefold()
            if c != "ـ" and not ("ً" <= c <= "ٟ") and c != "ٰ"
        ).split()
    )


@dataclass(frozen=True)
class PublishedReference:
    document_id: str
    title: str
    version_id: str
    version_number: int
    revision_id: str
    publication_id: str
    approval_fingerprint: str
    block_id: str
    location: str
    excerpt: str
    start_offset: int
    end_offset: int
    lineage_hash: str

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.document_id,
                self.title,
                self.version_id,
                self.revision_id,
                self.publication_id,
                self.block_id,
                self.location,
                self.excerpt,
            )
        ):
            raise InvalidDocumentError(
                "Published reference identity, text and location are required."
            )
        if self.version_number < 1 or self.start_offset < 0 or self.end_offset <= self.start_offset:
            raise InvalidDocumentError("Published reference version or passage range is invalid.")
        if self.end_offset - self.start_offset != len(self.excerpt):
            raise InvalidDocumentError("Published reference range must identify its exact excerpt.")
        for value in (self.approval_fingerprint, self.lineage_hash):
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise InvalidDocumentError("Published reference requires SHA-256 provenance.")


@dataclass(frozen=True)
class CurrentPublication:
    """What a document's live publication lets a citation prove (ADR-0099)."""

    publication_id: str
    fingerprint: str
    version_id: str
    version_number: int
    revision_id: str
    # (block id, label) for every block of the published version.
    block_labels: tuple[tuple[str, str], ...]
    # (block id, text) for every passage the published revision includes.
    passages: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ReferenceDocumentState:
    """A library document's citable state, as the reference library publishes it.

    Requirement work keeps a local copy of these, fed by the library's events, so
    it can check citations without reading the library (ADR-0099). `version`
    advances on every change to the document.
    """

    document_id: str
    owner_id: str
    title: str
    version: int
    published: CurrentPublication | None = None

    @property
    def publication_state(self) -> str:
        """How source-impact decisions identify the publication they were made against."""
        return f"{self.version}:{self.published.publication_id if self.published else 'withdrawn'}"

    def cites(self, citation: PublishedReference) -> bool:
        """True while `citation` still quotes this document's live publication exactly."""
        published = self.published
        if (
            published is None
            or published.publication_id != citation.publication_id
            or published.fingerprint != citation.approval_fingerprint
            or published.version_id != citation.version_id
            or published.revision_id != citation.revision_id
        ):
            return False
        passage = next(
            (text for block, text in published.passages if block == citation.block_id), None
        )
        return (
            passage is not None
            and self.title == citation.title
            and published.version_number == citation.version_number
            and any(
                block == citation.block_id and label == citation.location
                for block, label in published.block_labels
            )
            and hashlib.sha256(normalize_search(citation.excerpt).encode()).hexdigest()
            == citation.lineage_hash
            and passage[citation.start_offset : citation.end_offset] == citation.excerpt
        )

    def to_payload(self) -> dict[str, object]:
        """The event payload: plain JSON values."""
        published = self.published
        return {
            "document_id": self.document_id,
            "owner_id": self.owner_id,
            "title": self.title,
            "version": self.version,
            "published": None
            if published is None
            else {
                "publication_id": published.publication_id,
                "fingerprint": published.fingerprint,
                "version_id": published.version_id,
                "version_number": published.version_number,
                "revision_id": published.revision_id,
                "block_labels": [list(item) for item in published.block_labels],
                "passages": [list(item) for item in published.passages],
            },
        }

    @classmethod
    def from_payload(cls, payload: object) -> ReferenceDocumentState:
        """Rebuild a state from an event payload, refusing anything malformed."""
        try:
            data = _mapping(payload)
            published = data["published"]
            current = None
            if published is not None:
                item = _mapping(published)
                current = CurrentPublication(
                    _text(item["publication_id"]),
                    _text(item["fingerprint"]),
                    _text(item["version_id"]),
                    _number(item["version_number"]),
                    _text(item["revision_id"]),
                    _pairs(item["block_labels"]),
                    _pairs(item["passages"]),
                )
            return cls(
                _text(data["document_id"]),
                _text(data["owner_id"]),
                _text(data["title"]),
                _number(data["version"]),
                current,
            )
        except (KeyError, TypeError) as exc:
            raise InvalidDocumentError("Reference document event is malformed.") from exc


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected an object")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("expected text")
    return value


def _number(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("expected a whole number")
    return value


def _pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list | tuple):
        raise TypeError("expected a list")
    pairs: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, list | tuple) or len(item) != 2:
            raise TypeError("expected a pair")
        pairs.append((_text(item[0]), _text(item[1])))
    return tuple(pairs)
