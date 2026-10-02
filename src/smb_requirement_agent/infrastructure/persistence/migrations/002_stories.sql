CREATE UNIQUE INDEX IF NOT EXISTS features_feature_id_unique ON features(feature_id);

CREATE TABLE IF NOT EXISTS stories (
    feature_id text NOT NULL REFERENCES features(feature_id) ON DELETE CASCADE,
    story_id text NOT NULL,
    position integer NOT NULL CHECK (position >= 0),
    payload jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_id, story_id),
    UNIQUE (feature_id, position)
);

CREATE TABLE IF NOT EXISTS story_change_proposals (
    feature_id text NOT NULL REFERENCES features(feature_id) ON DELETE CASCADE,
    proposal_id text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (feature_id, proposal_id)
);
