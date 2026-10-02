-- Requirement attachments leave the shared reference library (ADR-0099).
--
-- Attachments were library_documents rows carrying an attachment_target. They
-- move to their own table, keeping their id, version and stored file record, so
-- an upload in flight keeps its lease, attempts and extraction. Their blobs stay
-- where they are in document_blobs, keyed by the same file id.
CREATE TABLE requirement_attachment_ingestions (
    id text PRIMARY KEY,
    source_id text NOT NULL,
    is_draft boolean NOT NULL,
    owner_id text NOT NULL,
    submission_key text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    UNIQUE (owner_id, submission_key)
);
CREATE INDEX requirement_attachment_ingestions_source
    ON requirement_attachment_ingestions(source_id, is_draft, id);
CREATE INDEX requirement_attachment_ingestions_work
    ON requirement_attachment_ingestions(id)
    WHERE payload->'file'->>'stage' IN ('queued', 'scanning', 'extracting', 'ready_for_review');

INSERT INTO requirement_attachment_ingestions
    (id, source_id, is_draft, owner_id, submission_key, version, payload)
SELECT
    d.id,
    d.payload->'attachment_target'->>'source_id',
    (d.payload->'attachment_target'->>'is_draft')::boolean,
    d.payload->'versions'->0->'uploaded_by'->'id'->>'value',
    d.payload->'versions'->0->>'idempotency_key',
    d.version,
    jsonb_build_object(
        'id', d.id,
        'target', d.payload->'attachment_target',
        'owner', d.payload->'owner',
        'file', (d.payload->'versions'->0) - 'number' - 'revisions',
        'version', d.version,
        'attached_document_id', COALESCE(d.payload->'attached_document_id', 'null'::jsonb),
        'excluded', COALESCE(d.payload->'attachment_excluded', 'false'::jsonb)
    )
FROM library_documents d
WHERE d.payload->'attachment_target'->>'source_id' IS NOT NULL;

DELETE FROM library_submissions s
USING library_documents d
WHERE s.document_id = d.id
  AND d.payload->'attachment_target'->>'source_id' IS NOT NULL;

DELETE FROM library_documents d
WHERE d.payload->'attachment_target'->>'source_id' IS NOT NULL;
