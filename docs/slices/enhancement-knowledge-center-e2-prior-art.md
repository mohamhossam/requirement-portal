# Enhancement — Knowledge Center E2: the historic corpus and prior art

> **Status:** in progress on `feat/knowledge-center-historic-corpus` (this repository),
> `feat/knowledge-center-historic-content-read` (knowledge-portal, E2a) and
> `feat/knowledge-center-historic-citations` (knowledge-portal, E2b), 2026-10-07.
> E2a merges first, because this repository pins its contract; E2b is cut from E2a and
> follows this one.
> **Parent:** the Knowledge Center re-plan, sub-slice E
> ([enhancement-knowledge-center.md](enhancement-knowledge-center.md)), decisions 10–13,
> [ADR-0102](../architecture/adr-0102-historic-requirements-and-ado-lineage.md) and its
> Amendment 1. E1 is [enhancement-knowledge-center-e1-historic-import.md](enhancement-knowledge-center-e1-historic-import.md).

## Objective

Make the historic requirements published in knowledge-portal useful to requirement work.
Requirement work keeps a copy, indexes it as a historic corpus apart from the live one, and
shows each Requirement's **similar past requirements** on the Knowledge step: delivered work
from old BRDs, with the AI judge's reason and the passages and Epic → Feature → User Story
lineage it was delivered as. It is reference only. It never adds a finding, never counts
toward readiness and never blocks confirmation.

## What is built

| Part | Where | What it does |
|---|---|---|
| Light event, paged read (E2a) | knowledge-portal | The event names the publication; `GET /internal/historic-requirements/{id}/passages` and `.../items` serve its content, ≤200 a page, with the publication's fingerprint. An older publication answers 409, a withdrawn one 404. |
| Projection | here | `ProjectHistoricRequirements` keeps a copy with its own cursor (`historic_requirements`) from 0, on its own loop. A withdrawal removes the record from search in the same transaction. |
| Historic corpus | here | `IndexHistoricCorpus` reads each publication a page at a time, cuts chunks (BRD passages as `historic_brd`; each Epic, Feature and User Story as `historic_backlog`, with its lineage), embeds them 16 at a time, and makes them searchable together. Search is RRF over an any-word lexical query and pgvector. |
| Prior-art check | here | A `screen_prior_art` job searches the corpus with the Requirement's screening text, shows the judge the five closest historic requirements (four passages each), validates what it cites, and keeps the check. |
| Read | here | `GET /requirements/{id}/prior-art`: status, matches still published, provenance, `label: historic`, `trust: reference`. |
| Knowledge step | here | "Similar past requirements", below the knowledge review: each match with a Historic badge, the Generated rationale, its BRD passages and its lineage with links that open Azure DevOps. |
| Cited by (E2b) | knowledge-portal | `GET /internal/knowledge/historic/citation-counts` and `.../{id}/citations` here; "Cited by" on knowledge-portal's Historic list and record page. |

## Decisions

| # | Decision | Why |
|---|---|---|
| 1 | The event is light; the content is read in pages. | Agreed in session (2026-10-07): one event could otherwise reach tens of megabytes (ADR-0102 Amendment 1). |
| 2 | Prior art is off until an operator turns it on (`PRIOR_ART_ENABLED`). | Agreed in session: the judge's precision is measured first, with `scripts/evaluate_prior_art.py`. |
| 3 | Checks are capped each hour (`PRIOR_ART_JUDGE_CALLS_PER_HOUR`, default 60), and embedding per historic requirement (`HISTORIC_EMBED_CHUNKS_PER_HOUR`, default 500). | Agreed in session. The job gate holds prior-art jobs queued, never failed, while the hour's checks are spent. |
| 4 | Prior-art jobs are claimed after every other queued job, and never make the Requirement look busy. | Agreed in session: prior art never delays anyone's work. |
| 5 | Re-checking is lazy: on a change to the Requirement, or on opening the Knowledge step when prior art is missing or out of date. | Agreed in session (2026-10-06): no mass re-screening. |
| 6 | Only a new or refreshed publication makes prior art out of date; a withdrawn match disappears when read. | My call: a withdrawal needs no new judge call to take effect. |
| 7 | Its own judge, prompt and enums; the live classifier and kinds are unchanged. | The live kind types findings and a published filter, and the live prompt calls similar topics unrelated (ADR-0102 Amendment 1). |
| 8 | Where a historic requirement is cited gives identity and state only. | As B2's corpus list: knowledge admins see who and when, never what was matched. |
| 9 | A failed check is not queued again for the same input. | No repeated spend on a failing judge; a member can retry the job. |

## Evaluation before enabling

`docs/evaluation/prior-art-synthetic.json` holds 12 synthetic cases (24 pairs). Each pairs a
proposed requirement with historic candidates, including topic-only near misses.
`application/prior_art_evaluation.py` reports precision, recall and invalid citations. The gate
is precision ≥ 0.8, recall ≥ 0.7 and no invalid citations. The fake judge passes it in CI (0.909
and 1.0); a judge that calls everything similar fails it. Before turning prior art on:

```bash
python scripts/evaluate_prior_art.py docs/evaluation/prior-art-synthetic.json
```

Synthetic cases exercise the harness only. Replace them with pairs a person has reviewed from
real BRDs before treating the result as release evidence.

## Tests

- `tests/unit/test_historic_corpus.py`:
  - the pinned event example;
  - malformed events refused;
  - safe links and cycle-safe lineage;
  - chunk fields, bounds and stable ids;
  - replay from 0 on its own cursor;
  - nothing searchable until read and embedded in full (450 passages in four reads);
  - withdrawal at once, republication taking over;
  - a superseded publication;
  - the hourly embedding budget.
- `tests/unit/test_prior_art.py`:
  - off by default;
  - nothing queued without historic knowledge;
  - a match found after the screen, changing neither readiness nor counts;
  - out of date after a new publication and re-checked on visit;
  - a withdrawn match hidden;
  - the hourly budget holding a check as waiting;
  - a judge citing what it was not shown failing once, never re-queued;
  - the internal citation reads and their bounds;
  - the public read;
  - the evaluation gates.
- `tests/unit/test_prior_art_judge_adapters.py`, `tests/unit/test_knowledge_http_contract.py`
  (the paged read against knowledge-portal's contract), `tests/unit/test_settings_and_container.py`.
- `tests/architecture/test_historic_reference_trust.py`: live screening, suggestions, the corpus,
  the review and unified search take no historic port; the live kinds gain no historic values.
  `test_provider_rate_limit.py` knows the judge and its scheduler.
- `tests/integration/test_historic_corpus_postgres.py` and `test_prior_art_postgres.py`.
- `frontend/src/features/priorArt/PriorArtPanel.test.tsx`.

## Validation evidence

Recorded on 2026-10-06, before the pull requests.

**Gates.**

| Repository | Ran | Result |
|---|---|---|
| This one | `ruff check`, `ruff format --check`, `mypy src tests`, `lint-imports`, pytest on PostgreSQL | Green: 1,772 tests. |
| This one, frontend | `lint`, `typecheck`, `api:check`, vitest, `build` | Green, except the download test in `client.test.ts`, which fails only on Node 22 (CI runs Node 24). |
| knowledge-portal, E2a and E2b | the same set, frontend included | Green: 266 frontend tests. |
| Judge evaluation | `LLM_PROVIDER=fake python scripts/evaluate_prior_art.py docs/evaluation/prior-art-synthetic.json` | Precision 0.909, recall 1.0, no invalid citations; the gate passes. |

**Live, both services split and joined by service tokens.**

This one ran on PostgreSQL with `PRIOR_ART_ENABLED=true`. knowledge-portal ran with `ADO_PROVIDER=fake`.

1. **Publish.** knowledge-portal imported four BRDs (the `.doc` file was refused), published two and withdrew one. This repository projected the events from 0 on the `historic_requirements` cursor. It read the content a page at a time and indexed the two published records: 9 `historic_brd` chunks and 12 `historic_backlog` chunks, at corpus version 2. The withdrawn record has no chunks.
2. **Match.** A Requirement, "XGPON fibre bundles for clinics", was screened when it was created. Its prior art is `current`, with one match: the XGPON BRD, labelled historic. The match carries the Epic and the User Story with their lineage, and the BRD paragraph. The knowledge review stayed `ready`, so confirmation is not blocked.
3. **Refresh.** Accepting the waiting refresh in knowledge-portal made the publication 2 and the corpus version 3. Prior art went `out_of_date`, and knowledge-portal showed the citation as an older check. Opening the Knowledge step (`knowledge-screen/ensure`) checked it again against publication 2. It is `current` again on both sides.
4. **Cited by.** knowledge-portal's list shows XGPON cited by 1 requirement and the others by none. A draft shows a dash. The record page lists the Requirement, its owner and when it was checked.
5. **Withdraw.** Withdrawing the cited record removed its chunks here at once, and its match no longer shows in the Requirement's prior art. knowledge-portal still names the Requirement, marked "Cited before it was withdrawn".
6. **Screens.** The Knowledge step and knowledge-portal's Historic list and record page were checked at 1440 and 390 pixels wide. On phones, a work-item type such as "User Story" broke across two lines in the lineage; it now stays on one.

**Critique of knowledge-portal's Cited by screens.** The dual-agent critique scored them 27/40, and the detector and axe-core found no WCAG 2.2 AA failures. These findings were fixed:
- the withdraw panel now says something about the citing Requirements even when their number is unknown or could not be read;
- "stops" or "stop" agrees with the count;
- the Checked on date no longer wraps;
- the check is a short status, with its reason on a second line;
- a withdrawn record's citations are shown as past;
- links are 24 pixels tall;
- Show more hands focus to the first row it adds;
- the stray phone line is gone.

The risk checks in the plan are covered by the unit tests named above:
- the event stays under 2 KB;
- a 450-passage record is read in four pages and checked against its fingerprint;
- with the switch off, nothing is queued;
- a cap of one call holds the second check as `waiting`;
- prior-art jobs are claimed last;
- the evaluation gate.
