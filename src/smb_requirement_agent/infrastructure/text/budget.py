"""A conservative text budget for model prompts."""


class Utf8BudgetCounter:
    """Conservative byte budget, not an English chars/4 estimate.

    One UTF-8 byte is charged as one budget unit, never a measured model token.
    A dated model-specific qualification measures representative chunks separately.
    Identity prevents silently mixing it with a later model-specific counter.
    """

    @property
    def identity(self) -> str:
        return "utf8-byte-upper-bound-v1"

    def count(self, text: str) -> int:
        return len(text.encode("utf-8"))
