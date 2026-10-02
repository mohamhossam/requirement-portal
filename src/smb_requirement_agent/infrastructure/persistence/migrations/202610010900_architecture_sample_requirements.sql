-- The team's shared sample requirements, checked against every new catalogue
-- version before it is published. One row, replaced under a revision check.
CREATE TABLE architecture_sample_requirements (
    set_id smallint PRIMARY KEY DEFAULT 1 CHECK (set_id = 1),
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
