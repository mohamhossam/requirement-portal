"""Exact text spans small enough to embed (ADR-0103 PR 15a; was in `requirement_knowledge`).

The historic corpus chunks with it as well as Requirement knowledge, so it is references'
(ADR-0103 Amendment 1).
"""


def bounded_knowledge_text(text: str) -> tuple[str, ...]:
    """Exact contiguous spans, at most 768 UTF-8 budget units, never model tokens."""
    parts: list[str] = []
    start = size = 0
    for position, character in enumerate(text):
        width = len(character.encode("utf-8"))
        if size + width > 768:
            parts.append(text[start:position])
            start, size = position, 0
        size += width
    if start < len(text):
        parts.append(text[start:])
    return tuple(parts)
