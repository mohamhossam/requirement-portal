"""Shared boundary checks for immutable document uploads (PDF, DOCX and TXT by default)."""

from pathlib import PurePosixPath, PureWindowsPath

from smb_requirement_agent.application.errors import UnsupportedDocumentError

SUPPORTED_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}


def validate_document_upload(
    filename: str,
    mime_type: str,
    content: bytes,
    max_bytes: int,
    supported: dict[str, str] = SUPPORTED_EXTENSIONS,
) -> tuple[str, str]:
    filename = filename.strip()
    if (
        not filename
        or "\x00" in filename
        or PurePosixPath(filename).name != filename
        or PureWindowsPath(filename).name != filename
    ):
        raise UnsupportedDocumentError("Document filename must not contain a path.")
    if not content:
        raise UnsupportedDocumentError("Document file must not be empty.")
    if len(content) > max_bytes:
        raise UnsupportedDocumentError(f"Document exceeds the {max_bytes} byte upload limit.")
    mime_type = mime_type.split(";", 1)[0].strip().lower()
    extensions = supported.get(mime_type, "")
    if not extensions or not filename.lower().endswith(tuple(extensions.split(","))):
        kinds = ", ".join(sorted({value.split(",")[0][1:].upper() for value in supported.values()}))
        raise UnsupportedDocumentError(
            f"Document extension and declared MIME type must agree for {kinds}."
        )
    return filename, mime_type
