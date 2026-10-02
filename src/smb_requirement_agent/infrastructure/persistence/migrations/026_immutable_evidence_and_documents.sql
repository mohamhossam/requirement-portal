CREATE TABLE architecture_knowledge_indexes (
    index_id text PRIMARY KEY,
    release_id text NOT NULL REFERENCES architecture_knowledge_releases(release_id)
);
INSERT INTO architecture_knowledge_indexes
SELECT DISTINCT release_id, release_id FROM architecture_knowledge_chunks;
ALTER TABLE architecture_knowledge_chunks DROP CONSTRAINT architecture_knowledge_chunks_release_id_fkey;
ALTER TABLE architecture_knowledge_chunks RENAME COLUMN release_id TO index_id;
ALTER TABLE architecture_knowledge_chunks ADD FOREIGN KEY (index_id)
    REFERENCES architecture_knowledge_indexes(index_id);
UPDATE architecture_knowledge_releases
SET payload = jsonb_set(payload, '{index_id}', to_jsonb(release_id))
WHERE release_id IN (SELECT index_id FROM architecture_knowledge_indexes);

CREATE TABLE architecture_knowledge_documents (
    version_id text PRIMARY KEY,
    payload jsonb NOT NULL,
    published boolean NOT NULL DEFAULT false
);
INSERT INTO architecture_knowledge_documents
SELECT document->>'id', document, bool_or(r.payload->>'status' = 'published')
FROM architecture_knowledge_releases r,
     jsonb_array_elements(r.payload->'documents') document
GROUP BY document->>'id', document;
