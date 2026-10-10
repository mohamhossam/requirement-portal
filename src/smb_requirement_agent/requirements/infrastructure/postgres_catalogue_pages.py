"""Paged drafts and documents, filtered, sorted and counted in PostgreSQL (hardening PR 13).

A draft belongs to the actor in `draft_ownership.payload->'owner'->'actor'->>'id'`
(`identity_payloads.draft_ownership_to_payload`). Every value is a parameter; the
SQL is assembled only from the constant fragments below.
"""

from __future__ import annotations

from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import (
    _integer,
    _payload,
    _string,
)
from smb_requirement_agent.requirements.application.ports.catalogue_pages import (
    DocumentCounts,
    DocumentFilter,
    DocumentOwner,
    DocumentPage,
    DocumentPageQuery,
    DocumentSort,
    DraftPage,
    DraftPageQuery,
    DraftSort,
    ListedDocument,
)
from smb_requirement_agent.requirements.domain.document.entities import SourceDocument
from smb_requirement_agent.requirements.infrastructure.document_payloads import (
    document_from_payload,
)
from smb_requirement_agent.requirements.infrastructure.requirement_snapshot import (
    requirement_draft_from_payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId

_OWNER_ID = "o.payload->'owner'->'actor'->>'id'"

_DRAFT_ORDER = {
    DraftSort.UPDATED_DESC: "d.updated_at DESC",
    DraftSort.UPDATED_ASC: "d.updated_at ASC",
    DraftSort.TITLE_ASC: "lower(d.payload->>'title') ASC",
    DraftSort.TITLE_DESC: "lower(d.payload->>'title') DESC",
}

# Every document the viewer may open, with what filtering and sorting need. The
# current version is the last one (`SourceDocument.current_version`).
_VISIBLE_DOCUMENTS = f"""
WITH visible AS (
    SELECT s.document_id, s.payload, s.requirement_id, s.draft_id,
           COALESCE(r.payload->>'title', d.payload->>'title') AS owner_title,
           COALESCE((s.payload->>'requires_attention')::boolean, false) AS attention,
           s.payload->>'included_version_id' IS NOT NULL AS included,
           s.payload->'versions'->-1->>'filename' AS filename,
           (s.payload->'versions'->-1->>'created_at')::timestamptz AS added_at
    FROM source_documents s
    LEFT JOIN requirements r ON r.requirement_id = s.requirement_id
    LEFT JOIN requirement_drafts d ON d.draft_id = s.draft_id
    LEFT JOIN draft_ownership o ON o.draft_id = s.draft_id
    WHERE NOT COALESCE((s.payload->>'removed')::boolean, false)
      AND (s.draft_id IS NULL OR {_OWNER_ID} = %s)
)
"""  # noqa: S608 - constant fragments; the viewer is a parameter

_DOCUMENT_FILTER = {
    DocumentFilter.ALL: "",
    DocumentFilter.ATTENTION: " AND attention",
    DocumentFilter.INCLUDED: " AND NOT attention AND included",
    DocumentFilter.EXCLUDED: " AND NOT attention AND NOT included",
}

# A document blocking analysis comes first, whatever the sort.
_DOCUMENT_ORDER = {
    DocumentSort.ADDED_DESC: "attention DESC, added_at DESC, document_id",
    DocumentSort.ADDED_ASC: "attention DESC, added_at ASC, document_id",
    DocumentSort.NAME_ASC: "attention DESC, lower(filename) ASC, document_id",
    DocumentSort.NAME_DESC: "attention DESC, lower(filename) DESC, document_id",
}


def _contains(q: str | None) -> str | None:
    """A case-insensitive LIKE pattern for `q`, its wildcards escaped with `!`."""
    needle = (q or "").strip().lower()
    if not needle:
        return None
    return "%" + needle.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def _text(value: object) -> str | None:
    return None if value is None else _string(value)


def _owner(requirement_id: object, draft_id: object, title: object) -> DocumentOwner:
    if requirement_id is not None:
        return DocumentOwner("requirement", RequirementId(_string(requirement_id)), _text(title))
    return DocumentOwner("draft", RequirementId(_string(draft_id)), _text(title))


class PostgresCataloguePages:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def drafts(self, query: DraftPageQuery) -> DraftPage:
        where = (
            f" AND {_OWNER_ID} = %s"
            if query.owner_id is not None
            else " AND (o.draft_id IS NULL OR jsonb_typeof(o.payload->'owner') IS DISTINCT FROM "
            "'object')"
        )
        params: list[object] = [] if query.owner_id is None else [query.owner_id.value]
        pattern = _contains(query.q)
        if pattern is not None:
            where += " AND lower(d.payload->>'title') LIKE %s ESCAPE '!'"
            params.append(pattern)
        base = (
            "FROM requirement_drafts d LEFT JOIN draft_ownership o ON o.draft_id = d.draft_id "
            "WHERE true" + where
        )
        with self._store.connection() as connection:
            rows = connection.execute(
                f"SELECT d.payload {base} "  # noqa: S608 - constant fragments; values are parameters
                f"ORDER BY {_DRAFT_ORDER[query.sort]}, d.draft_id OFFSET %s LIMIT %s",
                (*params, query.offset, query.limit),
            ).fetchall()
            total = connection.execute(
                f"SELECT count(*) {base}",  # noqa: S608 - constant fragments; values are parameters
                params,
            ).fetchone()
        return DraftPage(
            tuple(requirement_draft_from_payload(_payload(row[0])) for row in rows),
            _integer(total[0]) if total else 0,
        )

    def documents(self, query: DocumentPageQuery) -> DocumentPage:
        viewer = query.viewer_id.value
        where = _DOCUMENT_FILTER[query.filter]
        params: list[object] = []
        if query.owner_id is not None:
            where += " AND (requirement_id = %s OR draft_id = %s)"
            params += [query.owner_id.value, query.owner_id.value]
        pattern = _contains(query.q)
        if pattern is not None:
            where += (
                " AND (lower(filename) LIKE %s ESCAPE '!'"
                " OR lower(COALESCE(owner_title, '')) LIKE %s ESCAPE '!')"
            )
            params += [pattern, pattern]
        with self._store.connection() as connection:
            rows = connection.execute(
                f"{_VISIBLE_DOCUMENTS} SELECT payload, requirement_id, draft_id, owner_title "  # noqa: S608 - constant fragments; values are parameters
                f"FROM visible WHERE true{where} "
                f"ORDER BY {_DOCUMENT_ORDER[query.sort]} OFFSET %s LIMIT %s",
                (viewer, *params, query.offset, query.limit),
            ).fetchall()
            total = connection.execute(
                f"{_VISIBLE_DOCUMENTS} SELECT count(*) FROM visible WHERE true{where}",  # noqa: S608 - constant fragments; values are parameters
                (viewer, *params),
            ).fetchone()
            counts = connection.execute(
                f"{_VISIBLE_DOCUMENTS} SELECT count(*) FILTER (WHERE attention), "  # noqa: S608 - constant fragments; values are parameters
                "count(*) FILTER (WHERE NOT attention AND included), "
                "count(*) FILTER (WHERE NOT attention AND NOT included) FROM visible",
                (viewer,),
            ).fetchone()
            owners = connection.execute(
                f"{_VISIBLE_DOCUMENTS} SELECT DISTINCT requirement_id, draft_id, owner_title "  # noqa: S608 - constant fragments; values are parameters
                "FROM visible ORDER BY owner_title, requirement_id, draft_id",
                (viewer,),
            ).fetchall()
        return DocumentPage(
            documents=tuple(
                ListedDocument(
                    document_from_payload(_payload(row[0])), _owner(row[1], row[2], row[3])
                )
                for row in rows
            ),
            total=_integer(total[0]) if total else 0,
            counts=DocumentCounts(*(_integer(value) for value in counts))
            if counts
            else DocumentCounts(0, 0, 0),
            owners=tuple(_owner(row[0], row[1], row[2]) for row in owners),
        )

    def owner_of(self, document: SourceDocument) -> DocumentOwner:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT COALESCE(r.payload->>'title', d.payload->>'title') FROM source_documents s "
                "LEFT JOIN requirements r ON r.requirement_id = s.requirement_id "
                "LEFT JOIN requirement_drafts d ON d.draft_id = s.draft_id "
                "WHERE s.document_id = %s",
                (document.id.value,),
            ).fetchone()
        return _owner(
            document.requirement_id.value if document.requirement_id else None,
            document.draft_id.value if document.draft_id else None,
            row[0] if row else None,
        )
