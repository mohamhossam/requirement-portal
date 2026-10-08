"""The governance bounded context (ADR-0103): review, approval, revisions and export of a backlog.

Supporting subdomain, downstream of breakdown. `domain/review/` holds the `BreakdownReview` and
its rules; `domain/revision/` the immutable revisions an approved backlog is exported from.
"""
