# Running release qualification

The status and dated results live in `docs/slices/production-readiness-qualification.md`.
These tools supply evidence; neither tool grants production approval.

## Nonempty backup/restore

Use a disposable local PostgreSQL/pgvector container. The fixture requires database names starting
with `codex_qualification_test_`, refuses nonempty seed databases and cannot verify the source as
its own restore. It creates synthetic originals, an excluded passage, a private unpublished file,
review/publication, analysis decisions, immutable history and recorded dependencies. Fake generation
and scanner substitution exist only in the test fixture, never in deployment configuration.

The CI `recovery` job repeats this on the pinned PostgreSQL 17 image that development, CI and the
reference deployment all use (`tests/architecture/test_image_pins.py`), retaining the checksum
manifest and verification report. It uses the server's own `pg_dump`/`pg_restore` binaries. Failure propagates
to CI, including checksum differences. Local PowerShell equivalent (use new names on each run):

```powershell
$pgContainer = 'smb-ai-requirement-agent-postgres-1'
$sourceDb = 'codex_qualification_test_source_example'
$restoreDb = 'codex_qualification_test_restored_example'
# Resolve these two connection strings securely for your local test database role.
# Use 127.0.0.1 and connect_timeout=5 for this repository's local Docker mapping.
# $sourceUrl = connection string for $sourceDb
# $restoreUrl = connection string for $restoreDb
New-Item -ItemType Directory -Force .data/qualification | Out-Null
docker exec $pgContainer createdb -U smb $sourceDb
if ($LASTEXITCODE -ne 0) { throw 'Create source failed' }
.venv/Scripts/python.exe -m tests.release_recovery seed --database-url $sourceUrl --manifest .data/qualification/manifest.json
if ($LASTEXITCODE -ne 0) { throw 'Seed failed' }
docker exec $pgContainer pg_dump -U smb -Fc -d $sourceDb -f /tmp/qualification-example.dump
if ($LASTEXITCODE -ne 0) { throw 'Backup failed' }
docker exec $pgContainer createdb -U smb $restoreDb
if ($LASTEXITCODE -ne 0) { throw 'Create restore target failed' }
docker exec $pgContainer pg_restore -U smb --exit-on-error --no-owner -d $restoreDb /tmp/qualification-example.dump
if ($LASTEXITCODE -ne 0) { throw 'Restore failed' }
.venv/Scripts/python.exe -m tests.release_recovery verify --database-url $restoreUrl --manifest .data/qualification/manifest.json
if ($LASTEXITCODE -ne 0) { throw 'Verification failed' }
```

Keep application workers stopped while capturing the manifest and taking the backup. Verification
hashes all public table rows before creating a restored application graph, then checks original
bytes, private access, exclusion-safe search and dependency reads. It reruns migrations and two
projection rebuilds and confirms authoritative document/analysis/history data remain unchanged.
The harness does not delete either database or the backup. Current-schema synthetic recovery does
not replace a rehearsal using the intended production backup, legacy files, versions and RTO/RPO.

## HTTP search measurement

The load script measures `POST /knowledge/search/unified`: a member's own Requirement knowledge
and the published library passages the knowledge service returns. Library-only search load is
measured against the knowledge portal.

Prepare a UTF-8 JSON array of query strings, for example `["XGPON coverage", "high-speed orders"]`.
Use real representative queries for release qualification; the example is synthetic. Select the
environment explicitly and run:

```powershell
.venv/Scripts/python.exe -m tests.release_load --base-url https://your-staging-host --queries .data/qualification/queries.json --users 25 --requests 1000 --token-file .data/qualification/access-token.txt --output .data/qualification/search-load.json
```

Omit `--token-file` only for the fake-identity local test app. The file contains an existing access
token, not a username/password; never commit it. The command requires HTTPS for non-loopback bearer
tokens, does not follow redirects and does not print tokens, queries or response bodies. The target
must pass health/readiness before load begins. It invokes only read-only search, but a real provider
can incur query-embedding usage. Stop on provider quota errors; do not treat them as successful latency.

Results include total/successful requests, status/timeout/schema errors, empty results, successful
response p50/p95/max, throughput, client count and runtime. There is no excluded warmup or think time;
the clients form a closed-loop workload. Nonzero request errors return exit code 1. Preflight/input
failures also return nonzero and do not produce a successful report. `capacity_qualified` remains
false: the command cannot independently establish corpus size, relevance, support or ingestion fairness.

For production performance evidence, retain the release revision, infrastructure sizing, corpus and
embedding identity, eligible chunk count, query set and simultaneous ingestion workload with the
report. Measure database retrieval and actual query embedding separately using the deployed telemetry.
The parent gates remain one million chunks, 25 users, database p95 below 1s, HTTP p95 below 3s and no
ingestion starvation. A 100-request single-chunk local run is only harness validation.

## Final environment checks

Record hosted CI on the delivered commit, actual human retrieval/grounding judgments and model
configuration, scanner signature/clean/infected/outage checks, OCR English/Arabic and representative
Office rendering, quotas and monitored alert delivery. Rehearse maintenance, restored checksums,
worker crash/cancellation, provider outages and recovery on the intended deployment. Preserve the
existing owner approval and maintenance-window rules. Deployment approval remains pending until
these records exist; see `document-knowledge.md` and `production-readiness-maintenance.md`.
