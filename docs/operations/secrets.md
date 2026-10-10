# Secrets

Every secret the deployment holds: where it is set, how it reaches the processes, and how to
rotate it. `deployment.md` has the first-install steps.

## Values or files

Each application secret below can be set two ways:
- as `NAME`, in `deploy/production.env`;
- as `NAME_FILE`, naming a file that holds the value, such as a Docker or Kubernetes secret
  mounted at `/run/secrets/...`.

A file keeps the value out of the process environment and out of `docker inspect`. Settings
(`infrastructure/config/settings.py`) read either form. The boot stops when both are set, or
when the file is missing or empty.

| Secret | `NAME` / `NAME_FILE` | Used for |
|---|---|---|
| Database password | `DATABASE_PASSWORD` / `DATABASE_PASSWORD_FILE` | Filled into a `DATABASE_URL` that names a user and no password. A URL that already has one is refused, so the two cannot disagree. |
| OpenAI key | `OPENAI_API_KEY` / `OPENAI_API_KEY_FILE` | `LLM_PROVIDER=openai` |
| OpenRouter key | `OPENROUTER_API_KEY` / `OPENROUTER_API_KEY_FILE` | `LLM_PROVIDER=openrouter` |
| Model profile keys | the profile's `api_key_env`, or that name with `_FILE` | `LLM_PROVIDER=profiles` (`llm-configuration.md`) |
| Shared service tokens | `REQUIREMENT_SERVICE_TOKEN`, `KNOWLEDGE_SERVICE_TOKEN`, each with `_FILE` | Calls between the portals (ADR-0099) |
| Service client secret | `REQUIREMENT_SERVICE_CLIENT_SECRET` / `_FILE` | This service's client-credentials grant (ADR-0104) |

Compose's own secrets are set in the shell or `deploy/.env`, not `production.env`:

| Secret | Where it goes |
|---|---|
| `POSTGRES_PASSWORD` | The bundled database's role password, and the default `DATABASE_URL`. The monitoring overlay's PostgreSQL exporter reads it as a secret file. |
| `GRAFANA_ADMIN_PASSWORD` | Grafana's first admin password, used only when Grafana creates its database. |
| `ALERTMANAGER_URL` | The alert receiver's URL. Alertmanager writes it to a private file and never into its configuration. |
| `KERNEL_READ_TOKEN` | Read access to platform-kernel while building the backend image. Passed as a BuildKit secret, never stored in a layer. |

No OIDC secret is held: the browser client is public, and the issuer's signing keys are fetched
and rotated automatically (ADR-0018).

To use files with Compose, add an override that mounts them and names them. For example, for
the OpenAI key:

```yaml
# deploy/compose.secrets.yaml (yours, not in the repository)
services:
  api:
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key
    secrets: [openai_api_key]
  worker:
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key
    secrets: [openai_api_key]
secrets:
  openai_api_key:
    file: /etc/requirement-platform/openai_api_key
```

Remove `OPENAI_API_KEY` from `production.env` when you add its file.

## Rotating

After each rotation, check that `/api/ready` answers 200. Then start one AI job, or one call to
the knowledge portal, to show the new value works.

### Database password

The bundled database applies `POSTGRES_PASSWORD` only when it first creates its data directory,
so change the role itself:

1. `docker compose -f deploy/compose.production.yaml exec postgres psql -U smb -d smb_requirements -c "ALTER ROLE smb PASSWORD '<new>'"`
2. Set the new value in `POSTGRES_PASSWORD`, or in the file `DATABASE_PASSWORD_FILE` names.
3. `docker compose -f deploy/compose.production.yaml up -d`. The API and worker reconnect with
   the new password, and connections already open keep working until then.

For a managed PostgreSQL, change the password with the provider, then update `DATABASE_URL`, or
the password file if the URL has no password.

### Model provider keys

1. Create a new key with the provider.
2. Set it, or replace its file.
3. `docker compose -f deploy/compose.production.yaml up -d api worker`.
4. Revoke the old key once jobs succeed with the new one.

### Service client secret

1. In Keycloak, open Clients, then `requirement-service`, then Credentials, and choose
   Regenerate.
2. Set the new `REQUIREMENT_SERVICE_CLIENT_SECRET`, or replace its file.
3. Restart `api` and `worker`.

Tokens granted with the old secret stay valid until they expire, a few minutes. Calls to the
knowledge portal fail in between, and their workers retry them.

### Shared service tokens

Each side accepts one shared token per caller, so a rotation is a short coordinated restart:
1. Generate a new token: `openssl rand -hex 32`.
2. Set it on both portals, on the calling side and the receiving side.
3. Restart both portals' API and worker together.

Calls in between are refused and retried by the background workers. Client credentials avoid
this entirely, because each service holds only its own secret: move to them (`deployment.md`,
"Service credentials").

### Alert receiver URL

1. Set the new `ALERTMANAGER_URL`.
2. `docker compose ... -f deploy/compose.monitoring.yaml up -d alertmanager`.
3. Send a test alert (`deployment.md`, "Monitoring add-on"), then delete the old webhook.

### Grafana admin password

Change it in Grafana's user settings. `GRAFANA_ADMIN_PASSWORD` is read only when Grafana first
creates its database.

### Build token

Create a new fine-grained token with read-only Contents on platform-kernel. Export it as
`KERNEL_READ_TOKEN` for builds, and update the CI secret of the same name. Then revoke the old
token.
