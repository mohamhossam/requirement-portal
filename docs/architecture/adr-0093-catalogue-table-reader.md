# ADR 0093 — Reading catalogue tables without a model

## Status

Accepted. Extends ADR-0081 and ADR-0090. Builds on ADR-0091 and the ADR-0085 amendment of
2026-10-01.

## Context

A landscape document such as `SMB_Product_Architecture_Explorer_v4.md` already states the
catalogue in its tables. Each of 39 system rows gives a name, an ID, aliases and the systems it
integrates with. Its integration-details rows link two numbered activities whose performing
systems the activities table names.

A model reading those rows:
- **Varies from run to run.** One document gave 9 to 45 suggestions across replays.
- **Spends its answer budget copying cells,** about 150 output tokens per suggestion (ADR-0091).
- **Can't join tables across calls.** An integration row names activity numbers, while their
  systems sit in another table, often read in another call.

The rows need no judgement, only the cells.

## Decision

**A deterministic table reader runs before the model, for every provider.**
`infrastructure/architecture/catalogue_tables.py` holds two parts:
- `CatalogueTableReader` reads rows that carry their cells.
  - `LocatedText.cells` and `ExtractionSegment.cells` hold every column of the header. Markdown
    tables fill them (ADR-0090); other formats do not yet.
- `TableFirstCatalogueExtractor` wraps the configured extractor once, in
  `interfaces/api/composition/architecture.py`.

**Tables are recognised by their header, not their position.** Column names are compared lower
case, words only, with a few synonyms:
- **A systems table** has `System` and one of `ID`, `Function`, `Integrations` or `Aliases`. Each
  row gives:
  - **A system:** its name without pictographs, and its aliases from the Aliases cell plus the ID.
  - **A dependency per Integrations entry:** "Integrates with X", plus any "via" qualifier, kind
    `unspecified`, never reversed. Entries are handled as follows:
    - an entry `A / B` names two systems, unless it is a known name;
    - an entry of more than four words is a phrase, not a system, and is left out.
  - **Names resolve** through the catalogue, then the document's own names, aliases and IDs, then
    a name without its trailing parenthesis ("ECM" for "ECM (catalog)") while only one system has
    that base.
- **An activities table** has `#`, `Activity` and `Performing system`. Its rows give nothing on
  their own; they map activity numbers to systems.
- **An integration-details table** has `From`, `To` and `Interaction`. A row joining activities
  of two different systems gives a dependency.
  - Its description is the payload, with the interaction and interface in brackets.
  - Its kind is `calls_api` for an API interaction and `unspecified` otherwise.
  - A row inside one system gives nothing.
- **Evidence markers.** A row marked `GAP` gives nothing. A row marked `INFERRED` gives inferred
  suggestions with the rationale "The document marks this row INFERRED."

**Each suggestion cites its own row**, quoting the row's text verbatim. It is stored with model
`catalogue-table-reader` and prompt version `catalogue-tables-v1`, so the review list can say
"Read from table".

**The model reads what is left.**
- Integration-details rows are not sent to the model.
- System rows are sent marked `read`, and prompt `catalogue-extraction-v7` asks only for
  capabilities and constraints from them. Any system or dependency the model still proposes
  citing only read rows is dropped as a duplicate.
- If the model then fails outright, the reader's suggestions are kept and a note says the rest
  could not be read.
- The reading profile becomes `catalogue-extraction-v7+catalogue-tables-v1`, so documents already
  read can be read again.

**Nothing is decided.** Every result is a suggestion. One-id-per-system resolution, merging of
links listed from both ends, and possible matches (ADR-0085, ADR-0088 amendments) all apply as
for the model's suggestions.

## Consequences

- A landscape's systems, aliases, IDs and integrations come through completely and identically on
  every reading. For the reported file that is:
  - 39 systems;
  - 113 links from Integrations columns;
  - 14 links from integration details.
- The model's answers carry only capabilities and prose. That leaves room in each answer, and
  calls are cheaper.
- The reader knows a fixed set of column names. A table with other headers is still read by the
  model alone. Adding a synonym is a code change.
- Two links can join the same pair of systems: one from an Integrations column ("Integrates with
  CWOM") and one from integration details ("CWOM-compatible fixed order (API, …)"). Both are
  suggested, because they say different things, and a reviewer may reject one.
- Group words such as "Digital" or "Channels" become dependencies on systems the draft does not
  have. They wait one by one, with possible matches, and Accept all leaves them.

## Alternatives Considered

- **Import the Markdown as a catalogue file.** File import replaces the draft (ADR-0081), and
  would need a fixed format. A document with prose, products and journeys around its tables is a
  source to read, not a file to load.
- **Leave tables to a better prompt.** Prompt v6 reads rows well, but it still varies between
  runs, spends output on copying, and cannot join tables across calls.
- **Send the model nothing the reader read.** Function cells need wording that only the model
  gives: a capability name and matching phrases.
