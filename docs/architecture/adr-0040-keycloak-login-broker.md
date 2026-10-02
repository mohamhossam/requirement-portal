# ADR 0040 — Keycloak login broker for password and company SSO

## Status

Accepted

## Context

ADR-0018 established one provider-neutral OIDC boundary, but the browser only
offered a generic redirect. The product now needs administrator-provisioned
password accounts and Microsoft company SSO without receiving credentials or
introducing provider-specific identities into the application.

## Decision

- Keep Keycloak as the application's single OIDC issuer. Keycloak owns local
  passwords, recovery email, brute-force protection, and the Microsoft Entra
  identity broker.
- Keep Authorization Code with PKCE and session-storage tokens in the SPA. The
  public identity configuration adds labelled login choices and bounded OIDC
  authorization parameters; selecting Microsoft supplies only
  `kc_idp_hint=company-sso`.
- Disable self-registration, implicit flow, password grants, and automatic
  email-based broker linking. Administrators create local users and explicitly
  link Microsoft identities before either method can access the application.
- Theme Keycloak's credential, recovery, required-action, and error pages to
  match the application. The application never renders or submits passwords.
- Preserve the current actor derivation from issuer plus subject. A deployed
  issuer change requires an ownership-mapping audit and explicit migration.

## Consequences

The domain, application ports, access records, and persistence schema do not
change. Credentials remain inside Keycloak, and the existing API bearer-token
validation remains authoritative. Production now depends on a durable Keycloak
database, HTTPS, SMTP, and an Entra application registration. End-to-end Entra
and email recovery validation requires a configured staging environment.

## Alternatives Considered

- Application-owned passwords were rejected because they would duplicate
  credential storage, session, recovery, and abuse-protection responsibilities.
- Direct browser authentication against Entra plus a separate password issuer
  was rejected because two issuers would change actor identity and complicate
  token validation and ownership continuity.
- Automatic linking by matching email was rejected because an email match is
  not sufficient proof that two identities belong to the same person.
