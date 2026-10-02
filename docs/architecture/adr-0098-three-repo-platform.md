# ADR 0098 — A three-repository platform beside the original application

## Status

Accepted 2026-10-02. Supersedes Knowledge Center decision 2
(`docs/slices/enhancement-knowledge-center.md`, "a separate area inside the same application").

## Context

The shared reference library, the architecture catalogue and the squad (organisation) catalogue
are organisation-wide knowledge that knowledge administrators curate. They lived inside the
requirements application's Documents area. That area served two audiences:
- people doing requirement work, who need their attachments;
- administrators curating knowledge every requirement reasons with.

Requirement attachments belong to the first audience. The rest belongs to the second.

The product owner wanted that knowledge to become its own product, with its own interface, its own
service and its own data. They also wanted the running application,
`mohamhossam/smb-ai-requirement-agent`, left exactly as it is while the new platform is built.

## Decision

**Three new repositories, each a fresh start from `smb-ai-requirement-agent@d5cfb57`, with no
carried history.**

| Repository | Owns |
|---|---|
| `requirement-portal` (this repository) | The requirements service, its worker, its database, its UI (the Working Paper design system), **and the deployment of the whole platform** (`deploy/`) |
| `knowledge-portal` | The shared library, the architecture catalogue and the squad catalogue: its own API, worker, database and UI, with its own design system. Open to the `knowledge_admin` role only |
| `platform-kernel` | The Python package `smb_kernel`: shared mechanisms with no business meaning (ADR-0100). Both services pin it by git tag |

**The original repository lives in parallel.** `smb-ai-requirement-agent` stays maintained and
deployed, and nothing in this work commits to it. Each new repository keeps an `UPSTREAM.md`
recording:
- the original commit it was synced to;
- every fix ported since.

Porting is a deliberate, reviewed pull request, never automatic.

**One origin.** The platform is served from one host:
- `/` and `/api/` serve requirement-portal;
- `/knowledge/` and `/knowledge-api/` serve knowledge-portal;
- `/knowledge-api/internal/` is denied at the edge.

One Keycloak client covers both SPAs, so there is no CORS. The new platform runs on its own
origin, apart from the original deployment.

**Requirement attachments stay** with requirement-portal. People who are not knowledge
administrators keep **read-only** evidence and passage viewers inside requirement-portal, so
citations and impact evidence stay traceable.

The service boundary and data split are in ADR-0099; the kernel rule is in ADR-0100.

## Consequences

- **Curation becomes a separate product.** Knowledge curation can change on its own cadence, in
  its own interface, without a requirements release.
- **Fixes are made twice while the original lives.** A fix in `smb-ai-requirement-agent` reaches
  the new platform only by an explicit port. Until the original is retired, `UPSTREAM.md` is the
  only record of the gap.
- **Three CI pipelines and a release step.** Kernel changes ship as tagged releases, which
  Dependabot bumps in each service. The services can run different kernel versions for a while.
- **Deployment is centralised here.** knowledge-portal publishes images only. This repository's
  `deploy/` pulls them by tag and owns nginx routing, compose and the Keycloak realm.
- **The history is in the original repository.** `git blame` in the new repositories stops at
  the import commit. Earlier history is in `smb-ai-requirement-agent` up to `d5cfb57`.

## Alternatives Considered

- **An area inside the same application** (Knowledge Center decision 2). It was rejected because
  the product owner wanted a separate service, interface and database.
- **Split the original repository in place.** It was rejected because the original must stay
  untouched and keep running.
- **A separate hostname for the knowledge portal.** It was rejected for now: it needs a second
  Keycloak client or redirect set, CORS or a second proxy, and a second CSP, for no user benefit.
- **A shared UI package.** It was rejected because each portal gets its own design system.
- **Carrying git history with `git filter-repo`.** It was declined in favour of a fresh start
  that points back to the original.
