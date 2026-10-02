"""Reading architecture documents for proposed catalogue changes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.domain.architecture.candidates import CandidateBasis, CandidateContent


class CatalogueExtractionError(Exception):
    """The model produced nothing usable; the provider is at fault, not the caller."""


class CatalogueAnswerUnusableError(CatalogueExtractionError):
    """Every answer was malformed, empty or refused, even when asked again.

    Raised from the provider's last failure, so its classification (a timeout,
    a rate limit, invalid output) is what a person is told.
    """


class CatalogueCitationError(CatalogueExtractionError):
    """The model answered, but no suggestion quoted the document so it could be checked."""


class CatalogueExtractionUnsupportedError(Exception):
    """The configured model cannot read this kind of document (for example images)."""


@dataclass(frozen=True)
class ExtractionSegment:
    """A numbered, citable piece of the document: text, or an image read by a vision model.

    ``section`` is the headings the piece sits under, outermost first, so a table
    row read apart from its heading still says what it belongs to. ``cells`` are
    a table row's (column, value) pairs. ``read`` marks a row whose systems and
    dependencies were already taken from its cells (ADR-0093).
    """

    number: int
    location: str
    text: str = ""
    image_mime_type: str | None = None
    image: bytes = b""
    section: tuple[str, ...] = ()
    cells: tuple[tuple[str, str], ...] = ()
    read: bool = False


@dataclass(frozen=True)
class KnownSystem:
    id: str
    name: str
    aliases: tuple[str, ...]
    # Its components' names, so a reading reuses them rather than renaming them.
    components: tuple[str, ...] = ()


def _no_checkpoint() -> None:
    return None


@dataclass(frozen=True)
class ExtractionRequest:
    """A whole document. The extractor reads it in as many calls as its model needs.

    ``checkpoint`` runs before each call and raises to stop reading, for example
    when the document has left the draft meanwhile.
    """

    document_title: str
    segments: tuple[ExtractionSegment, ...]
    known_systems: tuple[KnownSystem, ...]
    checkpoint: Callable[[], None] = _no_checkpoint


@dataclass(frozen=True)
class ProposedChange:
    """A proposal and where it is stated: document locations and verbatim source text.

    ``source_name`` and ``target_name`` are the system names as the document
    writes them, kept because the content holds only ids. An inferred change
    carries the model's ``rationale`` for reading it from the passages.
    ``reader`` names what proposed it, as (name, version), when that was not
    the proposal's model, such as the table reader.
    """

    content: CandidateContent
    locations: tuple[str, ...]
    quote: str
    source_name: str = ""
    target_name: str = ""
    basis: CandidateBasis = CandidateBasis.STATED
    rationale: str | None = None
    reader: tuple[str, str] | None = None


@dataclass(frozen=True)
class CatalogueProposal:
    changes: tuple[ProposedChange, ...]
    model: str
    prompt_version: str
    warnings: tuple[str, ...] = ()


class CatalogueExtractorPort(Protocol):
    @property
    def supports_images(self) -> bool: ...

    @property
    def model(self) -> str: ...

    @property
    def prompt_version(self) -> str: ...

    def propose(self, request: ExtractionRequest) -> CatalogueProposal:
        """Propose changes citing the supplied segments only.

        A part of the document that cannot be read becomes a warning; the call
        raises CatalogueExtractionError (or the subclass naming why) only when
        no part could be read, and CatalogueExtractionUnsupportedError when the
        model cannot read it at all.
        """
        ...
