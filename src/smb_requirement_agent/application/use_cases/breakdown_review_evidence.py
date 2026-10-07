"""The evidence a breakdown review is built from: now `domain/review/evidence.py`.

MIGRATION SHIM (ADR-0103 PR 6): the import-rewrite commit points every importer at the
domain and deletes this module.
"""

from smb_requirement_agent.domain.review.evidence import ReviewEvidence as ReviewEvidence
from smb_requirement_agent.domain.review.evidence import (
    evidence_fingerprint as evidence_fingerprint,
)
