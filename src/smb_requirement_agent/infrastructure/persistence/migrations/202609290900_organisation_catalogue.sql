CREATE TABLE organisation_catalogue (
    catalogue_id smallint PRIMARY KEY DEFAULT 1 CHECK (catalogue_id = 1),
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE organisation_audit (
    audit_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id text NOT NULL,
    action text NOT NULL,
    subject_id text NOT NULL,
    created_at timestamptz NOT NULL
);
