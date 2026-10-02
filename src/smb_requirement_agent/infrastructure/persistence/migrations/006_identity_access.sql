CREATE TABLE IF NOT EXISTS actor_profiles (
    actor_id text PRIMARY KEY,
    payload jsonb NOT NULL,
    last_seen_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS requirement_access (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS draft_ownership (
    draft_id text PRIMARY KEY REFERENCES requirement_drafts(draft_id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
