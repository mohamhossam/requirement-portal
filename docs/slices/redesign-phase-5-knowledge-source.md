# Redesign Phase 5 — Knowledge `/knowledge` and Source `/capture`

`docs/ux-plan.md` §5 Phase 5, on Phases 0–4, governed by `docs/design-system.md`
and `DESIGN.md`. Presentation only (`CLAUDE.md`). Ends with build, lint,
`test:coverage` and the Playwright smoke green.

> Knowledge: "Has this been asked before, and does it contradict anything we
> know?" Source: "Is this requirement ready to analyse, and if not, what is
> missing?" — ux-plan §1.

## Where it stood

The plan expected both screens to get "most of their improvement free from the
Phase 0 shell". The frame did; the content had not moved. A baseline
`/impeccable critique` (dual assessment, live seeded screens at 1440 and 390,
Paper and Slate; snapshots in `.impeccable/critique/2026-09-26T10-28-22Z__*`)
scored **Knowledge 14/40** and **Source 16/40**:

- **Close as duplicate was unguarded** (P0): one click, filled red, in front of
  a disabled "Mark distinct", and a reason typed in the shared field was dropped
  silently when Close was pressed.
- **A finding could not be read as a comparison** (P1): the linked requirement
  was an eight-character hash, quotes were not labelled by side, set in the
  interface sans, with raw field names.
- **Status as the data record** (P1): eyebrows, a 10.9px uppercase badge with no
  CSS rule at all for `action_required`, `.replaceAll("_", " ")`, headings
  jumping h2 → h4, a pending resolution on Approved Green.
- **Source contradicted itself** (P0/P1): "Ready for analysis" in an indigo box
  while a file that could not be read held "Continue to analysis" shut — and
  the shut link still navigated on Enter.
- **Source rows overprinted at 390** (P0): a `flex-wrap` override on a grid row
  did nothing, so Retry and Include printed over the file's status.
- **Jargon and the type floor**: "Prompt attachments", "Exclude from prompt",
  "passages", "the embedding model changed"; row text at 10.9–11.2px; neutral
  evidence counts in red; hidden file inputs as extra tab stops; no
  confirmation on removing a file; the Source screen not showing the source.

## Decisions taken before starting

| Question | Decision |
|---|---|
| `DocumentPanel` is shared with intake (Phase 6) | **Redesign it now.** Intake gets the new attachment list early; its form layout stays for Phase 6. |
| Guarding Close as duplicate | **An explicit choice, then a confirmation.** "Are these the same need?" — each answer reveals its own field and button; closing confirms in a dialog naming both requirements and the consequence. |
| Scope | Every P0–P2 and minor, presentation only. Data changes raised, not made. |

## As built

### Knowledge

- **Labels.** `features/knowledge/labels.ts` names every status, decision and
  evidence field; a unit test asserts no raw value reaches the page. Field
  names Clarify already maps fall through to `evidenceFieldLabel`.
- **One status, said once.** The panel heading is the verdict — "2 overlaps
  need your decision", "Knowledge review clear", "Screening in progress" — with
  one line of what it means and a count ("2 to settle · 2 waiting on you"). The
  badge that repeated it is gone; provenance moved to the foot as "How this
  check was made".
- **A finding reads as a comparison.** Each is an `article` with an `h3`:
  "Possible contradiction with *Business line activation exception*", the
  linked requirement named by its own title from the evidence (its short ID
  only when the evidence carries no title). A verdict badge per finding —
  *Needs your decision*, *Needs your acceptance*, *Waiting for the other
  owner*, green only once settled; neutral *Waiting for an owner's decision*
  for people who cannot act. Quotes are labelled by side and set in the
  document serif; titles are not quoted as evidence, since they already name
  the heading and the page.
- **Both statements.** The screener cites what it matched, often only the other
  requirement's passage. Where the finding carries nothing from this side, this
  requirement's own business need — already loaded — stands above it, "This
  requirement · Business need, for comparison", so "permits… online" and "does
  not permit… online" can be read together.
- **The duplicate decision.** On the subject side, "Are these the same need?"
  with two radios. *Different needs* opens "Why they are different needs" and
  keeps focus on the radio (arrowing between choices must not throw the caret
  into a field — WCAG 3.2.2); *The same need* states what closing does and opens a
  dialog ("Close this requirement as a duplicate?") naming both requirements,
  Cancel focused. On the related side there is nothing to close: the form is
  *Mark as distinct*, with a link to the other requirement's own step. Each
  path has its own field, so nothing typed is dropped.
- **Resolutions.** "Proposed by Amina Owner · date. No owner has accepted it
  yet." in a hairline box — not green. *Accept shared resolution*, or "You
  accepted this. It is waiting for the other owner."; revising sits behind
  "Suggest different wording".
- **Gating.** Decision buttons are gated through `blockedReason` ("Say why they
  differ first."): tab stop kept, reason read. People who cannot decide get one
  line saying so and no forms. The screen's filled action goes to the first
  finding waiting on this person, once it can be taken.
- **Errors beside their cause.** A failed decision shows in the finding it was
  made on (`decisionError`, split from screening and retry errors).
- **Notices.** The outdated-reference and reference-conflict sections are
  warning cards naming where they are decided (Clarify). The index notice says
  "Getting the knowledge check ready" / "The knowledge check cannot start yet",
  "16 of 25 sections prepared", and an administrator — not "an operator" and
  "the embedding model". Someone not on the requirement cannot read its index
  state (403); the notice now renders nothing for them instead of a red
  "We couldn't complete that action" they never caused.

### Source

- **One verdict.** The first thing on `/capture` is a card combining the API's
  eligibility with the attachment state: *Ready for analysis* (success, check),
  *Checking the attached files*, or *Not ready for analysis* with the reason in
  words ("Still needed: a title and the business need, or a file included in
  analysis." / "A file below could not be read…"). "Continue to analysis" is a
  `ButtonLink` when ready and a gated `Button` otherwise — Enter no longer
  navigates past the gate.
- **The source is on the Source step.** "Business need" in the document-lead
  serif with Edit source beside it, then `RequirementFacts`: desired outcome,
  customer context, channels, systems, rules and constraints, only those filled
  in. The drawer uses the same component.
- **Attached files** (`DocumentPanel`, also intake and the drawer's edit form):
  - rows are a two-row grid below `sm` — actions under the filename, never over
    it;
  - readiness and stage as `Badge`s from `features/documents/labels.ts` ("Could
    not be read", "Checking the file is safe"); evidence counts only when
    non-zero, in neutral meta; errors in danger with a glyph, warnings in amber;
  - "Include in analysis" is the `Checkbox` primitive; "Leave out of analysis"
    replaces "Exclude from prompt"; short visible labels with the filename for
    screen readers ("Retry" / "Retry processing pricing-sheet.pdf");
  - removing a file asks first, Cancel focused;
  - the hidden file inputs are out of the tab order; the drop zone is the one
    dashed border, and Attach files is its single-pointer alternative
    (WCAG 2.5.7). Below `sm`, where nobody drags, it gives way to the format
    line.
- **Drawer.** No second title or full UUID above the business need. "What the
  analysis holds" is a labelled list, not `.source-facts`.

### Primitives and shell, found on the way

- **`Card` padding.** A caller's `p-4` never applied: Tailwind emits `.p-6`
  after `.p-4`, so the Card's own padding won on every card that passed one,
  including Phases 3 and 4. `Card` takes `padding="compact" | "snug" | "fluid"`
  now, and every caller that passed a padding class uses the prop.
- **Drawer header.** `sticky top-0` is resolved against the drawer's padding,
  so the header sat 24px below the edge its negative margin put it at and
  covered the first 8px of every drawer's body. `-top-6` fixes Source, People
  and the Backlog navigator alike.

### CSS deleted

`11-attachments.css` (the whole file); the `.knowledge-*` finding rules and
`.resolution-statement` in `10-portfolio-reports.css`; `.journey-panel*`,
`.source-copy`, `.source-facts*` in `05-intake-stages.css`; `.document-panel`,
`.document-list`, `.document-row-*`, `.document-help`, `.document-status`,
`.document-upload` in `06-source-documents.css`. `.eligibility-card`,
`.include-control`, `.icon-button`, `.knowledge-actions` and `.permission-note`
stay: intake, document detail, notifications, architecture knowledge and
people still use them.

### Logic untouched

No query, mutation, variable, invalidation or hook changed. `KnowledgeView`
passes the same mutation the same variables; it only splits one error prop in
two. `DocumentPanel`'s queries, mutations, upload flow and state callback are
line-for-line; the removal confirmation is local UI state in front of the same
`removal.mutate(document)`.

## Verification

- `npm run build`, `npm run lint`, `npm run test:coverage` green: 485 unit
  tests (new: the duplicate choice and dialog, focus staying in the choice,
  gating with a description, the related side, read-only viewers, resolution
  states, the comparison passage, error placement, no raw enums; attachment
  labels, removal confirmation, index notice copy).
- Smoke on a fresh API: `review-flow`, `attachment-flow`,
  `requirement-indexing`, `ingestion-completion`, `responsive-layout`,
  `focused-breakdown`, `content-security-policy` and
  `library-spreadsheet-merges` at 1440 and 740 — 45 passed, 5 skipped, then 2
  failures in `ingestion-completion` on copy it asserted ("Exclude failed
  upload", "Excluded from prompt"); updated, and it, `review-flow` and
  `attachment-flow` re-ran 26/26. Spec changes are copy and role locators only
  (`getByRole("article")` for findings, a gated `button` for Continue).
- Live, seeded, at 1440 in Paper and Slate and at 390: overflow 0 on every
  page; row actions below the filename at 390; Enter on the gated Continue stays
  on `/capture`; the drawer header 0–57px with the body at 73px, still pinned
  400px into a long edit form.

## Critique pass

A verification `/impeccable critique` (dual assessment on the built screens;
snapshots `.impeccable/critique/2026-09-26T10-57-24Z__*`) scored **Knowledge
26/40** (from 14) and **Source 28/40** (from 16). The detector was clean on all
seven files; every `aria-disabled` control kept a tab stop and a description;
one filled accent per page. It found three regressions and two overlay hits,
all fixed before this doc:

- the radio group moved focus into the reason field on arrow keys (3.2.2);
- a reviewer not on the requirement saw the index notice's 403 as a red error;
- the Source verdict offered "replace" for an upload that can only be retried
  or left out;
- the proposed-resolution box was a card inside the finding card;
- the drop zone's format line ran to ~123 characters.

Also taken from it: neutral badges for people who cannot act, the comparison
passage, the drop zone hidden on phones, and the failure said once rather than
three times. Its side-tab flag on the warning cards is the sanctioned 3px edge
(DESIGN.md, One Edge Rule).

## Follow-ups noted

- **The linked requirement's title** is known only when the screening's
  evidence cites that requirement's title; otherwise the heading falls back to
  "requirement 42a131e6". Showing it always needs the linked requirement's
  title on the finding — an API change, raised not made.
- **The subject's own opposing text.** A contradiction cites one side only
  (whatever the screener matched), so a true side-by-side needs both sides in
  the finding's evidence — an API change.
- **A reason for closing as a duplicate** is not recorded: the decision
  mutation sends no text for `duplicate`.
- **The Next block** reads "Analyse the requirement" on Source while the page
  says not ready, and on Knowledge while overlaps wait — and its link bypasses
  the Source gate. `journey.ts` is kept by decision (ux-plan §6); making the
  Next block defer to a stage's own verdict is a journey-model change, raised.
- **Naming the blocking file** in the Source verdict needs `AttachmentState`
  to carry it — a change to the hook contract between `DocumentPanel` and the
  workspace, raised. The row itself is marked.
- The raw extraction message from the API ("PDF text extraction failed.")
  is shown as sent.
- `ConfirmDialog` still carries a "Please confirm" eyebrow; the source-edit
  impact confirmation uses it. The new dialogs here use `Modal` directly, like
  Phase 3.
