CREATE TABLE architecture_extraction_runs (
    run_id text PRIMARY KEY,
    release_id text NOT NULL,
    document_version_id text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL
);
CREATE INDEX architecture_extraction_runs_release_idx
    ON architecture_extraction_runs (release_id, created_at);

CREATE TABLE architecture_catalogue_candidates (
    candidate_id text PRIMARY KEY,
    release_id text NOT NULL,
    document_version_id text NOT NULL,
    status text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL
);
CREATE INDEX architecture_catalogue_candidates_release_idx
    ON architecture_catalogue_candidates (release_id, document_version_id, status);
