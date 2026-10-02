"""Suggest capability domains when mapping found no catalogued system (ADR-0089).

The words come from the catalogue, never from code: a domain's own names and
the names and matching phrases of the capabilities placed in it. A match is a
whole phrase in the item's text. The result names the domain, the systems that
do work in it, and the words that matched; it never maps a system.
"""

from __future__ import annotations

import re

from smb_requirement_agent.domain.architecture.entities import DomainSuggestion
from smb_requirement_agent.domain.architecture.knowledge import ArchitectureKnowledge

MAX_DOMAIN_SUGGESTIONS = 2


def normalise(value: str) -> str:
    """Lower case, with every run of non-letters and non-digits as one space; keeps Arabic."""
    return " ".join(re.sub(r"[\W_]+", " ", value.casefold()).split())


def contains(corpus: str, phrase: str) -> bool:
    """Whether the normalised ``corpus`` holds ``phrase`` as whole words."""
    needle = normalise(phrase)
    return bool(needle) and f" {needle} " in f" {corpus} "


def suggest_domains(release: ArchitectureKnowledge, text: str) -> tuple[DomainSuggestion, ...]:
    corpus = normalise(text)
    if not corpus or not release.capability_domains:
        return ()
    terms: dict[str, list[str]] = {
        item.id: [item.name, *((item.name_ar,) if item.name_ar else ())]
        for item in release.capability_domains
    }
    systems: dict[str, set[str]] = {item.id: set() for item in release.capability_domains}
    names = {system.id: system.name for system in release.systems}
    for system in release.systems:
        for capability in system.capabilities:
            # A capability counts for its domain and every domain above it.
            for domain in release.domain_path(capability.domain_id):
                terms[domain.id].extend((capability.name, *capability.triggers))
                systems[domain.id].add(system.id)

    ranked: list[tuple[int, int, str, tuple[str, ...]]] = []
    for domain_id, words in terms.items():
        matched = tuple(word for word in dict.fromkeys(words) if contains(corpus, word))
        if matched and systems[domain_id]:
            depth = len(release.domain_path(domain_id))
            ranked.append((-len(matched), -depth, domain_id, matched))
    ranked.sort()

    chosen: list[DomainSuggestion] = []
    lines: list[tuple[str, set[str]]] = []
    for _, _, domain_id, matched in ranked:
        path = release.domain_path(domain_id)
        line = {item.id for item in path}
        # A domain and its own parent or child would say the same thing; siblings do not.
        if any(domain_id in other_line or other in line for other, other_line in lines):
            continue
        lines.append((domain_id, line))
        chosen.append(
            DomainSuggestion(
                domain_id,
                tuple(item.name for item in path),
                tuple(sorted(systems[domain_id])),
                matched,
                tuple(names[item] for item in sorted(systems[domain_id])),
            )
        )
        if len(chosen) == MAX_DOMAIN_SUGGESTIONS:
            break
    return tuple(chosen)
