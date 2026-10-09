-- One provider-call count and one token budget for every API and worker process (ADR-0106).
-- Each counted call is a row, so the per-actor window slides exactly; rows an hour old are
-- deleted as calls arrive.
CREATE TABLE IF NOT EXISTS provider_calls (
    call_id text PRIMARY KEY,
    actor_id text NOT NULL,
    called_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS provider_calls_actor_idx ON provider_calls (actor_id, called_at);
CREATE INDEX IF NOT EXISTS provider_calls_called_at_idx ON provider_calls (called_at);

-- Tokens the providers reported per UTC day: the daily budget reads today's row, and the
-- history stays for capacity planning.
CREATE TABLE IF NOT EXISTS provider_token_spend (
    day date PRIMARY KEY,
    tokens bigint NOT NULL DEFAULT 0
);
