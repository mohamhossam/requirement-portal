"""Aggregate-owned PostgreSQL SQL over the shared unit of work."""

from __future__ import annotations

from psycopg.errors import RaiseException, UniqueViolation
from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
    DuplicateRequirementError,
    PersistenceError,
    RequirementAnalysisConflictError,
    RequirementVersionConflictError,
)
from smb_requirement_agent.application.ports.requirement_draft_repository import (
    RequirementDraftRepositoryPort,
)
from smb_requirement_agent.application.ports.requirement_repository import (
    RequirementRepositoryPort,
)
from smb_requirement_agent.domain.analysis.entities import (
    AnalysisRound,
    ClarificationQuestion,
    RequirementAnalysis,
)
from smb_requirement_agent.domain.analysis.errors import (
    ClarificationVersionConflictError,
    InvalidClarificationTransitionError,
)
from smb_requirement_agent.domain.analysis.value_objects import AnalysisId, QuestionId
from smb_requirement_agent.domain.epic.entities import Epic
from smb_requirement_agent.domain.epic.value_objects import EpicId
from smb_requirement_agent.domain.feature.entities import Feature
from smb_requirement_agent.domain.feature.value_objects import FeatureId
from smb_requirement_agent.domain.requirement.entities import Requirement, RequirementDraft
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.story.entities import StoryChangeProposal, UserStory
from smb_requirement_agent.domain.story.value_objects import StoryId, StoryProposalId
from smb_requirement_agent.identity.domain.entities import (
    DraftOwnership,
    RequirementAccess,
)
from smb_requirement_agent.identity.domain.errors import RequirementAccessConflictError
from smb_requirement_agent.identity.infrastructure.identity_payloads import (
    access_from_payload,
    access_to_payload,
    draft_ownership_from_payload,
    draft_ownership_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.analysis_payloads import (
    analysis_from_payload,
    analysis_round_from_payload,
    analysis_round_to_payload,
    analysis_to_payload,
    clarification_question_from_payload,
    clarification_question_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.backlog_payloads import (
    epic_from_payload,
    epic_to_payload,
    feature_from_payload,
    feature_to_payload,
    story_from_payload,
    story_proposal_from_payload,
    story_proposal_to_payload,
    story_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.postgres_session import PostgresSession
from smb_requirement_agent.infrastructure.persistence.postgres_values import (
    _integer,
    _payload,
    requirement_id_for_epic,
    requirement_id_for_feature,
)
from smb_requirement_agent.infrastructure.persistence.requirement_snapshot import (
    requirement_draft_from_payload,
    requirement_draft_to_payload,
    requirement_from_payload,
    requirement_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.review_payloads import (
    review_from_payload,
    review_to_payload,
)
from smb_requirement_agent.infrastructure.persistence.shared_payloads import (
    actor_from_payload,
    actor_to_payload,
)
from smb_requirement_agent.shared_kernel.actors import (
    ActorId,
    ActorProfile,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


class PostgresRequirementRepository(RequirementRepositoryPort):
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def add(self, requirement: Requirement) -> None:
        with self._store.connection() as connection:
            try:
                connection.execute(
                    "INSERT INTO requirements (requirement_id, payload) VALUES (%s, %s)",
                    (requirement.id.value, Jsonb(requirement_to_payload(requirement))),
                )
            except UniqueViolation as exc:
                raise DuplicateRequirementError(
                    f"Requirement {requirement.id.value!r} already exists."
                ) from exc
            self._store.mark_requirement_dirty(requirement.id)

    def get(self, requirement_id: RequirementId) -> Requirement | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirements WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return requirement_from_payload(_payload(row[0])) if row is not None else None

    def list_all(self) -> list[Requirement]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM requirements ORDER BY updated_at DESC"
            ).fetchall()
        return [requirement_from_payload(_payload(row[0])) for row in rows]

    def save(self, requirement: Requirement) -> None:
        with self._store.connection() as connection:
            if requirement.version.value > 1:
                cursor = connection.execute(
                    """
                    UPDATE requirements SET payload = %s, updated_at = now()
                    WHERE requirement_id = %s
                    AND COALESCE((payload->>'version')::integer, 1) = %s
                    """,
                    (
                        Jsonb(requirement_to_payload(requirement)),
                        requirement.id.value,
                        requirement.version.value - 1,
                    ),
                )
                if cursor.rowcount != 1:
                    raise RequirementVersionConflictError(
                        f"Requirement {requirement.id.value!r} changed before it could be saved."
                    )
            else:
                connection.execute(
                    """
                    UPDATE requirements SET payload = %s, updated_at = now()
                    WHERE requirement_id = %s
                    """,
                    (Jsonb(requirement_to_payload(requirement)), requirement.id.value),
                )
            self._store.mark_requirement_dirty(requirement.id)


class PostgresRequirementDraftRepository(RequirementDraftRepositoryPort):
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def add(self, draft: RequirementDraft) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "INSERT INTO requirement_drafts (draft_id, payload) VALUES (%s, %s)",
                (draft.id.value, Jsonb(requirement_draft_to_payload(draft))),
            )

    def get(self, draft_id: RequirementId) -> RequirementDraft | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_drafts WHERE draft_id = %s",
                (draft_id.value,),
            ).fetchone()
        return requirement_draft_from_payload(_payload(row[0])) if row is not None else None

    def list_all(self) -> list[RequirementDraft]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM requirement_drafts ORDER BY updated_at DESC"
            ).fetchall()
        return [requirement_draft_from_payload(_payload(row[0])) for row in rows]

    def save(self, draft: RequirementDraft) -> None:
        with self._store.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE requirement_drafts SET payload = %s, updated_at = now()
                WHERE draft_id = %s AND (payload->>'version')::integer = %s
                """,
                (
                    Jsonb(requirement_draft_to_payload(draft)),
                    draft.id.value,
                    draft.version.value - 1,
                ),
            )
            if cursor.rowcount != 1:
                raise RequirementVersionConflictError(
                    f"Requirement draft {draft.id.value!r} changed before it could be saved."
                )

    def delete(self, draft_id: RequirementId) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM requirement_drafts WHERE draft_id = %s", (draft_id.value,)
            )


class PostgresAccessRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def get_requirement(self, requirement_id: RequirementId) -> RequirementAccess | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_access WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return access_from_payload(_payload(row[0])) if row is not None else None

    def save_requirement(self, access: RequirementAccess) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "SELECT requirement_id FROM requirements WHERE requirement_id = %s FOR UPDATE",
                (access.requirement_id.value,),
            )
            row = connection.execute(
                "SELECT payload FROM requirement_access WHERE requirement_id = %s",
                (access.requirement_id.value,),
            ).fetchone()
            if row is not None:
                current = access_from_payload(_payload(row[0]))
                if (
                    access.version != current.version + 1
                    or access.changes[: len(current.changes)] != current.changes
                ):
                    raise RequirementAccessConflictError(
                        "Requirement access changed before this operation completed."
                    )
            connection.execute(
                """
                INSERT INTO requirement_access (requirement_id, payload) VALUES (%s, %s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
                """,
                (access.requirement_id.value, Jsonb(access_to_payload(access))),
            )
            self._store.mark_requirement_dirty(access.requirement_id)

    def get_draft_ownership(self, draft_id: RequirementId) -> DraftOwnership | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM draft_ownership WHERE draft_id = %s", (draft_id.value,)
            ).fetchone()
        return draft_ownership_from_payload(_payload(row[0])) if row is not None else None

    def save_draft_ownership(self, ownership: DraftOwnership) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "SELECT draft_id FROM requirement_drafts WHERE draft_id = %s FOR UPDATE",
                (ownership.draft_id.value,),
            )
            row = connection.execute(
                "SELECT payload FROM draft_ownership WHERE draft_id = %s",
                (ownership.draft_id.value,),
            ).fetchone()
            if row is not None:
                current = draft_ownership_from_payload(_payload(row[0]))
                if current.owner != ownership.owner:
                    raise RequirementAccessConflictError(
                        "Draft ownership changed before this operation completed."
                    )
            connection.execute(
                """
                INSERT INTO draft_ownership (draft_id, payload) VALUES (%s, %s)
                ON CONFLICT (draft_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
                """,
                (ownership.draft_id.value, Jsonb(draft_ownership_to_payload(ownership))),
            )

    def delete_draft_ownership(self, draft_id: RequirementId) -> None:
        with self._store.connection() as connection:
            connection.execute("DELETE FROM draft_ownership WHERE draft_id = %s", (draft_id.value,))


class PostgresAnalysisRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def save(self, analysis: RequirementAnalysis) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """
                INSERT INTO requirement_analyses (requirement_id, payload)
                VALUES (%s, %s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
                WHERE (requirement_analyses.payload->>'version')::integer =
                          (EXCLUDED.payload->>'version')::integer - 1
                   OR requirement_analyses.payload = EXCLUDED.payload
                """,
                (analysis.requirement_id.value, Jsonb(analysis_to_payload(analysis))),
            )
            if result.rowcount == 0:
                raise RequirementAnalysisConflictError(
                    "Analysis changed before this mutation could be saved. Reload it."
                )
            self._store.mark_requirement_dirty(analysis.requirement_id)

    def get_by_requirement_id(self, requirement_id: RequirementId) -> RequirementAnalysis | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM requirement_analyses WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return analysis_from_payload(_payload(row[0])) if row is not None else None

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM requirement_analyses WHERE requirement_id = %s",
                (requirement_id.value,),
            )
            self._store.mark_requirement_dirty(requirement_id)


class PostgresAnalysisAuditRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def append_round(self, round_: AnalysisRound) -> None:
        with self._store.connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO analysis_rounds
                        (requirement_id, analysis_id, round_number, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        round_.requirement_id.value,
                        round_.id.value,
                        round_.number,
                        Jsonb(analysis_round_to_payload(round_)),
                    ),
                )
            except UniqueViolation as exc:
                raise PersistenceError("Analysis round identity or number already exists.") from exc
            self._store.mark_requirement_dirty(round_.requirement_id)

    def list_rounds(self, requirement_id: RequirementId) -> list[AnalysisRound]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM analysis_rounds
                WHERE requirement_id = %s ORDER BY round_number
                """,
                (requirement_id.value,),
            ).fetchall()
        return [analysis_round_from_payload(_payload(row[0])) for row in rows]

    def get_round(
        self, requirement_id: RequirementId, analysis_id: AnalysisId
    ) -> AnalysisRound | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT payload FROM analysis_rounds
                WHERE requirement_id = %s AND analysis_id = %s
                """,
                (requirement_id.value, analysis_id.value),
            ).fetchone()
        return analysis_round_from_payload(_payload(row[0])) if row is not None else None

    def add_question(self, question: ClarificationQuestion) -> None:
        with self._store.connection() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO analysis_questions
                        (question_id, requirement_id, first_analysis_id, payload)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        question.id.value,
                        question.requirement_id.value,
                        question.first_analysis_id.value,
                        Jsonb(clarification_question_to_payload(question)),
                    ),
                )
            except UniqueViolation as exc:
                raise PersistenceError(f"Question {question.id.value!r} already exists.") from exc
            self._store.mark_requirement_dirty(question.requirement_id)

    def save_question(self, question: ClarificationQuestion) -> None:
        try:
            with self._store.connection() as connection:
                cursor = connection.execute(
                    """
                    UPDATE analysis_questions SET payload = %s, updated_at = now()
                    WHERE question_id = %s AND requirement_id = %s
                      AND (payload->>'version')::integer = %s
                    """,
                    (
                        Jsonb(clarification_question_to_payload(question)),
                        question.id.value,
                        question.requirement_id.value,
                        question.version - 1,
                    ),
                )
                if cursor.rowcount != 1:
                    raise ClarificationVersionConflictError(
                        "Question changed since it was loaded. Refresh and try again."
                    )
                self._store.mark_requirement_dirty(question.requirement_id)
        except RaiseException as exc:
            raise InvalidClarificationTransitionError(
                "Resolved or superseded questions cannot be changed."
            ) from exc

    def get_question(
        self, requirement_id: RequirementId, question_id: QuestionId
    ) -> ClarificationQuestion | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT payload FROM analysis_questions
                WHERE requirement_id = %s AND question_id = %s
                """,
                (requirement_id.value, question_id.value),
            ).fetchone()
        return clarification_question_from_payload(_payload(row[0])) if row is not None else None

    def list_questions(self, requirement_id: RequirementId) -> list[ClarificationQuestion]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM analysis_questions
                WHERE requirement_id = %s ORDER BY created_at, question_id
                """,
                (requirement_id.value,),
            ).fetchall()
        return [clarification_question_from_payload(_payload(row[0])) for row in rows]


class PostgresEpicRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def save(self, epic: Epic) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """
                INSERT INTO epics (requirement_id, epic_id, payload)
                VALUES (%s, %s, %s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET epic_id = EXCLUDED.epic_id, payload = EXCLUDED.payload, updated_at = now()
                WHERE (epics.payload->>'version')::integer =
                          (EXCLUDED.payload->>'version')::integer - 1
                   OR epics.payload = EXCLUDED.payload
                """,
                (epic.requirement_id.value, epic.id.value, Jsonb(epic_to_payload(epic))),
            )
            if result.rowcount != 1:
                raise ArtifactVersionConflictError(
                    "The Epic changed before this mutation could be saved. Reload it."
                )
            self._store.mark_requirement_dirty(epic.requirement_id)

    def get_by_requirement_id(self, requirement_id: RequirementId) -> Epic | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM epics WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return epic_from_payload(_payload(row[0])) if row is not None else None

    def delete_by_requirement_id(self, requirement_id: RequirementId) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM epics WHERE requirement_id = %s", (requirement_id.value,)
            )
            self._store.mark_requirement_dirty(requirement_id)


class PostgresFeatureRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def set_version(self, epic_id: EpicId) -> int:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT version FROM feature_set_versions WHERE epic_id=%s",
                (epic_id.value,),
            ).fetchone()
        return _integer(row[0]) if row is not None else 1

    def replace_for_epic(
        self, epic_id: EpicId, features: list[Feature], expected_set_version: int
    ) -> int:
        with self._store.connection() as connection:
            requirement_id = requirement_id_for_epic(epic_id, connection)
            connection.execute(
                "INSERT INTO feature_set_versions(epic_id, version) VALUES (%s, 1) "
                "ON CONFLICT (epic_id) DO NOTHING",
                (epic_id.value,),
            )
            changed = connection.execute(
                "UPDATE feature_set_versions SET version=version+1 WHERE epic_id=%s AND version=%s",
                (epic_id.value, expected_set_version),
            )
            if changed.rowcount != 1:
                raise ArtifactVersionConflictError(
                    "The Feature set changed while this operation was in progress. Reload it."
                )
            # Retained rows must not collide with an inserted or reordered item's position.
            # Move them above both ranges within the same version-guarded transaction.
            connection.execute(
                "UPDATE features SET position=position + "
                "(SELECT COALESCE(MAX(position), 0) + %s + 1 FROM features WHERE epic_id=%s) "
                "WHERE epic_id=%s",
                (len(features), epic_id.value, epic_id.value),
            )
            for position, feature in enumerate(features):
                connection.execute(
                    """
                    INSERT INTO features (epic_id, feature_id, position, payload)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (epic_id, feature_id) DO UPDATE SET
                        position=EXCLUDED.position, payload=EXCLUDED.payload, updated_at=now()
                    """,
                    (
                        epic_id.value,
                        feature.id.value,
                        position,
                        Jsonb(feature_to_payload(feature)),
                    ),
                )
            retained_ids = [feature.id.value for feature in features]
            if retained_ids:
                connection.execute(
                    "DELETE FROM features WHERE epic_id=%s AND NOT (feature_id=ANY(%s))",
                    (epic_id.value, retained_ids),
                )
            else:
                connection.execute("DELETE FROM features WHERE epic_id=%s", (epic_id.value,))
            if requirement_id is not None:
                self._store.mark_requirement_dirty(requirement_id)
            return expected_set_version + 1

    def get_by_epic_id(self, epic_id: EpicId) -> list[Feature]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM features WHERE epic_id = %s ORDER BY position",
                (epic_id.value,),
            ).fetchall()
        return [feature_from_payload(_payload(row[0])) for row in rows]

    def get(self, epic_id: EpicId, feature_id: FeatureId) -> Feature | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM features WHERE epic_id = %s AND feature_id = %s",
                (epic_id.value, feature_id.value),
            ).fetchone()
        return feature_from_payload(_payload(row[0])) if row is not None else None

    def save(self, feature: Feature) -> None:
        with self._store.connection() as connection:
            payload = Jsonb(feature_to_payload(feature))
            result = connection.execute(
                """
                UPDATE features SET payload = %s, updated_at = now()
                WHERE epic_id = %s AND feature_id = %s
                  AND ((payload->>'version')::integer = %s OR payload = %s)
                """,
                (
                    payload,
                    feature.epic_id.value,
                    feature.id.value,
                    feature.version - 1,
                    payload,
                ),
            )
            if result.rowcount != 1:
                raise ArtifactVersionConflictError(
                    "The Feature changed before this mutation could be saved. Reload it."
                )
            requirement_id = requirement_id_for_epic(feature.epic_id, connection)
            if requirement_id is not None:
                self._store.mark_requirement_dirty(requirement_id)

    def delete_by_epic_id(self, epic_id: EpicId) -> None:
        with self._store.connection() as connection:
            requirement_id = requirement_id_for_epic(epic_id, connection)
            connection.execute("DELETE FROM features WHERE epic_id = %s", (epic_id.value,))
            if requirement_id is not None:
                self._store.mark_requirement_dirty(requirement_id)


class PostgresStoryRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def set_version(self, feature_id: FeatureId) -> int:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT version FROM story_set_versions WHERE feature_id=%s",
                (feature_id.value,),
            ).fetchone()
        return _integer(row[0]) if row is not None else 1

    def replace_for_feature(
        self, feature_id: FeatureId, stories: list[UserStory], expected_set_version: int
    ) -> int:
        with self._store.connection() as connection:
            requirement_id = requirement_id_for_feature(feature_id, connection)
            connection.execute(
                "INSERT INTO story_set_versions(feature_id, version) VALUES (%s, 1) "
                "ON CONFLICT (feature_id) DO NOTHING",
                (feature_id.value,),
            )
            changed = connection.execute(
                "UPDATE story_set_versions SET version=version+1 "
                "WHERE feature_id=%s AND version=%s",
                (feature_id.value, expected_set_version),
            )
            if changed.rowcount != 1:
                raise ArtifactVersionConflictError(
                    "The Story set changed while this operation was in progress. Reload it."
                )
            # Free final positions without deleting retained Stories or their references.
            connection.execute(
                "UPDATE stories SET position=position + "
                "(SELECT COALESCE(MAX(position), 0) + %s + 1 FROM stories WHERE feature_id=%s) "
                "WHERE feature_id=%s",
                (len(stories), feature_id.value, feature_id.value),
            )
            for position, story in enumerate(stories):
                connection.execute(
                    """
                    INSERT INTO stories (feature_id, story_id, position, payload)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (feature_id, story_id) DO UPDATE SET
                        position=EXCLUDED.position, payload=EXCLUDED.payload, updated_at=now()
                    """,
                    (feature_id.value, story.id.value, position, Jsonb(story_to_payload(story))),
                )
            retained_ids = [story.id.value for story in stories]
            if retained_ids:
                connection.execute(
                    "DELETE FROM stories WHERE feature_id=%s AND NOT (story_id=ANY(%s))",
                    (feature_id.value, retained_ids),
                )
            else:
                connection.execute("DELETE FROM stories WHERE feature_id=%s", (feature_id.value,))
            if requirement_id is not None:
                self._store.mark_requirement_dirty(requirement_id)
            return expected_set_version + 1

    def get_by_feature_id(self, feature_id: FeatureId) -> list[UserStory]:
        with self._store.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM stories WHERE feature_id = %s ORDER BY position",
                (feature_id.value,),
            ).fetchall()
        return [story_from_payload(_payload(row[0])) for row in rows]

    def get(self, feature_id: FeatureId, story_id: StoryId) -> UserStory | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM stories WHERE feature_id = %s AND story_id = %s",
                (feature_id.value, story_id.value),
            ).fetchone()
        return story_from_payload(_payload(row[0])) if row is not None else None

    def save(self, story: UserStory) -> None:
        with self._store.connection() as connection:
            payload = Jsonb(story_to_payload(story))
            result = connection.execute(
                """
                UPDATE stories SET payload = %s, updated_at = now()
                WHERE feature_id = %s AND story_id = %s
                  AND ((payload->>'version')::integer = %s OR payload = %s)
                """,
                (
                    payload,
                    story.feature_id.value,
                    story.id.value,
                    story.version - 1,
                    payload,
                ),
            )
            if result.rowcount != 1:
                raise ArtifactVersionConflictError(
                    "The Story changed before this mutation could be saved. Reload it."
                )
            requirement_id = requirement_id_for_feature(story.feature_id, connection)
            if requirement_id is not None:
                self._store.mark_requirement_dirty(requirement_id)


class PostgresStoryChangeProposalRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def save(self, proposal: StoryChangeProposal) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """
                INSERT INTO story_change_proposals (feature_id, proposal_id, payload)
                VALUES (%s, %s, %s)
                ON CONFLICT (feature_id, proposal_id) DO UPDATE SET payload = EXCLUDED.payload
                WHERE (story_change_proposals.payload->>'version')::integer =
                          (EXCLUDED.payload->>'version')::integer - 1
                   OR story_change_proposals.payload = EXCLUDED.payload
                """,
                (
                    proposal.feature_id.value,
                    proposal.id.value,
                    Jsonb(story_proposal_to_payload(proposal)),
                ),
            )
            if result.rowcount != 1:
                raise ArtifactVersionConflictError(
                    "The Story proposal changed before this mutation could be saved. Reload it."
                )
            requirement_id = requirement_id_for_feature(proposal.feature_id, connection)
            if requirement_id is not None:
                self._store.mark_requirement_dirty(requirement_id)

    def get(
        self, feature_id: FeatureId, proposal_id: StoryProposalId
    ) -> StoryChangeProposal | None:
        with self._store.connection() as connection:
            row = connection.execute(
                """
                SELECT payload FROM story_change_proposals
                WHERE feature_id = %s AND proposal_id = %s
                """,
                (feature_id.value, proposal_id.value),
            ).fetchone()
        return story_proposal_from_payload(_payload(row[0])) if row is not None else None

    def list_for_feature(self, feature_id: FeatureId) -> list[StoryChangeProposal]:
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM story_change_proposals
                WHERE feature_id = %s ORDER BY created_at, proposal_id
                """,
                (feature_id.value,),
            ).fetchall()
        return [story_proposal_from_payload(_payload(row[0])) for row in rows]

    def delete(self, feature_id: FeatureId, proposal_id: StoryProposalId) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                DELETE FROM story_change_proposals
                WHERE feature_id = %s AND proposal_id = %s
                """,
                (feature_id.value, proposal_id.value),
            )
            requirement_id = requirement_id_for_feature(feature_id, connection)
            if requirement_id is not None:
                self._store.mark_requirement_dirty(requirement_id)

    def delete_for_feature(self, feature_id: FeatureId) -> None:
        with self._store.connection() as connection:
            connection.execute(
                "DELETE FROM story_change_proposals WHERE feature_id = %s",
                (feature_id.value,),
            )
            requirement_id = requirement_id_for_feature(feature_id, connection)
            if requirement_id is not None:
                self._store.mark_requirement_dirty(requirement_id)


class PostgresBreakdownReviewRepository:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def save(self, review: BreakdownReview) -> None:
        with self._store.connection() as connection:
            result = connection.execute(
                """
                INSERT INTO breakdown_reviews (requirement_id, payload)
                VALUES (%s, %s)
                ON CONFLICT (requirement_id) DO UPDATE
                SET payload = EXCLUDED.payload, updated_at = now()
                WHERE (breakdown_reviews.payload->>'version')::integer =
                          (EXCLUDED.payload->>'version')::integer - 1
                   OR breakdown_reviews.payload = EXCLUDED.payload
                """,
                (review.requirement_id.value, Jsonb(review_to_payload(review))),
            )
            if result.rowcount == 0:
                raise ArtifactVersionConflictError(
                    "Breakdown review changed before this mutation could be saved. Reload it."
                )
            self._store.mark_requirement_dirty(review.requirement_id)

    def get(self, requirement_id: RequirementId) -> BreakdownReview | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM breakdown_reviews WHERE requirement_id = %s",
                (requirement_id.value,),
            ).fetchone()
        return review_from_payload(_payload(row[0])) if row is not None else None


class PostgresActorDirectory:
    def __init__(self, store: PostgresSession) -> None:
        self._store = store

    def record(self, actor: ActorProfile) -> None:
        with self._store.connection() as connection:
            connection.execute(
                """
                INSERT INTO actor_profiles (actor_id, payload) VALUES (%s, %s)
                ON CONFLICT (actor_id) DO UPDATE
                SET payload = EXCLUDED.payload, last_seen_at = now()
                """,
                (actor.id.value, Jsonb(actor_to_payload(actor))),
            )

    def get(self, actor_id: ActorId) -> ActorProfile | None:
        with self._store.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM actor_profiles WHERE actor_id = %s", (actor_id.value,)
            ).fetchone()
        return actor_from_payload(_payload(row[0])) if row is not None else None

    def search(self, query: str | None, limit: int) -> list[ActorProfile]:
        needle = f"%{(query or '').strip()}%"
        with self._store.connection() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM actor_profiles
                WHERE %s = '%%' OR payload->>'display_name' ILIKE %s
                    OR COALESCE(payload->>'email', '') ILIKE %s
                ORDER BY lower(payload->>'display_name') LIMIT %s
                """,
                (needle, needle, needle, limit),
            ).fetchall()
        return [actor_from_payload(_payload(row[0])) for row in rows]
