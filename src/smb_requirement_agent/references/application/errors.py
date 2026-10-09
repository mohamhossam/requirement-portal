"""Reference failures raised by the references use cases."""


class KnowledgeViewUnavailableError(Exception):
    """A cited passage or architecture evidence is no longer published (ADR-0099)."""


class CitationNotCurrentError(Exception):
    """A cited reference was withdrawn or replaced since it was cited (ADR-0099)."""
