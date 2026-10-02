-- Vectors per embedding model and passage text, so rebuilding an architecture
-- index only embeds passages that changed.
CREATE TABLE architecture_embedding_cache (
    model text NOT NULL,
    content_hash text NOT NULL,
    embedding vector(768) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (model, content_hash)
);
