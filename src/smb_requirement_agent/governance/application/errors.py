"""Review, approval and export failures raised by the governance use cases."""


class BreakdownReviewNotFoundError(Exception):
    """No generated breakdown review exists for the Requirement."""


class BreakdownReviewStaleError(Exception):
    """A review mutation targeted evidence that has since changed."""


class ReviewFlagNotFoundError(Exception):
    """A requested flag is absent from the current review."""


class ApprovalWorkflowNotReadyError(Exception):
    """The breakdown is incomplete or lacks current attributed approvals."""


class ApprovalPolicyBlockedError(Exception):
    """The configured governance policy prevents final approval."""


class BreakdownRevisionNotExportableError(Exception):
    """The selected immutable revision lacks a formal final approval."""


class BacklogExportFormatError(Exception):
    """A neutral export format cannot represent the selected content safely."""
