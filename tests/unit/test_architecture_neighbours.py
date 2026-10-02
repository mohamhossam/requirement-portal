"""Connected systems: one catalogued relationship away from a mapped impact (ADR-0087)."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.ports.generation_guidance import GenerationGuidance
from smb_requirement_agent.application.use_cases.approval_policy import artifact_fingerprint
from smb_requirement_agent.application.use_cases.resolve_architecture_knowledge import (
    ResolveArchitectureKnowledge,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureDependency,
    ArchitectureImpact,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.errors import InvalidArchitectureContentError
from smb_requirement_agent.domain.architecture.knowledge import SystemRelationship
from smb_requirement_agent.domain.architecture.neighbours import adjacent
from smb_requirement_agent.domain.organisation.catalogue import (
    OrganisationCatalogue,
    Squad,
    SquadSystemResource,
    ValueStream,
)
from smb_requirement_agent.infrastructure.architecture.embeddings import FakeEmbeddings
from smb_requirement_agent.infrastructure.architecture.evidence_index import (
    InMemoryEvidenceIndex,
)
from smb_requirement_agent.infrastructure.architecture.knowledge_yaml import seed_knowledge
from smb_requirement_agent.infrastructure.architecture.reasoning import FakeArchitectureReasoner
from smb_requirement_agent.infrastructure.architecture.tokenizer import FakeWordTokenizer
from smb_requirement_agent.infrastructure.architecture.yaml_knowledge import (
    YamlArchitectureKnowledge,
    default_knowledge_path,
)
from smb_requirement_agent.infrastructure.llm.prompts.generation_guidance import render_guidance
from smb_requirement_agent.infrastructure.persistence.in_memory_architecture_knowledge import (
    InMemoryArchitectureKnowledgeRepository,
)
from smb_requirement_agent.infrastructure.persistence.in_memory_organisation import (
    InMemoryOrganisationRepository,
)
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    architecture_from_payload,
    architecture_to_payload,
)
from smb_requirement_agent.infrastructure.time.fixed_clock import FixedClock
from tests.unit.test_feature_domain import make_feature

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _rel(source: str, target: str, text: str = "uses") -> SystemRelationship:
    return SystemRelationship(source, target, text)


def test_adjacent_walks_one_hop_both_ways_and_skips_selected_systems() -> None:
    result = adjacent(
        {"hub"},
        (
            _rel("hub", "billing"),
            _rel("portal", "hub"),
            _rel("billing", "ledger"),  # two hops away: not reached
            _rel("hub", "inside"),
            _rel("inside", "hub", "calls back"),
        ),
    )

    assert result.system_ids == ("inside", "billing", "portal")
    assert [(item.source_system_id, item.target_system_id) for item in result.dependencies] == [
        ("hub", "inside"),
        ("inside", "hub"),
        ("hub", "billing"),
        ("portal", "hub"),
    ]
    assert result.omitted == 0


def test_adjacent_ignores_relationships_inside_the_selection_and_caps_the_list() -> None:
    relationships = (
        _rel("a", "b"),
        *(_rel("a", f"n{index}") for index in range(5)),
    )

    result = adjacent({"a", "b"}, relationships, limit=3)

    assert result.system_ids == ("n0", "n1", "n2")
    assert result.omitted == 2
    assert all(
        "b" not in (item.source_system_id, item.target_system_id) for item in result.dependencies
    )
    assert adjacent({"a", "b"}, relationships, limit=3) == result
    assert adjacent(set(), relationships).system_ids == ()
    with pytest.raises(ValueError):
        adjacent({"a"}, relationships, limit=-1)


def _impact(**changes: object) -> ArchitectureImpact:
    base = ArchitectureImpact(
        "v1",
        NOW,
        (SystemReference("dcrm", "DCRM", True),),
        adjacent_systems=(SystemReference("cbcm", "CBCM", True),),
        adjacent_dependencies=(ArchitectureDependency("dcrm", "cbcm", "Reads customers."),),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_impact_rejects_connected_systems_that_are_mapped_or_unreached() -> None:
    assert _impact().cross_system is False

    with pytest.raises(InvalidArchitectureContentError, match="not already mapped"):
        _impact(adjacent_systems=(SystemReference("dcrm", "DCRM", True),))
    with pytest.raises(InvalidArchitectureContentError, match="needs the relationship"):
        _impact(adjacent_dependencies=())
    with pytest.raises(InvalidArchitectureContentError, match="join a mapped"):
        _impact(adjacent_dependencies=(ArchitectureDependency("cbcm", "other", "Elsewhere."),))
    with pytest.raises(InvalidArchitectureContentError, match="negative"):
        _impact(adjacent_omitted=-1)


def _resolver(organisation: InMemoryOrganisationRepository) -> ResolveArchitectureKnowledge:
    return ResolveArchitectureKnowledge(
        InMemoryArchitectureKnowledgeRepository(seed_knowledge()),
        InMemoryEvidenceIndex(FakeEmbeddings(), FakeWordTokenizer()),
        FakeArchitectureReasoner(),
        YamlArchitectureKnowledge(default_knowledge_path()),
        organisation,
    )


def test_resolver_lists_connected_systems_with_their_owners() -> None:
    organisation = InMemoryOrganisationRepository(FixedClock(NOW))
    organisation.change(
        lambda _: OrganisationCatalogue(
            value_streams=(ValueStream("retail", "Retail"),),
            squads=(
                Squad("care", "Care squad", "retail", None, (SquadSystemResource("cbcm-crmgw"),)),
            ),
        ),
        "amina",
        "seed",
        "all",
    )

    result = _resolver(organisation).match(
        ArchitectureQuery(text=("Capture back-office orders",), declared_systems=("DCRM",))
    )

    assert [item.id for item in result.systems] == ["dcrm"]
    assert result.dependencies == ()
    assert [item.id for item in result.adjacent_systems] == ["cbcm-crmgw"]
    assert [item.name for item in result.adjacent_systems[0].squads] == ["Care squad"]
    assert [
        (item.source_system_id, item.target_system_id) for item in result.adjacent_dependencies
    ] == [("dcrm", "cbcm-crmgw")]


def test_mapping_keeps_connected_systems_out_of_fingerprints_and_prompts() -> None:
    impact = _impact()
    bare = replace(impact, adjacent_systems=(), adjacent_dependencies=())

    assert architecture_from_payload(architecture_to_payload(impact)) == impact
    legacy = architecture_to_payload(bare)
    assert isinstance(legacy, dict)
    assert "adjacent_systems" not in legacy
    assert architecture_from_payload(legacy) == bare

    match = ArchitectureKnowledgeMatch(
        "v1",
        impact.systems,
        (),
        adjacent_systems=impact.adjacent_systems,
        adjacent_dependencies=impact.adjacent_dependencies,
    )
    rendered = render_guidance(GenerationGuidance(architecture=match))
    evidence = json.loads(rendered.split("\n", 3)[3])
    assert "adjacent_systems" not in evidence["architecture"]
    plain = replace(match, adjacent_systems=(), adjacent_dependencies=())
    assert render_guidance(GenerationGuidance(architecture=plain)) == rendered


def test_feature_fingerprint_ignores_connected_systems() -> None:
    feature = make_feature()
    with_neighbours = feature.with_architecture(_impact())
    without = feature.with_architecture(
        replace(_impact(), adjacent_systems=(), adjacent_dependencies=())
    )

    assert artifact_fingerprint(with_neighbours) == artifact_fingerprint(without)
