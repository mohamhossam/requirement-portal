"""Report imports between the candidate bounded contexts of ADR-0103.

Each domain, shared-kernel and application module is classified into the context `docs/architecture/
context-map.md` assigns it. The script then lists every import that crosses contexts, and
flags the ones that run against the dependency order:

    workflows > reporting > governance > breakdown > knowledge > analysis > references
    > requirements > {jobs | identity} > shared_kernel

A flagged edge runs against ADR-0103 §2; the `contexts_layered` import-linter contract rejects
it too. Infrastructure and interfaces are not classified: a context's adapters may use other
contexts' codecs, and the composition root wires every context.

Usage:

    python scripts/context_dependency_report.py            # summary and violations
    python scripts/context_dependency_report.py --edges    # also every allowed crossing
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict

import grimp

ROOT = "smb_requirement_agent"

# Higher ranks may import lower ranks. Equal ranks are independent siblings. The order is
# ADR-0103 section 2 as changed by its Amendment 1.
RANK = {
    "interfaces": 11,
    "workflows": 10,
    "reporting": 9,
    "governance": 8,
    "breakdown": 7,
    "knowledge": 6,
    "analysis": 5,
    "references": 4,
    "requirements": 3,
    "jobs": 2,
    "identity": 2,
    "shared_kernel": 1,
}
# Shared technical modules (errors, transactions, external work). Any context may use them,
# and they must use no context.
TECHNICAL = "technical"

# Every module is classified by the context docs/architecture/context-map.md assigns it.
# Most specific prefix wins. Prefixes are relative to the package root.
DOMAIN = {
    "shared_kernel": "shared_kernel",
}

PORTS = {
    TECHNICAL: ["domain_events", "expected_context", "external_work", "transaction_manager"],
}

APPLICATION_MODULES = {
    # Base errors only; the context errors moved to their contexts (F5, PR 16).
    "application.errors": TECHNICAL,
    # The in-process dispatcher (PR 4).
    "application.events": TECHNICAL,
}


# The context packages (ADR-0103 §1). Their domain and application layers are classified whole;
# their infrastructure, like the rest, is out of scope.
CONTEXT_PACKAGES = (
    "identity",
    "jobs",
    "requirements",
    "references",
    "analysis",
    "knowledge",
    "breakdown",
    "governance",
    "reporting",
    "workflows",
)


def _prefixes() -> dict[str, str]:
    table = dict(DOMAIN)
    for context in CONTEXT_PACKAGES:
        table.update({f"{context}.domain": context, f"{context}.application": context})
    table.update(APPLICATION_MODULES)
    for context, names in PORTS.items():
        table.update({f"application.ports.{name}": context for name in names})
    return table


def classify(module: str, table: dict[str, str]) -> str | None:
    """The context of a domain or application module, or None if it is not classified."""
    relative = module.removeprefix(f"{ROOT}.")
    best = max(
        (prefix for prefix in table if relative == prefix or relative.startswith(f"{prefix}.")),
        key=len,
        default=None,
    )
    return table[best] if best else None


def _in_scope(module: str) -> bool:
    relative = module.removeprefix(f"{ROOT}.")
    if relative in ("application", "application.ports"):
        return False
    moved = tuple(
        f"{context}.{layer}" for context in CONTEXT_PACKAGES for layer in ("domain", "application")
    )
    return relative.startswith(("application.", "shared_kernel", *moved))


def allowed(source: str, target: str) -> bool:
    if source == target or target == TECHNICAL:
        return True
    if source == TECHNICAL:
        # Shared technical code may use the shared kernel, and nothing else.
        return target == "shared_kernel"
    return RANK[source] > RANK[target]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--edges", action="store_true", help="also list allowed crossings")
    arguments = parser.parse_args(argv)

    graph = grimp.build_graph(ROOT)
    table = _prefixes()
    modules = sorted(module for module in graph.modules if _in_scope(module))
    unclassified = [module for module in modules if classify(module, table) is None]

    crossings: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for module in modules:
        source = classify(module, table)
        if source is None:
            continue
        for imported in sorted(graph.find_modules_directly_imported_by(module)):
            if not _in_scope(imported):
                continue
            target = classify(imported, table)
            if target is None or target == source:
                continue
            crossings[(source, target)].append((module, imported))

    violations = {pair: edges for pair, edges in crossings.items() if not allowed(*pair)}
    print(f"Classified {len(modules) - len(unclassified)} of {len(modules)} modules.")
    print(f"Context pairs crossed: {len(crossings)}; against the order: {len(violations)}.")
    print()
    print("Crossings against the dependency order:")
    for (source, target), edges in sorted(violations.items()):
        print(f"  {source} -> {target} ({len(edges)} imports)")
        for module, imported in edges:
            print(f"      {module.removeprefix(ROOT + '.')} -> {imported.removeprefix(ROOT + '.')}")
    if arguments.edges:
        print()
        print("Allowed crossings:")
        for (source, target), edges in sorted(crossings.items()):
            if (source, target) not in violations:
                print(f"  {source} -> {target} ({len(edges)} imports)")
    if unclassified:
        print()
        print("Unclassified modules (add them to this script and to the context map):")
        for module in unclassified:
            print(f"  {module.removeprefix(ROOT + '.')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
