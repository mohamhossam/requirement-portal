CREATE TABLE IF NOT EXISTS breakdown_reviews (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

