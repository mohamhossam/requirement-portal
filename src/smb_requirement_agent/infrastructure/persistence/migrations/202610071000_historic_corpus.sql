-- Knowledge Center E2 (ADR-0102): requirement work's copy of the historic requirements the
-- knowledge portal publishes, and the historic corpus built from their content. The corpus
-- is kept apart from the live one: nothing here keys on requirements, and nothing that
-- screens, suggests or answers for live work reads it.

-- One row per historic requirement: the newest event applied, and how far indexing has got.
CREATE TABLE historic_requirement_state (
    historic_requirement_id text PRIMARY KEY,
    seq bigint NOT NULL,
    payload jsonb NOT NULL,
    -- Read on every prior-art check, so kept beside the payload.
    published boolean NOT NULL,
    publication integer,
    title text NOT NULL DEFAULT '',
    -- The publication whose chunks are searchable, and for which embedding identity.
    indexed_seq bigint,
    indexed_identity text,
    failures integer NOT NULL DEFAULT 0,
    retry_at timestamptz,
    -- Reading the publication's content, a page at a time.
    stage_seq bigint,
    stage_identity text,
    stage_part text CHECK (stage_part IN ('passages', 'items')),
    stage_offset integer NOT NULL DEFAULT 0,
    chunks_built boolean NOT NULL DEFAULT false,
    -- Embedding spent on this record in the current hour.
    embed_window timestamptz,
    embedded integer NOT NULL DEFAULT 0
);

-- Raw content pages while a publication is being read; cleared once its chunks are cut.
CREATE TABLE historic_content_staging (
    historic_requirement_id text NOT NULL
        REFERENCES historic_requirement_state ON DELETE CASCADE,
    seq bigint NOT NULL,
    part text NOT NULL CHECK (part IN ('passages', 'items')),
    ordinal integer NOT NULL,
    entry jsonb NOT NULL,
    PRIMARY KEY (historic_requirement_id, seq, part, ordinal)
);

-- Advances each time a publication becomes searchable: prior art checked against an
-- older value is out of date.
CREATE SEQUENCE historic_corpus_version_seq;

-- A publication's chunks. Only those of the indexed publication and identity are searched;
-- a new publication's chunks are written beside them and take over in one update.
CREATE TABLE historic_knowledge_chunks (
    historic_requirement_id text NOT NULL
        REFERENCES historic_requirement_state ON DELETE CASCADE,
    seq bigint NOT NULL,
    embedding_identity text NOT NULL,
    chunk_id text NOT NULL,
    source_kind text NOT NULL CHECK (source_kind IN ('historic_brd', 'historic_backlog')),
    field text NOT NULL,
    text text NOT NULL,
    text_hash text NOT NULL,
    evidence jsonb NOT NULL,
    embedding vector(768),
    search_document tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED,
    PRIMARY KEY (historic_requirement_id, seq, embedding_identity, chunk_id)
);

CREATE INDEX historic_knowledge_chunks_hash
    ON historic_knowledge_chunks (embedding_identity, text_hash)
    WHERE embedding IS NOT NULL;
CREATE INDEX historic_knowledge_chunks_unembedded
    ON historic_knowledge_chunks (historic_requirement_id, seq, embedding_identity)
    WHERE embedding IS NULL;
CREATE INDEX historic_knowledge_chunks_search
    ON historic_knowledge_chunks USING gin (search_document);
CREATE INDEX historic_knowledge_chunks_embedding
    ON historic_knowledge_chunks USING hnsw (embedding vector_cosine_ops);
