"""The shared kernel of requirement-portal's bounded contexts (ADR-0103).

Pure domain: the review lifecycle, approvals, staleness, provenance, action availability,
`RequirementId`, the actor types, the citation contract and source lineage. It imports only
itself and platform-kernel's pure contract modules (`smb_kernel.identity.actor`,
`smb_kernel.documents.model`); the `shared_kernel_pure` import-linter contract enforces it.
A change here is a change to every context.
"""
