"""Supplement complete primary analysis with separately reviewed reference proposals."""

import hashlib
import json
import logging
from collections.abc import Sequence
from dataclasses import asdict

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.analysis.application.ports.reference_analysis import (
    ReferenceProposerPort,
)
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    IntentProposalCandidate,
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    IntentProposal,
    ReferenceGroundingStatus,
)
from smb_requirement_agent.application.errors import ServiceUnavailableError
from smb_requirement_agent.references.application.ports.embedding import TokenCounterPort
from smb_requirement_agent.references.application.ports.reference_grounding import (
    ReferenceEvidence,
    ReferenceKnowledgePort,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement
from smb_requirement_agent.shared_kernel.generation import Provenance

_log = logging.getLogger(__name__)


class ReferenceGrounding:
    def __init__(
        self,
        knowledge: ReferenceKnowledgePort,
        proposer: ReferenceProposerPort,
        tokens: TokenCounterPort,
        clock: ClockPort,
    ) -> None:
        self._knowledge, self._proposer, self._tokens, self._clock = (
            knowledge,
            proposer,
            tokens,
            clock,
        )

    def augment(
        self,
        requirement: Requirement,
        primary: RequirementAnalysisCandidate,
        decisions: Sequence[IntentProposal],
    ) -> RequirementAnalysisCandidate:
        """Add reference proposals to `primary`, recording what checking the library found.

        A connected knowledge portal that cannot be reached leaves the primary analysis
        standing, marked `unavailable`: the model call it took is not thrown away, and the
        reviewer sees that references were not checked (ADR-0104).
        """
        if not self._knowledge.is_connected():
            return _graded(primary, ReferenceGroundingStatus.NOT_CONNECTED)
        try:
            evidence = self._evidence(requirement, primary)
        except ServiceUnavailableError as exc:
            _log.warning("Reference grounding skipped: %s", exc)
            return _graded(primary, ReferenceGroundingStatus.UNAVAILABLE)
        if not evidence:
            return _graded(primary, ReferenceGroundingStatus.NO_EVIDENCE)
        return self._proposed(requirement, primary, evidence, decisions)

    def _evidence(
        self, requirement: Requirement, primary: RequirementAnalysisCandidate
    ) -> tuple[ReferenceEvidence, ...]:
        if not self._knowledge.has_published():
            return ()
        topics = [
            requirement.description.value,
            *primary["business_rules"][:2],
            *primary["constraints"][:1],
        ]
        evidence: list[ReferenceEvidence] = []
        seen: set[str] = set()
        counts: dict[str, int] = {}
        budget = 0
        for topic in topics:
            query = f"{requirement.title.value}\n{topic}"[:2000]
            for item in self._knowledge.search_evidence(query):
                citation, context = item.citation, item.context_text
                cost = self._tokens.count(f"{citation.title}\n{citation.location}\n{context}")
                if (
                    citation.lineage_hash in seen
                    or counts.get(citation.document_id, 0) >= 3
                    or len(evidence) >= 20
                    or budget + cost > 8000
                ):
                    continue
                evidence.append(item)
                seen.add(citation.lineage_hash)
                counts[citation.document_id] = counts.get(citation.document_id, 0) + 1
                budget += cost
        return tuple(evidence)

    def _proposed(
        self,
        requirement: Requirement,
        primary: RequirementAnalysisCandidate,
        evidence: tuple[ReferenceEvidence, ...],
        decisions: Sequence[IntentProposal],
    ) -> RequirementAnalysisCandidate:
        result = self._proposer.propose(requirement, primary, evidence, decisions)
        allowed = {item.citation for item in evidence}
        proposals: list[IntentProposalCandidate] = list(primary["intent_proposals"])
        for proposal in result.proposals:
            if not proposal.evidence or any(c not in allowed for c in proposal.evidence):
                raise RequirementAnalysisGenerationError(
                    "Reference proposal cites evidence outside its supplied context."
                )
            proposals.append(
                {
                    "kind": proposal.kind,
                    "statement": proposal.statement,
                    "rationale": proposal.rationale,
                    "success_measures": [],
                    "reference_evidence": proposal.evidence,
                    "reference_conflict": proposal.conflict,
                    "reference_provenance": Provenance(
                        self._clock.now(), result.model, result.prompt_version
                    ),
                }
            )
        # The persistence boundary rechecks these exact citations while holding publication locks.
        return {
            **primary,
            "reference_grounding": ReferenceGroundingStatus.GROUNDED,
            "intent_proposals": proposals,
            "stage_provenance": [
                *primary.get("stage_provenance", []),
                {
                    "stage": "reference_applicability",
                    "model": result.model,
                    "prompt_version": result.prompt_version,
                    "generated_at": self._clock.now(),
                    "input_fingerprint": hashlib.sha256(
                        json.dumps([asdict(c) for c in evidence], sort_keys=True).encode()
                    ).hexdigest(),
                },
            ],
        }


def _graded(
    primary: RequirementAnalysisCandidate, status: ReferenceGroundingStatus
) -> RequirementAnalysisCandidate:
    return {**primary, "reference_grounding": status}
