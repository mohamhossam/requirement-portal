"""The workflows context (ADR-0103): commands, jobs, access and reads that span several contexts.

Orchestration, downstream of every context. It has no domain layer: it coordinates the other
contexts' use cases, runs AI jobs, implements identity's `RequirementAccessPort` and the
generation context tokens, and serves the internal reads. No context imports it.
"""
