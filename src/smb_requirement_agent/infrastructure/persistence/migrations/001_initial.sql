CREATE TABLE IF NOT EXISTS requirements (
    requirement_id text PRIMARY KEY,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS requirement_analyses (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS epics (
    requirement_id text PRIMARY KEY REFERENCES requirements(requirement_id) ON DELETE CASCADE,
    epic_id text UNIQUE NOT NULL,
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS features (
    epic_id text NOT NULL REFERENCES epics(epic_id) ON DELETE CASCADE,
    feature_id text NOT NULL,
    position integer NOT NULL CHECK (position >= 0),
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (epic_id, feature_id),
    UNIQUE (epic_id, position)
);

CREATE TABLE IF NOT EXISTS requirement_revisions (
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE RESTRICT,
    revision_number integer NOT NULL CHECK (revision_number > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL,
    PRIMARY KEY (requirement_id, revision_number)
);

CREATE TABLE IF NOT EXISTS breakdown_revisions (
    requirement_id text NOT NULL REFERENCES requirements(requirement_id) ON DELETE RESTRICT,
    revision_number integer NOT NULL CHECK (revision_number > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    payload jsonb NOT NULL,
    PRIMARY KEY (requirement_id, revision_number)
);

CREATE OR REPLACE FUNCTION reject_revision_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'revision rows are immutable';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS requirement_revisions_immutable ON requirement_revisions;
CREATE TRIGGER requirement_revisions_immutable
BEFORE UPDATE OR DELETE ON requirement_revisions
FOR EACH ROW EXECUTE FUNCTION reject_revision_mutation();

DROP TRIGGER IF EXISTS breakdown_revisions_immutable ON breakdown_revisions;
CREATE TRIGGER breakdown_revisions_immutable
BEFORE UPDATE OR DELETE ON breakdown_revisions
FOR EACH ROW EXECUTE FUNCTION reject_revision_mutation();
