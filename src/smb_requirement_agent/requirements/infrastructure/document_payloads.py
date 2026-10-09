"""Snapshot mapping for source documents and their versions."""

from __future__ import annotations

from datetime import datetime

from smb_requirement_agent.infrastructure.persistence.payload_fields import (
    JsonObject,
    boolean_field,
    integer_field,
    item_text,
    json_array,
    json_object,
    nullable_text,
    optional_integer,
    optional_requirement_id,
    required_text,
    text_array,
)
from smb_requirement_agent.requirements.domain.document.entities import (
    DocumentAsset,
    DocumentEvidenceBlock,
    DocumentExtractionWarning,
    SourceDocument,
    SourceDocumentVersion,
)
from smb_requirement_agent.requirements.domain.document.value_objects import (
    DocumentId,
    DocumentVersionId,
    EvidenceBlockKind,
    ExtractionStatus,
    ExtractionWarningSeverity,
)


def document_to_payload(value: SourceDocument) -> JsonObject:
    return {
        "id": value.id.value,
        "requirement_id": value.requirement_id.value if value.requirement_id else None,
        "draft_id": value.draft_id.value if value.draft_id else None,
        "included_version_id": (
            value.included_version_id.value if value.included_version_id else None
        ),
        "included_hidden_worksheets": list(value.included_hidden_worksheets),
        "removed": value.removed,
        "requires_attention": value.requires_attention,
        "version_number": value.version_number,
        "versions": [
            {
                "id": version.id.value,
                "number": version.number,
                "filename": version.filename,
                "mime_type": version.mime_type,
                "size_bytes": version.size_bytes,
                "checksum_sha256": version.checksum_sha256,
                "extraction_status": version.extraction_status.value,
                "created_at": version.created_at.isoformat(),
                "extracted_text": version.extracted_text,
                "extraction_error": version.extraction_error,
                "extraction_version": version.extraction_version,
                "evidence_blocks": [
                    {
                        "id": block.id,
                        "kind": block.kind.value,
                        "ordinal": block.ordinal,
                        "section_path": list(block.section_path),
                        "label": block.label,
                        "content_fingerprint": block.content_fingerprint,
                        "text": block.text,
                        "asset_id": block.asset_id,
                    }
                    for block in version.evidence_blocks
                ],
                "extraction_warnings": [
                    {
                        "code": warning.code,
                        "severity": warning.severity.value,
                        "message": warning.message,
                        "block_id": warning.block_id,
                    }
                    for warning in version.extraction_warnings
                ],
                "assets": [
                    {
                        "id": asset.id,
                        "block_id": asset.block_id,
                        "mime_type": asset.mime_type,
                        "package_path": asset.package_path,
                        "checksum_sha256": asset.checksum_sha256,
                    }
                    for asset in version.assets
                ],
            }
            for version in value.versions
        ],
    }


def document_from_payload(data: JsonObject) -> SourceDocument:
    return SourceDocument(
        id=DocumentId(required_text(data, "id")),
        requirement_id=optional_requirement_id(data, "requirement_id"),
        draft_id=optional_requirement_id(data, "draft_id"),
        included_version_id=(
            DocumentVersionId(item_text(data["included_version_id"]))
            if data.get("included_version_id") is not None
            else None
        ),
        included_hidden_worksheets=tuple(
            text_array(data, "included_hidden_worksheets")
            if "included_hidden_worksheets" in data
            else ()
        ),
        removed=boolean_field(data, "removed"),
        requires_attention=bool(data.get("requires_attention", False)),
        version_number=optional_integer(data, "version_number", 1),
        versions=tuple(
            SourceDocumentVersion(
                id=DocumentVersionId(required_text(json_object(item), "id")),
                number=integer_field(json_object(item), "number"),
                filename=required_text(json_object(item), "filename"),
                mime_type=required_text(json_object(item), "mime_type"),
                size_bytes=integer_field(json_object(item), "size_bytes"),
                checksum_sha256=required_text(json_object(item), "checksum_sha256"),
                extraction_status=ExtractionStatus(
                    required_text(json_object(item), "extraction_status")
                ),
                created_at=datetime.fromisoformat(required_text(json_object(item), "created_at")),
                extracted_text=nullable_text(json_object(item), "extracted_text"),
                extraction_error=nullable_text(json_object(item), "extraction_error"),
                extraction_version=(
                    nullable_text(json_object(item), "extraction_version")
                    if "extraction_version" in json_object(item)
                    else None
                ),
                evidence_blocks=tuple(
                    DocumentEvidenceBlock(
                        id=required_text(json_object(block), "id"),
                        kind=EvidenceBlockKind(required_text(json_object(block), "kind")),
                        ordinal=integer_field(json_object(block), "ordinal"),
                        section_path=tuple(
                            item_text(value)
                            for value in json_array(json_object(block), "section_path")
                        ),
                        label=required_text(json_object(block), "label"),
                        content_fingerprint=required_text(
                            json_object(block), "content_fingerprint"
                        ),
                        text=nullable_text(json_object(block), "text"),
                        asset_id=nullable_text(json_object(block), "asset_id"),
                    )
                    for block in (
                        json_array(json_object(item), "evidence_blocks")
                        if "evidence_blocks" in json_object(item)
                        else []
                    )
                ),
                extraction_warnings=tuple(
                    DocumentExtractionWarning(
                        code=required_text(json_object(warning), "code"),
                        severity=ExtractionWarningSeverity(
                            required_text(json_object(warning), "severity")
                        ),
                        message=required_text(json_object(warning), "message"),
                        block_id=nullable_text(json_object(warning), "block_id"),
                    )
                    for warning in (
                        json_array(json_object(item), "extraction_warnings")
                        if "extraction_warnings" in json_object(item)
                        else []
                    )
                ),
                assets=tuple(
                    DocumentAsset(
                        id=required_text(json_object(asset), "id"),
                        block_id=required_text(json_object(asset), "block_id"),
                        mime_type=required_text(json_object(asset), "mime_type"),
                        package_path=required_text(json_object(asset), "package_path"),
                        checksum_sha256=required_text(json_object(asset), "checksum_sha256"),
                    )
                    for asset in (
                        json_array(json_object(item), "assets")
                        if "assets" in json_object(item)
                        else []
                    )
                ),
            )
            for item in json_array(data, "versions")
        ),
    )
