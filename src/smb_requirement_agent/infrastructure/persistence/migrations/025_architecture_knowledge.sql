CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE architecture_knowledge_releases (
    release_id text PRIMARY KEY,
    revision integer NOT NULL,
    payload jsonb NOT NULL,
    active boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX architecture_one_active_release
    ON architecture_knowledge_releases (active) WHERE active;

CREATE TABLE architecture_knowledge_chunks (
    release_id text NOT NULL REFERENCES architecture_knowledge_releases(release_id),
    chunk_id text NOT NULL,
    document_version_id text,
    source_label text NOT NULL,
    location text NOT NULL,
    content text NOT NULL,
    search_text tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    embedding vector(1024) NOT NULL,
    PRIMARY KEY (release_id, chunk_id)
);
CREATE INDEX architecture_chunks_search_idx ON architecture_knowledge_chunks USING gin(search_text);

CREATE TABLE architecture_jobs (
    job_id text PRIMARY KEY,
    kind text NOT NULL,
    subject_id text NOT NULL,
    fingerprint text NOT NULL,
    actor_id text NOT NULL,
    status text NOT NULL,
    attempts integer NOT NULL DEFAULT 0,
    lease_until timestamptz,
    error_category text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (kind, subject_id, fingerprint)
);

CREATE TABLE architecture_knowledge_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    release_id text NOT NULL,
    actor_id text NOT NULL,
    action text NOT NULL,
    revision integer NOT NULL,
    rationale text,
    created_at timestamptz NOT NULL DEFAULT now()
);
