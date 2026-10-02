# ADR 0078 — One authorization pattern for Requirement-scoped actions

## Status

Accepted. Refines ADR-0070: `RequirementCommands` keeps its unit of work, but
routes no longer choose a permission.

## Context

The second review found Requirement access decided four ways:

1. **A context manager over the raw access repository.**
   `authorized_requirement_mutation` took the repository and had its own
   `MutationPermission` enum. Ten modules used it.
2. **A copy of that fence in the service.**
   `RequirementAccessService.execute_member_mutation` and
   `execute_owner_mutation` were the same lock-and-check fence, written again.
3. **Route-chosen permissions.** `RequirementCommands.run(permission=...)` let
   the route pick, using a duplicate `RequirementPermission` enum.
4. **Inline checks.** About fifteen places read `RequirementAccess` and called
   `require_member`, `require_owner`, `includes` or `is_owner` themselves.

The rules agreed today, but any change had to be made in several places, and a
route could pick a weaker permission than its use case assumed.

## Decision

`RequirementAccessService` is the only component that decides a caller's
access to a Requirement.

- **`mutation(requirement_id, actor, permission)`** is the single fence. It
  checks access when the unit of work opens, around any provider I/O that
  releases the lock, and before commit. `execute_mutation` wraps it for
  callers that hold the work as a callable.
- **`automatic_mutation(requirement_id, operation)`** is the same fence for
  system work bound to a worker attempt.
- **`require(requirement_id, actor, permission)`** is a plain check for code
  already inside the unit of work.
- **Rules that need more than one permission level** get their own methods:
  `require_owner_of_either` (shared resolutions across two Requirements) and
  `require_answerer` (the owner, the question's assignee, or the team when the
  action allows).
- **One enum, `RequirementPermission`**, lives with the service.
  `mutation_authorization.py` and `MutationPermission` are deleted.
- **Use cases declare their permission.** Routes do not: `RequirementCommands`
  applies the member baseline to every command, and a use case that needs the
  owner enforces it through the same service. `ApprovalRecorder.require_member`
  and `require_owner` delegate to the service.
- **Guard tests** (`tests/architecture/test_authorization_placement.py`)
  enforce this. Outside the service, nothing calls `require_member` or
  `require_owner`, except through the delegating recorder. Nothing raises
  `AuthorizationDeniedError` for Requirement access. And no route names
  `RequirementPermission`.

## Consequences

- **One place to change a rule.** A change to who may act on a Requirement is
  made in one class, and the guard test fails if a new use case checks access
  its own way.
- **Constructor signatures changed.** Use cases that only authorized with the
  repository now take `authorization: RequirementAccessService`. Those that
  also read ownership data, to record owners or snapshot actors, keep the
  repository for reads.
- **A missing Requirement is now a 404, not a 403.** Source-impact queries
  about a Requirement that doesn't exist now return 404, the same as every
  other Requirement-scoped action.
- **Library documents are a separate resource.** Their ownership rules stay in
  their own use cases; the guard's allow-list names each one and why.

## Alternatives Considered

- **Keep route-level permissions, and remove self-authorization from use
  cases.** Rejected. The rule would be invisible to every other caller: the
  worker process, jobs, and tests.
- **A port for authorization.** Rejected for now. There is one implementation,
  and the service is already an application component that tests can build
  over in-memory repositories (`tests/unit/access_service.py`).
