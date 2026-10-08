"""Application failures caused by orchestration or external boundaries.

Infrastructure failures raised by platform-kernel mechanisms are re-exported, not
redefined (ADR-0100), so a handler for one of these names catches exactly what
the kernel raises.
"""

from smb_kernel.errors import AuthenticationRequiredError as AuthenticationRequiredError
from smb_kernel.errors import DocumentExtractionBusyError as DocumentExtractionBusyError
from smb_kernel.errors import DocumentExtractionError as DocumentExtractionError
from smb_kernel.errors import DocumentExtractionTimeoutError as DocumentExtractionTimeoutError
from smb_kernel.errors import IdentityProviderUnavailableError as IdentityProviderUnavailableError
from smb_kernel.errors import KnowledgeGenerationError as KnowledgeGenerationError
from smb_kernel.errors import ModelTransportError as ModelTransportError
from smb_kernel.errors import PersistenceError as PersistenceError
from smb_kernel.errors import ServiceResponseError as ServiceResponseError
from smb_kernel.errors import ServiceUnavailableError as ServiceUnavailableError
from smb_kernel.errors import UnsupportedDocumentError as UnsupportedDocumentError


class ArtifactVersionConflictError(Exception):
    """A generated artifact mutation used a stale aggregate version."""
