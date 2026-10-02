"""Catalogue files maintainers upload or download: Excel, YAML or JSON."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from smb_requirement_agent.domain.architecture.journeys import Journey
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    CapabilityDomain,
    InvalidKnowledgeError,
    LandscapeDomain,
    SystemDefinition,
    SystemRelationship,
)
from smb_requirement_agent.domain.architecture.products import ProductOffering


class CatalogueFileFormat(StrEnum):
    XLSX = "xlsx"
    YAML = "yaml"
    JSON = "json"

    @classmethod
    def from_filename(cls, filename: str) -> CatalogueFileFormat:
        suffix = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
        formats = {"xlsx": cls.XLSX, "yaml": cls.YAML, "yml": cls.YAML, "json": cls.JSON}
        if suffix not in formats:
            raise InvalidKnowledgeError(
                "Upload the catalogue as an Excel (.xlsx), YAML (.yaml, .yml) or JSON file."
            )
        return formats[suffix]

    @property
    def media_type(self) -> str:
        return {
            CatalogueFileFormat.XLSX: (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            CatalogueFileFormat.YAML: "application/yaml",
            CatalogueFileFormat.JSON: "application/json",
        }[self]


@dataclass(frozen=True)
class CatalogueContent:
    """The editable body of a release; identity, status and documents stay with the draft."""

    systems: tuple[SystemDefinition, ...]
    relationships: tuple[SystemRelationship, ...]
    capability_domains: tuple[CapabilityDomain, ...] = ()
    landscape_domains: tuple[LandscapeDomain, ...] = ()
    products: tuple[ProductOffering, ...] = ()
    journeys: tuple[Journey, ...] = ()


class CatalogueFilePort(Protocol):
    def read(self, file_format: CatalogueFileFormat, content: bytes) -> CatalogueContent:
        """Parse a file; a malformed one raises InvalidKnowledgeError naming where."""
        ...

    def write(self, file_format: CatalogueFileFormat, release: ArchitectureKnowledge) -> bytes: ...

    def template(self) -> bytes:
        """An empty Excel workbook with the expected sheets, headers and instructions."""
        ...
