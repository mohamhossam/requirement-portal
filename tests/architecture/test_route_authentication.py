"""Every HTTP operation resolves an authenticated actor unless it is a public probe.

Internal operations (ADR-0099) are the one other kind: they resolve an
authenticated *service* caller instead, and never a user.

Authentication is attached per router, so a new router that forgets the
dependency would silently expose its operations. This walks the dependency tree
FastAPI actually executes for each route, router-level dependencies included.
"""

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from smb_requirement_agent.interfaces.api.dependencies import (
    get_current_actor,
    require_service_caller,
)
from smb_requirement_agent.interfaces.api.main import create_app

# Reachable before sign-in by design: orchestrator probes and the login bootstrap.
PUBLIC_OPERATIONS = {
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/identity/config"),
    # A browser reports its own failures, signed in or not (production hardening PR 12).
    ("POST", "/client-errors"),
}


def _resolves(dependant: Dependant, call: object) -> bool:
    return dependant.call is call or any(_resolves(child, call) for child in dependant.dependencies)


def _resolves_actor(dependant: Dependant) -> bool:
    return _resolves(dependant, get_current_actor)


def _service_operations() -> list[tuple[str, str, bool, bool]]:
    application = create_app()
    found: list[tuple[str, str, bool, bool]] = []
    for context in iter_route_contexts(application.routes):
        if not isinstance(context.original_route, APIRoute):
            continue
        if not str(context.path).startswith("/internal"):
            continue
        for method in sorted(context.methods or ()):
            found.append(
                (
                    method,
                    str(context.path),
                    _resolves(context.dependant, require_service_caller),
                    _resolves_actor(context.dependant),
                )
            )
    return found


def _operations() -> list[tuple[str, str, bool]]:
    # The container is built in the lifespan, so creating the app wires nothing.
    application = create_app()
    operations: list[tuple[str, str, bool]] = []
    for context in iter_route_contexts(application.routes):
        if not isinstance(context.original_route, APIRoute):
            continue
        if str(context.path).startswith("/internal"):
            continue
        authenticated = _resolves_actor(context.dependant)
        for method in sorted(context.methods or ()):
            operations.append((method, str(context.path), authenticated))
    return operations


def test_every_operation_requires_an_authenticated_actor() -> None:
    operations = _operations()
    unauthenticated = {
        (method, path) for method, path, authenticated in operations if not authenticated
    }

    assert len(operations) > 100, "Route discovery found too few operations to be trusted."
    assert unauthenticated == PUBLIC_OPERATIONS, (
        f"Unauthenticated operations: {sorted(unauthenticated - PUBLIC_OPERATIONS)}; "
        f"public probes that now require sign-in: {sorted(PUBLIC_OPERATIONS - unauthenticated)}"
    )


def test_every_internal_operation_requires_a_service_caller_and_no_user() -> None:
    operations = _service_operations()

    assert operations, "No internal operations were discovered."
    assert all(service and not user for _, _, service, user in operations), [
        (method, path) for method, path, service, user in operations if not service or user
    ]
