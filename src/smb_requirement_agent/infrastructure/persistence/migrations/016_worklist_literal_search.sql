-- Rebuild worklist rows with the application casefold rules before enabling traffic.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
ALTER TABLE requirement_worklist_projection
    ADD COLUMN title_order text NOT NULL DEFAULT '';
CREATE INDEX requirement_worklist_search_trgm
    ON requirement_worklist_projection USING gin (search_text gin_trgm_ops);
CREATE INDEX requirement_worklist_title_order
    ON requirement_worklist_projection (title_order, requirement_id);
CREATE TABLE maintenance_markers (
    name text PRIMARY KEY,
    completed_at timestamptz NOT NULL DEFAULT now()
);
