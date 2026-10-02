CREATE TABLE requirement_drafts (
    draft_id text PRIMARY KEY,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
