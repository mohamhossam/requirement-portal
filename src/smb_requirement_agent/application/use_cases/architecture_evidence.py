"""The evidence a mapping reasons over: named systems first, then search results."""

from __future__ import annotations

import re

from smb_requirement_agent.application.ports.architecture_rag import (
    ArchitectureEvidenceIndexPort,
    EvidenceChunk,
)
from smb_requirement_agent.domain.architecture.knowledge import (
    ArchitectureKnowledge,
    SystemDefinition,
)

EVIDENCE_LIMIT = 8
MIN_SEARCH_RESULTS = 6


def named_systems(release: ArchitectureKnowledge, text: str) -> tuple[SystemDefinition, ...]:
    """Catalogue systems whose id, name, Arabic name or alias appears as a whole word."""
    folded = text.casefold()
    return tuple(
        system
        for system in release.systems
        if any(
            label and re.search(rf"(?<!\w){re.escape(label.casefold())}(?!\w)", folded)
            for label in (system.id, system.name, system.name_ar or "", *system.aliases)
        )
    )


def gather_evidence(
    index: ArchitectureEvidenceIndexPort,
    release: ArchitectureKnowledge,
    index_id: str,
    text: str,
) -> tuple[EvidenceChunk, ...]:
    """The record of every system the text names, then the best search results.

    Search alone can rank a named system's own record below document passages
    and drop it; the catalogue is authoritative, so a system named outright is
    always backed by its record. At least six slots stay open for search.
    """
    named = tuple(
        chunk
        for system in named_systems(release, text)
        if (chunk := index.system_chunk(index_id, system.id)) is not None
    )
    searched = tuple(
        chunk
        for chunk in index.retrieve(index_id, text, EVIDENCE_LIMIT + len(named))
        if chunk.id not in {item.id for item in named}
    )
    room = max(MIN_SEARCH_RESULTS, EVIDENCE_LIMIT - len(named))
    return (*named, *searched[:room])
