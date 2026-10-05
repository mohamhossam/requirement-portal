# UPSTREAM.md

This repository was imported fresh, with no history, from
[`mohamhossam/smb-ai-requirement-agent`](https://github.com/mohamhossam/smb-ai-requirement-agent)
(ADR-0098). The original stays maintained and deployed in parallel, so fixes made there do not
arrive here by themselves.

## Synced to

| Field | Value |
|---|---|
| Original commit | `d5cfb57` (Merge pull request #100, `claude/impact-product-context`) |
| Imported | 2026-10-02, as this repository's first commit |

## How to port a fix

1. Find the original commits that landed after the "Synced to" commit:
   `git -C ../smb-ai-requirement-agent log --oneline d5cfb57..origin/main`.
2. Decide each one: **port**, **not applicable** (the code has moved to knowledge-portal or
   platform-kernel, so port it there instead), or **skip** (with a reason).
3. Port it in its own pull request, titled `port: <original subject> (<original sha>)`.
4. Add a row below. Move "Synced to" forward only when every commit up to the new point has a
   row.

## Ported changes

These rows decide the 14 commits on the original's `smb-product-flow-architecture` branch (the Product Architecture Explorer, ADR-0101), which are not on its `main` yet. "Synced to" stays `d5cfb57` until they land there.

| Original commit | Decision | Where | Pull request |
|---|---|---|---|
| `02992a2` enterprise solution-architecture explorer with DOCX generation | Not applicable: re-implemented on the catalogue (ADR-0101) | knowledge-portal | — |
| `7199861` public MVP tab, solution-flow hero, calm theme | Skip: no static, public explorer tab here (ADR-0101) | — | — |
| `ca4a802` impacted-architecture first tab, leaner tab set | Not applicable: explorer screens | knowledge-portal | — |
| `1d71fec` Architecture explorer in the left sidebar | Skip: no explorer route here; at most a link to knowledge-portal | — | — |
| `9411896` calm borders instead of side-tab accents | Skip: styling of the static file | — | — |
| `e755684` business change requests, phase 1 | Not applicable: change requests become draft releases | knowledge-portal | — |
| `e629c77` dark-theme text on brand | Skip: styling of the static file | — | — |
| `8833e34` brand dot instead of a side stripe | Skip: styling of the static file | — | — |
| `dde1451` change requests from Requirement AI, phase 2 | Not applicable; the backlog export (schema 1.x) stays the contract it reads | knowledge-portal | — |
| `acc1b3a` CR-20261004-Business_Pro_Plus applied to the model | Not applicable: explorer model data | knowledge-portal (in the one-off seed) | — |
| `e7b05f3` product profile page | Not applicable: explorer screens | knowledge-portal | — |
| `8f19708` visual product page | Not applicable: explorer screens | knowledge-portal | — |
| `94b35aa` one scroll, not two; lifecycle board for journeys | Not applicable: explorer screens | knowledge-portal | — |
| `a1c19b3` product header and offering hero | Not applicable: explorer screens | knowledge-portal | — |
