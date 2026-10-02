CREATE TABLE IF NOT EXISTS analysis_rounds (
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    analysis_id text NOT NULL UNIQUE,
    round_number integer NOT NULL CHECK (round_number > 0),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (requirement_id, round_number)
);

CREATE TABLE IF NOT EXISTS analysis_questions (
    question_id text PRIMARY KEY,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    first_analysis_id text NOT NULL REFERENCES analysis_rounds(analysis_id) ON DELETE RESTRICT,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS analysis_questions_requirement_idx
    ON analysis_questions (requirement_id, created_at, question_id);

-- Existing current analyses predate identity/provenance. Give them a stable,
-- explicitly legacy round and question identities without inventing provider data.
UPDATE requirement_analyses a
SET payload = a.payload || jsonb_build_object(
    'analysis_id', 'legacy-' || md5(a.requirement_id || a.payload::text),
    'round_number', 1,
    'provenance', NULL,
    'source_requirement_version', COALESCE((r.payload->>'version')::integer, 1)
)
FROM requirements r
WHERE r.requirement_id = a.requirement_id
  AND a.payload->>'analysis_id' IS NULL;

INSERT INTO analysis_rounds (requirement_id, analysis_id, round_number, payload)
SELECT
    a.requirement_id,
    a.payload->>'analysis_id',
    1,
    jsonb_build_object('analysis', a.payload, 'question_ids', '[]'::jsonb)
FROM requirement_analyses a
WHERE NOT EXISTS (
    SELECT 1 FROM analysis_rounds ar WHERE ar.requirement_id = a.requirement_id
);

WITH uncertainty AS (
    SELECT a.requirement_id, a.payload->>'analysis_id' AS analysis_id,
           'assumption' AS kind, value AS subject, NULL::text AS rationale
    FROM requirement_analyses a,
         LATERAL jsonb_array_elements_text(a.payload->'assumptions') value
    UNION ALL
    SELECT a.requirement_id, a.payload->>'analysis_id', 'open_question',
           value->>'question', value->>'rationale'
    FROM requirement_analyses a,
         LATERAL jsonb_array_elements(a.payload->'open_questions') value
    UNION ALL
    SELECT a.requirement_id, a.payload->>'analysis_id', 'ambiguity',
           value->>'statement', value->>'reason'
    FROM requirement_analyses a,
         LATERAL jsonb_array_elements(a.payload->'ambiguities') value
    UNION ALL
    SELECT a.requirement_id, a.payload->>'analysis_id', 'potential_dependency',
           value, NULL::text
    FROM requirement_analyses a,
         LATERAL jsonb_array_elements_text(a.payload->'potential_dependencies') value
), legacy_questions AS (
    SELECT *, 'legacy-question-' || md5(requirement_id || kind || lower(trim(subject))) AS question_id
    FROM uncertainty
)
INSERT INTO analysis_questions
    (question_id, requirement_id, first_analysis_id, payload)
SELECT question_id, requirement_id, analysis_id,
    jsonb_build_object(
        'id', question_id,
        'requirement_id', requirement_id,
        'first_analysis_id', analysis_id,
        'kind', kind,
        'subject', subject,
        'rationale', rationale,
        'severity', 'medium',
        'is_blocker', true,
        'source', 'ai',
        'status', 'open',
        'version', 1,
        'asked_by', NULL,
        'asked_at', NULL,
        'assignee', NULL,
        'assignment_history', '[]'::jsonb,
        'draft_answer', NULL,
        'draft_updated_by', NULL,
        'draft_updated_at', NULL,
        'answer', NULL,
        'answered_by', NULL,
        'answered_at', NULL,
        'classification_changed_by', NULL,
        'classification_changed_at', NULL
    )
FROM legacy_questions
ON CONFLICT (question_id) DO NOTHING;

UPDATE analysis_rounds ar
SET payload = jsonb_set(
    ar.payload,
    '{question_ids}',
    COALESCE(
        (
            SELECT jsonb_agg(q.question_id ORDER BY q.created_at, q.question_id)
            FROM analysis_questions q
            WHERE q.requirement_id = ar.requirement_id
              AND q.first_analysis_id = ar.analysis_id
        ),
        '[]'::jsonb
    )
)
WHERE ar.analysis_id LIKE 'legacy-%';

DROP TRIGGER IF EXISTS analysis_rounds_immutable ON analysis_rounds;
CREATE TRIGGER analysis_rounds_immutable
BEFORE UPDATE OR DELETE ON analysis_rounds
FOR EACH ROW EXECUTE FUNCTION reject_revision_mutation();

CREATE OR REPLACE FUNCTION reject_terminal_question_mutation() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'clarification question audit records are immutable';
    END IF;
    IF OLD.payload->>'status' IN ('resolved', 'superseded') THEN
        RAISE EXCEPTION 'terminal clarification questions are immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS analysis_questions_terminal_immutable ON analysis_questions;
CREATE TRIGGER analysis_questions_terminal_immutable
BEFORE UPDATE OR DELETE ON analysis_questions
FOR EACH ROW EXECUTE FUNCTION reject_terminal_question_mutation();
