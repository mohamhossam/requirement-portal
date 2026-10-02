"""Token spans that size architecture evidence windows."""

from __future__ import annotations

import re


class FakeWordTokenizer:
    @property
    def profile(self) -> str:
        return "offline-word-v1"

    def spans(self, content: str) -> tuple[tuple[int, int], ...]:
        return tuple(match.span() for match in re.finditer(r"\S+", content))


class ApproximateTokenizer:
    """Model-agnostic token spans: words, with long words cut every four characters.

    Architecture evidence may be embedded by any configured provider, and hosted
    providers publish no tokenizer file. Four characters is at most one token for
    English subword vocabularies and a conservative window for Arabic, so a
    500-span window stays well inside every supported embedding model's input.
    """

    @property
    def profile(self) -> str:
        return "approx-4c-v1"

    def spans(self, content: str) -> tuple[tuple[int, int], ...]:
        return tuple(
            (start, min(start + 4, match.end()))
            for match in re.finditer(r"\S+", content)
            for start in range(match.start(), match.end(), 4)
        )
