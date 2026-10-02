CREATE TABLE IF NOT EXISTS analysis_evidence_fragments (
    cache_key text PRIMARY KEY,
    payload jsonb NOT NULL,
    generated_at timestamptz NOT NULL
);

ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS phase text;
ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS completed_units integer NOT NULL DEFAULT 0;
ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS total_units integer;
ALTER TABLE ai_jobs ADD COLUMN IF NOT EXISTS current_section_label text;
