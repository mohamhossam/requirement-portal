"""Source-preserving token offsets for architecture evidence windows."""

from typing import Protocol


class ArchitectureTokenizerPort(Protocol):
    @property
    def profile(self) -> str: ...

    def spans(self, content: str) -> tuple[tuple[int, int], ...]: ...
