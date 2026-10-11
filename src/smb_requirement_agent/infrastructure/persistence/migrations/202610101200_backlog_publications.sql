-- Which local backlog items exist in the work-item tracker, and every publication attempt
-- (Slice 13). One row per Requirement; its payload holds the external id mappings, the
-- attempts with each item's result, and the accepted product verdict once analysis
-- decides one. Saves advance the version by one, so concurrent writers cannot both win.
CREATE TABLE backlog_publications (
    requirement_id text PRIMARY KEY,
    target_key text NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
