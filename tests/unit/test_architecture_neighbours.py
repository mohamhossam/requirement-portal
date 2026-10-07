"""Connected systems on a mapped impact, as requirement work receives them (ADR-0087).

Finding connected systems in the catalogue is the knowledge service's job and is
covered there. These tests cover what requirement work does with the connected
systems it is given: record them, store them, and keep them out of approval
fingerprints and generation prompts.
"""

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
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapFeatureArchitecture,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureDependency,
    ArchitectureImpact,
    OrganisationReference,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.errors import InvalidArchitectureContentError
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementContext,
    RequirementDescription,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.infrastructure.llm.prompts.generation_guidance import render_guidance
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    architecture_from_payload,
    architecture_to_payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from tests.unit.test_feature_domain import make_feature

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


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


class _FixedKnowledge:
    """The knowledge service, answering every query with one fixed match."""

    def __init__(self, match: ArchitectureKnowledgeMatch) -> None:
        self.match_result = match
        self.queries: list[ArchitectureQuery] = []

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        self.queries.append(query)
        return self.match_result


def test_mapping_records_the_connected_systems_and_their_owners_as_given() -> None:
    care = OrganisationReference("care", "Care squad")
    knowledge = _FixedKnowledge(
        ArchitectureKnowledgeMatch(
            "v1",
            (SystemReference("dcrm", "DCRM", True),),
            (),
            adjacent_systems=(SystemReference("cbcm-crmgw", "CBCM CRM GW", True, squads=(care,)),),
            adjacent_dependencies=(
                ArchitectureDependency("dcrm", "cbcm-crmgw", "Reads customers."),
            ),
            adjacent_omitted=2,
        )
    )
    requirement = Requirement(
        id=RequirementId("req-1"),
        title=RequirementTitle("Back-office orders"),
        description=RequirementDescription("Capture back-office orders"),
        status=RequirementStatus.DRAFT,
        systems=(RequirementContext("DCRM"),),
    )

    mapped = MapFeatureArchitecture(knowledge).execute(requirement, make_feature(), NOW)

    assert knowledge.queries[0].declared_systems == ("DCRM",)
    impact = mapped.impact
    assert mapped.feature.architecture == impact
    assert [item.id for item in impact.systems] == ["dcrm"]
    assert impact.dependencies == ()
    assert [item.id for item in impact.adjacent_systems] == ["cbcm-crmgw"]
    assert [item.name for item in impact.adjacent_systems[0].squads] == ["Care squad"]
    assert [
        (item.source_system_id, item.target_system_id) for item in impact.adjacent_dependencies
    ] == [("dcrm", "cbcm-crmgw")]
    assert impact.adjacent_omitted == 2


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
