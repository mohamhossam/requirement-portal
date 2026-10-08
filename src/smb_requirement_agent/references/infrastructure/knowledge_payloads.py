"""Payload codecs for the reference and historic state knowledge-portal publishes.

They moved out of the domain in PR 2 of the bounded-context migration (ADR-0103), unchanged:
the same fields, the same tolerance of older copies, the same errors on malformed input. The
characterisation goldens `reference_document_state` and `historic_requirement_state` pin that.

`PayloadKnowledgeStateDecoder` lets the event-feed use cases decode without naming this module.
PR 15a replaces it with typed events decoded in the knowledge-portal ACL.
"""

from __future__ import annotations

from datetime import date, datetime

from smb_requirement_agent.references.domain.errors import InvalidKnowledgeError
from smb_requirement_agent.references.domain.historic import (
    HistoricPublication,
    HistoricRequirementState,
)
from smb_requirement_agent.references.domain.reference import (
    CurrentPublication,
    ReferenceDocumentState,
)
from smb_requirement_agent.requirements.domain.document.errors import InvalidDocumentError


def reference_document_state_to_payload(state: ReferenceDocumentState) -> dict[str, object]:
    """The event payload: plain JSON values."""
    published = state.published
    return {
        "document_id": state.document_id,
        "owner_id": state.owner_id,
        "title": state.title,
        "version": state.version,
        "published": None
        if published is None
        else {
            "publication_id": published.publication_id,
            "fingerprint": published.fingerprint,
            "version_id": published.version_id,
            "version_number": published.version_number,
            "revision_id": published.revision_id,
            "block_labels": [list(item) for item in published.block_labels],
            "passages": [list(item) for item in published.passages],
        },
        "review_due_on": None if state.review_due_on is None else state.review_due_on.isoformat(),
    }


def reference_document_state_from_payload(payload: object) -> ReferenceDocumentState:
    """Rebuild a state from an event payload, refusing anything malformed."""
    try:
        data = _mapping(payload)
        published = data["published"]
        current = None
        if published is not None:
            item = _mapping(published)
            current = CurrentPublication(
                _text(item["publication_id"]),
                _text(item["fingerprint"]),
                _text(item["version_id"]),
                _number(item["version_number"]),
                _text(item["revision_id"]),
                _pairs(item["block_labels"]),
                _pairs(item["passages"]),
            )
        return ReferenceDocumentState(
            _text(data["document_id"]),
            _text(data["owner_id"]),
            _text(data["title"]),
            _number(data["version"]),
            current,
            # Absent from events and copies written before Knowledge Center D.
            _day(data.get("review_due_on")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidDocumentError("Reference document event is malformed.") from exc


def historic_requirement_state_to_payload(state: HistoricRequirementState) -> dict[str, object]:
    published = state.published
    return {
        "historic_requirement_id": state.historic_requirement_id,
        "version": state.version,
        "published": None
        if published is None
        else {
            "publication": published.number,
            "fingerprint": published.fingerprint,
            "title": published.title,
            "published_at": published.published_at.isoformat(),
            "published_by": {"name": published.published_by},
            "root_ids": list(published.root_ids),
        },
    }


def historic_requirement_state_from_payload(payload: object) -> HistoricRequirementState:
    """Rebuild a state from an event payload, refusing anything malformed.

    Only the reference fields are read, so an event that still carries its content
    (as the first historic events did) is read the same way.
    """
    try:
        data = _mapping(payload)
        published = data["published"]
        current = None
        if published is not None:
            item = _mapping(published)
            by = _mapping(item["published_by"])
            current = HistoricPublication(
                _positive(item["publication"]),
                _text(item["fingerprint"]),
                _text(item["title"]),
                datetime.fromisoformat(_text(item["published_at"])),
                _text(by["name"]),
                tuple(_positive(value) for value in _list(item.get("root_ids", []))),
            )
        return HistoricRequirementState(
            _text(data["historic_requirement_id"]), _positive(data["version"]), current
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidKnowledgeError("Historic requirement event is malformed.") from exc


class PayloadKnowledgeStateDecoder:
    """`KnowledgeStateDecoderPort` over the codecs above."""

    def reference_document(self, payload: object) -> ReferenceDocumentState:
        return reference_document_state_from_payload(payload)

    def historic_requirement(self, payload: object) -> HistoricRequirementState:
        return historic_requirement_state_from_payload(payload)


def _day(value: object) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(_text(value))


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected an object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list | tuple):
        raise TypeError("expected a list")
    return list(value)


def _text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError("expected text")
    return value


def _number(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError("expected a whole number")
    return value


def _positive(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError("expected a positive whole number")
    return value


def _pairs(value: object) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list | tuple):
        raise TypeError("expected a list")
    pairs: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, list | tuple) or len(item) != 2:
            raise TypeError("expected a pair")
        pairs.append((_text(item[0]), _text(item[1])))
    return tuple(pairs)
