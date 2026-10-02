CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS origin text NOT NULL DEFAULT 'user';

CREATE TABLE IF NOT EXISTS requirement_knowledge_index (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    corpus_fingerprint text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS requirement_knowledge_chunks (
    chunk_id text PRIMARY KEY,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    embedding vector(768) NOT NULL,
    search_document tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', coalesce(payload->>'text', ''))) STORED
);

CREATE INDEX IF NOT EXISTS requirement_knowledge_chunks_requirement_idx
    ON requirement_knowledge_chunks (requirement_id);
CREATE INDEX IF NOT EXISTS requirement_knowledge_chunks_text_idx
    ON requirement_knowledge_chunks USING gin (search_document);
CREATE INDEX IF NOT EXISTS requirement_knowledge_chunks_embedding_idx
    ON requirement_knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS requirement_knowledge_screens (
    screen_id text PRIMARY KEY,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    input_fingerprint text NOT NULL,
    payload jsonb NOT NULL,
    generated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS requirement_knowledge_screens_current_idx
    ON requirement_knowledge_screens (requirement_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS requirement_knowledge_findings (
    finding_id text PRIMARY KEY,
    screen_id text NOT NULL REFERENCES requirement_knowledge_screens(screen_id) ON DELETE RESTRICT,
    subject_requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE RESTRICT,
    related_requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (subject_requirement_id <> related_requirement_id)
);
CREATE INDEX IF NOT EXISTS requirement_knowledge_findings_subject_idx
    ON requirement_knowledge_findings (subject_requirement_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS requirement_knowledge_findings_related_idx
    ON requirement_knowledge_findings (related_requirement_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS requirement_knowledge_finding_revisions (
    finding_id text NOT NULL REFERENCES requirement_knowledge_findings(finding_id) ON DELETE RESTRICT,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (finding_id, version)
);

CREATE OR REPLACE FUNCTION reject_knowledge_revision_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'requirement knowledge finding revisions are immutable';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS requirement_knowledge_revision_immutable
    ON requirement_knowledge_finding_revisions;
CREATE TRIGGER requirement_knowledge_revision_immutable
BEFORE UPDATE OR DELETE ON requirement_knowledge_finding_revisions
FOR EACH ROW EXECUTE FUNCTION reject_knowledge_revision_mutation();

CREATE TABLE IF NOT EXISTS clarification_answer_suggestion_sets (
    suggestion_set_id text PRIMARY KEY,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    question_id text NOT NULL,
    payload jsonb NOT NULL,
    generated_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS clarification_answer_suggestions_current_idx
    ON clarification_answer_suggestion_sets
        (requirement_id, question_id, generated_at DESC);
