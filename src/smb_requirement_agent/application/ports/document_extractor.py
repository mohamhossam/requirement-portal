"""Structured evidence extraction boundary for validated document bytes."""

from dataclasses import dataclass
from typing import Protocol

from smb_requirement_agent.domain.document.entities import (
    DocumentAsset,
    DocumentEvidenceBlock,
    DocumentExtractionWarning,
)


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    extraction_version: str
    evidence_blocks: tuple[DocumentEvidenceBlock, ...]
    warnings: tuple[DocumentExtractionWarning, ...]
    assets: tuple[DocumentAsset, ...]


class DocumentExtractorPort(Protocol):
    def extract(self, mime_type: str, content: bytes) -> str: ...

    def extract_structured(self, mime_type: str, content: bytes) -> ExtractedDocument: ...

    def extract_asset(self, mime_type: str, content: bytes, package_path: str) -> bytes: ...
