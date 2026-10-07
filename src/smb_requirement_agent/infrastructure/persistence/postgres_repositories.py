"""Aggregate-owned PostgreSQL SQL over the shared unit of work."""

from __future__ import annotations

from psycopg.errors import RaiseException, UniqueViolation
from psycopg.types.json import Jsonb

from smb_requirement_agent.application.errors import (
    ArtifactVersionConflictError,
    PersistenceError,
    RequirementAnalysisConflictError,
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
from smb_requirement_agent.domain.review.entities import BreakdownReview
from smb_requirement_agent.domain.story.entities import StoryChangeProposal, UserStory
from smb_requirement_agent.domain.story.value_objects import StoryId, StoryProposalId
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
from smb_requirement_agent.infrastructure.persistence.review_payloads import (
    review_from_payload,
    review_to_payload,
)
from smb_requirement_agent.shared_kernel.identifiers import RequirementId


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
