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

| Original commit | Decision | Where | Pull request |
|---|---|---|---|
| — | — | — | — |
