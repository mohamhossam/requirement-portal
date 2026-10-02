-- The active catalogue release's name, carried by activation events (ADR-0099),
-- so requirement work can label the version in use without asking.
ALTER TABLE active_architecture_release ADD COLUMN IF NOT EXISTS name text;

-- While the catalogue still lives in this database, take the current name from it.
UPDATE active_architecture_release a
SET name = r.payload->>'name'
FROM architecture_knowledge_releases r
WHERE r.release_id = a.release_id AND a.name IS NULL;
