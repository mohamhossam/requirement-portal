-- The reference library's and the architecture catalogue's file bytes leave the
-- blob store requirement documents use (ADR-0099), so each side owns its own.
--
-- Library blobs are keyed by library version id; catalogue blobs by each
-- document version's storage key, whether a release lists it or only the
-- registry does. Everything else (source documents, attachment uploads) stays.
CREATE TABLE knowledge_document_blobs (
    document_version_id text PRIMARY KEY,
    checksum_sha256 text NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    content bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (octet_length(content) = size_bytes)
);

CREATE TEMPORARY TABLE knowledge_blob_keys (document_version_id text PRIMARY KEY) ON COMMIT DROP;

INSERT INTO knowledge_blob_keys
SELECT DISTINCT v->>'id'
FROM library_documents d, jsonb_array_elements(d.payload->'versions') v
WHERE v->>'id' IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_blob_keys
SELECT DISTINCT payload->>'storage_key'
FROM architecture_knowledge_documents
WHERE payload->>'storage_key' IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_blob_keys
SELECT DISTINCT document->>'storage_key'
FROM architecture_knowledge_releases r, jsonb_array_elements(r.payload->'documents') document
WHERE document->>'storage_key' IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO knowledge_document_blobs
    (document_version_id, checksum_sha256, size_bytes, content, created_at)
SELECT b.document_version_id, b.checksum_sha256, b.size_bytes, b.content, b.created_at
FROM document_blobs b
JOIN knowledge_blob_keys k ON k.document_version_id = b.document_version_id;

DELETE FROM document_blobs b
USING knowledge_blob_keys k
WHERE b.document_version_id = k.document_version_id;
