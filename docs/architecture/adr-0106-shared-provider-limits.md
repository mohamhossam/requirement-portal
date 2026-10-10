# ADR 0106 — Provider limits shared by every process, a daily token budget, and edge limits

## Status

Accepted 2026-10-08 ("count the provider rate limit in Postgres"), and implemented 2026-10-09
with production hardening PR 7 (`docs/slices/production-hardening.md`). The spend-cap behaviour
was chosen by the repository owner on 2026-10-09 ("pause AI work until reset"). It amends ADR-0074,
where the provider rate limit is per API process. It retires the AGENTS.md debt row that recorded
that limitation.

## Context

**The rate limit was per process.** `ProviderCallRateLimit` (ADR-0074) counted each actor's
provider-calling operations per minute in the API process's memory. Behind N API replicas an
actor could start N times the limit, and a restart forgot every count.

**Nothing capped spend.** The rate limit bounds how fast one actor starts work, not how much
all actors spend together. A busy day, a loop of automatic work, or a script spread across
actors had no ceiling. Every model response already reports its tokens, and the kernel's
metered transport reads them into `smb_provider_tokens_total`, but nothing acted on them.

**The edge had no limits.** nginx proxied any rate of requests to the API. Impact preview, which
the browser calls while a person edits, recomputes a Requirement's impact on every call.

## Decision

- **One count for every process.** The limiter keeps its sliding window and refund rules, but its
  calls live behind `ProviderCallLogPort`.
  - With PostgreSQL, `provider_calls` holds one row per counted call. A transaction-scoped
    advisory lock per actor serialises the check across processes, so two replicas cannot both
    admit the call that fills the window.
  - Rows an hour old are deleted as calls arrive.
  - The in-memory log, used offline, keeps today's behaviour.
- **A daily token budget that pauses AI work.** `PROVIDER_DAILY_TOKEN_BUDGET` is the tokens the
  providers may spend per UTC day, across every process.
  - **Counting.** A counting transport inside each model client's metered transport adds the
    tokens every successful response reports to `provider_token_spend` (one row per day). A
    failure to record is logged, never raised.
  - **Refusing.** Once the day's budget is spent, `AiJobs` refuses new starts and retries with
    429, `provider_budget_exhausted`, and `Retry-After` until 00:00 UTC. A replayed
    idempotency key still answers.
  - **Waiting.** `SpendGatedQueue` stops workers claiming queued jobs, so they wait and run after
    the reset.
  - **Not paused.** Editing Requirements keeps working: the routes that only queue automatic work
    are not refused. Embedding (indexing) is counted but not paused, because search and screening
    depend on a current index and its cost is small.
  - **Overshoot.** Calls in flight finish, so a day can overshoot by them.
  - **Unlimited.** A budget of 0 records spend without limiting it.
- **Edge limits per client address.** nginx limits each client address on `/api/` to
  `EDGE_RATE_PER_SECOND` (default 50/s, bursts of `EDGE_BURST`, 100), and impact preview to 2/s
  (bursts of 5).
  - A refusal is 429 in the API's error shape (`edge_rate_limited`, with `Retry-After`). The
    API's own 429s pass through.
  - The client address comes from `X-Forwarded-For` only when the request arrives from
    `TRUSTED_PROXY_CIDR`, the TLS proxy in front. The default trusts no one.

## Consequences

- **Exact across replicas.** The per-actor ceiling holds however many API replicas run. Each
  provider-calling request costs one locked transaction in PostgreSQL.
- **Bounded spend.** A day's model spend is bounded by the budget plus the work in flight. When
  the cap is reached, people see why and when it resets, and nothing already queued is lost.
- **Counted from what providers report.** A provider or local server that reports no usage is
  not counted; this is visible as a flat `smb_provider_tokens_total`. The knowledge service's
  model work is its own deployment's to cap.
- **Shared addresses.** People behind one NAT share an address at the edge, so the defaults are
  generous and configurable. A deployment behind a TLS proxy must set `TRUSTED_PROXY_CIDR`, or
  the edge limit applies to everyone together.
- **Blocked spend is counted.** Since production hardening PR 9, `smb_provider_spend_blocked_total`
  counts each refused start and each claim a worker skipped, and `ProviderSpendBlocked` alerts on
  it (`docs/operations/alerts.md`).

## Alternatives Considered

- **Fixed one-minute windows** (one upsert per actor and minute). This is simpler, but a burst
  across a window boundary admits twice the limit, and it differs from the in-memory window's
  meaning.
- **A gateway limit only.** That needs a component the reference deployment does not have, and
  does not know actors.
- **A hard stop at the model client.** This refuses every call once over budget. It would fail
  jobs halfway and fail automatic work rather than letting it wait. The owner chose pausing.
- **Count only, cap later.** This would leave spend unbounded through the pilot.
