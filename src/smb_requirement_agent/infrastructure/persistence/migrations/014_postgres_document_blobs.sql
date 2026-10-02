CREATE TABLE IF NOT EXISTS document_blobs (
    document_version_id text PRIMARY KEY,
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    content bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (octet_length(content) = size_bytes)
);

CREATE TABLE IF NOT EXISTS document_blob_imports (
    document_version_id text PRIMARY KEY REFERENCES document_blobs(document_version_id),
    source_checksum_sha256 text NOT NULL,
    imported_at timestamptz NOT NULL DEFAULT now()
);
