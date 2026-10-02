import { ArrowLeftRight, Check, CircleAlert, Download, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { BreakdownComparison, ExportFormat, RevisionHistory } from "../../api/client";
import { Disclosure } from "../../components/Disclosure";
import { Badge } from "../../components/ui/Badge";
import { Button, ButtonLink } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { cx } from "../../components/ui/cx";
import { FOCUS_RING } from "../../components/ui/recipes";
import { Select } from "../../components/ui/Select";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../../components/ui/Table";
import {
  approvalBasis,
  backlogContents,
  changeSummary,
  factChanges,
  readChange,
  revisionState,
  whenLabel,
  wordDiff,
  type BacklogRevision,
  type NeedVersion,
} from "./labels";

type Props = {
  history: RevisionHistory;
  comparison: BreakdownComparison | null;
  busy: boolean;
  /** The comparison failed. */
  error: string | null;
  exportError: string | null;
  exportingRevision: number | null;
  /** The last download that finished, so the page can say it did. */
  exported?: { revision: number; format: ExportFormat } | null;
  canExportApprovedRevisions: boolean;
  /** Where final approval happens, for the screen that has nothing to export yet. */
  reviewHref?: string;
  /** This requirement's activity, for who did what. */
  activityHref?: string;
  onCompare: (fromRevision: number, toRevision: number) => void;
  onDownload: (revision: number, format: ExportFormat) => void;
};

const FORMATS: Record<ExportFormat, { label: string; hint: string }> = {
  json: { label: "JSON", hint: "Structured data, for tools and scripts." },
  xlsx: { label: "Excel workbook", hint: "A workbook to read, share or import by hand." },
};

/** A history longer than FOLD_OVER shows its newest SHOW_NEWEST and the approved one. */
const FOLD_OVER = 8;
const SHOW_NEWEST = 6;

/**
 * History (docs/ux-plan.md Flow E): "What changed, and give me the approved
 * export." So the approved export comes first, then — separately, and in amber —
 * what has changed since it was signed off; then a comparison of any two
 * versions; then every backlog version with what it changed; then the business
 * need as it was written each time, with each edit shown word by word.
 */
export function RevisionPanel({
  history,
  comparison,
  busy,
  error,
  exportError,
  exportingRevision,
  exported = null,
  canExportApprovedRevisions,
  reviewHref,
  activityHref,
  onCompare,
  onDownload,
}: Props) {
  const versions = history.breakdown_revisions;
  const latest = versions.at(-1) ?? null;
  const approved = [...versions].reverse().find((revision) => revision.exportable) ?? null;
  const basis = approved ? approvalBasis(history.requirement_revisions, approved.final_approved_at) : null;
  const [fromRevision, setFromRevision] = useState(versions.at(-2)?.number ?? versions[0]?.number ?? 1);
  const [toRevision, setToRevision] = useState(latest?.number ?? 1);

  const compare = (from: number, to: number) => {
    setFromRevision(from);
    setToRevision(to);
    onCompare(from, to);
  };

  return (
    <div className="grid min-w-0 gap-8">
      {approved ? (
        <div className="grid gap-3">
          <ApprovedExport
            approved={approved}
            basis={basis}
            canExport={canExportApprovedRevisions}
            error={exportError}
            exported={exported}
            exporting={exportingRevision}
            onDownload={onDownload}
          />
          <SinceApproval
            approved={approved}
            basis={basis}
            currentNeed={history.requirement_revisions.at(-1) ?? null}
            latest={latest}
            onCompareWithCurrent={latest && latest.number !== approved.number ? () => compare(approved.number, latest.number) : undefined}
          />
        </div>
      ) : (
        <NothingApproved latest={latest} reviewHref={reviewHref} />
      )}
      <Compare
        approved={approved}
        busy={busy}
        comparison={comparison}
        error={error}
        from={fromRevision}
        onCompare={compare}
        setFrom={setFromRevision}
        setTo={setToRevision}
        to={toRevision}
        versions={versions}
      />
      <BacklogVersions activityHref={activityHref} approvedNumber={approved?.number ?? null} onCompare={compare} versions={versions} />
      <NeedVersions basisNumber={basis?.number ?? null} history={history} />
    </div>
  );
}

function SectionHeading({ id, title, description, action }: { id: string; title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2">
      <div className="grid gap-1">
        <h2 className="text-headline text-ink m-0" id={id}>
          {title}
        </h2>
        {description && <p className="text-body text-ink-muted m-0 max-w-[var(--measure-document)]">{description}</p>}
      </div>
      {action}
    </header>
  );
}

function ErrorLine({ children }: { children: ReactNode }) {
  return (
    <p className="text-danger text-meta m-0 flex items-start gap-1.5 font-semibold" role="alert">
      <CircleAlert aria-hidden="true" className="mt-px shrink-0" size={14} />
      <span>{children}</span>
    </p>
  );
}

function NothingApproved({ latest, reviewHref }: { latest: BacklogRevision | null; reviewHref?: string }) {
  const hasBacklog = Boolean(latest && (latest.feature_count > 0 || latest.story_count > 0));
  const underReview = latest?.review_status === "under_review";
  const message = !latest
    ? "Export opens once a backlog has been generated, reviewed and given final approval."
    : underReview
      ? `Version ${latest.number} is under review, waiting for final approval. Once it is approved it can be downloaded here, exactly as it was signed off.`
      : hasBacklog
        ? "The backlog has not had final approval yet. Once it has, the approved version can be downloaded here, exactly as it was signed off."
        : "There is no backlog yet. Export opens once a backlog has been generated, reviewed and given final approval.";
  return (
    <Card aria-labelledby="export-title" className="grid gap-3" padding="fluid">
      <SectionHeading description={message} id="export-title" title="Nothing is approved for export yet" />
      {hasBacklog && reviewHref && (
        <ButtonLink className="w-fit" to={reviewHref} variant="secondary">
          Go to Review &amp; approve
        </ButtonLink>
      )}
    </Card>
  );
}

function ApprovedExport({
  approved,
  basis,
  canExport,
  exporting,
  exported,
  error,
  onDownload,
}: {
  approved: BacklogRevision;
  basis: NeedVersion | null;
  canExport: boolean;
  exporting: number | null;
  exported: { revision: number; format: ExportFormat } | null;
  error: string | null;
  onDownload: (revision: number, format: ExportFormat) => void;
}) {
  const [format, setFormat] = useState<ExportFormat>("json");
  const running = exporting === approved.number;

  return (
    <Card aria-labelledby="export-title" className="grid gap-5" padding="fluid" tone="success">
      <div className="grid gap-1">
        <h2 className="text-headline text-ink m-0 flex flex-wrap items-center gap-x-3 gap-y-1" id="export-title">
          <span className="inline-flex items-center gap-2">
            <Check aria-hidden="true" className="text-success" size={20} />
            Approved backlog
          </span>
          <Badge>Version {approved.number}</Badge>
        </h2>
        <p className="text-body text-ink-soft m-0 max-w-[var(--measure-document)]">
          Approved
          {approved.final_approved_by ? ` by ${approved.final_approved_by.display_name}` : ""}
          {approved.final_approved_at ? ` on ${whenLabel(approved.final_approved_at)}` : ""}.
          {" "}It holds {backlogContents(approved).toLowerCase()}
          {approved.epic_name ? `, under the Epic “${approved.epic_name}”` : ""}
          {basis ? `, built from business need version ${basis.number}` : ""}.
        </p>
      </div>

      {canExport ? (
        <div className="grid gap-3">
          <fieldset className="m-0 grid gap-2 border-0 p-0">
            <legend className="text-label text-ink mb-1 p-0">Format</legend>
            <div className="flex flex-wrap gap-x-6 gap-y-2">
              {(Object.keys(FORMATS) as ExportFormat[]).map((key) => (
                <label className="grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] items-start gap-x-2" key={key}>
                  <input
                    checked={format === key}
                    className="mt-1 size-4 cursor-pointer accent-[var(--ink)]"
                    name="export-format"
                    onChange={() => setFormat(key)}
                    type="radio"
                    value={key}
                  />
                  <span className="grid">
                    <span className="text-body text-ink font-semibold">{FORMATS[key].label}</span>
                    <span className="text-meta text-ink-muted">{FORMATS[key].hint}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex flex-wrap items-center gap-3">
            {/* Kept enabled while the file is prepared: disabling the button that
                has focus drops focus to the page. A second press is ignored. */}
            <Button
              aria-busy={running || undefined}
              icon={<Download aria-hidden="true" size={16} />}
              onClick={() => {
                if (exporting === null) onDownload(approved.number, format);
              }}
              variant="primary"
            >
              {running ? `Preparing version ${approved.number}…` : `Download version ${approved.number}`}
            </Button>
            <p aria-live="polite" className="text-meta text-ink-soft m-0" role="status">
              {!running && exported?.revision === approved.number && !error
                ? `Downloaded version ${approved.number} as ${FORMATS[exported.format].label}.`
                : ""}
            </p>
          </div>
          {error && <ErrorLine>The download did not complete: {error} Try again; the file is prepared fresh each time.</ErrorLine>}
        </div>
      ) : (
        <p className="text-body text-ink-muted m-0">
          Only the requirement owner and its reviewers can download it. People, at the top of the page, lists who they are.
        </p>
      )}
    </Card>
  );
}

/**
 * What the approval does not cover. Its own amber block rather than a bullet in
 * the green one: an approval signed against an earlier business need is the
 * one unresolved thing on this page (PRODUCT.md Principle 1), and green around
 * it said "done".
 */
function SinceApproval({
  approved,
  basis,
  currentNeed,
  latest,
  onCompareWithCurrent,
}: {
  approved: BacklogRevision;
  basis: NeedVersion | null;
  currentNeed: NeedVersion | null;
  latest: BacklogRevision | null;
  onCompareWithCurrent?: () => void;
}) {
  const needEdited = basis && currentNeed && currentNeed.number > basis.number ? currentNeed : null;
  const laterBacklog = latest && latest.number > approved.number ? latest : null;
  if (!needEdited && !laterBacklog) return null;

  return (
    <Card aria-labelledby="since-approval-title" className="grid gap-3" padding="fluid" tone="warning">
      <h2 className="text-title text-ink m-0 flex items-center gap-2" id="since-approval-title">
        <TriangleAlert aria-hidden="true" className="text-warning shrink-0" size={18} />
        {needEdited ? "Approved against an earlier business need" : "The backlog has changed since this approval"}
      </h2>
      <div className="text-body text-ink-soft grid max-w-[var(--measure-document)] gap-2">
        {needEdited && basis && (
          <p className="m-0">
            Version {approved.number} was approved against business need version {basis.number}. The need is now version{" "}
            {needEdited.number}, so the approved backlog may not reflect that edit.
          </p>
        )}
        {laterBacklog && (
          <p className="m-0">
            The backlog is now version {laterBacklog.number}: {revisionState(laterBacklog).label.toLowerCase()}
            {laterBacklog.stale_story_count > 0
              ? `, with ${laterBacklog.stale_story_count} ${laterBacklog.stale_story_count === 1 ? "story" : "stories"} out of date`
              : ""}
            .
          </p>
        )}
        <p className="text-ink m-0 font-semibold">The download above is version {approved.number}, exactly as it was approved.</p>
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1">
        {needEdited && (
          <a className="text-accent text-body inline-flex min-h-6 items-center font-semibold" href="#need-versions">
            See what changed in the business need
          </a>
        )}
        {onCompareWithCurrent && (
          <Button onClick={onCompareWithCurrent} variant="text">
            Compare version {approved.number} with the current backlog
          </Button>
        )}
      </div>
    </Card>
  );
}

function optionLabel(revision: BacklogRevision, approvedNumber: number | null, latestNumber: number | undefined) {
  const tags = [
    revision.number === approvedNumber ? "approved" : null,
    revision.number === latestNumber ? "current" : null,
  ].filter(Boolean);
  return `Version ${revision.number}: ${tags.length ? tags.join(", ") : revisionState(revision).label.toLowerCase()}`;
}

function Compare({
  versions,
  approved,
  from,
  to,
  setFrom,
  setTo,
  comparison,
  busy,
  error,
  onCompare,
}: {
  versions: BacklogRevision[];
  approved: BacklogRevision | null;
  from: number;
  to: number;
  setFrom: (value: number) => void;
  setTo: (value: number) => void;
  comparison: BreakdownComparison | null;
  busy: boolean;
  error: string | null;
  onCompare: (from: number, to: number) => void;
}) {
  const resultHeading = useRef<HTMLHeadingElement>(null);
  const latest = versions.at(-1);
  const previous = versions.at(-2);

  // A new result is brought to the top of the screen and takes focus, so it is
  // seen and read the moment it arrives — wherever the button that asked for it
  // was. Focus is the announcement; the result is not also a live region, which
  // read it twice.
  useEffect(() => {
    const heading = resultHeading.current;
    if (!comparison || !heading) return;
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    heading.scrollIntoView?.({ block: "start", behavior: still ? "auto" : "smooth" });
    heading.focus({ preventScroll: true });
  }, [comparison]);

  if (versions.length < 2) {
    return (
      <section aria-labelledby="compare-title" className="grid gap-3">
        <SectionHeading id="compare-title" title="Compare versions" />
        <p className="text-body text-ink-muted m-0">
          Comparison needs two backlog versions. There {versions.length === 1 ? "is one" : "are none"} so far.
        </p>
      </section>
    );
  }

  const byNumber = new Map(versions.map((revision) => [revision.number, revision]));
  const before = comparison ? byNumber.get(comparison.from_revision) : undefined;
  const after = comparison ? byNumber.get(comparison.to_revision) : undefined;
  const facts = before && after ? factChanges(before, after) : [];
  const outOfDate = comparison && (comparison.from_revision !== from || comparison.to_revision !== to);
  const backwards = comparison && comparison.from_revision > comparison.to_revision;
  const options = [...versions].reverse().map((revision) => (
    <option key={revision.number} value={revision.number}>
      {optionLabel(revision, approved?.number ?? null, latest?.number)}
    </option>
  ));
  const approvedPair = approved && latest && approved.number !== latest.number ? { from: approved.number, to: latest.number } : null;
  const previousPair = previous && latest && previous.number !== approved?.number ? { from: previous.number, to: latest.number } : null;

  return (
    <section aria-labelledby="compare-title" className="grid gap-4">
      <SectionHeading
        description="Pick two backlog versions to see what changed between them."
        id="compare-title"
        title="Compare versions"
      />
      <div className="flex flex-wrap items-start gap-3">
        <Select fieldClassName="min-w-[15rem] flex-1 md:flex-none" label="From" onChange={(event) => setFrom(Number(event.target.value))} value={from}>
          {options}
        </Select>
        <Button
          aria-label="Swap From and To"
          className="mt-[1.4rem]"
          icon={<ArrowLeftRight aria-hidden="true" size={16} />}
          onClick={() => {
            setFrom(to);
            setTo(from);
          }}
          variant="ghost"
        />
        <Select fieldClassName="min-w-[15rem] flex-1 md:flex-none" label="To" onChange={(event) => setTo(Number(event.target.value))} value={to}>
          {options}
        </Select>
        <div className="mt-[1.4rem]">
          <Button
            blockedReason={from === to ? "Pick two different versions." : undefined}
            onClick={() => {
              if (!busy && from !== to) onCompare(from, to);
            }}
            variant="secondary"
          >
            {busy ? "Comparing…" : "Compare"}
          </Button>
        </div>
      </div>
      {(approvedPair || previousPair) && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="text-meta text-ink-muted">Quick pairs:</span>
          {approvedPair && (
            <Button onClick={() => onCompare(approvedPair.from, approvedPair.to)} variant="text">
              Approved to current
            </Button>
          )}
          {previousPair && (
            <Button onClick={() => onCompare(previousPair.from, previousPair.to)} variant="text">
              Previous to current
            </Button>
          )}
        </div>
      )}
      {error && <ErrorLine>The comparison did not run: {error} Try again.</ErrorLine>}

      {comparison && (
        <Card className="grid gap-4" inset padding="fluid">
          <div className="grid gap-1">
            <h3
              className={cx("text-title text-ink m-0 scroll-mt-[calc(var(--header-height)+var(--space-4))] rounded-xs", FOCUS_RING)}
              ref={resultHeading}
              tabIndex={-1}
            >
              Version {comparison.from_revision} to version {comparison.to_revision}
            </h3>
            {backwards && (
              <p className="text-meta text-ink-muted m-0">This runs backwards: the later version is on the left.</p>
            )}
            {outOfDate && (
              <p className="text-meta text-warning m-0 flex items-center gap-1.5 font-semibold">
                <TriangleAlert aria-hidden="true" size={14} />
                You have picked other versions since. Compare again to update this.
              </p>
            )}
          </div>
          {facts.length > 0 ? (
            <Table caption={`What changed from version ${comparison.from_revision} to version ${comparison.to_revision}`}>
              <TableHead sticky={false}>
                <tr>
                  <TableHeaderCell>What</TableHeaderCell>
                  <TableHeaderCell>Version {comparison.from_revision}</TableHeaderCell>
                  <TableHeaderCell>Version {comparison.to_revision}</TableHeaderCell>
                </tr>
              </TableHead>
              <TableBody columns={3}>
                {facts.map((fact) => (
                  <TableRow key={fact.label}>
                    <th className="text-body text-ink px-3 py-2 text-left font-semibold" scope="row">
                      {fact.label}
                    </th>
                    <TableCell className="tabular-nums">{fact.before}</TableCell>
                    <TableCell className="text-ink tabular-nums">{fact.after}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="text-body text-ink-muted m-0">The counts and status are the same in both versions.</p>
          )}
          {comparison.changes.length > 0 ? (
            <div className="grid gap-2">
              <h4 className="text-body text-ink m-0 font-semibold">Changes recorded between them</h4>
              <ul className="text-body text-ink-soft m-0 grid max-w-[var(--measure-document)] gap-1 pl-5">
                {comparison.changes.map((change) => {
                  const read = readChange(change);
                  return (
                    <li key={change}>
                      {read.text}
                      {read.ids.length > 0 && (
                        <Disclosure label={`Show the ${read.text.replace(/ (added|removed|changed)\.$/, "")} by ID`}>
                          <ul className="text-meta text-ink-muted m-0 grid list-none gap-0.5 p-0 font-mono">
                            {read.ids.map((id) => (
                              <li className="[overflow-wrap:anywhere]" key={id}>
                                {id}
                              </li>
                            ))}
                          </ul>
                        </Disclosure>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <p className="text-body text-ink-muted m-0">No content change is recorded between these versions.</p>
          )}
        </Card>
      )}
    </section>
  );
}

type Row = { kind: "version"; revision: BacklogRevision } | { kind: "gap"; from: number; to: number };

function BacklogVersions({
  versions,
  approvedNumber,
  activityHref,
  onCompare,
}: {
  versions: BacklogRevision[];
  approvedNumber: number | null;
  activityHref?: string;
  onCompare: (from: number, to: number) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const newestFirst = [...versions].reverse();
  const latestNumber = versions.at(-1)?.number;
  const byNumber = new Map(versions.map((revision) => [revision.number, revision]));
  const folded = !showAll && newestFirst.length > FOLD_OVER;
  const shown = folded
    ? newestFirst.filter((revision, index) => index < SHOW_NEWEST || revision.number === approvedNumber)
    : newestFirst;

  // Rows, with a marker wherever folding skipped versions, so a jump from 13
  // to 8 never reads as consecutive.
  const rows: Row[] = [];
  shown.forEach((revision, index) => {
    const newer = shown[index - 1];
    if (newer && newer.number - revision.number > 1) rows.push({ kind: "gap", from: revision.number + 1, to: newer.number - 1 });
    rows.push({ kind: "version", revision });
  });
  const oldestShown = shown.at(-1);
  const first = versions[0]?.number ?? 1;
  if (folded && oldestShown && oldestShown.number > first) rows.push({ kind: "gap", from: first, to: oldestShown.number - 1 });

  return (
    <section aria-labelledby="backlog-versions-title" className="grid gap-4">
      <SectionHeading
        action={
          activityHref ? (
            <Link className="text-accent text-body inline-flex min-h-6 items-center" to={activityHref}>
              Who did what, in Activity
            </Link>
          ) : undefined
        }
        description="A new version is saved at every analysis, generation, edit and review decision. Newest first."
        id="backlog-versions-title"
        title="Backlog versions"
      />
      {versions.length === 0 ? (
        <p className="text-body text-ink-muted m-0">The first version is saved when the requirement is first analysed.</p>
      ) : (
        <>
          <Table caption="Backlog versions, newest first" className="table-fixed">
            <colgroup>
              <col className="w-[6rem]" />
              <col className="md:w-[13.5rem]" />
              {/* Zero width below md rather than hidden: a fixed table keeps a
                  hidden <col>'s width. */}
              <col className="max-md:w-0" />
              <col className="w-[3.5rem] max-md:w-0 lg:w-[10rem]" />
            </colgroup>
            <TableHead className="max-md:hidden" sticky={false}>
              <tr>
                <TableHeaderCell>Version</TableHeaderCell>
                <TableHeaderCell>Status and time saved</TableHeaderCell>
                <TableHeaderCell>Changed from the previous version</TableHeaderCell>
                <TableHeaderCell>
                  <span className="sr-only">Compare</span>
                </TableHeaderCell>
              </tr>
            </TableHead>
            <TableBody columns={4}>
              {rows.map((row) => {
                if (row.kind === "gap") {
                  const count = row.to - row.from + 1;
                  return (
                    <tr key={`gap-${row.from}`}>
                      <td className="text-meta text-ink-muted bg-surface-sunken px-3 py-1.5" colSpan={4}>
                        {count === 1 ? `Version ${row.from} is folded away` : `Versions ${row.from} to ${row.to} are folded away`}
                      </td>
                    </tr>
                  );
                }
                const { revision } = row;
                const state = revisionState(revision);
                const previous = byNumber.get(revision.number - 1);
                const open = [
                  revision.unresolved_count > 0 &&
                    `${revision.unresolved_count} unresolved ${revision.unresolved_count === 1 ? "question" : "questions"}`,
                  revision.stale_story_count > 0 &&
                    `${revision.stale_story_count} ${revision.stale_story_count === 1 ? "story" : "stories"} out of date`,
                ].filter(Boolean) as string[];
                return (
                  <TableRow
                    className={cx(revision.number === approvedNumber && "shadow-[inset_3px_0_0_var(--success)]")}
                    key={revision.number}
                  >
                    <TableCell className="align-top">
                      <span className="grid justify-items-start gap-1">
                        <span className="text-ink font-semibold tabular-nums">{revision.number}</span>
                        {revision.number === latestNumber && <Badge>Current</Badge>}
                      </span>
                    </TableCell>
                    <TableCell className="align-top">
                      <span className="grid justify-items-start gap-1">
                        <Badge icon={state.tone === "success" ? <Check aria-hidden="true" size={12} /> : undefined} tone={state.tone}>
                          {state.label}
                        </Badge>
                        <span className="text-meta text-ink-muted tabular-nums">
                          <time dateTime={revision.created_at}>{whenLabel(revision.created_at)}</time>
                        </span>
                        {/* Below md the change column folds in here. */}
                        <span className="text-meta text-ink-soft md:hidden">{changeSummary(previous, revision)}</span>
                        {open.length > 0 && (
                          <span className="text-meta text-warning inline-flex items-start gap-1">
                            <TriangleAlert aria-hidden="true" className="mt-0.5 shrink-0" size={12} />
                            {open.join(" · ")}
                          </span>
                        )}
                      </span>
                    </TableCell>
                    <TableCell className="align-top max-md:hidden">
                      <span className="grid gap-0.5">
                        <span className="text-ink-soft">{changeSummary(previous, revision)}</span>
                        <span className="text-meta text-ink-muted">{backlogContents(revision)}</span>
                      </span>
                    </TableCell>
                    <TableCell className="align-top max-md:hidden">
                      {previous && (
                        <Button
                          aria-label={`Compare version ${revision.number} with version ${previous.number}`}
                          icon={<ArrowLeftRight aria-hidden="true" size={14} />}
                          onClick={() => onCompare(previous.number, revision.number)}
                          size="sm"
                          variant="ghost"
                        >
                          <span className="max-lg:hidden">With previous</span>
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          {newestFirst.length > FOLD_OVER && (
            <Button className="w-fit" onClick={() => setShowAll((value) => !value)} variant="secondary">
              {showAll ? `Show the newest ${SHOW_NEWEST} only` : `Show all ${newestFirst.length} versions`}
            </Button>
          )}
        </>
      )}
    </section>
  );
}

/** An edit, word by word: added words underlined, removed ones struck through, each also said in words. */
function Diff({ before, after }: { before: string; after: string }) {
  return (
    <>
      {wordDiff(before, after).map((part, index) =>
        part.kind === "same" ? (
          <span key={index}>{part.text}</span>
        ) : part.kind === "added" ? (
          <ins className="text-ink decoration-ink underline decoration-2 underline-offset-2" key={index}>
            <span className="sr-only">[added: </span>
            {part.text}
            <span className="sr-only">]</span>
          </ins>
        ) : (
          <del className="text-ink-muted line-through" key={index}>
            <span className="sr-only">[removed: </span>
            {part.text}
            <span className="sr-only">]</span>
          </del>
        ),
      )}
    </>
  );
}

function NeedVersions({ history, basisNumber }: { history: RevisionHistory; basisNumber: number | null }) {
  const oldestFirst = history.requirement_revisions;
  const newestFirst = [...oldestFirst].reverse();
  return (
    <section
      aria-labelledby="need-versions-title"
      className="grid scroll-mt-[calc(var(--header-height)+var(--space-4))] gap-4"
      id="need-versions"
    >
      <SectionHeading
        description="The requirement as it was written, each time it was saved. Each edit is shown word by word: added words are underlined, removed words struck through."
        id="need-versions-title"
        title="Business need versions"
      />
      {newestFirst.length === 0 ? (
        <p className="text-body text-ink-muted m-0">No version of the business need has been saved yet.</p>
      ) : (
        <ol className="border-line bg-surface m-0 grid list-none rounded-md border border-solid p-0">
          {newestFirst.map((revision, index) => {
            const previous = oldestFirst.find((candidate) => candidate.number === revision.number - 1);
            return (
              <li
                className={cx("grid gap-2 px-4 py-3", index > 0 && "[border-top:1px_solid_var(--line)]")}
                key={revision.number}
              >
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="text-ink font-semibold tabular-nums">Version {revision.number}</span>
                  {index === 0 && <Badge>Current</Badge>}
                  {revision.number === basisNumber && (
                    <Badge icon={<Check aria-hidden="true" size={12} />} tone="success">
                      The approved backlog was built from this
                    </Badge>
                  )}
                  <time className="text-meta text-ink-muted tabular-nums" dateTime={revision.created_at}>
                    {whenLabel(revision.created_at)}
                  </time>
                </div>
                <p className="text-title text-ink m-0 [overflow-wrap:anywhere]">
                  {previous && previous.title !== revision.title ? <Diff after={revision.title} before={previous.title} /> : revision.title}
                </p>
                {previous && (
                  <Disclosure defaultOpen={index === 0} label={`What changed from version ${previous.number}`}>
                    {previous.description === revision.description ? (
                      <p className="text-body text-ink-muted m-0">The text of the business need did not change.</p>
                    ) : (
                      <p className="font-serif text-document text-ink m-0 max-w-[var(--measure-document)] whitespace-pre-line">
                        <Diff after={revision.description} before={previous.description} />
                      </p>
                    )}
                  </Disclosure>
                )}
                <Disclosure label={`Read version ${revision.number} in full`}>
                  <p className="font-serif text-document text-ink m-0 max-w-[var(--measure-document)] whitespace-pre-line">
                    {revision.description || "No business need was written in this version."}
                  </p>
                </Disclosure>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
