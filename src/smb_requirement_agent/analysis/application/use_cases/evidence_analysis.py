"""Budgeted structured-evidence planning, validation, caching, and consolidation."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import asdict, dataclass

from smb_kernel.time.clock import ClockPort

from smb_requirement_agent.analysis.application.errors import RequirementAnalysisGenerationError
from smb_requirement_agent.analysis.application.ports.requirement_analyzer import (
    ActiveQuestionContext,
    AnalysisDocumentContext,
    AnalysisEvidenceBlock,
    AnalysisEvidenceReferenceCandidate,
    AnalysisImageAsset,
    AnalysisStageProvenanceCandidate,
    IntentProposalCandidate,
    QuestionReviewCandidate,
    RequirementAnalysisCandidate,
    RequirementAnalyzerPort,
    UncertaintyCandidate,
)
from smb_requirement_agent.analysis.application.ports.requirement_evidence_analyzer import (
    AnalysisProgressPort,
    EvidenceFragmentCacheEntry,
    EvidenceFragmentCachePort,
    RequirementEvidenceAnalyzerPort,
)
from smb_requirement_agent.analysis.application.use_cases.analysis_mapping import (
    analysis_evidence_key,
)
from smb_requirement_agent.analysis.application.use_cases.generation_effects import (
    stage_generation_effect,
)
from smb_requirement_agent.analysis.domain.value_objects import (
    ClarificationKind,
    ClarificationSource,
    HumanClarification,
    IntentProposal,
    IntentProposalKind,
    QuestionChangeAction,
)
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement

PACKET_PROMPT_RESERVE_CHARACTERS = 12_000
MAX_PACKET_IMAGES = 3
_BUSINESS_USE_CASE_HEADING = re.compile(r"^\[?BUC\s*\d+\]?\b", re.IGNORECASE)


class AssembleRequirementEvidence:
    """Select structured document contexts without flattening their block order."""

    def execute(
        self, documents: Sequence[AnalysisDocumentContext]
    ) -> tuple[AnalysisDocumentContext, ...]:
        return tuple(item for item in documents if item.get("evidence_blocks"))


class PlanEvidencePackets:
    def __init__(self, max_input_characters: int) -> None:
        self._block_budget = max(1, max_input_characters - PACKET_PROMPT_RESERVE_CHARACTERS)

    def execute(
        self, documents: Sequence[AnalysisDocumentContext]
    ) -> tuple[tuple[AnalysisDocumentContext, ...], ...]:
        packets: list[tuple[AnalysisDocumentContext, ...]] = []
        for document in documents:
            blocks = document.get("evidence_blocks", [])
            image_by_block = {item["block_id"]: item for item in document.get("image_assets", [])}
            current: list[AnalysisEvidenceBlock] = []
            current_size = 0
            current_images = 0
            inside_business_use_cases = False
            bounded_blocks = (
                bounded for block in blocks for bounded in self._bounded_blocks(block)
            )
            for block in bounded_blocks:
                top_level_heading = block["kind"] == "heading" and len(block["section_path"]) == 1
                business_use_case = top_level_heading and bool(
                    _BUSINESS_USE_CASE_HEADING.match(block["label"].strip())
                )
                if (
                    current
                    and top_level_heading
                    and (business_use_case or inside_business_use_cases)
                ):
                    packets.append((self._context(document, current, image_by_block),))
                    current, current_size, current_images = [], 0, 0
                inside_business_use_cases = inside_business_use_cases or business_use_case
                size = len(block.get("text") or "") + len(block["label"]) + 100
                is_image = block["kind"] == "image"
                if current and (
                    current_size + size > self._block_budget
                    or (is_image and current_images >= MAX_PACKET_IMAGES)
                ):
                    packets.append((self._context(document, current, image_by_block),))
                    current, current_size, current_images = [], 0, 0
                current.append(block)
                current_size += size
                current_images += int(is_image)
            if current:
                packets.append((self._context(document, current, image_by_block),))
        return tuple(packets)

    def _bounded_blocks(self, block: AnalysisEvidenceBlock) -> tuple[AnalysisEvidenceBlock, ...]:
        text = block.get("text") or ""
        if len(text) + len(block["label"]) + 100 <= self._block_budget:
            return (block,)
        # Reserve room for the generated "part N of M" suffix as well as packet markup.
        overhead = len(block["label"]) + 140
        text_budget = self._block_budget - overhead
        if text_budget < 1:
            raise RequirementAnalysisGenerationError(
                "The configured provider context cannot hold an evidence block header."
            )
        if block["kind"] == "image":
            raise RequirementAnalysisGenerationError(
                f"Image evidence block {block['block_id']!r} exceeds the provider packet budget."
            )
        parts = [text[index : index + text_budget] for index in range(0, len(text), text_budget)]
        return tuple(
            AnalysisEvidenceBlock(
                block_id=block["block_id"],
                kind=block["kind"],
                section_path=block["section_path"],
                label=f"{block['label']} (part {index} of {len(parts)})",
                text=part,
                asset_id=block.get("asset_id"),
            )
            for index, part in enumerate(parts, start=1)
        )

    @staticmethod
    def _context(
        source: AnalysisDocumentContext,
        blocks: list[AnalysisEvidenceBlock],
        image_by_block: Mapping[str, AnalysisImageAsset],
    ) -> AnalysisDocumentContext:
        block_ids = {item["block_id"] for item in blocks}
        return AnalysisDocumentContext(
            document_id=source["document_id"],
            version_id=source["version_id"],
            filename=source["filename"],
            checksum_sha256=source["checksum_sha256"],
            extracted_text="\n".join(item.get("text") or "[image]" for item in blocks),
            extraction_version=source.get("extraction_version", "unknown"),
            evidence_blocks=list(blocks),
            image_assets=[
                item for block_id, item in image_by_block.items() if block_id in block_ids
            ],
        )


class ValidateAnalysisCitations:
    def execute(
        self,
        candidate: RequirementAnalysisCandidate,
        documents: Sequence[AnalysisDocumentContext],
        clarifications: Sequence[HumanClarification] = (),
    ) -> None:
        allowed = {
            (
                block["block_id"],
                document["document_id"],
                document["version_id"],
                document["checksum_sha256"],
            )
            for document in documents
            for block in document.get("evidence_blocks", [])
        }
        evidence = candidate.get("evidence_references", {})
        human_evidence = candidate.get("clarification_references", {})
        expected = _candidate_keys(candidate)
        if set(evidence) | set(human_evidence) != expected:
            raise RequirementAnalysisGenerationError(
                "Structured analysis did not cite every generated item."
            )
        for key in expected:
            references = evidence.get(key, [])
            numbers = human_evidence.get(key, [])
            if len(numbers) != len(set(numbers)) or any(
                isinstance(number, bool)
                or not isinstance(number, int)
                or number < 1
                or number > len(clarifications)
                for number in numbers
            ):
                raise RequirementAnalysisGenerationError(
                    "Structured analysis returned invalid human answer citations."
                )
            if not references and not numbers:
                raise RequirementAnalysisGenerationError(
                    "Structured analysis returned blank or out-of-packet citations."
                )
            for item in references:
                identity = (
                    item["block_id"].strip(),
                    item["document_id"],
                    item["version_id"],
                    item["checksum_sha256"],
                )
                if not identity[0] or identity not in allowed:
                    raise RequirementAnalysisGenerationError(
                        "Structured analysis returned blank, stale, or out-of-packet citations."
                    )


@dataclass(frozen=True)
class PendingEvidenceFragment:
    cache_key: str
    entry: EvidenceFragmentCacheEntry


class AnalyzeEvidencePacket:
    def __init__(
        self,
        analyzer: RequirementEvidenceAnalyzerPort,
        validator: ValidateAnalysisCitations,
        cache: EvidenceFragmentCachePort,
        clock: ClockPort,
    ) -> None:
        self._analyzer = analyzer
        self._validator = validator
        self._cache = cache
        self._clock = clock

    def execute(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        packet: Sequence[AnalysisDocumentContext],
        intent_decisions: Sequence[IntentProposal],
        active_questions: Sequence[ActiveQuestionContext] = (),
        stage: str = "evidence_packet",
    ) -> tuple[
        RequirementAnalysisCandidate,
        AnalysisStageProvenanceCandidate,
        PendingEvidenceFragment | None,
    ]:
        fingerprint = _packet_fingerprint(packet)
        # Cache the entire semantic input, including citation/section metadata.
        # Earlier entries remain durable but are never consulted by this namespace.
        cache_input = {
            "format": "evidence-fragment-v3",
            "configuration_fingerprint": getattr(self._analyzer, "configuration_fingerprint", ""),
            "stage": stage,
            "requirement": asdict(requirement),
            "clarifications": [asdict(item) for item in clarifications],
            "intent_decisions": [asdict(item) for item in intent_decisions],
            "active_questions": list(active_questions),
            "packet": list(packet),
            "model": self._analyzer.model,
            "prompt_version": self._analyzer.prompt_version,
        }
        cache_key = (
            "v3:"
            + hashlib.sha256(
                json.dumps(cache_input, sort_keys=True, separators=(",", ":"), default=str).encode()
            ).hexdigest()
        )
        cached = self._cache.get(cache_key)
        pending: PendingEvidenceFragment | None = None
        if cached is None:
            candidate = self._analyzer.analyze_evidence(
                requirement, clarifications, packet, intent_decisions, active_questions
            )
            self._validator.execute(candidate, packet, clarifications)
            cached = EvidenceFragmentCacheEntry(deepcopy(candidate), self._clock.now())
            pending = PendingEvidenceFragment(cache_key, cached)
        else:
            candidate = deepcopy(cached.candidate)
            _rebind_cached_references(candidate, packet)
            self._validator.execute(candidate, packet, clarifications)
        return (
            deepcopy(candidate),
            {
                "stage": stage,
                "model": self._analyzer.model,
                "prompt_version": self._analyzer.prompt_version,
                "generated_at": cached.generated_at,
                "input_fingerprint": fingerprint,
            },
            pending,
        )

    def commit(self, pending: Sequence[PendingEvidenceFragment]) -> None:
        self._cache.put_many(tuple((item.cache_key, item.entry) for item in pending))


class ConsolidateEvidenceAnalysis:
    """Hierarchically reconcile packet findings without exceeding provider budgets."""

    def __init__(
        self,
        planner: PlanEvidencePackets,
        packet_analyzer: AnalyzeEvidencePacket,
    ) -> None:
        self._planner = planner
        self._packet_analyzer = packet_analyzer

    def execute(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        fragments: Sequence[RequirementAnalysisCandidate],
        intent_decisions: Sequence[IntentProposal],
        active_questions: Sequence[ActiveQuestionContext],
    ) -> tuple[
        RequirementAnalysisCandidate,
        list[AnalysisStageProvenanceCandidate],
        list[PendingEvidenceFragment],
    ]:
        if not fragments:
            raise RequirementAnalysisGenerationError("No evidence packets were available.")
        current = list(fragments)
        provenance: list[AnalysisStageProvenanceCandidate] = []
        pending_cache_entries: list[PendingEvidenceFragment] = []
        for _round in range(6):
            merged = self._merge(current, ())
            documents, source_references, human_sources = _consolidation_documents(merged)
            packets = self._planner.execute(documents)
            if not packets:
                raise RequirementAnalysisGenerationError(
                    "No cited findings were available for consolidation."
                )
            next_round: list[RequirementAnalysisCandidate] = []
            final_round = len(packets) == 1
            for packet in packets:
                candidate, stage, pending = self._packet_analyzer.execute(
                    requirement,
                    clarifications,
                    packet,
                    intent_decisions,
                    active_questions if final_round else (),
                    "evidence_consolidation",
                )
                _restore_source_references(candidate, source_references, human_sources)
                next_round.append(candidate)
                provenance.append(stage)
                if pending is not None:
                    pending_cache_entries.append(pending)
            if final_round:
                return next_round[0], provenance, pending_cache_entries
            if len(next_round) >= len(current):
                raise RequirementAnalysisGenerationError(
                    "Evidence findings could not be consolidated within the provider "
                    "context budget."
                )
            current = next_round
        raise RequirementAnalysisGenerationError(
            "Evidence consolidation exceeded the supported hierarchy depth."
        )

    @staticmethod
    def _merge(
        fragments: Sequence[RequirementAnalysisCandidate],
        active_questions: Sequence[ActiveQuestionContext],
    ) -> RequirementAnalysisCandidate:
        result = _empty_candidate(fragments[0]["model"], fragments[0]["prompt_version"])
        evidence: dict[str, list[AnalysisEvidenceReferenceCandidate]] = {}
        for fragment in fragments:
            for kind, values, additions in (
                ("known_fact", result["known_facts"], fragment["known_facts"]),
                ("constraint", result["constraints"], fragment["constraints"]),
                ("business_rule", result["business_rules"], fragment["business_rules"]),
                ("assumption", result["assumptions"], fragment["assumptions"]),
                (
                    "potential_dependency",
                    result["potential_dependencies"],
                    fragment["potential_dependencies"],
                ),
            ):
                _merge_statements(values, additions, kind, fragment, evidence)
            _merge_objects(
                result["open_questions"],
                fragment["open_questions"],
                lambda item: item["question"],
                "open_question",
                fragment,
                evidence,
            )
            _merge_objects(
                result["ambiguities"],
                fragment["ambiguities"],
                lambda item: item["statement"],
                "ambiguity",
                fragment,
                evidence,
            )
            _merge_proposals(result, fragment, evidence)
        result["evidence_references"] = evidence
        human_evidence: dict[str, list[int]] = {}
        for fragment in fragments:
            for key, numbers in fragment.get("clarification_references", {}).items():
                if key in _candidate_keys(result):
                    human_evidence[key] = sorted(set((*human_evidence.get(key, []), *numbers)))
        if human_evidence:
            result["clarification_references"] = human_evidence
        result["question_reviews"] = [
            QuestionReviewCandidate(
                question_id=item["question_id"],
                action=QuestionChangeAction.RETAINED,
                rationale="The cited source evidence does not resolve this question.",
                replacement=None,
            )
            for item in active_questions
            if item["source"] is ClarificationSource.AI
        ]
        result["new_uncertainties"] = _uncertainties(result)
        return result


class StructuredRequirementAnalyzer(RequirementAnalyzerPort):
    """Use packetized analysis for structured documents and preserve legacy behavior."""

    def __init__(
        self,
        fallback: RequirementAnalyzerPort,
        assembler: AssembleRequirementEvidence,
        planner: PlanEvidencePackets,
        packet_analyzer: AnalyzeEvidencePacket,
        consolidator: ConsolidateEvidenceAnalysis,
        validator: ValidateAnalysisCitations,
        clock: ClockPort,
        progress: AnalysisProgressPort,
    ) -> None:
        self._fallback = fallback
        self._assembler = assembler
        self._planner = planner
        self._packet_analyzer = packet_analyzer
        self._consolidator = consolidator
        self._validator = validator
        self._clock = clock
        self._progress = progress

    def analyze(
        self,
        requirement: Requirement,
        clarifications: Sequence[HumanClarification],
        documents: Sequence[AnalysisDocumentContext] = (),
        intent_decisions: Sequence[IntentProposal] = (),
        active_questions: Sequence[ActiveQuestionContext] = (),
    ) -> RequirementAnalysisCandidate:
        evidence_documents = self._assembler.execute(documents)
        if not evidence_documents:
            return self._fallback.analyze(
                requirement,
                clarifications,
                documents,
                intent_decisions,
                active_questions,
            )
        packets = self._planner.execute(evidence_documents)
        fragments: list[RequirementAnalysisCandidate] = []
        stages: list[AnalysisStageProvenanceCandidate] = []
        pending_cache_entries: list[PendingEvidenceFragment] = []
        total_units = len(packets) + 2
        self._progress.report(requirement.id, "planning_evidence", 1, total_units, None)
        for index, packet in enumerate(packets, start=1):
            blocks = packet[0].get("evidence_blocks", [])
            section_label = next(
                (" → ".join(block["section_path"]) for block in blocks if block["section_path"]),
                packet[0]["filename"],
            )
            self._progress.report(
                requirement.id,
                "analyzing_evidence",
                index,
                total_units,
                section_label,
            )
            fragment, provenance, pending = self._packet_analyzer.execute(
                requirement, clarifications, packet, intent_decisions
            )
            fragments.append(fragment)
            stages.append(provenance)
            if pending is not None:
                pending_cache_entries.append(pending)
        self._progress.report(
            requirement.id, "consolidating_findings", total_units - 1, total_units, None
        )
        result, consolidation_stages, consolidation_pending = self._consolidator.execute(
            requirement,
            clarifications,
            fragments,
            intent_decisions,
            active_questions,
        )
        stages.extend(consolidation_stages)
        pending_cache_entries.extend(consolidation_pending)
        self._validator.execute(result, evidence_documents, clarifications)
        self._progress.report(
            requirement.id,
            "validating_evidence_references",
            total_units,
            total_units,
            None,
        )
        result["stage_provenance"] = stages
        stage_generation_effect(lambda: self._packet_analyzer.commit(pending_cache_entries))
        return result


def _consolidation_documents(
    candidate: RequirementAnalysisCandidate,
) -> tuple[
    tuple[AnalysisDocumentContext, ...],
    dict[str, AnalysisEvidenceReferenceCandidate],
    dict[str, list[int]],
]:
    statements = _statements_by_evidence_key(candidate)
    blocks: dict[str, AnalysisEvidenceBlock] = {}
    source_references: dict[str, AnalysisEvidenceReferenceCandidate] = {}
    source_checksums: set[str] = set()
    human_sources: dict[str, list[int]] = {}
    for key, numbers in candidate.get("clarification_references", {}).items():
        statement = statements.get(key)
        if statement is None:
            continue
        synthetic_id = "human-" + hashlib.sha256(key.encode()).hexdigest()[:24]
        human_sources[synthetic_id] = list(numbers)
        blocks[synthetic_id] = AnalysisEvidenceBlock(
            block_id=synthetic_id,
            kind="paragraph",
            section_path=["Human answers"],
            label="Human answer evidence",
            text=f"Validated human-supported finding: {statement}",
            asset_id=None,
        )
        source_checksums.add(hashlib.sha256((key + str(numbers)).encode()).hexdigest())
    for key, references in candidate.get("evidence_references", {}).items():
        statement = statements.get(key)
        if statement is None:
            continue
        for reference in references:
            source_checksums.add(reference["checksum_sha256"])
            source_identity = "|".join(
                (
                    reference["document_id"],
                    reference["version_id"],
                    reference["checksum_sha256"],
                    reference["block_id"],
                )
            )
            synthetic_id = f"source-{hashlib.sha256(source_identity.encode()).hexdigest()[:24]}"
            source_references[synthetic_id] = reference
            block = blocks.get(synthetic_id)
            finding = f"Validated packet finding: {statement}"
            if block is None:
                blocks[synthetic_id] = AnalysisEvidenceBlock(
                    block_id=synthetic_id,
                    kind="paragraph",
                    section_path=[],
                    label=reference["label"],
                    text=finding,
                    asset_id=None,
                )
            elif finding not in (block.get("text") or ""):
                block["text"] = f"{block.get('text') or ''}\n{finding}"
    fingerprint = hashlib.sha256("|".join(sorted(source_checksums)).encode()).hexdigest()
    documents = (
        AnalysisDocumentContext(
            document_id="evidence-consolidation",
            version_id=fingerprint[:24],
            filename="Validated packet findings for cross-section consolidation",
            checksum_sha256=fingerprint,
            extracted_text="\n".join(block.get("text") or "" for block in blocks.values()),
            extraction_version="analysis-fragment-v1",
            evidence_blocks=list(blocks.values()),
            image_assets=[],
        ),
    )
    return documents, source_references, human_sources


def _restore_source_references(
    candidate: RequirementAnalysisCandidate,
    source_references: Mapping[str, AnalysisEvidenceReferenceCandidate],
    human_sources: Mapping[str, list[int]],
) -> None:
    for key, references in candidate.get("evidence_references", {}).items():
        restored: list[AnalysisEvidenceReferenceCandidate] = []
        for reference in references:
            numbers = human_sources.get(reference["block_id"])
            if numbers is not None:
                human = candidate.setdefault("clarification_references", {}).setdefault(key, [])
                human[:] = sorted(set((*human, *numbers)))
                continue
            source = source_references.get(reference["block_id"])
            if source is None:
                raise RequirementAnalysisGenerationError(
                    "Consolidation returned an unknown source evidence citation."
                )
            restored.append(source)
        references[:] = restored


def _statements_by_evidence_key(
    candidate: RequirementAnalysisCandidate,
) -> dict[str, str]:
    values: list[tuple[str, str]] = [
        *(("known_fact", item) for item in candidate["known_facts"]),
        *(("constraint", item) for item in candidate["constraints"]),
        *(("business_rule", item) for item in candidate["business_rules"]),
        *(("assumption", item) for item in candidate["assumptions"]),
        *(("open_question", item["question"]) for item in candidate["open_questions"]),
        *(("ambiguity", item["statement"]) for item in candidate["ambiguities"]),
        *(("potential_dependency", item) for item in candidate["potential_dependencies"]),
        *(("intent_proposal", item["statement"]) for item in candidate["intent_proposals"]),
    ]
    return {analysis_evidence_key(kind, statement): statement for kind, statement in values}


def _packet_fingerprint(documents: Sequence[AnalysisDocumentContext]) -> str:
    payload = [
        {
            "checksum": item["checksum_sha256"],
            "extraction_version": item.get("extraction_version", "unknown"),
            "blocks": [
                (block["block_id"], block["kind"], block.get("text"), block.get("asset_id"))
                for block in item.get("evidence_blocks", [])
            ],
        }
        for item in documents
    ]
    return hashlib.sha256(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()


def _rebind_cached_references(
    candidate: RequirementAnalysisCandidate,
    documents: Sequence[AnalysisDocumentContext],
) -> None:
    """Point checksum-reusable fragments at the current immutable document versions."""
    current: dict[tuple[str, str], AnalysisEvidenceReferenceCandidate] = {}
    for document in documents:
        for block in document.get("evidence_blocks", []):
            identity = document["checksum_sha256"], block["block_id"]
            current.setdefault(
                identity,
                AnalysisEvidenceReferenceCandidate(
                    document_id=document["document_id"],
                    version_id=document["version_id"],
                    checksum_sha256=document["checksum_sha256"],
                    block_id=block["block_id"],
                    label=block["label"],
                ),
            )
    for references in candidate.get("evidence_references", {}).values():
        for index, reference in enumerate(references):
            replacement = current.get((reference["checksum_sha256"], reference["block_id"]))
            if replacement is not None:
                references[index] = replacement


def _empty_candidate(model: str, prompt_version: str) -> RequirementAnalysisCandidate:
    return RequirementAnalysisCandidate(
        known_facts=[],
        constraints=[],
        business_rules=[],
        assumptions=[],
        open_questions=[],
        ambiguities=[],
        potential_dependencies=[],
        intent_proposals=[],
        model=model,
        prompt_version=prompt_version,
    )


def _candidate_keys(candidate: RequirementAnalysisCandidate) -> set[str]:
    return {
        *(analysis_evidence_key("known_fact", item) for item in candidate["known_facts"]),
        *(analysis_evidence_key("constraint", item) for item in candidate["constraints"]),
        *(analysis_evidence_key("business_rule", item) for item in candidate["business_rules"]),
        *(analysis_evidence_key("assumption", item) for item in candidate["assumptions"]),
        *(
            analysis_evidence_key("open_question", item["question"])
            for item in candidate["open_questions"]
        ),
        *(
            analysis_evidence_key("ambiguity", item["statement"])
            for item in candidate["ambiguities"]
        ),
        *(
            analysis_evidence_key("potential_dependency", item)
            for item in candidate["potential_dependencies"]
        ),
        *(
            analysis_evidence_key("intent_proposal", item["statement"])
            for item in candidate["intent_proposals"]
        ),
    }


def _merge_statements(
    target_values: list[str],
    source_values: Sequence[str],
    kind: str,
    source: RequirementAnalysisCandidate,
    evidence: dict[str, list[AnalysisEvidenceReferenceCandidate]],
) -> None:
    for value in source_values:
        if value.casefold() not in {item.casefold() for item in target_values}:
            target_values.append(value)
        _merge_evidence(evidence, source, analysis_evidence_key(kind, value))


def _merge_objects[Finding](
    target_values: list[Finding],
    source_values: Sequence[Finding],
    subject_of: Callable[[Finding], str],
    kind: str,
    source: RequirementAnalysisCandidate,
    evidence: dict[str, list[AnalysisEvidenceReferenceCandidate]],
) -> None:
    for value in source_values:
        subject = subject_of(value)
        if subject.casefold() not in {subject_of(item).casefold() for item in target_values}:
            target_values.append(value)
        _merge_evidence(evidence, source, analysis_evidence_key(kind, subject))


def _merge_proposals(
    target: RequirementAnalysisCandidate,
    source: RequirementAnalysisCandidate,
    evidence: dict[str, list[AnalysisEvidenceReferenceCandidate]],
) -> None:
    values: list[IntentProposalCandidate] = target["intent_proposals"]
    for value in source["intent_proposals"]:
        if value["kind"] is IntentProposalKind.DESIRED_OUTCOME and any(
            item["kind"] is IntentProposalKind.DESIRED_OUTCOME for item in values
        ):
            continue
        if (value["kind"], value["statement"].casefold()) not in {
            (item["kind"], item["statement"].casefold()) for item in values
        }:
            values.append(value)
        _merge_evidence(
            evidence, source, analysis_evidence_key("intent_proposal", value["statement"])
        )


def _merge_evidence(
    target: dict[str, list[AnalysisEvidenceReferenceCandidate]],
    source: RequirementAnalysisCandidate,
    key: str,
) -> None:
    current = target.setdefault(key, [])
    known = {(item["document_id"], item["version_id"], item["block_id"]) for item in current}
    for item in source.get("evidence_references", {}).get(key, []):
        identity = item["document_id"], item["version_id"], item["block_id"]
        if identity not in known:
            current.append(item)
            known.add(identity)


def _uncertainties(candidate: RequirementAnalysisCandidate) -> list[UncertaintyCandidate]:
    return [
        *(
            UncertaintyCandidate(kind=ClarificationKind.ASSUMPTION, subject=item, rationale=None)
            for item in candidate["assumptions"]
        ),
        *(
            UncertaintyCandidate(
                kind=ClarificationKind.OPEN_QUESTION,
                subject=item["question"],
                rationale=item["rationale"],
            )
            for item in candidate["open_questions"]
        ),
        *(
            UncertaintyCandidate(
                kind=ClarificationKind.AMBIGUITY,
                subject=item["statement"],
                rationale=item["reason"],
            )
            for item in candidate["ambiguities"]
        ),
        *(
            UncertaintyCandidate(
                kind=ClarificationKind.POTENTIAL_DEPENDENCY, subject=item, rationale=None
            )
            for item in candidate["potential_dependencies"]
        ),
    ]
