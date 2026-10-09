# Enhancement 8A.2 — Active Directory login with Keycloak-managed roles

> Status: **planned; not started.** Decisions recorded 2026-09-26. Implementation
> must not begin until this spec is scheduled in `ROADMAP.md`.

## Objective

People sign in with their existing Active Directory credentials. Keycloak
checks the password against AD through LDAP user federation, and decides what
each person may do through Keycloak-managed roles carried in the access token.
Only people granted the `app_user` role can use the application.

## User Outcome

A colleague opens the application, chooses the company sign-in, and enters the
same username and password they use for Windows. If an administrator has
granted them access in Keycloak, they land in the workspace with the right
permissions. If not, Keycloak tells them they have no access and no session is
created. Nobody has a separate password for this application.

## Recorded decisions

| # | Question | Decision |
|---|---|---|
| 1 | Directory type | Microsoft Active Directory |
| 2 | Where roles are assigned | In Keycloak (groups carrying client roles), not derived from AD groups |
| 3 | Who may sign in | Only people with the `app_user` role |
| 4 | Application-side role check | Yes, as defense in depth behind the Keycloak gate |
| 5 | Microsoft Entra SSO and local Keycloak accounts | Removed. AD replaces both; only Keycloak's own emergency administrator remains, in the `master` realm |
| 6 | Existing users and data | None; the application is in development. No actor-ID migration is required |

## Current state (as found)

- The API validates Keycloak bearer tokens (ADR-0018, ADR-0040) and reads roles
  from the top-level claim named by `OIDC_ROLES_CLAIM` (default `roles`).
- The application enforces two global roles: `knowledge_reader` and
  `knowledge_maintainer` (ADR-0068). Requirement owner and reviewer are
  per-Requirement access records owned by the application and are unaffected.
- `deploy/keycloak/realm-requirement-ai.json` defines **no roles and no role
  mapper**. Keycloak's default places realm roles under `realm_access.roles`,
  so no Keycloak role reaches the application today.
- The audience mapper names a `requirement-api` client that the realm does not
  define.
- Any authenticated person can use the whole Requirement workflow.
- The realm assumes Keycloak-held passwords: password reset, a password policy,
  SMTP, temporary passwords, and the `company-sso` Entra broker with its
  `deny-unlinked-company-sso` first-login flow.

## In Scope

### Keycloak realm (`deploy/keycloak/realm-requirement-ai.json`)

**Roles and token contents**
- Add a `requirement-api` client that holds the application's roles, with every
  login flow disabled (it is a resource, not a login client). Client roles:
  - `app_user`: may use the application;
  - `knowledge_reader`;
  - `knowledge_maintainer`.
- Add groups that carry those roles, so administrators grant access by group
  membership:
  - `requirement-ai-users` → `app_user`;
  - `requirement-ai-knowledge-readers` → `app_user`, `knowledge_reader`;
  - `requirement-ai-knowledge-maintainers` → `app_user`, `knowledge_reader`,
    `knowledge_maintainer`.
- On `requirement-spa`, add a **User Client Role** mapper for client
  `requirement-api`:
  - claim name `roles`, multivalued;
  - access token and introspection only; not in the ID token or userinfo.
- Set `fullScopeAllowed=false` on `requirement-spa`, and scope-map only the three
  `requirement-api` roles, so tokens carry nothing else.
- Confirm the existing audience mapper now produces `aud: requirement-api`.
- Set the access-token lifespan to 300 seconds; that bounds how long a role
  change takes to apply. Set the SSO session idle and maximum times explicitly
  (proposed: 30 minutes and 10 hours).

**Active Directory federation (LDAP user storage provider)**

Connection:
- vendor Active Directory;
- `ldaps://` (or `ldap://` with StartTLS), with the AD CA trusted through
  Keycloak's truststore (`KC_TRUSTSTORE_PATHS`);
- bind with a dedicated read-only service account:
  - its DN comes from `${LDAP_BIND_DN}`;
  - its password comes from the `${LDAP_BIND_CREDENTIAL}` placeholder, filled
    from the environment like the current SMTP settings. The password never
    appears in the repository.

Users:
- users DN `${LDAP_USERS_DN}`, subtree search, pagination on;
- user object classes `person, organizationalPerson, user`;
- username attribute `sAMAccountName`, RDN `cn`, UUID `objectGUID`;
- a user filter that excludes disabled accounts:
  `(!(userAccountControl:1.2.840.113556.1.4.803:=2))`.

Sync behaviour:
- edit mode `READ_ONLY`, so Keycloak never writes to AD;
- import users on; sync registrations off; Kerberos off;
- changed-users sync hourly, full sync daily.

Mappers:
- username ← `sAMAccountName`;
- email ← `mail`;
- first name ← `givenName`;
- last name ← `sn`;
- **MSAD account controls**, so disabled, locked or expired AD accounts and
  expired passwords are refused at login.

**Who may sign in**
- Copy the browser flow as `requirement-ai-browser` and bind it as the realm's
  browser flow.
- After the username and password step, add a conditional sub-flow:
  - **Condition – user role** for `requirement-api` `app_user`, with *negate
    output* on;
  - then **Deny access** (Required).
- A person without `app_user` therefore receives no token and sees Keycloak's
  themed access-denied page.

**Removed**
- The `company-sso` identity provider and the `deny-unlinked-company-sso` flow.
- Password reset (`resetPasswordAllowed=false`), temporary-password handling,
  the realm password policy, and the SMTP server block. Passwords are managed
  in AD.
- Registration stays off, and direct password grants stay off.

**Kept**
- Brute-force protection. Its failure threshold must be lower than the AD
  domain lockout threshold, so failed logins here cannot lock the AD account.

### Keycloak deployment (`deploy/keycloak/compose.yaml`)

- New variables: `LDAP_CONNECTION_URL`, `LDAP_BIND_DN`, `LDAP_BIND_CREDENTIAL`
  and `LDAP_USERS_DN`, plus a mounted AD CA certificate added to the truststore.
- Drop the `ENTRA_*` and `SMTP_*` requirements.
- Add a development-only Active Directory: a Samba 4 AD domain controller
  container behind a `ldap-dev` Compose profile, pinned by digest (image chosen
  at implementation). A provisioning script creates:
  - a service account;
  - `alice.user` (app_user);
  - `rita.reader` (knowledge reader);
  - `max.maintainer` (knowledge maintainer);
  - `nora.noaccess` (no roles);
  - `dave.disabled` (disabled in AD).

  Their Keycloak group memberships are set by a documented bootstrap step. This
  exists only to exercise the real AD attribute set locally. OpenLDAP lacks
  `sAMAccountName`, `objectGUID` and `userAccountControl`.

### Application

- **App-side role check (defense in depth):**
  - `ResolveCurrentActor` refuses an authenticated actor that lacks the required
    role, raising `AuthorizationDeniedError` (HTTP 403).
  - The check runs **before** the actor is recorded in the known-actor
    directory, so refused people never appear as assignable reviewers.
  - The required role comes from a new setting, `OIDC_REQUIRED_ROLE` (default
    `app_user`). It applies only when `IDENTITY_PROVIDER=oidc`.
- **Fake identity:** add `app_user` to all three fake personas, so offline
  development and tests behave as before.
- **Login label:** add a setting `OIDC_PASSWORD_LOGIN_LABEL` so `/identity/config`
  can say "Continue with your company account" instead of "Continue with email
  and password". Deployments set `OIDC_COMPANY_SSO_ENABLED=false`. The dormant
  company-SSO code path stays; removing it is out of scope.
- `.env.example` and `deploy/production.env.example` document the new and
  changed settings.

### Documentation

- `docs/operations/keycloak-login.md` rewritten for AD:
  - prerequisites to request from the AD team;
  - realm bootstrap, and step-by-step instructions for an already-persisted
    realm;
  - how to grant and remove access through groups;
  - lockout alignment and session revocation (**Sign out all sessions**);
  - the staging checklist below.
- New ADR-0080 recording AD federation through Keycloak and Keycloak client
  roles as the source of global roles. It supersedes the Entra and
  local-password parts of ADR-0040.
- `README.md` and `START_GUIDE.md` sign-in references updated.

## Out of Scope

- Deriving roles from AD groups (decision 2). Adding a group-LDAP mapper later
  is possible without application changes.
- Kerberos/SPNEGO single sign-on, multi-factor authentication, self-service
  password change.
- Looking people up in AD before they have signed in, for example to assign a
  reviewer who has never logged in. The known-actor directory still lists only
  signed-in actors (ADR-0018). This is a separate, later decision.
- Removing the company-SSO code path from the API and SPA.
- Actor-ID migration (decision 6: no existing users).
- A dedicated in-app "no access" screen. The Keycloak gate stops people without
  access before the app. The app-side 403 is only reachable through a Keycloak
  misconfiguration and shows the existing error state. A dedicated screen would
  be a frontend change under the redesign rules and needs its own decision.

## Domain

- No change. `ActorProfile.roles` already carries provider-neutral global roles.

## Application Use Cases

- `ResolveCurrentActor` gains the required-role precondition described above.
  No other use case changes. Knowledge roles keep their existing checks.

## Ports

- No change. `IdentityProviderPort` and `ActorDirectoryPort` are unchanged.

## Adapters

- The OIDC adapter is unchanged: it already reads a top-level multivalued `roles`
  claim.
- The fake identity adapter adds `app_user` to its personas.

## API

- Protected routes return 403 `AuthorizationDeniedError` for an OIDC actor
  without `OIDC_REQUIRED_ROLE`.
- `GET /identity/config` returns the configurable password-login label.
- The OpenAPI schema is unchanged unless the error body changes; regenerate and
  check it.

## UI

- No frontend code change. The login choice list comes from `/identity/config`.
  AD sign-in happens on Keycloak's themed page. The Keycloak login theme's
  messages gain AD-specific wording: "Sign in with your company account", an
  access-denied explanation, and where to reset a forgotten password.

## Business Rules

- Passwords live only in Active Directory. Neither Keycloak nor the application
  stores or resets them.
- Access requires `app_user`, granted only by a Keycloak administrator through
  group membership. AD membership alone grants nothing.
- Global roles come only from the access token. Per-Requirement owner and
  reviewer access remains application data.
- A person disabled in AD cannot start a new session. Existing sessions end
  within the SSO idle timeout, or at once when an administrator signs them out.
- A role change applies at the next access-token refresh, within 5 minutes.
- If AD is unreachable, new logins fail closed. Existing sessions continue
  until they expire.
- Never delete and re-create the AD federation provider. That deletes the
  imported users and changes their Keycloak IDs, which are the application's
  actor IDs.

## Tests

- **Unit, application:** `ResolveCurrentActor` accepts an actor with the
  required role; refuses one without it with `AuthorizationDeniedError`; and
  does not record a refused actor in the directory. Fake mode is unaffected.
- **Unit, settings:** `OIDC_REQUIRED_ROLE` and `OIDC_PASSWORD_LOGIN_LABEL`
  defaults and validation; `/identity/config` label contract.
- **API:** a protected route returns 403 for an OIDC token without `app_user`,
  and 200 with it.
- **Realm structure:** rewrite `tests/unit/test_keycloak_login_config.py`, which
  currently asserts the Entra broker. It must check:
  - the `requirement-api` client and its three roles;
  - the groups and their role mappings;
  - the `roles` mapper is access-token only;
  - `fullScopeAllowed=false`;
  - the AD provider is `READ_ONLY`, with `ldaps` or StartTLS and the
    account-controls mapper;
  - the bind credential is a `${…}` placeholder;
  - the `app_user` deny sub-flow is bound as the browser flow;
  - no identity providers; reset, registration and direct grants are off.
- **Compose:** `docker compose config` for the Keycloak stack with and without
  the `ldap-dev` profile; image pins covered by `test_image_pins.py`.
- **Local end-to-end (scripted, against Keycloak and the Samba AD dev
  container):**
  - `alice.user` signs in and reaches the worklist;
  - `max.maintainer` can maintain architecture knowledge, and `rita.reader`
    cannot;
  - `nora.noaccess` and `dave.disabled` are refused by Keycloak;
  - a wrong password fails;
  - a role removed in Keycloak disappears after token refresh.

  Whether this also runs in CI is decided at implementation, based on runtime
  cost.

## Acceptance Criteria

- [ ] AD users sign in with their AD username and password; no password is stored by Keycloak or the application.
- [ ] Only users with `app_user` receive a token; others see Keycloak's access-denied page.
- [ ] The application independently returns 403 for a token without `app_user`, and refused users are not added to the known-actor directory.
- [ ] `knowledge_reader` and `knowledge_maintainer` granted through Keycloak groups control Architecture knowledge exactly as before.
- [ ] Disabled or locked AD accounts cannot sign in.
- [ ] Microsoft Entra brokering, local Keycloak user accounts, password reset and SMTP are removed from the realm; only the `master` realm emergency administrator remains.
- [ ] Fake identity remains account-free, and all personas keep working.
- [ ] Realm, Compose and application tests pass; all backend and frontend quality gates are green; CI is green.
- [ ] Staging acceptance below is complete.

## Staging acceptance

Against the real AD, using the production hostname and certificate:
- an AD login succeeds, and a wrong password fails;
- a disabled AD account is refused;
- a user without `app_user` is refused, and no token is issued;
- Keycloak's lockout triggers before AD's;
- adding and removing `knowledge_maintainer` takes effect within 5 minutes;
- during an AD outage new logins fail closed, while existing sessions continue;
- logout and front-channel logout work;
- the token's issuer, audience, signature and expiry are validated by the API;
- the desktop and mobile Keycloak pages show the AD wording.

## Prerequisites from the AD team

- LDAPS host and port, or StartTLS support, and the issuing CA certificate.
- A read-only service account, with its DN and password delivered through the
  secret store.
- The users' base DN (OU) to search.
- The domain lockout threshold and observation window, to set Keycloak's lower
  threshold.
- Whether people sign in with `sAMAccountName` (proposed) or `userPrincipalName`.

## Files expected to change

- `deploy/keycloak/realm-requirement-ai.json`
- `deploy/keycloak/compose.yaml`
- `deploy/keycloak/ldap-dev/` (new: Samba AD provisioning)
- `deploy/keycloak/themes/requirement-ai/login/messages/messages_en.properties`
- `src/smb_requirement_agent/application/use_cases/identity_access.py`
- `src/smb_requirement_agent/infrastructure/config/settings.py`
- `src/smb_requirement_agent/infrastructure/config/settings_validation.py`
- `src/smb_requirement_agent/identity/infrastructure/fake_identity.py` (moved by ADR-0103 PR 7)
- `src/smb_requirement_agent/interfaces/api/container.py`
- `src/smb_requirement_agent/interfaces/api/routes/identity.py`
- `tests/unit/test_keycloak_login_config.py`, `tests/unit/test_identity_access.py`,
  and the settings and API identity tests
- `.env.example`, `deploy/production.env.example`
- `docs/operations/keycloak-login.md`, `docs/architecture/adr-0080-…`,
  `README.md`, `START_GUIDE.md`

## Validation Evidence

None yet; not started.
