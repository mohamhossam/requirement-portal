"""Systems one catalogued relationship away from a mapped impact.

A mapped system rarely changes alone: what it calls and what calls it are the
first places a change can break. This walks the published relationships one hop
in both directions. It never selects a system; it lists what a reviewer should
check.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from smb_requirement_agent.domain.architecture.entities import ArchitectureDependency
from smb_requirement_agent.domain.architecture.knowledge import SystemRelationship

ADJACENT_LIMIT = 8


@dataclass(frozen=True)
class Adjacency:
    """Connected systems, the relationships that connect them, and how many were left out."""

    system_ids: tuple[str, ...]
    dependencies: tuple[ArchitectureDependency, ...]
    omitted: int


def adjacent(
    selected_ids: Iterable[str],
    relationships: Iterable[SystemRelationship],
    limit: int = ADJACENT_LIMIT,
) -> Adjacency:
    """Systems directly connected to ``selected_ids`` that were not selected themselves.

    Systems with more connections to the selection come first, then by id, so the
    result is the same on every call. Only the relationships of the kept systems
    are returned.
    """
    if limit < 0:
        raise ValueError("The adjacent-system limit must not be negative.")
    selected = set(selected_ids)
    edges: dict[str, list[SystemRelationship]] = {}
    for item in relationships:
        source_in = item.source_system_id in selected
        target_in = item.target_system_id in selected
        if source_in == target_in:
            continue
        other = item.target_system_id if source_in else item.source_system_id
        edges.setdefault(other, []).append(item)
    ranked = sorted(edges, key=lambda system_id: (-len(edges[system_id]), system_id))
    kept = ranked[:limit]
    dependencies = tuple(
        ArchitectureDependency(
            item.source_system_id, item.target_system_id, item.description, item.kind
        )
        for system_id in kept
        for item in sorted(
            edges[system_id],
            key=lambda rel: (rel.source_system_id, rel.target_system_id, rel.description),
        )
    )
    return Adjacency(tuple(kept), dependencies, len(ranked) - len(kept))
