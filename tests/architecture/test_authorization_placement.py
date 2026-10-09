"""Authorization and units of work are application decisions, never a route handler's.

A route that checks roles or membership itself hides the rule from every other
caller of the use case (the worker process, a CLI, another route) and invites
checks that run after data has already been loaded. A route that opens
snapshots, locks, or fences itself lets each route order those steps slightly
differently; `RequirementCommands` owns that order instead.
"""

import ast
from pathlib import Path

import smb_requirement_agent as root_package
import smb_requirement_agent.interfaces.api.routes as routes_package

ROLE_CHECKS = {"require_maintainer", "require_reader"}
UNIT_OF_WORK_AND_AUTHORIZATION = {
    "automatic_mutation",
    "can_access_draft",
    "execute_mutation",
    "lock_requirement",
    "mutation",
    "read_snapshot",
    "require_draft_owner",
    "require_requirement_member",
    "require_requirement_owner",
    "transaction",
}


def _route_sources() -> list[tuple[str, ast.AST]]:
    return [
        (path.name, ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(Path(routes_package.__file__).parent.glob("*.py"))
    ]


def test_route_handlers_do_not_perform_role_checks() -> None:
    offenders = [
        f"{name}:{node.lineno} {node.id}"
        for name, tree in _route_sources()
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in ROLE_CHECKS
    ]

    assert not offenders, "Move these checks into the use case: " + ", ".join(offenders)


def test_route_handlers_do_not_assemble_units_of_work_or_authorize() -> None:
    offenders = [
        f"{name}:{node.lineno} .{node.attr}"
        for name, tree in _route_sources()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr in UNIT_OF_WORK_AND_AUTHORIZATION
    ]

    assert not offenders, (
        "Use RequirementCommands or a self-authorizing use case instead: " + ", ".join(offenders)
    )


def test_generation_context_checks_are_not_made_by_routes() -> None:
    # `GenerationContextTokens.require(...)` is the check RequirementCommands makes
    # with an ExpectedContext; routes only compute tokens for their views.
    offenders = [
        f"{name}:{node.lineno}"
        for name, tree in _route_sources()
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "require"
        and isinstance(node.value, ast.Name)
        and node.value.id == "generation_context"
    ]

    assert not offenders, "Pass ExpectedContext to RequirementCommands instead: " + ", ".join(
        offenders
    )


def test_routes_never_choose_a_permission() -> None:
    # A command's permission is its use case's rule; routes get the member
    # baseline from RequirementCommands and nothing else (ADR-0078).
    offenders = [
        f"{name}:{node.lineno}"
        for name, tree in _route_sources()
        for node in ast.walk(tree)
        if isinstance(node, ast.Name | ast.Attribute)
        and (getattr(node, "id", None) or getattr(node, "attr", None)) == "RequirementPermission"
    ]

    assert not offenders, "Declare the permission in the use case: " + ", ".join(offenders)


# The service that owns Requirement authorization (ADR-0078).
ACCESS_SERVICE = "identity_access.py"
# Raising AuthorizationDeniedError outside the access service is reserved for
# rules about something other than the caller's access to a Requirement.
OTHER_AUTHORIZATION_RULES = {
    "analysis_collaboration.py": "a question assignee must be on the Requirement team",
    "document_library.py": "library document ownership",
    "library_governance.py": "library document ownership",
    "reference_knowledge.py": "library document ownership",
    "source_impact.py": "library document ownership",
}


def _use_case_sources() -> list[tuple[str, ast.AST]]:
    # Every context's use cases (ADR-0103): each context package has its own.
    sources: list[tuple[str, ast.AST]] = [
        (path.name, ast.parse(path.read_text(encoding="utf-8")))
        for path in sorted(Path(root_package.__file__).parent.glob("*/application/use_cases/*.py"))
    ]
    assert ACCESS_SERVICE in {name for name, _ in sources}, "the access service has moved"
    return sources


def test_only_the_access_service_checks_requirement_membership() -> None:
    """Membership and ownership are checked by RequirementAccessService, nowhere else.

    `ApprovalRecorder` keeps its `require_member`/`require_owner` names for its
    callers, and they delegate to the service, so calls through `self._recorder`
    are the one permitted spelling outside it.
    """
    offenders = []
    for name, tree in _use_case_sources():
        if name == ACCESS_SERVICE:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"require_member", "require_owner"}
                and ast.unparse(node.func.value) != "self._recorder"
            ):
                offenders.append(f"{name}:{node.lineno} {ast.unparse(node.func)}")

    assert not offenders, "Use RequirementAccessService instead: " + ", ".join(offenders)


def test_authorization_denials_come_from_the_access_service() -> None:
    offenders = [
        f"{name}:{node.lineno}"
        for name, tree in _use_case_sources()
        if name != ACCESS_SERVICE and name not in OTHER_AUTHORIZATION_RULES
        for node in ast.walk(tree)
        if isinstance(node, ast.Raise)
        and node.exc is not None
        and "AuthorizationDeniedError" in ast.unparse(node.exc)
    ]

    assert not offenders, (
        "Requirement access is decided by RequirementAccessService; move these checks there: "
        + ", ".join(offenders)
    )
