-- Maintained current-state projection for bounded portfolio worklist reads.
-- Classification is computed by the Application projector and persisted by
-- the PostgreSQL adapter in the same transaction as each logical mutation.
CREATE TABLE IF NOT EXISTS requirement_worklist_projection (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    title text NOT NULL,
    search_text text NOT NULL,
    requirement_status text NOT NULL,
    workflow_status text NOT NULL,
    current_stage text NOT NULL,
    next_action text NOT NULL,
    answered_items integer NOT NULL DEFAULT 0,
    unresolved_items integer NOT NULL DEFAULT 0,
    stale_items integer NOT NULL DEFAULT 0,
    epic_count integer NOT NULL DEFAULT 0,
    feature_count integer NOT NULL DEFAULT 0,
    story_count integer NOT NULL DEFAULT 0,
    owner_id text,
    owner_payload jsonb,
    reviewer_ids text[] NOT NULL DEFAULT '{}',
    reviewer_count integer NOT NULL DEFAULT 0,
    active_ai_operation text,
    latest_activity timestamptz NOT NULL,
    last_activity_payload jsonb,
    attention_rank integer NOT NULL DEFAULT 100,
    projected_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_worklist_status_activity
    ON requirement_worklist_projection(workflow_status, latest_activity DESC, requirement_id);
CREATE INDEX IF NOT EXISTS ix_worklist_owner
    ON requirement_worklist_projection(owner_id, latest_activity DESC);
CREATE INDEX IF NOT EXISTS ix_worklist_reviewers
    ON requirement_worklist_projection USING gin(reviewer_ids);
CREATE INDEX IF NOT EXISTS ix_worklist_search
    ON requirement_worklist_projection USING gin(to_tsvector('simple', search_text));
CREATE INDEX IF NOT EXISTS ix_worklist_attention
    ON requirement_worklist_projection(attention_rank, latest_activity, requirement_id);

CREATE TABLE IF NOT EXISTS requirement_knowledge_dependencies (
    source_requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    dependent_requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    source_version integer NOT NULL CHECK (source_version > 0),
    PRIMARY KEY (source_requirement_id, dependent_requirement_id)
);
CREATE INDEX IF NOT EXISTS ix_knowledge_dependencies_dependent
    ON requirement_knowledge_dependencies(dependent_requirement_id);

-- The maintenance command performs the initial backfill after blob import.
-- Application startup intentionally never rebuilds this table.
