"""Safe text extraction with page, paragraph, line, or row references."""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

from pypdf import PdfReader
from smb_kernel.documents.ports import DocumentExtractorPort

from smb_requirement_agent.application.ports.located_document_extractor import LocatedText
from smb_requirement_agent.domain.document.value_objects import EvidenceBlockKind
from smb_requirement_agent.infrastructure.architecture.markdown_passages import (
    markdown_passages,
)


class LocatedDocumentExtractor:
    def __init__(self, validator: DocumentExtractorPort) -> None:
        self._validator = validator

    def extract(self, mime_type: str, content: bytes) -> tuple[LocatedText, ...]:
        # Spreadsheet rows come straight from the validated extraction.
        if mime_type == _XLSX:
            return self._worksheet_rows(content)
        if mime_type in {"text/csv", "text/tab-separated-values"}:
            return tuple(
                LocatedText(block.label.lower(), block.text)
                for block in self._validator.extract_structured(mime_type, content).evidence_blocks
                if block.kind is EvidenceBlockKind.TABLE_ROW and block.text
            )
        self._validator.extract(mime_type, content)
        if mime_type in {"image/png", "image/jpeg"}:
            # Images carry no citable text; a vision model reads them for suggestions only.
            return ()
        if mime_type == "application/pdf":
            reader = PdfReader(io.BytesIO(content), strict=True)
            return tuple(
                LocatedText(f"page {number}", text.strip())
                for number, page in enumerate(reader.pages, 1)
                if (text := page.extract_text() or "").strip()
            )
        if mime_type == "text/markdown":
            # Passages follow its headings and tables (ADR-0090, as amended).
            return markdown_passages(content.decode("utf-8-sig"))
        if mime_type == "text/plain":
            lines = content.decode("utf-8-sig").splitlines()
            return tuple(
                LocatedText(
                    f"lines {start + 1}-{min(start + 40, len(lines))}",
                    "\n".join(lines[start : start + 40]).strip(),
                )
                for start in range(0, len(lines), 40)
                if "\n".join(lines[start : start + 40]).strip()
            )
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
            styles = (
                _heading_styles(ElementTree.fromstring(archive.read("word/styles.xml")))
                if "word/styles.xml" in archive.namelist()
                else {}
            )
        body = root.find(f"{_W}body")
        if body is None:
            return ()
        segments: list[LocatedText] = []
        headings: list[str] = []
        paragraph_number = 0

        def append_paragraph(
            paragraph: ElementTree.Element, location: str, block: str | None = None
        ) -> None:
            nonlocal paragraph_number, headings
            paragraph_number += 1
            value = "".join(node.text or "" for node in paragraph.iter(f"{_W}t")).strip()
            if not value:
                return
            level = None if block else _heading_level(paragraph, styles)
            if level is None:
                segments.append(LocatedText(location, value, tuple(headings), block=block))
                return
            headings = [*headings[: level - 1], value]
            segments.append(LocatedText(location, value, tuple(headings[:-1]), heading=True))

        table_number = 0
        for element in body:
            if element.tag == f"{_W}p":
                append_paragraph(element, f"paragraph {paragraph_number + 1}")
            elif element.tag == f"{_W}tbl":
                table_number += 1
                for row_number, row in enumerate(element.findall(f"{_W}tr"), 1):
                    for cell_number, cell in enumerate(row.findall(f"{_W}tc"), 1):
                        for paragraph in cell.iter(f"{_W}p"):
                            append_paragraph(
                                paragraph,
                                f"table {table_number}, row {row_number}, "
                                f"cell {cell_number}, paragraph {paragraph_number + 1}",
                                f"table {table_number}, row {row_number}",
                            )
        return tuple(segments)

    def _worksheet_rows(self, content: bytes) -> tuple[LocatedText, ...]:
        """One passage per non-empty row, under its sheet's name.

        Hidden sheets are left out, as they are for requirement documents: nobody
        reviewing the workbook sees them.
        """
        segments: list[LocatedText] = []
        sheet_name = ""
        for block in self._validator.extract_structured(_XLSX, content).evidence_blocks:
            if not block.text or (block.section_path and block.section_path[0].startswith(_HIDDEN)):
                continue
            if block.kind is EvidenceBlockKind.HEADING:
                sheet_name = block.text
                location = f"sheet {block.label.removeprefix('Worksheet ')}"
                segments.append(LocatedText(location, sheet_name, heading=True))
            elif block.kind is EvidenceBlockKind.WORKSHEET_RANGE:
                row = _ROW.match(block.label)
                if row is None:  # A chart: its title and the ranges it plots.
                    segments.append(LocatedText(block.label.lower(), block.text))
                else:
                    segments.append(
                        LocatedText(
                            f"sheet {row['sheet']}, row {row['row']}", block.text, (sheet_name,)
                        )
                    )
        return tuple(segments)


_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_HIDDEN = "Hidden worksheet: "
_ROW = re.compile(r"^Worksheet (?P<sheet>\d+)!(?P<row>\d+):(?P=row)$")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_HEADING_NAME = re.compile(r"^heading\s*([1-9])$")


def _level(value: str | None) -> int | None:
    """A Word outline level (0-8) as a heading depth (1-9); 9 means body text."""
    if value is None or not value.isdigit() or int(value) > 8:
        return None
    return int(value) + 1


def _heading_styles(styles: ElementTree.Element) -> dict[str, int]:
    """Heading depth per paragraph style id, from outline levels or heading names.

    Style ids are localised (for example "berschrift1"), so the outline level or
    the style's English name decides, not the id.
    """
    result: dict[str, int] = {}
    for style in styles.iter(f"{_W}style"):
        style_id = style.get(f"{_W}styleId")
        if not style_id or style.get(f"{_W}type") != "paragraph":
            continue
        outline = style.find(f"{_W}pPr/{_W}outlineLvl")
        name_node = style.find(f"{_W}name")
        name = (name_node.get(f"{_W}val") if name_node is not None else "") or ""
        match = _HEADING_NAME.match(name.strip().casefold())
        level = _level(outline.get(f"{_W}val") if outline is not None else None) or (
            1 if name.strip().casefold() == "title" else int(match.group(1)) if match else None
        )
        if level is not None:
            result[style_id] = level
    return result


def _heading_level(paragraph: ElementTree.Element, styles: dict[str, int]) -> int | None:
    outline = paragraph.find(f"{_W}pPr/{_W}outlineLvl")
    if outline is not None:
        return _level(outline.get(f"{_W}val"))
    style = paragraph.find(f"{_W}pPr/{_W}pStyle")
    style_id = style.get(f"{_W}val") if style is not None else None
    if not style_id:
        return None
    if style_id in styles:
        return styles[style_id]
    match = _HEADING_NAME.match(style_id.casefold())
    return 1 if style_id.casefold() == "title" else int(match.group(1)) if match else None
