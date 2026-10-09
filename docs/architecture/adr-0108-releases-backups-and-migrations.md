# ADR 0108 — Signed releases deployed by tag, backups, and expand/contract migrations

## Status

Accepted 2026-10-09 with production hardening PR 6
(`docs/slices/production-hardening.md`).

## Context

**Deployment.** Every deployment built its images on the target host from whatever checkout it
had. Nothing recorded which commit a host ran, the images were neither scanned nor signed where
they ran, and "roll back" meant checking out an older commit and building again. CI already
scanned images, but threw them away.

**Backups.** The manifest had no backup. `deployment.md` said to back up the `postgres_data`
volume. The recovery job in CI proves a `pg_dump`/`pg_restore` round trip on synthetic data,
but no deployment ran one.

**Migrations.** Migrations ran in whatever form they were written. Dropping or renaming a column
the previous release still reads makes that release fail on the migrated database. That rules
out both an overlapping rollout and a quick rollback.

The knowledge portal already publishes images by tag from its own `release.yml`.

## Decision

- **Releases are tags.** A tag `vX.Y.Z` runs `.github/workflows/release.yml`:
  - **Gate.** It checks the tag against `pyproject.toml`, `frontend/package.json` and a
    `CHANGELOG.md` section, then runs the whole of `ci.yml` on the tagged commit as a reusable
    workflow.
  - **Build.** It builds each image once, refuses fixable HIGH or CRITICAL findings (Trivy) and
    pushes to `ghcr.io`.
  - **Sign.** It signs each image keyless with cosign, and attests an SPDX SBOM made by syft.
  - **Publish.** It creates the GitHub release from the changelog section, with both digests
    and SBOMs.
- **The web image is built per deployment.** Its Content-Security-Policy names the OIDC issuer,
  and its links name the knowledge portal, both at build time. So the release builds the
  production deployment's web image from the `production` GitHub environment's variables
  (`requirement-web-production`).
  - A second deployment is a second web build.
  - The API image is the same for every deployment.
  - The owner chose this over making the web image configurable at run time (2026-10-09).
- **Deploy by tag.** The manifest names its images `${REQUIREMENT_API_IMAGE}:${IMAGE_TAG}` and
  `${REQUIREMENT_WEB_IMAGE}:${IMAGE_TAG}`; a local build remains the default.
  - **Upgrade:** back up → pull the new tag → `up -d --no-build`, which runs `migrate` first.
  - **Roll back:** redeploy the previous tag. When a contract step lies in between, restore the
    backup taken before the upgrade.
  - `/health` reports the running version.
- **Backups are a service.** The `backup` profile runs `pg_dump --format=custom` on the database
  image into a `backups` volume, writes each dump under its final name only once complete, and
  prunes dumps past `BACKUP_RETENTION_DAYS`.
  - Scheduling it and copying dumps off the host are the operator's part.
  - `docs/operations/backup-restore.md` gives the procedure and the proposed RPO (24h) and RTO
    (1h), which the owner is to confirm.
  - CI's `deployment` job runs the service and restores its dump on every pull request.
- **Migrations expand; a contract step is marked.** A migration adds. Dropping, renaming,
  retyping or truncating is a separate contract step:
  - it ships only once no deployed release reads the old shape;
  - its file carries `-- contract-step: <why it is safe now>`;
  - the changelog names it.

  `tests/architecture/test_migration_expand_contract.py` enforces this, scanning string
  literals so statements built inside `EXECUTE` count too. Migrations through `202610091200`
  are grandfathered.

## Consequences

- **Traceable.** A deployment runs a known, scanned and signed artifact, and says which one.
- **Simple rollback.** Rolling back is a tag change, except across a contract step.
- **Every release runs every gate.** It passes the full CI suite before anything is published,
  so a release takes as long as CI.
- **More bookkeeping.**
  - A version bump touches `pyproject.toml`, `package.json`, `CHANGELOG.md` and the OpenAPI
    snapshot, whose `info.version` follows the package.
  - Releases need a `production` GitHub environment holding `CSP_IDENTITY_ORIGINS`.
  - Renaming a column takes two releases: an expand, then a contract.
- **Base-image fixes need a patch release.** A digest bump from Dependabot reaches a deployment
  only through a new tag.
- **Backups are logical dumps.** Point-in-time recovery needs a managed PostgreSQL or WAL
  archiving, which is not included.

## Alternatives Considered

- **Keep building on the host.** There would be no record of what runs, nothing scanned or
  signed at the point of use, and rollback would mean rebuilding.
- **One generic web image, configured at run time.** This would deliver the CSP as an nginx
  header and the links through a runtime config file. It is cleaner for many deployments, but
  changes how the CSP is delivered and the frontend's configuration logic. Deferred; the owner
  chose per-deployment builds.
- **Volume snapshots instead of dumps.** They depend on the host's storage and are not portable
  across PostgreSQL minor versions or hosts. A dump restores anywhere and is what CI already
  proves.
- **Review migrations by hand, without a test.** A dynamic `DROP` inside `EXECUTE` is easy to
  miss in review, as the knowledge-table retirement showed.
