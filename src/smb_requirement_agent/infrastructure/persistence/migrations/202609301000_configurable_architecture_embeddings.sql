-- Architecture evidence now uses the application's configured 768-dimension
-- embedding model. Indexes built with the former 1,024-dimension local model
-- cannot be compared with it, so they are dropped; releases keep their records
-- and the index-profile check asks maintainers to build and publish again.
DELETE FROM architecture_knowledge_chunks;
ALTER TABLE architecture_knowledge_chunks ALTER COLUMN embedding TYPE vector(768);
