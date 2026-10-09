# Changelog

Each release has a `## vX.Y.Z` section, written before the tag is pushed. The release workflow
(`.github/workflows/release.yml`, ADR-0108) refuses a tag without one and publishes the section as
the GitHub release notes. The tag must match `version` in `pyproject.toml` and
`frontend/package.json`.

Under each heading, list what changed for whoever deploys, then any upgrade step. Name every
contract-step migration (WORKSPACE.md, "Migrations"), because rolling back past one means
restoring a backup.

## v0.1.0

The first published release: the pilot candidate, closing the pilot gate of
`docs/slices/production-hardening.md`, with its shared provider limits and platform-kernel 1.2.0.

- **Production configuration fails closed.**
  - The production manifest always runs `APP_ENV=production` with OIDC sign-in.
  - A fake model, the debug trace or non-JSON logs refuse to start.
  - The API documentation is not served at the edge.
- **Analysis survives a knowledge-portal outage.** It is kept and marked "references not
  checked".
- **AI jobs retry transient outages with backoff.**
  - The waits are `AI_JOB_RETRY_FIRST_SECONDS` and `AI_JOB_RETRY_MAX_SECONDS`.
  - Exhausted jobs are labelled in metrics.
- **Model-backed work runs only as a durable job (ADR-0105).**
  - The synchronous provider routes are removed.
  - The edge's `/api/` timeout is 60 seconds.
  - Architecture mapping runs through the job routes and needs Requirement membership only.
- **Probes and shutdown.**
  - `/ready` answers within 2.5 seconds on its own threads.
  - In-flight requests get 25 seconds on a stop.
  - `web` has a healthcheck.
- **The browser keeps working through a token renewal.**
  - Requests abandoned by a sign-out or identity switch are silent.
  - A crash or a redeployed page shows a way out (ADR-0109).
- **Releases, backups, upgrade and rollback (ADR-0108).**
  - Signed images, with SBOMs, are published to `ghcr.io` by tag.
  - `/health` reports the version.
  - A `backup` service is added.
  - Migrations follow an expand/contract policy.
- **Shared provider limits, a daily token budget, and edge limits (ADR-0106).**
  - The per-person provider rate limit holds across API replicas.
  - `PROVIDER_DAILY_TOKEN_BUDGET` pauses new AI work until 00:00 UTC once spent
    (`provider_budget_exhausted`, 429). Queued jobs wait.
  - nginx limits each client address (`EDGE_RATE_PER_SECOND`, `EDGE_BURST`).
  - A deployment behind a TLS proxy must set `TRUSTED_PROXY_CIDR`.
- **Platform-kernel 1.2.0.**
  - **Sign-in.** A person's token must be an access token issued to `OIDC_CLIENT_ID`. Other
    clients are accepted only when listed in `OIDC_AUTHORIZED_PARTIES`.
  - **Clock difference.** `OIDC_LEEWAY_SECONDS` (60) of clock difference is tolerated.
  - **Issuer outages.** A brief issuer outage no longer fails sign-ins: the last good signing
    keys keep being served (ADR-0018 amendment).
  - **OpenAI.** Each reply is capped at `OPENAI_MAX_OUTPUT_TOKENS` (8192).
  - **Migrations.** A migration waits at most 10 seconds for a table lock, and concurrent
    `migrate` runs take turns.
  - **Knowledge service.** Calls pause for 30 seconds after 5 failures in a row.

Upgrade: none (first release). Contract-step migrations: none after `202610091200`.
