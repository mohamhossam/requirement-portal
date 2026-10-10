# Security policy

## Reporting a vulnerability

Report it privately through GitHub: open the repository's **Security** tab and choose
**Report a vulnerability**, or go to
<https://github.com/mohamhossam/requirement-portal/security/advisories/new>.

Please don't open a public issue, pull request or discussion for a vulnerability.

A useful report says:

- what an attacker can do, and what they need first (an account, a role, network access);
- the affected version (`GET /api/health` reports it) or commit;
- steps to reproduce, or a proof of concept;
- any configuration it depends on, such as the identity provider or a deployment setting.

Reports are handled in the private advisory. A fix ships in a release; the advisory is
published, with credit if you want it, once a fixed release is available.

## Supported versions

| Version | Supported |
|---|---|
| The latest release (`v0.1.x`) | Yes |
| `main` | Yes, ahead of the next release |
| Anything older | No: upgrade to the latest release |

Releases are signed images published by tag (`docs/operations/deployment.md`, "Releases and
upgrades"). A new vulnerability in a released image's packages is found by the weekly rescan.

## What is in scope

The requirement portal's API, worker, web image and their deployment manifests in this
repository. The knowledge portal and the platform kernel are separate repositories with
their own policies.

Known and accepted risks are recorded in
`docs/architecture/adr-0111-accepted-risks.md`; a report that one of them is more serious
than recorded there is welcome.
