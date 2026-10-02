"""Supplement complete primary analysis with separately reviewed reference proposals."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict

from smb_requirement_agent.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.application.ports.clock import ClockPort
from smb_requirement_agent.application.ports.reference_grounding import (
    ReferenceEvidence,
    ReferenceProposerPort,
)
from smb_requirement_agent.application.ports.reference_index import TokenCounterPort
from smb_requirement_agent.application.ports.requirement_analyzer import (
    IntentProposalCandidate,
    RequirementAnalysisCandidate,
)
from smb_requirement_agent.application.use_cases.reference_knowledge import ReferenceKnowledge
from smb_requirement_agent.domain.analysis.value_objects import IntentProposal
from smb_requirement_agent.domain.requirement.entities import Requirement
from smb_requirement_agent.domain.shared.generation import Provenance


class ReferenceGrounding:
    def __init__(
        self,
        knowledge: ReferenceKnowledge,
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
        if not self._knowledge.has_published():
            return primary
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
            for chunk in self._knowledge.search(query):
                citation = self._knowledge.citation(chunk)
                context = chunk.context_text or f"{citation.location}\n{citation.excerpt}"
                cost = self._tokens.count(f"{citation.title}\n{citation.location}\n{context}")
                if (
                    citation.lineage_hash in seen
                    or counts.get(citation.document_id, 0) >= 3
                    or len(evidence) >= 20
                    or budget + cost > 8000
                ):
                    continue
                evidence.append(
                    ReferenceEvidence(
                        citation,
                        context,
                        chunk.context_locations or (chunk.location,),
                    )
                )
                seen.add(citation.lineage_hash)
                counts[citation.document_id] = counts.get(citation.document_id, 0) + 1
                budget += cost
        if not evidence:
            return primary
        result = self._proposer.propose(requirement, primary, tuple(evidence), decisions)
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
