# ADR 0085 — Matching document names to catalogue systems, and inferred dependencies

## Status

Accepted. Extends ADR 0081.

## Context

Two limits of reading documents into the catalogue (ADR 0081) cost maintainers time.

- **Name matching was exact.** A document's system name matched a catalogue system only by its
  exact id, name, Arabic name or alias, ignoring case. "Dynamics CRM" did not match `bcrm`,
  whose aliases are "Microsoft Dynamics sales CRM" and "sales CRM". It became a new system
  instead, and every dependency on it waited for "its system first".
- **Only stated dependencies were proposed.** A document that described an interaction without
  saying "depends on" produced no dependency. Examples are "Order Hub posts invoices to SAP", a
  row in an integration table, or an arrow in a diagram.

AGENTS.md §7 and §8 still apply. AI output is a candidate that a person approves, and inference
is kept apart from source fact.

## Decision

**Similar names are suggested, never linked automatically.**

- **Unmatched names are checked.** After extraction, `ProposeCatalogueChanges` collects every
  name that no draft system answers to: new systems, plus the source or target of any other
  suggestion. It sends them to a `SystemMatcherPort` in one pass per document.
- **`StructuredSystemMatcher` shortlists, then asks.**
  - It shortlists up to 5 catalogue systems per name. A system qualifies on the best of word
    overlap, spelling likeness (`difflib`), an abbreviation check, or embedding similarity of
    "name; aliases; capabilities". Embeddings come from the configured knowledge embedding model;
    if it fails, the shortlist uses names only and the run records a warning.
  - It then asks the catalogue model, with prompt `catalogue-matching-v1`, which shortlisted
    systems are the same system under another name. The model sees each name with its passage.
    A sibling product or a system doing similar work is not a match.
  - Up to 3 options per name are returned, each with a one-line reason. An id outside that
    name's shortlist, or a blank reason, is dropped.
- **Matches are stored on the suggestion.** A `PossibleMatch` records the role (`system` or
  `target`), the name as written, the system id and the reason. `ExtractionRun` records the
  matcher's model and prompt version.
- **A matching failure does not fail extraction.** The suggestions are kept and the run records
  a warning. `SystemMatchingError` is mapped to 502 (`catalogue_matching`) all the same.
- **The maintainer decides.**
  - "Add to BCRM" accepts a system suggestion with `system_id` set to the existing system, so
    the written name becomes an alias.
  - "Use BCRM" re-points a dependency, capability or constraint.
  - "Keep as a new system" accepts the suggestion as written.
  - The existing decision endpoint carries the edited content, so no new endpoint is needed.
- **Linking one name resolves the rest.** `find_system` now falls back to comparing words
  alone, with case and punctuation ignored, and answers only when exactly one system fits. After
  "Dynamics CRM" becomes an alias of `bcrm`, a dependency that points at `dynamics-crm` resolves
  to `bcrm` without being rewritten. Once the name is resolved, the API stops returning its
  possible matches.
- **Names follow the draft.** Each suggestion carries `system_name` and `target_system_name`,
  the names of the draft systems its references resolve to. A linked dependency therefore reads
  "Order Hub → BCRM", not the suggested id.

**Dependencies may be inferred from what the passages describe.**

- **Prompt.** `catalogue-extraction-v2` adds a `basis` of `stated` or `implied`, with one sentence
  of reasoning for `implied`. Only a dependency can be implied, and never from general product
  knowledge. Citation and quote checks are unchanged, so an inferred dependency still cites the
  passages it rests on.
- **Stored separately from fact.** An implied dependency becomes a suggestion with basis
  `inferred` and a `rationale`. The domain refuses an inferred suggestion of another kind, an
  inferred one without a rationale, and a stated one with a rationale. If the same dependency is
  also stated, the stated copy wins. An inferred dependency between systems the draft already
  links is left out, with a warning.
- **"Accept all" skips them.** Inferred suggestions and suggestions whose possible matches are
  still open (`needs_one_by_one`) wait for a one-by-one decision. The UI says how many were left.

## Consequences

- Fewer duplicate systems, and fewer dependencies stuck waiting for a system the catalogue
  already has.
- Maintainers see interactions that a document describes but never labels, marked "Inferred"
  with the reasoning next to the quote.
- A document with unmatched names costs one more model call, plus one embedding call. Large
  numbers of names are split into bounded batches.
- Stored suggestions and runs from before this change load unchanged: the new fields have
  defaults.

## Alternatives Considered

- **Auto-link confident matches.** Rejected. It would let a model change the catalogue on its
  own, which ADR 0081 and slice 14 forbid.
- **Ask the extraction model for "possibly the same as".** Rejected. The model may see only a
  trimmed catalogue on small context windows, and has no shortlist to stay inside.
- **Embeddings alone.** Rejected. Short names embed poorly, and a threshold cannot tell a sibling
  product from the same system.
- **Infer dependencies from catalogue knowledge, without the document.** Rejected. It could not
  be cited, and would be the model's product knowledge presented as the organisation's
  architecture.

## Amendment — Catalogue tables and one id per system (2026-10-01)

A Markdown landscape (`docs/slices/enhancement-catalogue-table-reading-rules.md`) showed four
problems once it was read in many calls:
- Each system's Integrations column was treated as implied dependencies, so every link had to be
  decided on its own.
- Names kept their emoji ("📈 BCRM").
- `SYS-*` IDs were lost.
- One system named two ways ("CBCM / CRMGW" in its row, "CRM GW" in another row) became two ids.

The prompt, `catalogue-extraction-v6`, now reads tables as records:
- **A system row** names one system, without decoration. Its aliases are the Aliases column plus
  the ID value.
- **Its Function** is one stated capability, with matching phrases taken from that text.
- **Each Integrations entry** is a **stated** dependency from the row's system to that entry,
  kind `unspecified` unless the entry says how, and never in reverse.
- **Entries:**
  - an entry `A / B` names two systems, unless it is a known name;
  - group words such as "Digital" or "Channels" are left out.
- **Other tables:**
  - a component's system responsibility, or an activity's system function, is a capability of
    that system;
  - supporting systems are not dependencies;
  - rows linking activities by number, and activity flow diagrams, are not system dependencies.
- **Owner and domain columns** are ignored.
- **Document markers:** rows marked GAP are left out, and a row marked INFERRED gives an implied
  dependency.

"A row of an integration table" no longer counts as implied evidence.

**Names.**
- The extractor removes pictographs (symbols, emoji joiners, variation selectors and skin tones)
  from every system name the model returns, before resolving it. Quotes stay verbatim.
- `find_system` gains a last fallback: the words run together, so "CRM GW" finds a system
  aliased "CRMGW". Like the word fallback, it answers only when exactly one system fits.

**One id per system across calls.** Before merging proposals, `ProposeCatalogueChanges` builds a
provisional draft with every suggested system added. It then re-resolves each proposal's system
and target against it. A document's names for one system therefore share one id. A dependency
that resolves to a system on both ends is left out, as ADR-0091 records.
