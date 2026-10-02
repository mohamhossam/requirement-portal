"""Every HTTP operation resolves an authenticated actor unless it is a public probe.

Authentication is attached per router, so a new router that forgets the
dependency would silently expose its operations. This walks the dependency tree
FastAPI actually executes for each route, router-level dependencies included.
"""

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, iter_route_contexts

from smb_requirement_agent.interfaces.api.dependencies import get_current_actor
from smb_requirement_agent.interfaces.api.main import create_app

# Reachable before sign-in by design: orchestrator probes and the login bootstrap.
PUBLIC_OPERATIONS = {
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/identity/config"),
}


def _resolves_actor(dependant: Dependant) -> bool:
    return dependant.call is get_current_actor or any(
        _resolves_actor(child) for child in dependant.dependencies
    )


def _operations() -> list[tuple[str, str, bool]]:
    # The container is built in the lifespan, so creating the app wires nothing.
    application = create_app()
    operations: list[tuple[str, str, bool]] = []
    for context in iter_route_contexts(application.routes):
        if not isinstance(context.original_route, APIRoute):
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
