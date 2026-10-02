# Keycloak login operations

The application trusts one OIDC issuer: Keycloak. Keycloak provides local
administrator-created accounts and brokers Microsoft Entra ID. The React app
never receives a password.

The optional Compose stack pins Keycloak 26.7.3. Review Keycloak release and
migration notes before changing that version.

## Local setup

1. Install `mkcert`, trust its local certificate authority, and generate the
   files ignored by Git:

   ```powershell
   New-Item -ItemType Directory -Force deploy/keycloak/certs
   mkcert -cert-file deploy/keycloak/certs/local.crt -key-file deploy/keycloak/certs/local.key localhost 127.0.0.1 ::1
   ```

2. Put the required values in the repository's ignored `.env` file or the
   current shell. Do not commit them:

   ```dotenv
   KEYCLOAK_DB_PASSWORD=<random-database-password>
   KEYCLOAK_ADMIN=<bootstrap-admin-name>
   KEYCLOAK_ADMIN_PASSWORD=<random-bootstrap-password>
   REQUIREMENT_APP_ORIGIN=http://127.0.0.1:5173
   ENTRA_TENANT_ID=<tenant-id>
   ENTRA_CLIENT_ID=<broker-client-id>
   ENTRA_CLIENT_SECRET=<broker-client-secret>
   SMTP_HOST=<smtp-host>
   SMTP_PORT=587
   SMTP_FROM=<verified-sender-address>
   SMTP_USERNAME=<smtp-user>
   SMTP_PASSWORD=<smtp-password>
   ```

3. Start the identity service from the repository root:

   ```powershell
   docker compose --env-file .env -f deploy/keycloak/compose.yaml up -d
   ```

4. Configure the API to trust the local realm. The Python runtime and operating
   system must trust the `mkcert` root so discovery and JWKS verification remain
   enabled:

   ```dotenv
   IDENTITY_PROVIDER=oidc
   OIDC_ISSUER_URL=https://localhost:8443/realms/requirement-ai
   OIDC_AUDIENCE=requirement-api
   OIDC_CLIENT_ID=requirement-spa
   OIDC_SCOPES=openid profile email
   OIDC_COMPANY_SSO_ENABLED=true
   OIDC_COMPANY_SSO_ALIAS=company-sso
   OIDC_PASSWORD_LOGIN_ENABLED=true
   ```

Compose maps `KEYCLOAK_ADMIN` and `KEYCLOAK_ADMIN_PASSWORD` to Keycloak's
`KC_BOOTSTRAP_ADMIN_USERNAME` and `KC_BOOTSTRAP_ADMIN_PASSWORD` container settings.
These create a temporary administrator on the initial startup; they do not reset
an existing administrator. If an earlier startup already created the master realm
without an administrator, use Keycloak's [admin recovery procedure](https://www.keycloak.org/server/bootstrap-admin-recovery)
with all Keycloak nodes stopped instead of deleting the persistent database.

The realm import is an initial bootstrap. Once Keycloak has persisted the realm,
make later production changes through a reviewed export or an administrator
change process; restarting does not overwrite an existing realm.

## Microsoft Entra registration

Create a single-tenant Web application in Entra for Keycloak's confidential
broker connection. Register this exact redirect URI, replacing the host for
each environment:

```text
https://localhost:8443/realms/requirement-ai/broker/company-sso/endpoint
```

Record its tenant ID, client ID, and client secret in the deployment secret
store. The imported broker uses OIDC endpoints for that tenant and sets
`linkOnly=false` so explicitly linked users can sign in. Its first-login flow,
`deny-unlinked-company-sso`, contains only a **Required** **Deny access** execution.
Keycloak invokes this flow for identities without an existing federated link,
so neither new accounts nor links based on matching email can be created during
Microsoft login. Already-linked identities bypass this first-login flow.

For each authorized person, create one enabled Keycloak user with a verified
email. Give password users a temporary password so Keycloak requires a change
on first login. In the user's **Identity provider links** section, explicitly
link the matching Microsoft identity when SSO is allowed. Never enable automatic
linking based only on email.

### Updating an existing realm

The startup import does not apply these fixes to an existing realm. In the
administrator console, create a basic top-level flow named
`deny-unlinked-company-sso` containing only **Deny access**, set to **Required**.
For the `company-sso` identity provider, select that flow as **First login flow**
and save it **before** turning **Account linking only** off. Keep the provider
enabled and **Trust email** off. Do not enable broker login with the default
first-login flow: that flow can provision or link users.

The implementation follows Keycloak 26.7.3's [broker login handling](https://github.com/keycloak/keycloak/blob/26.7.3/services/src/main/java/org/keycloak/services/resources/IdentityBrokerService.java)
and built-in [Deny access authenticator](https://github.com/keycloak/keycloak/blob/26.7.3/services/src/main/java/org/keycloak/authentication/authenticators/access/DenyAccessAuthenticator.java).

## Recovery and security checks

Test the realm's SMTP connection before onboarding users. Password reset must
return the same visible result for known and unknown email addresses. Confirm
that reset links expire and cannot be reused, five failed attempts trigger the
configured temporary lockout, registration remains absent, and direct password
grants remain disabled.

Use stable Keycloak realm URLs in production. Application actor IDs are derived
from the issuer and subject. Before changing either, export the existing actor,
ownership, reviewer, draft, and approval mappings and run an explicit migration
that preserves those relationships.

## Staging acceptance

Production activation remains blocked until a staging environment verifies:

- local password login, temporary-password change, logout, and recovery email;
- Microsoft login for an explicitly linked account and denial for unlinked
  accounts with both a new email and an email matching an existing local user;
- no user or federated link created by either denied login attempt;
- API audience, issuer, signature, expiry, callback, and front-channel logout behavior;
- desktop and mobile login pages using the production hostname and certificate.
