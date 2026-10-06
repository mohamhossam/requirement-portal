-- Knowledge Center E2 (ADR-0102): each Requirement's latest prior-art check against the
-- historic corpus. Informational only: nothing here is a knowledge finding, and nothing
-- that counts findings or decides readiness reads it.

CREATE TABLE requirement_prior_art (
    requirement_id text PRIMARY KEY REFERENCES requirements ON DELETE CASCADE,
    subject_fingerprint text NOT NULL,
    corpus_version bigint NOT NULL,
    embedding_identity text NOT NULL,
    model text NOT NULL,
    prompt_version text NOT NULL,
    checked_at timestamptz NOT NULL
);

CREATE TABLE requirement_prior_art_matches (
    requirement_id text NOT NULL REFERENCES requirement_prior_art ON DELETE CASCADE,
    historic_requirement_id text NOT NULL
        REFERENCES historic_requirement_state ON DELETE CASCADE,
    rank integer NOT NULL,
    publication integer NOT NULL,
    title text NOT NULL,
    verdict text NOT NULL CHECK (verdict IN ('similar_past_requirement')),
    rationale text NOT NULL,
    -- The cited passages as the judge read them.
    evidence jsonb NOT NULL,
    PRIMARY KEY (requirement_id, historic_requirement_id)
);

CREATE INDEX requirement_prior_art_matches_historic
    ON requirement_prior_art_matches (historic_requirement_id);

-- Judge calls spent in each hour, across the portal.
CREATE TABLE prior_art_call_windows (
    window_start timestamptz PRIMARY KEY,
    calls integer NOT NULL
);
