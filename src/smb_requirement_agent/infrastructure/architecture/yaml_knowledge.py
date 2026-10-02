"""Validated YAML-backed architecture knowledge and deterministic matching."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureKnowledgePort,
    ArchitectureQuery,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureDependency,
    SystemCapability,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.knowledge import RelationshipKind
from smb_requirement_agent.infrastructure.config.options import ConfigurationError


@dataclass(frozen=True)
class _Capability:
    reference: SystemCapability
    triggers: tuple[str, ...]


@dataclass(frozen=True)
class _System:
    id: str
    name: str
    aliases: tuple[str, ...]
    capabilities: tuple[_Capability, ...]


class YamlArchitectureKnowledge(ArchitectureKnowledgePort):
    """Load knowledge once and match only against catalogue-owned phrases."""

    def __init__(self, path: Path) -> None:
        self._version, self._systems, self._dependencies = _load(path)
        self._alias_index: dict[str, _System] = {}
        for system in self._systems:
            for alias in (system.id, system.name, *system.aliases):
                self._alias_index[_normalise(alias)] = system

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        corpus = _normalise(" ".join(query.text))
        selected: dict[str, tuple[_System, dict[str, SystemCapability]]] = {}

        for raw in query.declared_systems:
            stripped = raw.strip()
            if not stripped:
                continue
            system = self._alias_index.get(_normalise(stripped))
            if system is None:
                identity = hashlib.sha256(_normalise(stripped).encode()).hexdigest()[:12]
                unknown = _System(f"declared-{identity}", stripped, (), ())
                selected[unknown.id] = (unknown, {})
            else:
                selected.setdefault(system.id, (system, {}))

        for system in self._systems:
            capabilities = {
                item.reference.id: item.reference
                for item in system.capabilities
                if any(_contains(corpus, trigger) for trigger in item.triggers)
            }
            aliases = (system.name, *system.aliases)
            direct = any(
                len(_normalise(alias)) > 2 and _contains(corpus, alias) for alias in aliases
            )
            if direct or capabilities:
                current = selected.setdefault(system.id, (system, {}))[1]
                current.update(capabilities)

        systems = tuple(
            SystemReference(
                id=system.id,
                name=system.name,
                catalogued=system in self._systems,
                capabilities=tuple(capabilities.values()),
            )
            for system, capabilities in selected.values()
        )
        system_ids = {item.id for item in systems}
        dependencies = tuple(
            item
            for item in self._dependencies
            if item.source_system_id in system_ids and item.target_system_id in system_ids
        )
        return ArchitectureKnowledgeMatch(self._version, systems, dependencies)


def default_knowledge_path() -> Path:
    return Path(__file__).with_name("knowledge") / "smb_architecture.yaml"


def _load(path: Path) -> tuple[str, tuple[_System, ...], tuple[ArchitectureDependency, ...]]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise ConfigurationError(
            f"Architecture knowledge could not be loaded from {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("Architecture knowledge must be a YAML object.")
    data = cast(dict[str, object], raw)
    version = _required_text(data, "version")
    systems = _systems(data.get("systems"))
    dependencies = _dependencies(data.get("dependencies", []), {item.id for item in systems})
    return version, systems, dependencies


def _systems(raw: object) -> tuple[_System, ...]:
    rows = _rows(raw, "systems")
    if not rows:
        raise ConfigurationError("Architecture knowledge needs at least one system.")
    result: list[_System] = []
    ids: set[str] = set()
    aliases: dict[str, str] = {}
    for row in rows:
        system_id = _required_text(row, "id")
        name = _required_text(row, "name")
        if system_id in ids:
            raise ConfigurationError(f"Duplicate architecture system id {system_id!r}.")
        ids.add(system_id)
        system_aliases = _text_list(row.get("aliases", []), f"aliases for {system_id}")
        for alias in (system_id, name, *system_aliases):
            key = _normalise(alias)
            owner = aliases.get(key)
            if owner is not None and owner != system_id:
                raise ConfigurationError(
                    f"Architecture alias {alias!r} belongs to multiple systems."
                )
            aliases[key] = system_id
        capabilities = _capabilities(row.get("capabilities", []), system_id)
        result.append(_System(system_id, name, system_aliases, capabilities))
    return tuple(result)


def _capabilities(raw: object, system_id: str) -> tuple[_Capability, ...]:
    result: list[_Capability] = []
    ids: set[str] = set()
    for row in _rows(raw, f"capabilities for {system_id}"):
        capability = SystemCapability(_required_text(row, "id"), _required_text(row, "name"))
        if capability.id in ids:
            raise ConfigurationError(
                f"Duplicate capability id {capability.id!r} for system {system_id!r}."
            )
        ids.add(capability.id)
        triggers = _text_list(row.get("triggers"), f"triggers for {capability.id}")
        if not triggers:
            raise ConfigurationError(f"Capability {capability.id!r} needs at least one trigger.")
        result.append(_Capability(capability, triggers))
    return tuple(result)


def _dependencies(raw: object, system_ids: set[str]) -> tuple[ArchitectureDependency, ...]:
    result: list[ArchitectureDependency] = []
    for row in _rows(raw, "dependencies"):
        kind = str(row.get("kind") or RelationshipKind.UNSPECIFIED.value)
        if kind not in {item.value for item in RelationshipKind}:
            raise ConfigurationError(f"Unknown architecture dependency kind {kind!r}.")
        item = ArchitectureDependency(
            _required_text(row, "source_system_id"),
            _required_text(row, "target_system_id"),
            _required_text(row, "description"),
            RelationshipKind(kind),
        )
        if item.source_system_id not in system_ids or item.target_system_id not in system_ids:
            raise ConfigurationError(
                "Architecture dependency references a system absent from the catalogue."
            )
        result.append(item)
    return tuple(result)


def _rows(raw: object, field: str) -> list[dict[str, object]]:
    if not isinstance(raw, list):
        raise ConfigurationError(f"Architecture {field} must be a list.")
    rows: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ConfigurationError(f"Every architecture {field} entry must be an object.")
        rows.append(cast(dict[str, object], item))
    return rows


def _required_text(data: dict[str, object], key: str) -> str:
    if key not in data:
        raise ConfigurationError(f"Architecture field {key!r} is required.")
    return _item_text(data[key], key)


def _item_text(raw: object, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ConfigurationError(f"Architecture {field} must be non-blank text.")
    return raw.strip()


def _text_list(raw: object, field: str) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ConfigurationError(f"Architecture {field} must be a list.")
    return tuple(_item_text(item, field) for item in raw)


def _normalise(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())


def _contains(corpus: str, phrase: str) -> bool:
    needle = _normalise(phrase)
    return bool(needle) and f" {needle} " in f" {corpus} "
