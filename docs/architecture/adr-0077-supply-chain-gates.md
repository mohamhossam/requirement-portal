# ADR 0077 — Supply-chain gates in CI

## Status

Accepted.

## Context

The second review found no dependency or image scanning, base images pinned
only by mutable tag, and no coverage measurement. The first audit found:

- **Pillow 11.3.0** (35 advisories) and **pypdf 5.9.0** (77 advisories). Both
  parse untrusted uploads, and both were held back by upper version bounds.
- **js-yaml**, 2 high advisories in the OpenAPI type generator, a dev
  dependency.
- **The web base image**, `nginx-unprivileged:1.27-alpine`, carried 38 fixable
  HIGH or CRITICAL issues (OpenSSL, c-ares).

## Decision

- **Dependency audits** run in a CI `supply-chain` job:
  - `pip-audit --strict` over the locked export of what the image ships, with
    no dev tools;
  - `npm audit --audit-level=high` over all frontend dependencies, because dev
    tooling runs in CI and builds the served bundle;
  - (added by the third review remediation) `pip-audit --strict` over the
    export that includes the optional `document-ocr` extra (docling). The
    image omits it, but an operator who extends the image for OCR installs
    that tree.
- **Image scan.** The `deployment` job scans both built images with Trivy
  (pinned by digest). It fails on HIGH or CRITICAL issues that have a fix.
- **Digest pinning.** Every third-party image is pinned as `tag@sha256:…` in the
  Dockerfiles, both compose files and CI services.
  `tests/architecture/test_image_pins.py` enforces this and requires one
  PostgreSQL image everywhere.
- **Action pinning** (added by the third review remediation). Every GitHub
  Action is pinned by full commit SHA, with its release in a trailing
  `# vX.Y.Z` comment. `tests/architecture/test_action_pins.py` enforces this.
  A tag can be moved upstream and would change what runs with the
  repository's CI credentials. Dependabot updates the SHAs.
- **Security patches in the web image.** It runs `apk upgrade` at build time, so
  Alpine fixes published between base releases are included.
- **Dependabot** proposes weekly updates for uv, npm, Dockerfiles, compose
  files and GitHub Actions. That is how pins and bounds move.
  **Amended 2026-09-25**, after enabling it on `main` opened 15 PRs at once.
  - Actions updates are one grouped PR.
  - Each ecosystem has at most three open PRs.
  - Runtime and database majors are ignored: Python beyond 3.12, Node majors
    and PostgreSQL majors are deliberate upgrades, not image bumps.
- **Coverage floors.** Backend coverage must stay at or above 92% of
  statements (`[tool.coverage.report]`), just below the measured baseline.
  It was 90% against a 92% baseline, and was raised when the third review
  remediation measured 92.44%. Frontend floors sit
  just below the 2026-09-24 baseline (`vitest.config.ts`). Local `pytest` stays
  fast; CI measures.

## Consequences

- A new advisory can turn CI red without a code change. That is intended: the
  fix is a Dependabot PR, or a bounded upgrade like Pillow 12 and pypdf 6 here.
- `apk upgrade` makes the web image depend on build time, not only on the pinned
  digest. The digest still pins the nginx and Alpine release; only security
  patches float. The third review raised this again and it stays: a
  build-time dependency is the price of not shipping known-fixed OpenSSL
  and c-ares issues while waiting for a new base release.
- Coverage floors only ratchet up. Lowering one needs a stated reason in its
  commit.

## Alternatives Considered

- **Audit dev dependencies for Python too.** Deferred. Python dev tools never
  reach an image or the browser. The Python audit covers what ships.
- **Pin GitHub Actions by tag only.** Initially chosen, then replaced by SHA
  pinning in the third review remediation. A moved tag changes CI without a
  commit, and Dependabot updates SHA pins just as well.
