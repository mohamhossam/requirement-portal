CREATE TABLE source_documents (
    document_id text PRIMARY KEY,
    requirement_id text REFERENCES requirements(requirement_id),
    draft_id text REFERENCES requirement_drafts(draft_id),
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT source_document_scope CHECK (
        (requirement_id IS NOT NULL AND draft_id IS NULL)
        OR (requirement_id IS NULL AND draft_id IS NOT NULL)
    )
);

CREATE INDEX source_documents_requirement_idx
    ON source_documents (requirement_id, updated_at DESC);
CREATE INDEX source_documents_draft_idx
    ON source_documents (draft_id, updated_at DESC);
