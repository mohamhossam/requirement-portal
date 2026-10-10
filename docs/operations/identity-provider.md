# Identity provider: clients and token lifetimes

Requirement work trusts one OIDC issuer, the `requirement-ai` realm. Its export is
`deploy/keycloak/realm-requirement-ai.json`; `keycloak-login.md` covers setting it up. This
page says what each client is for, and how long its tokens and sessions last.

## The two clients

| Client | Kind | Used by | Gets tokens through | Token audience |
|---|---|---|---|---|
| `requirement-spa` | Public: no secret, because a browser cannot keep one | The React app, for each person signed in | Authorization code with PKCE (`S256`). Password and implicit grants are off. | `requirement-api`, plus the person's realm roles as `roles` |
| `requirement-service` | Confidential: Keycloak generates its secret | The API and worker, when they call the knowledge portal's internal API (ADR-0104) | Client credentials only. No browser flow, and no secret in the export. | `knowledge-internal` only (`fullScopeAllowed` is off) |

- The API accepts a person's token only when it names `requirement-spa` as its authorized party,
  unless `OIDC_AUTHORIZED_PARTIES` lists more clients (ADR-0018). An ID token is refused: only an
  access token (`typ: Bearer`) is accepted.
- `requirement-service`'s secret is `REQUIREMENT_SERVICE_CLIENT_SECRET`. `secrets.md` says how to
  rotate it.
- The knowledge portal has its own clients in the same realm. Its repository documents them.

## Token and session lifetimes

The realm export sets no lifetimes, so Keycloak's defaults apply. Change them under Realm
settings, then Sessions and Tokens. Re-importing the export does not overwrite a realm that
already exists.

| Setting | Default | What it means here |
|---|---|---|
| Access token lifespan | 5 minutes | How long a stolen access token is useful. The API also allows `OIDC_LEEWAY_SECONDS` (60) of clock skew. |
| SSO session idle | 30 minutes | A person idle this long signs in again. Each renewal counts as activity. |
| SSO session max | 10 hours | Everyone signs in again at least once a working day, however active. |
| Refresh tokens for `requirement-spa` | On | How the app renews without third-party cookies (below). |

The service client's tokens follow the same access token lifespan. The API and worker reuse each
one until 30 seconds before it expires, then fetch a new one, so its lifespan never shows to
anyone.

## How the app renews a person's token

The app (`frontend/src/auth/AuthProvider.tsx`) uses oidc-client-ts with automatic silent
renewal. About a minute before the access token expires, and whenever the API answers 401, it
renews:

1. **With the refresh token**, which Keycloak issued at sign-in. This is a direct request to
   Keycloak's token endpoint, so it needs no cookie. It keeps working in browsers that block
   third-party cookies (Safari, Firefox, and Chrome with them blocked) and when Keycloak is on
   another site than the app.
2. **With a hidden iframe** (`/auth/silent-callback`, `prompt=none`), only if there is no
   refresh token. This needs Keycloak's session cookie inside a third-party frame, which those
   browsers refuse. Renewal then fails, and the person is asked to sign in again.

So keep refresh tokens on for `requirement-spa`. A test (`test_keycloak_login_config.py`)
fails if the export turns them off.

The app keeps its tokens in `sessionStorage`: they are gone when the tab closes, and another tab
signs in on its own (through the Keycloak session, without a password while that lasts). The
Content-Security-Policy limits the scripts that could read them.

## Changing lifetimes

- **Shorter access tokens** shrink the window for a stolen token, at the cost of more renewal
  requests. Five minutes is a reasonable floor.
- **A longer SSO idle timeout** signs people out less often. It also keeps an unattended
  browser signed in longer. Match it to your organisation's screen-lock policy.
- **Offline tokens** (`offline_access`) are not used and should not be: they outlive the
  Keycloak session, so signing out would not end them.
