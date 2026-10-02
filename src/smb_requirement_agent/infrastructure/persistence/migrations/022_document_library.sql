-- Original blobs use the existing immutable document_blobs table. No attachment is published.
CREATE TABLE library_documents (
    id text PRIMARY KEY,
    owner_id text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    published_id text,
    payload jsonb NOT NULL
);
CREATE INDEX library_documents_owner ON library_documents(owner_id, id);
CREATE INDEX library_documents_published ON library_documents(id) WHERE published_id IS NOT NULL;
CREATE TABLE library_submissions (
    owner_id text NOT NULL,
    submission_key text NOT NULL,
    document_id text NOT NULL REFERENCES library_documents(id),
    version_id text NOT NULL,
    PRIMARY KEY (owner_id, submission_key)
);
CREATE TABLE library_embedding_cache (
    identity text NOT NULL,
    content_hash text NOT NULL,
    embedding vector(768) NOT NULL,
    PRIMARY KEY(identity,content_hash)
);
CREATE TABLE library_chunks (
    identity text NOT NULL,
    id text NOT NULL,
    document_id text NOT NULL REFERENCES library_documents(id),
    publication_id text NOT NULL,
    search_text text NOT NULL,
    payload jsonb NOT NULL,
    embedding vector(768) NOT NULL,
    lexical tsvector GENERATED ALWAYS AS (to_tsvector('simple',search_text)) STORED,
    PRIMARY KEY(identity,id)
);
CREATE INDEX library_chunks_lexical ON library_chunks USING gin(lexical);
CREATE INDEX library_chunks_semantic ON library_chunks USING hnsw(embedding vector_cosine_ops);
CREATE INDEX library_chunks_publication ON library_chunks(document_id,publication_id);
