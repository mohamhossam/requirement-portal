"""Deterministic offline adapters for requirement knowledge."""

from __future__ import annotations

import hashlib
import re

from smb_requirement_agent.analysis.domain.entities import ClarificationQuestion
from smb_requirement_agent.application.ports.prior_art import (
    PriorArtCandidateInput,
    PriorArtJudgement,
)
from smb_requirement_agent.application.ports.requirement_knowledge import (
    AnswerSuggestionCandidate,
    Embedding,
    RelationshipCandidate,
)
from smb_requirement_agent.domain.knowledge.entities import (
    KnowledgeChunk,
    KnowledgeMatch,
    KnowledgeRelationshipKind,
)
from smb_requirement_agent.references.application.ports.reference_grounding import ReferenceEvidence
from smb_requirement_agent.requirements.domain.requirement.entities import Requirement

_WORDS = re.compile(r"[a-z0-9]+")
_NEGATIONS = {"not", "never", "exclude", "excluded", "cannot", "disabled", "only"}
# Words too common to make two requirements alike.
_STOP = {"a", "an", "and", "as", "for", "i", "in", "is", "of", "on", "or", "the", "to", "with"}


class FakeKnowledgeEmbedding:
    model = "fake-knowledge-embedding-768"

    def embed(self, texts: tuple[str, ...]) -> tuple[Embedding, ...]:
        return tuple(_embedding(text) for text in texts)


class FakeRequirementRelationshipClassifier:
    model = "fake-knowledge-classifier"
    prompt_version = "knowledge-screen-v1"

    def classify(
        self,
        requirement: Requirement,
        subject_text: str,
        matches: tuple[KnowledgeMatch, ...],
    ) -> tuple[RelationshipCandidate, ...]:
        subject_words = set(_WORDS.findall(subject_text.casefold()))
        grouped: dict[str, list[KnowledgeMatch]] = {}
        for match in matches:
            grouped.setdefault(match.chunk.requirement_id.value, []).append(match)
        findings: list[RelationshipCandidate] = []
        for values in grouped.values():
            related_text = " ".join(item.chunk.text for item in values)
            related_words = set(_WORDS.findall(related_text.casefold()))
            meaningful = (subject_words - _NEGATIONS).intersection(related_words - _NEGATIONS)
            coverage = len(meaningful) / max(1, min(len(subject_words), len(related_words)))
            if coverage < 0.35:
                continue
            subject_negated = bool(subject_words.intersection(_NEGATIONS))
            related_negated = bool(related_words.intersection(_NEGATIONS))
            kind = (
                KnowledgeRelationshipKind.POSSIBLE_CONTRADICTION
                if subject_negated != related_negated
                else KnowledgeRelationshipKind.POSSIBLE_DUPLICATE
            )
            findings.append(
                RelationshipCandidate(
                    values[0].chunk.requirement_id,
                    kind,
                    (
                        "Trusted requirement evidence expresses an opposing rule."
                        if kind is KnowledgeRelationshipKind.POSSIBLE_CONTRADICTION
                        else "Trusted requirement evidence substantially overlaps this requirement."
                    ),
                    tuple(item.chunk.id.value for item in values[:3]),
                )
            )
        return tuple(findings[:10])


class FakePriorArtJudge:
    """Similar when enough of the subject's words recur in a candidate's evidence."""

    model = "fake-prior-art-judge"
    prompt_version = "prior-art-v1"

    def judge(
        self, title: str, subject_text: str, candidates: tuple[PriorArtCandidateInput, ...]
    ) -> tuple[PriorArtJudgement, ...]:
        subject_words = set(_WORDS.findall(f"{title} {subject_text}".casefold())) - _STOP
        judged: list[tuple[float, PriorArtJudgement]] = []
        for candidate in candidates:
            text = " ".join(item.text for item in candidate.evidence)
            words = set(_WORDS.findall(f"{candidate.title} {text}".casefold())) - _STOP
            shared = subject_words & words
            coverage = len(shared) / max(1, min(len(subject_words), len(words)))
            if coverage < 0.35:
                continue
            cited = tuple(
                item.number
                for item in candidate.evidence
                if shared & set(_WORDS.findall(item.text.casefold()))
            )[:3] or (candidate.evidence[0].number,)
            judged.append(
                (
                    coverage,
                    PriorArtJudgement(
                        candidate.number,
                        "It delivered much the same capability: "
                        + ", ".join(sorted(shared)[:5])
                        + ".",
                        cited,
                    ),
                )
            )
        judged.sort(key=lambda pair: pair[0], reverse=True)
        return tuple(judgement for _, judgement in judged[:5])


class FakeClarificationAnswerSuggester:
    model = "fake-grounded-answer-suggester"
    prompt_version = "clarification-suggestions-v4"

    def suggest(
        self,
        requirement: Requirement,
        question: ClarificationQuestion,
        current_analysis: tuple[KnowledgeChunk, ...],
        matches: tuple[KnowledgeMatch, ...],
        references: tuple[ReferenceEvidence, ...] = (),
    ) -> tuple[AnswerSuggestionCandidate, ...]:
        del requirement, question
        candidates: list[AnswerSuggestionCandidate] = (
            [
                AnswerSuggestionCandidate(
                    references[0].citation.excerpt,
                    "Published reference; confirm applicability before using this answer.",
                    ("reference:0",),
                )
            ]
            if references
            else []
        )
        if current_analysis:
            chunk = current_analysis[0]
            candidates.append(
                AnswerSuggestionCandidate(
                    chunk.text.strip(),
                    "This answer is supported by the current unconfirmed analysis.",
                    (chunk.id.value,),
                )
            )
        if matches:
            chunk = matches[0].chunk
            candidates.append(
                AnswerSuggestionCandidate(
                    chunk.text.strip(),
                    "This answer is supported by trusted requirement knowledge.",
                    (chunk.id.value,),
                )
            )
        if current_analysis and matches:
            current = current_analysis[0]
            trusted = matches[0].chunk
            candidates.append(
                AnswerSuggestionCandidate(
                    f"{current.text.strip()} {trusted.text.strip()}",
                    "This answer combines current analysis with trusted knowledge.",
                    (current.id.value, trusted.id.value),
                )
            )
        seen = {item.answer.casefold() for item in candidates}
        evidence = (*current_analysis[1:], *(match.chunk for match in matches[1:]))
        for chunk in evidence:
            if len(candidates) == 3:
                break
            answer = chunk.text.strip()
            normalized = answer.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(
                AnswerSuggestionCandidate(
                    answer,
                    "This answer is directly supported by the cited evidence.",
                    (chunk.id.value,),
                )
            )
        unique: dict[str, AnswerSuggestionCandidate] = {}
        for candidate in candidates:
            unique.setdefault(candidate.answer.strip().casefold(), candidate)
        return tuple(unique.values())[:3]


def _embedding(text: str) -> Embedding:
    values = [0.0] * 768
    words = re.findall(r"\w+", text.casefold()) or [text]
    for word in words:
        digest = hashlib.sha256(word.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % len(values)
        values[index] += -1.0 if digest[2] & 1 else 1.0
    if not any(values):
        values[0] = 1.0  # Hash collisions must not make the offline vector unusable.
    return tuple(values)
