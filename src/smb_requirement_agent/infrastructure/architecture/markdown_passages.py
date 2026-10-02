"""Markdown cut into citable passages that follow its headings and tables (ADR-0090).

A deliberately small reader of the GitHub-flavoured Markdown that architects
write: ATX and setext headings, paragraphs and lists, fenced code blocks, pipe
tables, and front matter. It never renders anything; a passage's text is the
document's own words, so a quote taken from it can be checked against it.

- A heading is its own passage and sets the heading path of what follows.
- A table row is one passage, ``line N``, written as ``Column: value | …`` so
  every row carries its header with it, whatever batch it lands in.
- Paragraphs, lists, block quotes and fenced blocks are passages of at most
  ``MAX_PASSAGE_LINES`` lines, ``line N`` or ``lines A-B``.
"""

from __future__ import annotations

import re

from smb_requirement_agent.application.ports.located_document_extractor import LocatedText

MAX_PASSAGE_LINES = 40
# Cells that say "nothing here" are left out of a row's text.
_EMPTY_CELLS = frozenset({"", "-", "—", "–", "n/a", "N/A"})

_ATX = re.compile(r"^ {0,3}(?P<marks>#{1,6})(?:[ \t]+(?P<text>.*?))?(?:[ \t]+#+)?[ \t]*$")
_SETEXT = re.compile(r"^ {0,3}(?P<mark>=+|-+)[ \t]*$")
_BREAK = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
_DELIMITER_CELL = re.compile(r"^:?-+:?$")
_LIST_ITEM = re.compile(r"^ {0,3}(?:[-+*]|\d{1,9}[.)])(?:[ \t]|$)")
_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def _cells(line: str) -> list[str]:
    """A table line's cells, outer pipes removed and escaped pipes restored."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.strip().replace("\\|", "|") for cell in _UNESCAPED_PIPE.split(body)]


def _delimiter(line: str) -> bool:
    if "-" not in line:
        return False
    return all(_DELIMITER_CELL.match(cell) for cell in _cells(line))


def _table_start(lines: list[str], index: int) -> bool:
    """A header line followed by a delimiter row with the same number of cells."""
    if index + 1 >= len(lines) or "|" not in lines[index]:
        return False
    return _delimiter(lines[index + 1]) and len(_cells(lines[index])) == len(
        _cells(lines[index + 1])
    )


def _location(first: int, last: int) -> str:
    """1-based line numbers as a passage location."""
    return f"line {first}" if first == last else f"lines {first}-{last}"


class _Reader:
    def __init__(self, lines: list[str]) -> None:
        self._lines = lines
        self._headings: list[str] = []
        # Each open heading's level, beside it: a document may start at "##", and a
        # heading closes every open one at its level or deeper, whatever the numbers.
        self._levels: list[int] = []
        self.passages: list[LocatedText] = []

    def _add(self, first: int, lines: list[str]) -> None:
        """Body text from 0-based line ``first``, in passages of bounded length."""
        for start in range(0, len(lines), MAX_PASSAGE_LINES):
            chunk = lines[start : start + MAX_PASSAGE_LINES]
            text = "\n".join(chunk).strip()
            if text:
                number = first + start + 1
                self.passages.append(
                    LocatedText(
                        _location(number, number + len(chunk) - 1),
                        text,
                        tuple(self._headings),
                    )
                )

    def _heading(self, index: int, level: int, text: str) -> None:
        text = text.strip()
        if not text:
            return
        while self._levels and self._levels[-1] >= level:
            self._levels.pop()
            self._headings.pop()
        self._levels.append(level)
        self._headings.append(text)
        self.passages.append(
            LocatedText(_location(index + 1, index + 1), text, tuple(self._headings[:-1]), True)
        )

    def read(self) -> tuple[LocatedText, ...]:
        lines, index = self._lines, 0
        if lines and lines[0].strip() == "---":
            # Front matter: kept as one passage, never read as a setext heading.
            end = next(
                (i for i in range(1, len(lines)) if lines[i].strip() in {"---", "..."}), None
            )
            if end is not None:
                self._add(0, lines[: end + 1])
                index = end + 1
        while index < len(lines):
            line = lines[index]
            if not line.strip() or _BREAK.match(line):
                # A thematic break only separates; an underline is read with its paragraph.
                index += 1
            elif heading := _ATX.match(line):
                self._heading(index, len(heading["marks"]), heading["text"] or "")
                index += 1
            elif fence := _FENCE.match(line):
                index = self._fenced(index, fence["fence"])
            elif _table_start(lines, index):
                index = self._table(index)
            else:
                index = self._paragraph(index)
        return tuple(self.passages)

    def _fenced(self, index: int, fence: str) -> int:
        closing = re.compile(rf"^ {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}[ \t]*$")
        end = next(
            (i for i in range(index + 1, len(self._lines)) if closing.match(self._lines[i])),
            len(self._lines) - 1,
        )
        self._add(index, self._lines[index : end + 1])
        return end + 1

    def _table(self, index: int) -> int:
        header = [
            cell or f"Column {number}" for number, cell in enumerate(_cells(self._lines[index]), 1)
        ]
        row = index + 2
        while row < len(self._lines) and self._lines[row].strip() and "|" in self._lines[row]:
            values = _cells(self._lines[row])
            # Every column, an empty cell as "", so a reader sees the table's whole header.
            cells = tuple(
                (
                    header[number] if number < len(header) else f"Column {number + 1}",
                    values[number] if number < len(values) else "",
                )
                for number in range(max(len(header), len(values)))
            )
            pairs = [(name, value) for name, value in cells if value not in _EMPTY_CELLS]
            if pairs:
                self.passages.append(
                    LocatedText(
                        _location(row + 1, row + 1),
                        " | ".join(f"{name}: {value}" for name, value in pairs),
                        tuple(self._headings),
                        cells=cells,
                    )
                )
            row += 1
        if row == index + 2:
            # A header with no rows says something only as text.
            self._add(index, self._lines[index : index + 1])
        return row

    def _paragraph(self, index: int) -> int:
        """Lines up to a blank line or another block; a setext heading when underlined."""
        end = index
        while end + 1 < len(self._lines):
            following = self._lines[end + 1]
            if (
                not following.strip()
                or _ATX.match(following)
                or _FENCE.match(following)
                or _table_start(self._lines, end + 1)
            ):
                break
            underline = _SETEXT.match(following)
            if underline and not _LIST_ITEM.match(self._lines[index]):
                level = 1 if underline["mark"].startswith("=") else 2
                self._add(index, self._lines[index:end])
                self._heading(end, level, self._lines[end])
                return end + 2
            if _BREAK.match(following):
                break
            end += 1
        self._add(index, self._lines[index : end + 1])
        return end + 1


def markdown_passages(text: str) -> tuple[LocatedText, ...]:
    """The passages of a decoded Markdown document, in document order."""
    return _Reader(text.splitlines()).read()
