## What and why

<!-- What this changes, and the problem it solves. Link the slice, ADR or issue. -->

## Changes

<!-- The changes a reviewer should look at, grouped by area. -->

## Checklist

- [ ] Backend gates pass: `pytest` (with `TEST_DATABASE_URL`), `ruff check .`, `ruff format --check .`, `mypy src tests`, `lint-imports`.
- [ ] Frontend gates pass, if `frontend/` changed: `npm test`, `npm run lint`, `npm run typecheck`, `npm run build`, `npm run api:check`.
- [ ] Frontend logic changes (hooks, services, state, data fetching, API calls) are recorded in ADR-0109's "Exceptions on record".
- [ ] New environment variables are read only in `settings.py` and documented in `.env.example`; Compose-only variables are documented in `docs/operations/deployment.md`.
- [ ] Migrations are expand-only, or a contract step is named in `CHANGELOG.md` (ADR-0108).
- [ ] New public errors are in the catalogue and its status test.
- [ ] `CHANGELOG.md` says what changes for whoever deploys.

## Validation

<!-- Commands run and their results; anything not run locally and why. -->
