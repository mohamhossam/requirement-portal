CREATE TABLE IF NOT EXISTS saved_requirement_views (
    view_id text PRIMARY KEY,
    actor_id text NOT NULL,
    name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 80),
    criteria jsonb NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS saved_requirement_views_actor_name_idx
    ON saved_requirement_views (actor_id, lower(name));
CREATE INDEX IF NOT EXISTS requirement_revisions_created_idx
    ON requirement_revisions (created_at DESC, requirement_id);
CREATE INDEX IF NOT EXISTS breakdown_revisions_created_idx
    ON breakdown_revisions (created_at DESC, requirement_id);
CREATE INDEX IF NOT EXISTS analysis_rounds_created_idx
    ON analysis_rounds (created_at DESC, requirement_id);
