# ADR 0100 — The platform kernel holds mechanisms, never meaning

## Status

Accepted 2026-10-02. Follows ADR-0098.

## Context

requirement-portal and knowledge-portal both need certain machinery:
- validating Keycloak tokens;
- scanning and extracting uploaded files safely;
- calling models for structured output, and embedding text;
- running migrations against PostgreSQL;
- correlating logs across services;
- calling each other.

Copying that machinery into both repositories would mean every security fix is made twice. A
loose shared library, on the other hand, would turn into a back door for coupling the two domains.

## Decision

**`mohamhossam/platform-kernel` publishes the Python package `smb_kernel`.** Both services pin it
by release tag, as a standard direct reference that pip (used by the launchers) and uv both read:

```toml
dependencies = [
    "smb-platform-kernel @ git+https://github.com/mohamhossam/platform-kernel@v1.0.0",
]
```

**The rule: mechanisms only, never meaning.**

| Area | In the kernel | Stays in each app |
|---|---|---|
| Identity | OIDC/JWKS validation, the identity-provider port, actor primitives (`ActorId`, `ActorProfile`, `ActorSnapshot`), the fake-provider mechanism | Authorization and business roles (requirement assignments, `knowledge_admin` checks), fake persona lists |
| Documents | Secure extraction and scanning: the extractor port, the bounded subprocess extractor, format extractors, OCR, the Office renderer, the ClamAV and offline scanners, the storage port | Ingestion workflows: attachment ingestion, library review and publication |
| LLM | Transport and structured-output mechanics, response sanitising, model profiles | Prompts, schemas, and adapters that interpret output into the domain |
| Embeddings | The generic configured embedding adapter and its profile | Retrieval behaviour |
| Persistence | Connectors, the transaction-manager port and its in-memory version, `run_migrations(url, migrations_package)` | Schemas, migrations, repositories, in-memory repositories |
| Operations | Logging, metrics setup, correlation, the clock port and clocks, the body-size limit, infrastructure error bases | Domain metrics and domain errors |
| Internal HTTP | Service-token middleware, and an `InternalHttpClient` with timeouts, retries, correlation forwarding and error mapping | API request and response models, and contracts |

**How the rule is enforced and released:**
- The kernel's import-linter forbids importing `smb_requirement_agent` or `knowledge_portal`.
- The kernel follows semantic versioning, and a tag is cut only on green CI.
- Dependabot raises bump pull requests in both services.

## Consequences

- **Security fixes are made once.** A fix to token validation, file scanning or extraction limits
  ships in one release.
- **Shared changes take two steps.** A kernel change ships only after a kernel release and a bump
  in each service. During that gap the services may run different kernel versions.
- **Builds need access to the kernel.** CI and Docker builds need read access to the kernel
  repository through a build secret. Air-gapped builds need vendored wheels.
- **The kernel cannot carry business decisions.** A change that needs business meaning (a role
  name, a prompt, a DTO) belongs in an app. Reviewers reject it in the kernel.

## Alternatives Considered

- **Copy now, extract later.** It was rejected because security-sensitive code would drift between
  copies.
- **Publish the kernel from this repository.** It was rejected because kernel releases would then
  be tied to this repository's history and CI.
- **Share API models through the kernel.** It was rejected: it couples the services' release
  cycles and hides contract breaks that contract tests would catch.
