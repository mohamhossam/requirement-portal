"""The breakdown review rules: now `domain/review/policy.py`.

MIGRATION SHIM (ADR-0103 PR 6): the import-rewrite commit points every importer at the
domain and deletes this module.
"""

from smb_requirement_agent.domain.review.policy import (
    REVIEW_RULESET_VERSION as REVIEW_RULESET_VERSION,
)
from smb_requirement_agent.domain.review.policy import (
    BreakdownReviewPolicy as BreakdownReviewPolicy,
)
