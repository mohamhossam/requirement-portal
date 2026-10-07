"""Approval subjects and the blocker policy: now `domain/review/fingerprints.py` and `policy.py`.

MIGRATION SHIM (ADR-0103 PR 6): the import-rewrite commit points every importer at the
domain and deletes this module.
"""

from smb_requirement_agent.domain.review.fingerprints import (
    artifact_fingerprint as artifact_fingerprint,
)
from smb_requirement_agent.domain.review.fingerprints import (
    breakdown_fingerprint as breakdown_fingerprint,
)
from smb_requirement_agent.domain.review.policy import ApprovalPolicy as ApprovalPolicy
