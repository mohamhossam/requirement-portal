"""Suggesting which catalogue system a document's system name may refer to.

A shortlist comes from how alike the names are and, when the embedding model
answers, how alike their meaning is. A model then decides which shortlisted
systems really are the same system. Nothing here links anything: a maintainer
confirms every suggestion.
"""

from __future__ import annotations

import json
import math
import re
from difflib import SequenceMatcher

from pydantic import BaseModel, Field, ValidationError

from smb_requirement_agent.application.errors import ModelTransportError
from smb_requirement_agent.application.ports.architecture_rag import (
    ArchitectureEvidenceError,
    EmbeddingPort,
)
from smb_requirement_agent.application.ports.system_matcher import (
    MatchableSystem,
    MatchQuery,
    MatchResult,
    MatchSuggestion,
    SystemMatchingError,
)
from smb_requirement_agent.infrastructure.llm.prompts.catalogue_matching_prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from smb_requirement_agent.infrastructure.llm.structured_output import (
    StructuredOutputClient,
    StructuredOutputError,
)

SHORTLIST_SIZE = 5
# Below these a catalogue system is not worth showing to the model.
NAME_FLOOR = 0.5
MEANING_FLOOR = 0.6
# The offline fake suggests only names this alike, having no model to judge the rest.
_FAKE_FLOOR = 0.8
# Names per call, so a document naming many systems still fits a small model.
_MAX_NAMES_PER_CALL = 20
_MAX_REASON = 300


class MatchOutput(BaseModel):
    number: int
    system_id: str = Field(max_length=200)
    reason: str = Field(max_length=_MAX_REASON)


class MatchingOutput(BaseModel):
    matches: list[MatchOutput] = Field(max_length=3 * _MAX_NAMES_PER_CALL)


_SCHEMA_TEXT = json.dumps(MatchingOutput.model_json_schema())


def _tokens(text: str) -> int:
    return len(text) // 4 + 1


def _words(value: str) -> list[str]:
    return re.findall(r"\w+", value.casefold())


def _initials(words: list[str]) -> str:
    return "".join(word[0] for word in words)


def name_likeness(written: str, label: str) -> float:
    """How alike two names are, from 0 to 1, by their words and letters alone."""
    ours, theirs = _words(written), _words(label)
    if not ours or not theirs:
        return 0.0
    shared = len(set(ours) & set(theirs)) / len(set(ours))
    spelling = SequenceMatcher(None, " ".join(ours), " ".join(theirs)).ratio()
    joined_ours, joined_theirs = "".join(ours), "".join(theirs)
    abbreviation = (
        1.0
        if len(joined_ours) > 1
        and (
            (len(theirs) > 1 and joined_ours == _initials(theirs))
            or (len(ours) > 1 and joined_theirs == _initials(ours))
        )
        else 0.0
    )
    return max(shared, spelling, abbreviation)


def _labels(system: MatchableSystem) -> tuple[str, ...]:
    return tuple(
        label for label in (system.id, system.name, system.name_ar or "", *system.aliases) if label
    )


def _profile(system: MatchableSystem) -> str:
    return "; ".join((system.name, *system.aliases, *system.capabilities))


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    norm = math.sqrt(sum(x * x for x in left)) * math.sqrt(sum(x * x for x in right))
    return sum(x * y for x, y in zip(left, right, strict=True)) / norm if norm else 0.0


def shortlists(
    queries: tuple[MatchQuery, ...],
    systems: tuple[MatchableSystem, ...],
    embeddings: EmbeddingPort | None,
) -> tuple[list[tuple[MatchQuery, list[tuple[float, MatchableSystem]]]], tuple[str, ...]]:
    """The likeliest catalogue systems for each name, best first, with how alike they are.

    Names with no likely system are left out.
    """
    meaning: dict[tuple[int, int], float] = {}
    warnings: tuple[str, ...] = ()
    if embeddings is not None:
        try:
            vectors = embeddings.embed(
                tuple(query.written_as for query in queries)
                + tuple(_profile(system) for system in systems)
            )
        except ArchitectureEvidenceError:
            warnings = (
                "Similar systems were looked for by name only; the embedding model did not answer.",
            )
        else:
            for q, query_vector in enumerate(vectors[: len(queries)]):
                for s, system_vector in enumerate(vectors[len(queries) :]):
                    meaning[(q, s)] = _cosine(query_vector, system_vector)
    result: list[tuple[MatchQuery, list[tuple[float, MatchableSystem]]]] = []
    for q, query in enumerate(queries):
        scored: list[tuple[float, int]] = []
        for s, system in enumerate(systems):
            by_name = max(name_likeness(query.written_as, label) for label in _labels(system))
            by_meaning = meaning.get((q, s), 0.0)
            if by_name >= NAME_FLOOR or by_meaning >= MEANING_FLOOR:
                scored.append((max(by_name, by_meaning), s))
        scored.sort(key=lambda item: (-item[0], item[1]))
        if scored:
            result.append((query, [(score, systems[s]) for score, s in scored[:SHORTLIST_SIZE]]))
    return result, warnings


class StructuredSystemMatcher:
    def __init__(
        self,
        client: StructuredOutputClient,
        embeddings: EmbeddingPort,
        *,
        max_input_tokens: int | None = None,
    ) -> None:
        """``max_input_tokens`` is the prompt room the client allows; None means ample."""
        self._client = client
        self._embeddings = embeddings
        self._max_input_tokens = max_input_tokens

    @property
    def model(self) -> str:
        return self._client.model

    @property
    def prompt_version(self) -> str:
        return PROMPT_VERSION

    def _batches(
        self, items: list[tuple[int, MatchQuery, list[MatchableSystem]]]
    ) -> list[list[tuple[int, MatchQuery, list[MatchableSystem]]]]:
        room = (
            int(self._max_input_tokens * 0.9) - _tokens(SYSTEM_PROMPT) - _tokens(_SCHEMA_TEXT)
            if self._max_input_tokens is not None
            else 10**9
        )
        batches: list[list[tuple[int, MatchQuery, list[MatchableSystem]]]] = []
        current: list[tuple[int, MatchQuery, list[MatchableSystem]]] = []
        for item in items:
            candidate = [*current, item]
            if current and (
                len(candidate) > _MAX_NAMES_PER_CALL or _tokens(build_user_prompt(candidate)) > room
            ):
                batches.append(current)
                candidate = [item]
            current = candidate
        if current:
            batches.append(current)
        return batches

    def match(
        self, queries: tuple[MatchQuery, ...], systems: tuple[MatchableSystem, ...]
    ) -> MatchResult:
        listed, warnings = shortlists(queries, systems, self._embeddings)
        items = [
            (number, query, [system for _, system in shortlist])
            for number, (query, shortlist) in enumerate(listed, 1)
        ]
        suggestions: list[MatchSuggestion] = []
        for batch in self._batches(items):
            try:
                output = self._client.parse(
                    system_prompt=SYSTEM_PROMPT,
                    user_prompt=build_user_prompt(batch),
                    schema_type=MatchingOutput,
                )
            except (StructuredOutputError, ValidationError, ModelTransportError) as exc:
                raise SystemMatchingError("The matching model's answer was unusable.") from exc
            asked = {number: (query, {s.id for s in listed}) for number, query, listed in batch}
            usable = [
                MatchSuggestion(
                    asked[item.number][0].written_as, item.system_id, item.reason.strip()
                )
                for item in output.matches
                if item.number in asked
                and item.system_id in asked[item.number][1]
                and item.reason.strip()
            ]
            if output.matches and not usable:
                raise SystemMatchingError(
                    "The matching model named no shortlisted system with a reason."
                )
            suggestions.extend(usable)
        return MatchResult(tuple(suggestions), warnings)


class FakeSystemMatcher:
    """Deterministic offline matching by name likeness alone; not a language model."""

    model = "fake-system-matcher"
    prompt_version = PROMPT_VERSION

    def match(
        self, queries: tuple[MatchQuery, ...], systems: tuple[MatchableSystem, ...]
    ) -> MatchResult:
        listed, _ = shortlists(queries, systems, None)
        return MatchResult(
            tuple(
                MatchSuggestion(query.written_as, best.id, f"Similar name to {best.name}.")
                for query, ((score, best), *_) in listed
                if score >= _FAKE_FLOOR
            )
        )
