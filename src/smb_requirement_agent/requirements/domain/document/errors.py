"""Document domain errors.

`DocumentError` and `InvalidDocumentError` are platform-kernel's, re-exported
(ADR-0100), so extraction failures and lifecycle failures share one hierarchy.
"""

from smb_kernel.documents.model import DocumentError as DocumentError
from smb_kernel.documents.model import InvalidDocumentError as InvalidDocumentError


class DocumentInclusionError(DocumentError):
    """A failed or removed version was selected for analysis."""
