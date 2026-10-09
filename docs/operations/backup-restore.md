# Backup and restore

Requirement work keeps everything in one PostgreSQL database, `smb_requirements`:
- Requirements, analyses, breakdowns, approvals and their immutable history;
- attachments and the search index;
- AI jobs and notifications;
- the local copy of each cited reference's state.

The knowledge portal backs up its own database (ADR-0104). ClamAV's signatures are downloaded
again on start, so `clamav_data` needs no backup.

## Recovery targets

*Proposed, to be confirmed by the owner. Until then these are the planning assumption, not a
commitment.*

| Target | Proposed | Follows from |
|---|---|---|
| **RPO**, the most work that can be lost | 24 hours | A daily backup |
| **RTO**, the longest the service is down for a restore | 1 hour | Restoring a dump of this size, then a smoke check |

A tighter RPO needs more frequent backups, or a managed PostgreSQL with point-in-time recovery.

## Taking a backup

The `backup` service in `deploy/compose.production.yaml` dumps the database in PostgreSQL's
custom format into the `backups` volume. It uses the same image as the database. It runs online,
without stopping the API or workers:

```bash
docker compose -f deploy/compose.production.yaml run --rm backup
# prints /backups/smb_requirements-<UTC timestamp>.dump
```

- **Crash-safe.** A dump is written as `….dump.partial` and renamed once complete, so a
  file named `*.dump` is always whole.
- **Retention.** After a successful run, dumps older than `BACKUP_RETENTION_DAYS` are deleted.
  The default is 14 days; this is a Compose variable, set in `deploy/.env`.
- **Before every upgrade.** Always take one (`deployment.md`, "Upgrade").

**Schedule it** at least daily, from the host's scheduler. For example, cron at 02:15 UTC:

```cron
15 2 * * * cd /srv/requirement-portal && docker compose -f deploy/compose.production.yaml run --rm backup
```

**Copy it off the host.** A dump that stays on the host is lost with the host. After each run,
copy the newest dump to storage in another failure domain (object storage, another site), and
keep that copy encrypted. For example:

```bash
volume=$(docker volume inspect requirement-platform_backups --format '{{ .Mountpoint }}')
latest=$(ls -1t "$volume"/smb_requirements-*.dump | head -n 1)
# copy "$latest" with the storage's own tool, e.g. `aws s3 cp` or `rclone copy`
```

A dump holds personal data and every Requirement's content. Protect it like the database:
restrict who can read it, and delete off-host copies on the same retention.

## Restoring

Restore into a new database, check it, then switch to it. Never restore over the live
database.

1. **Stop the writers.** Run `docker compose -f deploy/compose.production.yaml stop api worker`.
2. **Restore into a new database.** Here the dump is already in the `backups` volume; copy an
   off-host one back there first.

   ```bash
   docker compose -f deploy/compose.production.yaml run --rm --entrypoint sh backup -ec '
     createdb --host=postgres --username=smb smb_requirements_restored
     pg_restore --exit-on-error --no-owner --host=postgres --username=smb \
       --dbname=smb_requirements_restored /backups/smb_requirements-<timestamp>.dump
     psql --host=postgres --username=smb --dbname=smb_requirements_restored \
       -tAc "SELECT max(version) FROM schema_migrations"'
   ```

   The last line names the newest migration the dump contains. It must be no newer than the
   release you will run, and normally it is that release's newest.
3. **Switch.** Rename the databases while nothing is connected. This keeps the old one for
   comparison until you drop it.

   ```bash
   docker compose -f deploy/compose.production.yaml exec postgres psql -U smb -d postgres -c \
     "ALTER DATABASE smb_requirements RENAME TO smb_requirements_replaced" -c \
     "ALTER DATABASE smb_requirements_restored RENAME TO smb_requirements"
   ```

4. **Start.** Run `docker compose -f deploy/compose.production.yaml up -d --no-build` (or
   `up -d` for a source build). `migrate` brings the schema up to the running release. Then
   check that `/api/ready` answers 200, sign in, and open a recent Requirement.
5. **Clean up.** Once satisfied, drop `smb_requirements_replaced`.

Derived projections, such as the search index and the activity feed, are restored with
everything else. Run `maintenance` only if `/ready` reports the maintenance marker missing.

## How the procedure is checked

- **On every pull request.** CI's `deployment` job runs the `backup` service against the
  freshly installed stack. It restores the dump into a new database with `pg_restore
  --exit-on-error` and reads its migrations back.
- **The data survives.** CI's `recovery` job seeds a database with reviewed content and
  immutable history (`tests/release_recovery.py seed`), dumps it and restores it into a new
  database. It then verifies checksums, history, access control, search and maintenance on the
  restored copy (`verify`).

  That fixture uses synthetic data and never touches an application database.
- **A real restore drill.** Run one at least each quarter, and after any change to PostgreSQL's
  version or this procedure:
  - restore the latest off-host dump on a separate host with the steps above;
  - record how long it took against the RTO;
  - record the age of the dump against the RPO.
