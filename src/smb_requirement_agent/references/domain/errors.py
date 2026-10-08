"""The base knowledge error and the invalid-content error references and knowledge share.

references' (ADR-0103 PR 15a); the screening errors are knowledge's, in `screening_errors.py`.
"""


class KnowledgeError(Exception):
    """Base error for knowledge-review behavior."""


class InvalidKnowledgeError(KnowledgeError):
    """Knowledge content violates a domain invariant."""
