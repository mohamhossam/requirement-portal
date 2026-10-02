import { useQuery } from "@tanstack/react-query";
import { Check, CircleAlert, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { api, type DocumentSummary } from "../api/client";
import { errorMessage } from "../api/errors";
import { PageHeader } from "../components/shell";
import { AsyncState, asyncStatus } from "../components/states";
import { Badge, Pill } from "../components/ui/Badge";
import { ButtonLink } from "../components/ui/Button";
import { cx } from "../components/ui/cx";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  type SortDirection,
} from "../components/ui/Table";
import { fileTypeLabel, readinessView, sizeLabel } from "../features/documents/labels";
import { useDocumentOwners, type DocumentOwner } from "../features/documents/useDocumentOwners";
import { CONTROL, SEARCH_FRAME, SEARCH_INPUT } from "./dashboard/controls";
import { updatedLabel } from "./dashboard/labels";
import { queryKeys } from "./queryKeys";
import { useDocumentTitle } from "./useDocumentTitle";

type Filter = "all" | "attention" | "included" | "excluded";
type SortKey = "name" | "added";

/*
 * Three states, one name each, and every file in exactly one. "Blocks analysis"
 * is `requires_attention`: someone asked for a file that turned out unreadable,
 * and the requirement cannot be analysed until a person uploads a readable
 * version or leaves it out. It is not "left out" — it was never decided — so it
 * is not counted there, and it is the one thing on this screen that needs a
 * person (PRODUCT.md Principle 1).
 */
const blocksAnalysis = (document: DocumentSummary) => document.requires_attention;
const FILTERS: Array<{ key: Exclude<Filter, "all">; label: string; test: (document: DocumentSummary) => boolean }> = [
  { key: "attention", label: "Blocks analysis", test: blocksAnalysis },
  { key: "included", label: "In analysis", test: (document) => !blocksAnalysis(document) && document.included_in_analysis },
  { key: "excluded", label: "Left out", test: (document) => !blocksAnalysis(document) && !document.included_in_analysis },
];

const FOLD = "max-md:hidden";

/** In analysis, left out, or blocking it — in words and a glyph, never by colour alone. */
function Inclusion({ document }: { document: DocumentSummary }) {
  if (blocksAnalysis(document)) {
    return (
      <span className="text-danger inline-flex items-center gap-1 font-semibold">
        <CircleAlert className="shrink-0" size={14} aria-hidden="true" />
        Blocks analysis
      </span>
    );
  }
  return document.included_in_analysis ? (
    <span className="text-ink inline-flex items-center gap-1">
      <Check className="text-success shrink-0" size={14} aria-hidden="true" />
      In analysis
    </span>
  ) : (
    <span className="text-ink-muted">Left out</span>
  );
}

/**
 * Whether the file could be read, then what analysis does with it — one cell,
 * two lines, because together they answer "can the AI see this?". Readiness is
 * weighed by `readinessView`: a file whose only warnings are notes on how its
 * type is read is "Ready", so amber is left for files with something to check.
 * The hidden comma keeps the two from being read as one run-on phrase.
 */
function FileStatus({ document, id }: { document: DocumentSummary; id?: string }) {
  const readiness = readinessView(document.current_version);
  return (
    <span className="text-meta grid justify-items-start gap-1" id={id}>
      <Badge tone={readiness.tone}>{readiness.label}</Badge>
      <span className="sr-only">, </span>
      <Inclusion document={document} />
    </span>
  );
}

function OwnerLink({ owner }: { owner: DocumentOwner | null }) {
  if (!owner) return <span className="text-ink-muted">Not attached</span>;
  const fallback = owner.kind === "draft" ? "Draft" : "Requirement";
  return (
    // `relative` lifts this link above the row's stretched file link, so the
    // two stay separate targets on one line.
    <Link className="text-accent relative inline-block min-h-6 min-w-0 py-0.5 [overflow-wrap:anywhere] hover:underline" to={owner.to}>
      {owner.title ?? fallback}
      {owner.kind === "draft" && owner.title && <span className="text-ink-muted"> (draft)</span>}
    </Link>
  );
}

function Added({ document }: { document: DocumentSummary }) {
  const raw = document.current_version.created_at;
  // Relative, as on the worklist, so files added the same day still read apart
  // and the sort visibly does something; the exact time is in the tooltip and
  // on the file's own page.
  return <time dateTime={raw} title={new Date(raw).toLocaleString()}>{updatedLabel(raw)}</time>;
}

function added(document: DocumentSummary) {
  return new Date(document.current_version.created_at);
}

/**
 * Every file attached to a requirement or a draft (docs/ux-plan.md Phase 7).
 *
 * It was a grid of 176px cards showing the filename, the raw MIME type and
 * "Included in analysis" — a file that could not be read looked exactly like
 * one that could, and nothing said which requirement a file belonged to. A
 * list that can outgrow a screen ships search, filters and sort
 * (docs/design-system.md §14), so this is the worklist's table: one row per
 * file, the whole row one link, readiness in words beside it.
 *
 * Filtering and sorting are on the rows already loaded; the API returns the
 * whole catalogue in one read.
 */
export function DocumentsPage() {
  useDocumentTitle("Documents");
  const documents = useQuery({ queryKey: queryKeys.documents(), queryFn: api.listDocuments });
  const ownerOf = useDocumentOwners(documents.data);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [ownerFilter, setOwnerFilter] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({ key: "added", direction: "desc" });

  const counts = useMemo(() => Object.fromEntries(FILTERS.map(({ key, test }) =>
    [key, documents.data?.filter(test).length ?? 0])) as Record<Exclude<Filter, "all">, number>, [documents.data]);

  // The requirements and drafts files are attached to, for the filter: people
  // look for "the files on High-speed business bundles", not for a filename.
  const owners = [...new Map((documents.data ?? []).flatMap((document) => {
    const owner = ownerOf(document);
    return owner ? [[owner.to, owner] as const] : [];
  })).values()].sort((a, b) => (a.title ?? "").localeCompare(b.title ?? ""));

  const needle = search.trim().toLowerCase();
  const test = FILTERS.find(({ key }) => key === filter)?.test;
  const sign = sort.direction === "asc" ? 1 : -1;
  const rows = (documents.data ?? [])
    .filter((document) => !test || test(document))
    .filter((document) => !ownerFilter || ownerOf(document)?.to === ownerFilter)
    .filter((document) => !needle
      || document.current_version.filename.toLowerCase().includes(needle)
      || Boolean(ownerOf(document)?.title?.toLowerCase().includes(needle)))
    // Whatever the sort, a file blocking analysis comes first: it is the one
    // row that needs somebody, and it should not depend on being the newest.
    .sort((a, b) => Number(blocksAnalysis(b)) - Number(blocksAnalysis(a)) || sign * (sort.key === "name"
      ? a.current_version.filename.localeCompare(b.current_version.filename)
      : added(a).getTime() - added(b).getTime()));
  // Two requirements can share a title; the select tells them apart by the
  // start of their id, as the worklist does.
  const titleCounts = new Map<string, number>();
  owners.forEach((owner) => { if (owner.title) titleCounts.set(owner.title, (titleCounts.get(owner.title) ?? 0) + 1); });
  const ownerLabel = (owner: DocumentOwner) => {
    const title = owner.title ?? (owner.kind === "draft" ? "A draft" : "A requirement");
    const draft = owner.kind === "draft" && owner.title ? " (draft)" : "";
    const clash = owner.title && (titleCounts.get(owner.title) ?? 0) > 1 ? ` · ${owner.id.slice(0, 8)}` : "";
    return `${title}${draft}${clash}`;
  };

  const toggleSort = (key: SortKey) => setSort((current) => ({
    key,
    direction: current.key === key
      ? (current.direction === "asc" ? "desc" : "asc")
      : key === "name" ? "asc" : "desc",
  }));
  const direction = (key: SortKey) => (sort.key === key ? sort.direction : null);
  const total = documents.data?.length ?? 0;
  const filtered = filter !== "all" || needle !== "" || ownerFilter !== "";

  return (
    <>
      <PageHeader
        title="Documents"
        description="Every file attached to a requirement or a draft. Open one to see what was read from it and whether analysis uses it."
        actions={<>
          <ButtonLink variant="secondary" to="/documents/library">Shared library</ButtonLink>
          <ButtonLink variant="secondary" to="/architecture-knowledge">Architecture catalogue</ButtonLink>
          <ButtonLink variant="secondary" to="/architecture-knowledge/squads">Squad catalogue</ButtonLink>
        </>}
      />
      <AsyncState
        status={asyncStatus(documents, documents.data?.length === 0)}
        loading={{ label: "Loading documents", variant: "row", bars: 4 }}
        error={{ title: "We couldn’t load the documents", message: errorMessage(documents.error) }}
        onRetry={() => void documents.refetch()}
        headingLevel="h2"
        empty={{
          title: "No documents yet",
          message: "Files appear here once they are attached to a requirement or a draft. Attach them when you describe a new requirement, or on a requirement’s Source step.",
          action: <ButtonLink variant="secondary" to="/requirements/new">New requirement</ButtonLink>,
        }}
      >
        <div className="border-line bg-surface rounded-md border border-solid">
          {/* One constrained column: a grid track otherwise grows to its widest
              child, and a requirement title in the select below can be long. */}
          <div className="border-line grid grid-cols-[minmax(0,1fr)] gap-3 border-0 border-b border-solid p-4">
            <div className="flex flex-wrap items-center gap-2">
              <label className={SEARCH_FRAME}>
                <Search className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
                <span className="sr-only">Search files and requirements</span>
                <input
                  className={SEARCH_INPUT}
                  type="search"
                  value={search}
                  placeholder="Search files or requirements"
                  onChange={(event) => setSearch(event.target.value)}
                />
              </label>
              {owners.length > 1 && (
                <label className="contents">
                  <span className="sr-only">Attached to</span>
                  <select
                    className={cx(CONTROL, "w-auto max-w-full min-w-0 cursor-pointer")}
                    value={ownerFilter}
                    onChange={(event) => setOwnerFilter(event.target.value)}
                  >
                    <option value="">Every requirement</option>
                    {owners.map((owner) => (
                      <option key={owner.to} value={owner.to}>{ownerLabel(owner)}</option>
                    ))}
                  </select>
                </label>
              )}
              {/* Below `md` the table's header row is not drawn — every column but
                  File folds into it — so this select is the one sort control
                  there, and above `md` the column headers are. */}
              <label className="contents">
                <span className="sr-only">Sort</span>
                <select
                  className={cx(CONTROL, "w-auto max-w-full cursor-pointer md:hidden")}
                  value={`${sort.key}-${sort.direction}`}
                  onChange={(event) => {
                    const [key, value] = event.target.value.split("-") as [SortKey, SortDirection];
                    setSort({ key, direction: value });
                  }}
                >
                  <option value="added-desc">Newest first</option>
                  <option value="added-asc">Oldest first</option>
                  <option value="name-asc">Name A–Z</option>
                  <option value="name-desc">Name Z–A</option>
                </select>
              </label>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Show">
                <Pill active={filter === "all"} count={total} onClick={() => setFilter("all")}>All</Pill>
                {/* Only what somebody has; a "Needs a decision 0" pill is not information. */}
                {FILTERS.filter(({ key }) => counts[key] > 0 || filter === key).map(({ key, label }) => (
                  <Pill key={key} active={filter === key} count={counts[key]} onClick={() => setFilter(key)}>
                    {label}
                  </Pill>
                ))}
              </div>
              {/* Beside the pills it counts, not at the far end of the row. */}
              {filtered && (
                <p className="text-meta text-ink-muted m-0 tabular-nums" role="status">
                  Showing {rows.length} of {total}
                </p>
              )}
            </div>
          </div>
          {/* Four columns, and only two of them fixed. The File column is the one
              a person scans, so it never has to share the squeeze alone: it and
              Attached to split what the fixed Status column leaves, and Added
              folds into the File cell below `lg`. With five fixed columns the
              filename was 50px wide at 1100 and broke every two letters. */}
          <Table caption="Documents" framed={false} className="table-fixed">
            <colgroup>
              <col />
              <col className="w-[11rem] max-md:hidden" />
              <col className="w-[30%] max-md:hidden" />
              <col className="w-[8.5rem] max-lg:hidden" />
            </colgroup>
            <TableHead className="max-md:hidden">
              <tr>
                <TableHeaderCell sort={direction("name")} onSort={() => toggleSort("name")}>File</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell>Attached to</TableHeaderCell>
                <TableHeaderCell className="max-lg:hidden" sort={direction("added")} onSort={() => toggleSort("added")}>
                  Added
                </TableHeaderCell>
              </tr>
            </TableHead>
            <TableBody
              columns={4}
              empty={rows.length === 0 ? "No files match. Clear the search, choose Every requirement, or choose All." : undefined}
            >
              {rows.map((document) => {
                const version = document.current_version;
                const owner = ownerOf(document);
                const statusId = `document-${document.id}-status`;
                return (
                  <TableRow
                    key={document.id}
                    interactive
                    className={cx(
                      "relative has-[a[data-row-link]:focus-visible]:[outline:3px_solid_var(--focus)] has-[a[data-row-link]:focus-visible]:[outline-offset:-3px]",
                      // The row that needs somebody carries the one edge.
                      blocksAnalysis(document) && "shadow-[inset_3px_0_0_var(--danger)]",
                    )}
                  >
                    <TableCell className="py-3">
                      <span className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1">
                        {/* The file link is stretched over the whole row, so the
                            row is one click; it is described by the status
                            cell, so tabbing reads the name and then the state. */}
                        <Link
                          data-row-link=""
                          aria-describedby={statusId}
                          className="text-title text-ink min-w-0 no-underline [overflow-wrap:break-word] after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:outline-none"
                          to={`/documents/${document.id}`}
                        >
                          {version.filename}
                        </Link>
                        <span className="text-meta text-ink-muted tabular-nums">
                          {fileTypeLabel(version.mime_type)} · {sizeLabel(version.size_bytes)}
                          {document.version_count > 1 && ` · Version ${version.number}`}
                          <span className="lg:hidden"> · Added <Added document={document} /></span>
                        </span>
                        {/* The columns this row folds away below `md`. */}
                        <span className="grid grid-cols-[minmax(0,1fr)] justify-items-start gap-1.5 md:hidden">
                          <FileStatus document={document} />
                          <OwnerLink owner={owner} />
                        </span>
                      </span>
                    </TableCell>
                    <TableCell className={FOLD}><FileStatus document={document} id={statusId} /></TableCell>
                    <TableCell className={FOLD}><OwnerLink owner={owner} /></TableCell>
                    <TableCell className="text-meta text-ink-muted tabular-nums max-lg:hidden">
                      <Added document={document} />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      </AsyncState>
    </>
  );
}
