-- Keep legacy knowledge tables intact. New embedding identities use isolated generations.
CREATE TABLE knowledge_index_generations (
    generation_id text PRIMARY KEY,
    embedding_identity text NOT NULL,
    status text NOT NULL CHECK (status IN ('staging','active','retired')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX knowledge_one_staging_identity
    ON knowledge_index_generations (embedding_identity) WHERE status='staging';
CREATE UNIQUE INDEX knowledge_one_active_generation
    ON knowledge_index_generations (status) WHERE status='active';
CREATE TABLE knowledge_generation_index (
    generation_id text NOT NULL REFERENCES knowledge_index_generations(generation_id),
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    corpus_fingerprint text NOT NULL,
    source_change bigint NOT NULL,
    PRIMARY KEY (generation_id, requirement_id)
);
CREATE TABLE knowledge_generation_chunks (
    generation_id text NOT NULL REFERENCES knowledge_index_generations(generation_id),
    chunk_id text NOT NULL,
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    embedding vector(768) NOT NULL,
    search_document tsvector GENERATED ALWAYS AS (
        to_tsvector('simple',coalesce(payload->>'text',''))
    ) STORED,
    PRIMARY KEY (generation_id,chunk_id)
);
CREATE INDEX knowledge_generation_chunks_source
    ON knowledge_generation_chunks (generation_id,requirement_id);
CREATE INDEX knowledge_generation_chunks_text
    ON knowledge_generation_chunks USING gin(search_document);
