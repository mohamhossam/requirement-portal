"""How one system depends on another, on the impacts requirement work receives (ADR-0088).

Kinds on catalogue relationships (curation, files, suggestions and reading) are
the knowledge service's job and are covered there. These tests cover the kind
as requirement work holds it: on a mapped dependency, recorded as given, stored,
and joining approval fingerprints only once it is specified.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from smb_requirement_agent.application.ports.architecture_knowledge import (
    ArchitectureKnowledgeMatch,
    ArchitectureQuery,
)
from smb_requirement_agent.application.use_cases.approval_policy import artifact_fingerprint
from smb_requirement_agent.application.use_cases.architecture_mapping import (
    MapFeatureArchitecture,
)
from smb_requirement_agent.domain.architecture.entities import (
    ArchitectureDependency,
    ArchitectureImpact,
    SystemReference,
)
from smb_requirement_agent.domain.architecture.errors import InvalidArchitectureContentError
from smb_requirement_agent.domain.architecture.knowledge import (
    InvalidKnowledgeError,
    RelationshipKind,
    relationship_kind,
)
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.requirement.value_objects import (
    RequirementDescription,
    RequirementId,
    RequirementStatus,
    RequirementTitle,
)
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    architecture_from_payload,
    architecture_to_payload,
)
from tests.unit.test_feature_domain import make_feature

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def test_a_dependency_is_unspecified_until_a_source_says_how() -> None:
    assert ArchitectureDependency("a", "b", "uses").kind is RelationshipKind.UNSPECIFIED
    stored = ArchitectureDependency("a", "b", "uses", "calls_api")  # type: ignore[arg-type]
    assert stored.kind is RelationshipKind.CALLS_API
    assert relationship_kind("orchestrates") is RelationshipKind.ORCHESTRATES
    with pytest.raises(InvalidKnowledgeError, match="Unknown relationship kind"):
        relationship_kind("telepathy")
    with pytest.raises(InvalidArchitectureContentError, match="Unknown relationship kind"):
        ArchitectureDependency("a", "b", "uses", "telepathy")  # type: ignore[arg-type]


class _FixedKnowledge:
    """The knowledge service, answering every query with one fixed match."""

    def __init__(self, match: ArchitectureKnowledgeMatch) -> None:
        self.match_result = match

    def match(self, query: ArchitectureQuery) -> ArchitectureKnowledgeMatch:
        return self.match_result


def test_mapping_and_connected_systems_record_the_kind_as_given() -> None:
    knowledge = _FixedKnowledge(
        ArchitectureKnowledgeMatch(
            "v1",
            (SystemReference("b2b-web", "B2B Web", True), SystemReference("rtf", "RTF", True)),
            (ArchitectureDependency("b2b-web", "rtf", "Calls it.", RelationshipKind.CALLS_API),),
            adjacent_systems=(SystemReference("cwom", "CWOM", True),),
            adjacent_dependencies=(
                ArchitectureDependency("rtf", "cwom", "Routes.", RelationshipKind.ORCHESTRATES),
            ),
        )
    )
    requirement = Requirement(
        id=RequirementId("req-1"),
        title=RequirementTitle("Orders"),
        description=RequirementDescription("Route orders"),
        status=RequirementStatus.DRAFT,
    )

    impact = MapFeatureArchitecture(knowledge).execute(requirement, make_feature(), NOW).impact

    assert [item.kind for item in impact.dependencies] == [RelationshipKind.CALLS_API]
    assert [item.kind for item in impact.adjacent_dependencies] == [RelationshipKind.ORCHESTRATES]
    assert architecture_from_payload(architecture_to_payload(impact)) == impact


def _impact(kind: RelationshipKind) -> ArchitectureImpact:
    return ArchitectureImpact(
        "v1",
        NOW,
        (SystemReference("a", "A", True), SystemReference("b", "B", True)),
        (ArchitectureDependency("a", "b", "uses", kind),),
    )


def test_an_unspecified_kind_leaves_payloads_and_fingerprints_as_they_were() -> None:
    unspecified = _impact(RelationshipKind.UNSPECIFIED)
    stated = _impact(RelationshipKind.CALLS_API)

    payload = architecture_to_payload(unspecified)
    assert isinstance(payload, dict)
    assert payload["dependencies"] == [
        {"source_system_id": "a", "target_system_id": "b", "description": "uses"}
    ]
    assert architecture_from_payload(payload) == unspecified
    assert architecture_from_payload(architecture_to_payload(stated)) == stated

    feature = make_feature()
    before_kinds = replace(
        unspecified,
        dependencies=(ArchitectureDependency("a", "b", "uses"),),
    )
    assert artifact_fingerprint(feature.with_architecture(unspecified)) == artifact_fingerprint(
        feature.with_architecture(before_kinds)
    )
    assert artifact_fingerprint(feature.with_architecture(stated)) != artifact_fingerprint(
        feature.with_architecture(unspecified)
    )
