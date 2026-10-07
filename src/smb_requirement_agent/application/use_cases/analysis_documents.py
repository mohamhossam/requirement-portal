"""Assemble a Requirement's included source documents into analysis input.

Analysis reads requirement work's documents through its ports; the analysis input
types it builds are analysis's own (ADR-0103 PR 9).
"""

from __future__ import annotations

from dataclasses import dataclass

from smb_kernel.documents.ports import DocumentExtractorPort, DocumentStoragePort

from smb_requirement_agent.application.errors import DocumentContextTooLargeError
from smb_requirement_agent.application.ports.requirement_analyzer import AnalysisDocumentContext
from smb_requirement_agent.domain.analysis.entities import AnalysisDocumentReference
from smb_requirement_agent.requirements.application.ports.document_repository import (
    DocumentRepositoryPort,
)
from smb_requirement_agent.requirements.application.use_cases.requirement_sources import (
    source_eligibility,
)
from smb_requirement_agent.requirements.domain.document.entities import SourceDocument
from smb_requirement_agent.requirements.domain.requirement.entities import (
    AnalysisEligibility,
    Requirement,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


@dataclass(frozen=True)
class AnalysisDocumentSelection:
    contexts: tuple[AnalysisDocumentContext, ...]
    references: tuple[AnalysisDocumentReference, ...]


class AssembleAnalysisDocuments:
    def __init__(
        self,
        documents: DocumentRepositoryPort,
        storage: DocumentStoragePort,
        extractor: DocumentExtractorPort,
        max_characters: int,
    ) -> None:
        self._documents = documents
        self._storage = storage
        self._extractor = extractor
        self._max_characters = max_characters

    def selection_snapshot(self, requirement_id: RequirementId) -> tuple[SourceDocument, ...]:
        """Read source metadata without extracting bytes or invoking a provider."""
        return tuple(
            sorted(
                self._documents.list_for_requirement(requirement_id), key=lambda item: item.id.value
            )
        )

    def eligibility(self, requirement: Requirement) -> AnalysisEligibility:
        return source_eligibility(requirement, self.selection_snapshot(requirement.id))

    def execute(self, requirement_id: RequirementId) -> AnalysisDocumentSelection:
        contexts: list[AnalysisDocumentContext] = []
        references: list[AnalysisDocumentReference] = []
        total = 0
        for document in self._documents.list_for_requirement(requirement_id):
            if not document.is_included or document.included_version_id is None:
                continue
            version = document.version(document.included_version_id)
            selected_blocks = document.included_blocks
            text = (
                "\n".join(block.text for block in selected_blocks if block.text)
                if version.extraction_version is not None
                else version.extracted_text or ""
            )
            total += len(text) if version.extraction_version is None else 0
            if total > self._max_characters:
                raise DocumentContextTooLargeError(
                    "Selected document text exceeds the configured analysis context window; "
                    "exclude a document and try again."
                )
            contexts.append(
                AnalysisDocumentContext(
                    document_id=document.id.value,
                    version_id=version.id.value,
                    filename=version.filename,
                    checksum_sha256=version.checksum_sha256,
                    extracted_text=text,
                    extraction_version=version.extraction_version or "legacy-plain-text",
                    evidence_blocks=[
                        {
                            "block_id": block.id,
                            "kind": block.kind.value,
                            "section_path": list(block.section_path),
                            "label": block.label,
                            "text": block.text,
                            "asset_id": block.asset_id,
                        }
                        for block in selected_blocks
                    ],
                    image_assets=[
                        {
                            "asset_id": asset.id,
                            "block_id": asset.block_id,
                            "mime_type": asset.mime_type,
                            "content": self._extractor.extract_asset(
                                version.mime_type,
                                self._storage.get(version.id),
                                asset.package_path,
                            ),
                        }
                        for asset in version.assets
                        if asset.block_id in {block.id for block in selected_blocks}
                    ],
                )
            )
            references.append(
                AnalysisDocumentReference(
                    document.id.value,
                    version.id.value,
                    version.filename,
                    version.checksum_sha256,
                )
            )
        return AnalysisDocumentSelection(tuple(contexts), tuple(references))
