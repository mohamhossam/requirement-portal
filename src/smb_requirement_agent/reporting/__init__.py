"""The reporting bounded context (ADR-0103): the Requirement worklist, activity and saved views.

A read side, downstream of every context but workflows. It has no domain layer: it
reads projections other contexts' changes maintain, and owns the ports for them.
"""
