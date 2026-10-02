"""Located text segments for verifiable architecture citations."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LocatedText:
    """One citable passage.

    `heading_path` holds the headings the passage sits under, outermost first.
    `heading` marks a passage that is itself a heading. Passages that share a
    `block` (the cells of one table row) belong together when indexed.
    `cells` holds a table row's (column, value) pairs, every column of its
    header included, when the format has one row per passage.
    """

    location: str
    text: str
    heading_path: tuple[str, ...] = ()
    heading: bool = False
    block: str | None = None
    cells: tuple[tuple[str, str], ...] = ()


class LocatedDocumentExtractorPort(Protocol):
    def extract(self, mime_type: str, content: bytes) -> tuple[LocatedText, ...]: ...
