"""PostgreSQL pgvector adapter for requirement knowledge and review state."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from psycopg.types.json import Jsonb
from pydantic import TypeAdapter

from smb_requirement_agent.application.ports.requirement_knowledge import Embedding
from smb_requirement_agent.domain.analysis.value_objects import QuestionId
from smb_requirement_agent.domain.knowledge.entities import (
    AnswerSuggestion,
    AnswerSuggestionId,
    AnswerSuggestionSet,
    AnswerSuggestionSetId,
    KnowledgeChunk,
    KnowledgeChunkId,
    KnowledgeDecision,
    KnowledgeDecisionKind,
    KnowledgeFinding,
    KnowledgeFindingId,
    KnowledgeFindingStatus,
    KnowledgeMatch,
    KnowledgeRelationshipKind,
    KnowledgeScreen,
    KnowledgeScreenId,
    KnowledgeSourceKind,
    RelationshipEvidence,
)
from smb_requirement_agent.domain.knowledge.errors import KnowledgeFindingConflictError
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import _integer
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorSnapshot,
)
from smb_requirement_agent.shared_kernel.citation import PublishedReference
from smb_requirement_agent.shared_kernel.generation import Provenance
from smb_requirement_agent.shared_kernel.identifiers import RequirementId
from smb_requirement_agent.shared_kernel.lineage import SourceLineage


class PostgresRequirementKnowledgeStore:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def indexed_fingerprint(self, requirement_id: RequirementId) -> str | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT corpus_fingerprint FROM requirement_knowledge_index "
                "WHERE requirement_id=%s",
                (requirement_id.value,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def pending_sources(self, limit: int, after: str = "") -> tuple[tuple[RequirementId, int], ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT requirement_id,change_number FROM knowledge_source_changes "
                "WHERE dirty AND requirement_id > %s ORDER BY requirement_id LIMIT %s",
                (after, limit),
            ).fetchall()
        return tuple((RequirementId(str(row[0])), _integer(row[1])) for row in rows)

    def replace_if_current(
        self,
        requirement_id: RequirementId,
        expected_change: int,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> bool:
        with self._store.transaction():
            with self._store.connection() as connection:
                row = connection.execute(
                    "SELECT change_number FROM knowledge_source_changes "
                    "WHERE requirement_id=%s AND change_number=%s AND dirty FOR UPDATE",
                    (requirement_id.value, expected_change),
                ).fetchone()
                if row is None:
                    return False
                self.replace(requirement_id, corpus_fingerprint, chunks, embeddings)
                connection.execute(
                    "UPDATE knowledge_source_changes SET dirty=false WHERE requirement_id=%s",
                    (requirement_id.value,),
                )
                return True

    def replace(
        self,
        requirement_id: RequirementId,
        corpus_fingerprint: str,
        chunks: tuple[KnowledgeChunk, ...],
        embeddings: tuple[Embedding, ...],
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Each knowledge chunk requires one embedding.")
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM requirement_knowledge_chunks WHERE requirement_id=%s",
                (requirement_id.value,),
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                connection.execute(
                    """
                    INSERT INTO requirement_knowledge_chunks
                        (chunk_id,requirement_id,payload,embedding)
                    VALUES (%s,%s,%s,%s::vector)
                    """,
                    (
                        chunk.id.value,
                        requirement_id.value,
                        Jsonb(_chunk_payload(chunk)),
                        _vector(embedding),
                    ),
                )
            connection.execute(
                """
                INSERT INTO requirement_knowledge_index (requirement_id,corpus_fingerprint)
                VALUES (%s,%s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET corpus_fingerprint=EXCLUDED.corpus_fingerprint,updated_at=now()
                """,
                (requirement_id.value, corpus_fingerprint),
            )

    def search(
        self,
        query_text: str,
        query_embedding: Embedding,
        exclude_requirement_id: RequirementId | None,
        limit: int,
    ) -> tuple[KnowledgeMatch, ...]:
        with self._store.connection() as connection:
            lexical = connection.execute(
                """
                SELECT chunk_id,payload,
                       ts_rank_cd(search_document,websearch_to_tsquery('simple',%s)) score
                FROM requirement_knowledge_chunks
                WHERE requirement_id IS DISTINCT FROM %s
                  AND search_document @@ websearch_to_tsquery('simple',%s)
                ORDER BY score DESC,chunk_id LIMIT %s
                """,
                (
                    query_text,
                    (exclude_requirement_id.value if exclude_requirement_id else None),
                    query_text,
                    limit,
                ),
            ).fetchall()
            semantic = connection.execute(
                """
                SELECT chunk_id,payload,embedding <=> %s::vector distance
                FROM requirement_knowledge_chunks
                WHERE requirement_id IS DISTINCT FROM %s
                ORDER BY distance,chunk_id LIMIT %s
                """,
                (
                    _vector(query_embedding),
                    (exclude_requirement_id.value if exclude_requirement_id else None),
                    limit,
                ),
            ).fetchall()
        lexical_rank = {str(row[0]): rank for rank, row in enumerate(lexical, 1)}
        semantic_rank = {str(row[0]): rank for rank, row in enumerate(semantic, 1)}
        rows = {str(row[0]): row for row in (*lexical, *semantic)}
        matches = [
            KnowledgeMatch(
                _chunk_from_payload(_object(row[1])),
                lexical_rank.get(chunk_id),
                semantic_rank.get(chunk_id),
                (1 / (60 + lexical_rank[chunk_id]) if chunk_id in lexical_rank else 0)
                + (1 / (60 + semantic_rank[chunk_id]) if chunk_id in semantic_rank else 0),
            )
            for chunk_id, row in rows.items()
        ]
        return tuple(sorted(matches, key=lambda item: item.fused_score, reverse=True)[:limit])

    def get_chunks(self, chunk_ids: tuple[str, ...]) -> tuple[KnowledgeChunk, ...]:
        if not chunk_ids:
            return ()
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM requirement_knowledge_chunks WHERE chunk_id=ANY(%s)",
                (list(chunk_ids),),
            ).fetchall()
        return tuple(_chunk_from_payload(_object(row[0])) for row in rows)

    def append_screen(
        self, screen: KnowledgeScreen, findings: tuple[KnowledgeFinding, ...]
    ) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO requirement_knowledge_screens
                    (screen_id,requirement_id,input_fingerprint,payload,generated_at)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    screen.id.value,
                    screen.requirement_id.value,
                    screen.input_fingerprint,
                    Jsonb(_screen_payload(screen)),
                    screen.provenance.generated_at,
                ),
            )
            for finding in findings:
                payload = Jsonb(_finding_payload(finding))
                connection.execute(
                    """
                    INSERT INTO requirement_knowledge_findings
                        (finding_id,screen_id,subject_requirement_id,related_requirement_id,
                         version,payload)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        finding.id.value,
                        finding.screen_id.value,
                        finding.subject_requirement_id.value,
                        finding.related_requirement_id.value,
                        finding.version,
                        payload,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO requirement_knowledge_finding_revisions
                        (finding_id,version,payload) VALUES (%s,%s,%s)
                    """,
                    (finding.id.value, finding.version, payload),
                )
            connection.execute(
                "DELETE FROM requirement_knowledge_dependencies WHERE dependent_requirement_id=%s",
                (screen.requirement_id.value,),
            )
            for source_id in sorted({item.related_requirement_id.value for item in findings}):
                source = connection.execute(
                    "SELECT COALESCE((payload->>'version')::integer,1) "
                    "FROM requirements WHERE requirement_id=%s",
                    (source_id,),
                ).fetchone()
                if source is not None:
                    connection.execute(
                        """
                        INSERT INTO requirement_knowledge_dependencies
                            (source_requirement_id,dependent_requirement_id,source_version)
                        VALUES (%s,%s,%s)
                        ON CONFLICT (source_requirement_id,dependent_requirement_id)
                        DO UPDATE SET source_version=EXCLUDED.source_version
                        """,
                        (source_id, screen.requirement_id.value, source[0]),
                    )
            self._store.mark_requirement_dirty(screen.requirement_id)

    def current_screen(self, requirement_id: RequirementId) -> KnowledgeScreen | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT payload FROM requirement_knowledge_screens
                WHERE requirement_id=%s ORDER BY generated_at DESC,screen_id DESC LIMIT 1
                """,
                (requirement_id.value,),
            ).fetchone()
        return _screen_from_payload(_object(row[0])) if row is not None else None

    def get_finding(self, finding_id: KnowledgeFindingId) -> KnowledgeFinding | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_knowledge_findings WHERE finding_id=%s",
                (finding_id.value,),
            ).fetchone()
        return finding_from_payload(_object(row[0])) if row is not None else None

    def list_findings(self, screen_id: str) -> tuple[KnowledgeFinding, ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM requirement_knowledge_findings
                WHERE screen_id=%s ORDER BY finding_id
                """,
                (screen_id,),
            ).fetchall()
        return tuple(finding_from_payload(_object(row[0])) for row in rows)

    def save_finding(self, finding: KnowledgeFinding, expected_version: int) -> None:
        payload = Jsonb(_finding_payload(finding))
        with self._store.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE requirement_knowledge_findings
                SET version=%s,payload=%s,updated_at=now()
                WHERE finding_id=%s AND version=%s
                """,
                (finding.version, payload, finding.id.value, expected_version),
            )
            if cursor.rowcount != 1:
                raise KnowledgeFindingConflictError(
                    "The knowledge finding changed since it was loaded. Refresh and try again."
                )
            connection.execute(
                """
                INSERT INTO requirement_knowledge_finding_revisions
                    (finding_id,version,payload) VALUES (%s,%s,%s)
                """,
                (finding.id.value, finding.version, payload),
            )
            self._store.mark_requirement_dirty(finding.subject_requirement_id)

    def list_related_findings(self, requirement_id: RequirementId) -> tuple[KnowledgeFinding, ...]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM requirement_knowledge_findings
                WHERE subject_requirement_id=%s OR related_requirement_id=%s
                ORDER BY updated_at DESC,finding_id
                """,
                (requirement_id.value, requirement_id.value),
            ).fetchall()
        return tuple(finding_from_payload(_object(row[0])) for row in rows)

    def append_suggestion_set(self, suggestions: AnswerSuggestionSet) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO clarification_answer_suggestion_sets
                    (suggestion_set_id,requirement_id,question_id,payload,generated_at)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    suggestions.id.value,
                    suggestions.requirement_id.value,
                    suggestions.question_id.value,
                    Jsonb(_suggestion_set_payload(suggestions)),
                    suggestions.provenance.generated_at,
                ),
            )

    def latest_suggestion_set(
        self, requirement_id: RequirementId, question_id: str
    ) -> AnswerSuggestionSet | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT payload FROM clarification_answer_suggestion_sets
                WHERE requirement_id=%s AND question_id=%s
                ORDER BY generated_at DESC,suggestion_set_id DESC LIMIT 1
                """,
                (requirement_id.value, question_id),
            ).fetchone()
        return _suggestion_set_from_payload(_object(row[0])) if row is not None else None


def _chunk_payload(value: KnowledgeChunk) -> dict[str, object]:
    return {
        "source_lineage": TypeAdapter(tuple[SourceLineage, ...]).dump_python(
            value.source_lineage, mode="json"
        ),
        "id": value.id.value,
        "requirement_id": value.requirement_id.value,
        "requirement_version": value.requirement_version,
        "source_kind": value.source_kind.value,
        "field": value.field,
        "text": value.text,
        "fingerprint": value.fingerprint,
        "evidence_path": value.evidence_path,
        "owner": _actor_payload(value.owner) if value.owner else None,
    }


def _chunk_from_payload(data: dict[str, Any]) -> KnowledgeChunk:
    owner = data.get("owner")
    return KnowledgeChunk(
        KnowledgeChunkId(str(data["id"])),
        RequirementId(str(data["requirement_id"])),
        int(data["requirement_version"]),
        KnowledgeSourceKind(str(data["source_kind"])),
        str(data["field"]),
        str(data["text"]),
        str(data["fingerprint"]),
        str(data["evidence_path"]),
        _actor(_object(owner)) if owner is not None else None,
        TypeAdapter(tuple[SourceLineage, ...]).validate_python(data.get("source_lineage", [])),
    )


def _evidence_payload(value: RelationshipEvidence) -> dict[str, object]:
    return {
        "source_lineage": TypeAdapter(tuple[SourceLineage, ...]).dump_python(
            value.source_lineage, mode="json"
        ),
        "chunk_id": value.chunk_id.value,
        "requirement_id": value.requirement_id.value,
        "field": value.field,
        "excerpt": value.excerpt,
        "evidence_path": value.evidence_path,
        "fingerprint": value.fingerprint,
    }


def _evidence(data: dict[str, Any]) -> RelationshipEvidence:
    return RelationshipEvidence(
        KnowledgeChunkId(str(data["chunk_id"])),
        RequirementId(str(data["requirement_id"])),
        str(data["field"]),
        str(data["excerpt"]),
        str(data["evidence_path"]),
        str(data.get("fingerprint", data["chunk_id"])),
        TypeAdapter(tuple[SourceLineage, ...]).validate_python(data.get("source_lineage", [])),
    )


def _finding_payload(value: KnowledgeFinding) -> dict[str, object]:
    return {
        "id": value.id.value,
        "screen_id": value.screen_id.value,
        "subject_requirement_id": value.subject_requirement_id.value,
        "subject_version": value.subject_version,
        "related_requirement_id": value.related_requirement_id.value,
        "related_version": value.related_version,
        "kind": value.kind.value,
        "rationale": value.rationale,
        "evidence": [_evidence_payload(item) for item in value.evidence],
        "status": value.status.value,
        "version": value.version,
        "resolution_statement": value.resolution_statement,
        "resolution_approvals": [item.value for item in value.resolution_approvals],
        "decisions": [
            {
                "kind": item.kind.value,
                "actor": _actor_payload(item.actor),
                "recorded_at": item.recorded_at.isoformat(),
                "rationale": item.rationale,
            }
            for item in value.decisions
        ],
    }


def finding_from_payload(data: dict[str, Any]) -> KnowledgeFinding:
    return KnowledgeFinding(
        KnowledgeFindingId(str(data["id"])),
        KnowledgeScreenId(str(data["screen_id"])),
        RequirementId(str(data["subject_requirement_id"])),
        int(data["subject_version"]),
        RequirementId(str(data["related_requirement_id"])),
        int(data["related_version"]),
        KnowledgeRelationshipKind(str(data["kind"])),
        str(data["rationale"]),
        tuple(_evidence(_object(item)) for item in _list(data.get("evidence"))),
        KnowledgeFindingStatus(str(data.get("status", "open"))),
        int(data.get("version", 1)),
        str(data["resolution_statement"]) if data.get("resolution_statement") else None,
        tuple(ActorId(str(item)) for item in _list(data.get("resolution_approvals"))),
        tuple(
            KnowledgeDecision(
                KnowledgeDecisionKind(str(item["kind"])),
                _actor(_object(item["actor"])),
                datetime.fromisoformat(str(item["recorded_at"])),
                str(item["rationale"]) if item.get("rationale") else None,
            )
            for item in (_object(raw) for raw in _list(data.get("decisions")))
        ),
    )


def _screen_payload(value: KnowledgeScreen) -> dict[str, object]:
    return {
        "id": value.id.value,
        "requirement_id": value.requirement_id.value,
        "input_fingerprint": value.input_fingerprint,
        "subject_version": value.subject_version,
        "finding_ids": [item.value for item in value.finding_ids],
        "provenance": _provenance_payload(value.provenance),
    }


def _screen_from_payload(data: dict[str, Any]) -> KnowledgeScreen:
    return KnowledgeScreen(
        KnowledgeScreenId(str(data["id"])),
        RequirementId(str(data["requirement_id"])),
        str(data["input_fingerprint"]),
        int(data["subject_version"]),
        tuple(KnowledgeFindingId(str(item)) for item in _list(data.get("finding_ids"))),
        _provenance(_object(data["provenance"])),
    )


def _suggestion_set_payload(value: AnswerSuggestionSet) -> dict[str, object]:
    return {
        "id": value.id.value,
        "requirement_id": value.requirement_id.value,
        "question_id": value.question_id.value,
        "question_fingerprint": value.question_fingerprint,
        "suggestions": [
            {
                "id": item.id.value,
                "answer": item.answer,
                "rationale": item.rationale,
                "evidence": [_evidence_payload(evidence) for evidence in item.evidence],
                "reference_evidence": [asdict(c) for c in item.reference_evidence],
            }
            for item in value.suggestions
        ],
        "provenance": _provenance_payload(value.provenance),
    }


def _suggestion_set_from_payload(data: dict[str, Any]) -> AnswerSuggestionSet:
    return AnswerSuggestionSet(
        AnswerSuggestionSetId(str(data["id"])),
        RequirementId(str(data["requirement_id"])),
        QuestionId(str(data["question_id"])),
        str(data["question_fingerprint"]),
        tuple(
            AnswerSuggestion(
                AnswerSuggestionId(str(item["id"])),
                str(item["answer"]),
                str(item["rationale"]),
                tuple(_evidence(_object(raw)) for raw in _list(item.get("evidence"))),
                TypeAdapter(tuple[PublishedReference, ...]).validate_python(
                    item.get("reference_evidence", [])
                ),
            )
            for item in (_object(raw) for raw in _list(data.get("suggestions")))
        ),
        _provenance(_object(data["provenance"])),
    )


def _actor_payload(value: ActorSnapshot) -> dict[str, object]:
    return {"id": value.id.value, "display_name": value.display_name, "email": value.email}


def _actor(data: dict[str, Any]) -> ActorSnapshot:
    return ActorSnapshot(
        ActorId(str(data["id"])),
        str(data["display_name"]),
        str(data["email"]) if data.get("email") else None,
    )


def _provenance_payload(value: Provenance) -> dict[str, object]:
    return {
        "generated_at": value.generated_at.isoformat(),
        "model": value.model,
        "prompt_version": value.prompt_version,
    }


def _provenance(data: dict[str, Any]) -> Provenance:
    return Provenance(
        datetime.fromisoformat(str(data["generated_at"])),
        str(data["model"]),
        str(data["prompt_version"]),
    )


def _vector(value: Embedding) -> str:
    if len(value) != 768:
        raise ValueError(f"Knowledge embeddings must contain 768 values; received {len(value)}.")
    return "[" + ",".join(str(float(item)) for item in value) + "]"


def _object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError("Stored knowledge payload must be an object.")
    return cast(dict[str, Any], value)


def _list(value: object) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise TypeError("Stored knowledge payload member must be a list.")
    return value
