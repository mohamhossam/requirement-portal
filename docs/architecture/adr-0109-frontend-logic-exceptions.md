# ADR 0109 — Frontend logic changes during the UI redesign are recorded exceptions

## Status

Accepted 2026-10-08 by the repository owner ("grant an exception" for the production-hardening
frontend fixes), and recorded 2026-10-09 with production hardening PR 5. It does not change
CLAUDE.md's rule. It records how exceptions to that rule have been granted, so each one is
deliberate and can be found.

## Context

CLAUDE.md limits frontend work during the UI redesign to presentation: hooks, services, state
logic, data fetching and API calls are not changed, and a redesign that seems to need such a
change stops and raises it. That keeps the redesign from mixing behaviour changes into visual
ones.

Some defects cannot be fixed by presentation, because they live in the request and session code
itself:
- a browser that sends a request that can only fail;
- a browser that duplicates work;
- a browser that shows another identity's answer;
- a browser that leaves the person on a blank page.

The owner has allowed such fixes case by case:
- G3, G4 and G6 of `docs/slices/fix-ai-job-trace-gaps.md` (2026-10-08);
- the knowledge-portal link of `docs/slices/enhancement-independent-portals.md` (2026-10-09);
- the frontend items of `docs/slices/production-hardening.md`:
  - PR 4a, mapping through the job routes;
  - PR 5;
  - PR 12.

Until now these were recorded only in their own slices, and AGENTS.md's debt register still
described frontend logic fixes as deferred until the redesign.

## Decision

**A frontend logic change during the redesign is allowed only as a recorded exception:**
- **Approved.** The repository owner approves it, before or with the change.
- **Named.** The slice or PR names the files whose logic changes, under an "Exception to
  CLAUDE.md's presentation-only rule" heading or an "(exception)" label.
- **Narrow.** It is limited to correctness, safety or recovery that presentation cannot provide:
  - requests that can only fail;
  - duplicated work;
  - data crossing identities;
  - unrecoverable failure states;
  - contract drift.
- **Separate.** It ships in its own PR, not inside a redesign change.
- **Tested.** The behaviour it changes has a test.

An exception sets no precedent for the redesign: it changes behaviour, not the look.

**Exceptions on record:**
- **G3, G4, G6** (`fix-ai-job-trace-gaps.md`): job starts that can only fail are refused locally,
  workspace invalidation waits for in-flight reads, and a start whose outcome is unknown keeps
  its idempotency key (`startKeys.ts`).
- **Independent portals:** the knowledge-portal link comes from `VITE_KNOWLEDGE_PORTAL_URL`, and
  every link to it is hidden when the variable is empty.
- **Production hardening PR 4a:** architecture mapping runs through the job routes
  (`features/architecture/runMappingJob.ts`).
- **Production hardening PR 4b:** client functions whose routes were removed are deleted, with
  the regenerated types.
- **Production hardening PR 5:**
  - **Token renewal.** A renewed token for the same signed-in person replaces the request headers
    without aborting requests in flight (`replaceAuthenticationHeaders`), and refetches. It no
    longer reloads the identity or hides the workspace.
  - **Abandoned requests.** A request abandoned because the identity changed is
    `ApiError(0, "request_aborted")`, before or after its answer arrives. It produces no failure
    notice, and keeps a job start's idempotency key.
  - **Error boundaries.** A root boundary and a route boundary built on `ErrorState` replace a
    blank page, and offer a reload when a redeploy removed the page's code.
- **Production hardening PR 12:**
  - **Timeouts and cancellation** (`api/client.ts`). Requests give up after 30 seconds, or 120 for
    uploads and downloads, as `ApiError(0, "request_timeout")`. The read methods take a query's
    `{ signal }`, and every `queryFn` passes it, so a query nobody needs any more stops its fetch.
    A cancelled query is `request_aborted`, like an identity change.
  - **Correlation IDs.** `errorReference(error)` (`api/errors.ts`) gives `ErrorNotice`, `ErrorState`
    and failure toasts (`app/mutationErrors.ts`) the API's correlation ID to show.
  - **Client error reports** (`api/clientErrors.ts`). The boundaries and window listeners report
    the kind of failure, once per kind per page load, to `POST /api/client-errors`.
  - **Runtime values** (`api/knowledge.ts`). The knowledge portal's address and role come from
    `<meta>` tags the web container renders when it starts, before `import.meta.env`.
- **Production hardening PR 13:**
  - **Paged documents** (`app/DocumentsPage.tsx`). Search, filter, owner and sort are sent to
    `GET /documents`, which answers a page with its counts and owners; the page reads more with
    "Load more" (`useInfiniteQuery`). Client-side filtering and sorting are gone.
  - **Owners from the server** (`features/documents/owners.ts`). Each document carries its
    owner's title, so `useDocumentOwners`, which fetched each owner one by one, is deleted;
    `DocumentDetailPage` reads the owner from the detail response.
  - **Drafts envelope** (`api/client.ts`, `app/DashboardPage.tsx`). `GET /requirements/drafts`
    answers a page; the dashboard asks for the newest one only.

## Consequences

- **Findable.** Every logic change to the frontend during the redesign can be found and traced
  to an approval and a test.
- **Gated.** Fixes for real defects in request and session code no longer wait for the redesign,
  but each needs an approval.
- **Easier redesign.** The redesign rebuilds screens over request code whose behaviour is pinned
  by those tests.
- **Still deferred.** The two deferred review-remediation items in AGENTS.md's debt register
  (`review/rules.ts` and the hand-written knowledge types) can now be taken this way. They are
  not approved yet.

## Alternatives Considered

- **Wait for the redesign to fix request and session defects.** Session aborts, unrecoverable
  crashes and duplicate jobs would stay in front of pilot users for the length of the redesign.
- **Drop the presentation-only rule.** That would mix behaviour changes into visual ones,
  which the rule exists to prevent.
