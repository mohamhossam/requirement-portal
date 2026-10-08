"""Project recorded citations at write time, never infer origins from matching text."""

import hashlib
import json
from dataclasses import asdict, replace

from smb_requirement_agent.analysis.domain.lineage import analysis_lineage
from smb_requirement_agent.breakdown.domain.story.entities import UserStory
from smb_requirement_agent.governance.application.ports.breakdown_repository import (
    BreakdownRepositoryPort,
)
from smb_requirement_agent.knowledge.application.ports.source_dependencies import (
    SourceDependency,
    SourceDependencyPort,
)
from smb_requirement_agent.reporting.application.ports.requirement_worklist import (
    RequirementWorklistSnapshot,
    RequirementWorklistSnapshotPort,
)
from smb_requirement_agent.requirements.domain.requirement.value_objects import RequirementStatus
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class DependencyProjection:
    def __init__(
        self, snapshots: RequirementWorklistSnapshotPort, index: SourceDependencyPort
    ) -> None:
        self._snapshots, self._index = snapshots, index

    def refresh(self, requirement_id: RequirementId) -> None:
        snapshots = self._snapshots.list_snapshots((requirement_id.value,))
        if not snapshots:
            self._index.replace_current(requirement_id.value, ())
            return
        self.project(snapshots[0])

    def project(self, snapshot: RequirementWorklistSnapshot) -> None:
        requirement_id = snapshot.requirement.id
        rows: list[SourceDependency] = []
        requirement = snapshot.requirement
        enabled = requirement.status is not RequirementStatus.DUPLICATE
        analysis = snapshot.analysis

        def add(
            kind: str,
            target_id: str,
            statement: str,
            content: object,
            origins: tuple[SourceLineage, ...],
            active: bool = True,
            status: str = "recorded",
        ) -> None:
            digest = fingerprint(content)
            for origin in origins:
                identity = fingerprint(
                    (requirement_id.value, kind, target_id, digest, asdict(origin))
                )
                rows.append(
                    SourceDependency(
                        identity,
                        requirement_id.value,
                        requirement.title.value,
                        kind,
                        target_id,
                        statement,
                        digest,
                        origin,
                        active and enabled,
                        status=status,
                        analysis_id=analysis.id.value if analysis and analysis.id else None,
                        round_number=analysis.round_number if analysis else None,
                    )
                )

        if analysis:
            for proposal in analysis.intent_proposals:
                add(
                    "proposal",
                    proposal.id.value,
                    proposal.effective_statement or proposal.statement,
                    asdict(proposal),
                    tuple(SourceLineage(c) for c in proposal.reference_evidence),
                    proposal.status.value != "rejected",
                    proposal.status.value,
                )
            for number, answer in enumerate(analysis.clarifications):
                add(
                    "clarification",
                    answer.question_id.value if answer.question_id else str(number),
                    answer.answer,
                    asdict(answer),
                    answer.source_lineage,
                )
            origins = analysis_lineage(analysis)
            # Aggregate dependencies describe supplied context, not a claim that every
            # generated sentence is directly supported by every passage.
            content = asdict(analysis)
            for key in ("version", "confirmed_by", "confirmed_at", "is_human_confirmed"):
                content.pop(key, None)
            add(
                "analysis",
                analysis.id.value if analysis.id else "legacy",
                "Analysis inputs",
                content,
                origins,
            )
            add(
                "requirement",
                requirement_id.value,
                requirement.title.value,
                (asdict(requirement), content),
                tuple(o.through("analysis inputs") for o in origins),
            )
        for item in (
            ((snapshot.epic,) if snapshot.epic else ()) + snapshot.features + snapshot.stories
        ):
            kind = (
                "epic"
                if item is snapshot.epic
                else "feature"
                if item in snapshot.features
                else "story"
            )
            payload = asdict(item)
            for key in ("status", "version", "approvals", "staleness", "architecture"):
                payload.pop(key, None)
            statement = item.voice if isinstance(item, UserStory) else item.name.value
            add(
                kind,
                item.id.value,
                statement,
                payload,
                item.source_lineage,
                status=item.status.value,
            )
        self._index.replace_current(requirement_id.value, tuple(rows))

    def backfill(self, requirement_id: RequirementId, revisions: BreakdownRepositoryPort) -> None:
        snapshots = self._snapshots.list_snapshots((requirement_id.value,))
        if not snapshots:
            return
        current = snapshots[0]
        for revision in revisions.list_breakdown_revisions(requirement_id):
            self.project(
                replace(
                    current,
                    analysis=revision.analysis,
                    epic=revision.epic,
                    features=revision.features,
                    stories=revision.stories,
                )
            )
        self.project(current)
