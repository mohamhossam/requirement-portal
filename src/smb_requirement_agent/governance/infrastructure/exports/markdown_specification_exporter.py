"""Markdown adapter for the Business Requirements Document: GitHub-flavoured, UTF-8, LF."""

from __future__ import annotations

from smb_requirement_agent.governance.application.specification import (
    RequirementSpecification,
    SpecificationFormat,
)
from smb_requirement_agent.governance.infrastructure.exports.specification_outline import (
    Block,
    Bullets,
    Heading,
    Numbered,
    Paragraph,
    Table,
    outline,
)

MARKDOWN_MEDIA_TYPE = "text/markdown; charset=utf-8"


class MarkdownSpecificationExporter:
    @property
    def format(self) -> SpecificationFormat:
        return SpecificationFormat.MARKDOWN

    @property
    def extension(self) -> str:
        return "md"

    @property
    def media_type(self) -> str:
        return MARKDOWN_MEDIA_TYPE

    def render(self, document: RequirementSpecification) -> bytes:
        text = "\n\n".join(_render(block) for block in outline(document))
        return (text.replace("\r\n", "\n").rstrip("\n") + "\n").encode("utf-8")


def _render(block: Block) -> str:
    match block:
        case Heading(level, text):
            return f"{'#' * (level + 1)} {_inline(text)}"
        case Paragraph(text, note):
            return f"*{_inline(text)}*" if note else text.strip()
        case Bullets(items):
            return "\n".join(f"- {_inline(item)}" for item in items)
        case Numbered(items):
            return "\n".join(f"{number}. {_inline(item)}" for number, item in enumerate(items, 1))
        case Table(headers, rows):
            lines = [
                "| " + " | ".join(_cell(item) for item in headers) + " |",
                "|" + "|".join(" --- " for _ in headers) + "|",
            ]
            lines.extend("| " + " | ".join(_cell(item) for item in row) + " |" for row in rows)
            return "\n".join(lines)


def _inline(value: str) -> str:
    return " ".join(value.split())


def _cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\r\n", "\n").replace("\n", "<br>").strip()
