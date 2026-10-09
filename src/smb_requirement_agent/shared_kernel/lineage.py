"""Recorded evidence origins, independent of wording and retrieval similarity."""

from dataclasses import dataclass, replace

from smb_kernel.documents.model import InvalidDocumentError

from smb_requirement_agent.shared_kernel.citation import PublishedReference


@dataclass(frozen=True)
class SourceLineage:
    citation: PublishedReference
    via: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if any(not step.strip() for step in self.via):
            raise InvalidDocumentError("Evidence lineage steps cannot be blank.")

    def through(self, source: str) -> "SourceLineage":
        return replace(self, via=(*self.via, source))


def merge_lineage(*groups: tuple[SourceLineage, ...]) -> tuple[SourceLineage, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group))
