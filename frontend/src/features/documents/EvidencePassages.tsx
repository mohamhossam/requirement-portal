import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";

import { api } from "../../api/client";
import { Disclosure } from "../../components/Disclosure";
import { errorMessage } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { ErrorNotice, Skeleton } from "../../components/states";
import { Badge, Table, cx } from "../../components/ui";
import { groupPassages, hiddenSheetOf, type EvidenceBlock, type PassageRun } from "./passages";

function EvidenceImage({
  documentId,
  versionId,
  block,
}: {
  documentId: string;
  versionId: string;
  block: EvidenceBlock;
}) {
  const asset = useQuery({
    queryKey: queryKeys.scope("document-asset", documentId, versionId, block.asset_id),
    queryFn: () => api.getDocumentAsset(documentId, versionId, block.asset_id!),
    enabled: Boolean(block.asset_id),
  });
  const url = useMemo(() => asset.data ? URL.createObjectURL(asset.data) : null, [asset.data]);
  useEffect(() => () => { if (url) URL.revokeObjectURL(url); }, [url]);
  if (asset.isError) return <ErrorNotice message={errorMessage(asset.error)} />;
  return url
    ? <img className="border-line block max-h-[42rem] max-w-full rounded-sm border border-solid object-contain" src={url} alt={`${block.label} evidence`} loading="lazy" />
    : <Skeleton label="Loading protected image" variant="inline" />;
}

const NOT_SENT = "bg-surface-sunken";
const BACK = "text-accent text-meta underline underline-offset-2 inline-flex min-h-6 items-center";

/**
 * The passage's place in the file. Plain text: a link on every passage was a
 * tab stop per paragraph, and the outline and the warnings already link in.
 * A heading says it is one — the reader labels it by position, "Paragraph 1".
 */
function Location({ block }: { block: EvidenceBlock }) {
  return (
    <span className="text-ink-muted inline-flex min-h-6 items-center">
      {block.kind === "heading" && !block.label.startsWith("Hidden worksheet") && !block.label.startsWith("Worksheet") ? `Heading · ${block.label}` : block.label}
    </span>
  );
}

function RunNotes({ notSent, flagged }: { notSent: boolean; flagged: boolean }) {
  return (
    <>
      {notSent && <Badge tone="neutral">Not sent · hidden sheet</Badge>}
      {flagged && (
        <>
          <Badge tone="warning">Check this</Badge>
          {/* "Show in the file" brings a person here; this takes them back. */}
          <a className={BACK} href="#what-to-check">Back to what to check</a>
        </>
      )}
    </>
  );
}

/**
 * Runs of table rows and worksheet ranges, drawn as the table they came from:
 * column letters for a sheet, positions for a Word table, row numbers down the
 * side, the cells in the document serif. Each passage's first row keeps the
 * `#block-<id>` anchor, so links into it still land on the right line.
 */
function PassageGrid({ run, flagged, notSent, badge }: {
  run: Extract<PassageRun, { type: "grid" }>;
  flagged: Set<string>;
  notSent: boolean;
  badge: boolean;
}) {
  const anyFlagged = run.blocks.some((block) => flagged.has(block.id));
  const first = run.rows[0]?.number;
  const last = run.rows.at(-1)?.number;
  const caption = `${run.section}${first !== undefined ? `, rows ${first}${last !== first ? `–${last}` : ""}` : ""}`;
  return (
    <li className={cx("grid min-w-0 gap-2 px-4 py-4 sm:px-6", notSent && NOT_SENT)}>
      <p className="text-meta text-ink-muted m-0 flex flex-wrap items-center gap-x-2 gap-y-1">
        <span>{caption}</span>
        <RunNotes notSent={badge} flagged={anyFlagged} />
      </p>
      <Table caption={caption} framed={false}>
        <thead className="bg-surface-sunken [border-bottom:1px_solid_var(--line)]">
          <tr>
            <th className="text-label text-ink-muted w-12 px-3 py-2 text-left" scope="col">Row</th>
            {run.columns.map((column) => (
              <th className="text-label text-ink-muted px-3 py-2 text-left" key={column} scope="col">
                {run.kind === "worksheet_range" ? column : `Column ${column}`}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&>tr+tr]:[border-top:1px_solid_var(--line)]">
          {run.rows.map((row) => (
            <tr
              id={row.first ? `block-${row.block.id}` : undefined}
              key={`${row.block.id}-${row.number}`}
              className={cx(
                flagged.has(row.block.id) && "[&>th]:shadow-[inset_3px_0_0_var(--warning-edge)]",
                "target:bg-accent-wash [&:target>th]:shadow-[inset_3px_0_0_var(--accent)]",
              )}
            >
              <th className="text-meta text-ink-muted px-3 py-2 text-left align-top font-normal tabular-nums" scope="row">
                {row.number}
              </th>
              {run.columns.map((column) => (
                <td
                  className={cx("font-serif text-document px-3 py-2 align-top [overflow-wrap:break-word]", notSent ? "text-ink-muted" : "text-ink")}
                  key={column}
                >
                  {row.cells[column] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </Table>
    </li>
  );
}

/**
 * What the reader took from the file, in the document register — this is the
 * text analysis reads, so it is set the way every other piece of requirement
 * prose is (DESIGN.md, "The Register Rule").
 *
 * Passages from a hidden sheet nobody ticked are shown, because a person has to
 * see what they would be sending before they tick it, but on the margin ground
 * with "Not sent · hidden sheet": the heading above this list says every
 * passage below is what analysis reads, and for those it is not.
 *
 * `#block-<id>` is a contract: Clarify's "Open this passage" links land here.
 * The passage a link points at carries the indigo edge; one a warning points at,
 * the amber edge and a way back to the warning.
 */
export function EvidencePassages({
  documentId,
  versionId,
  blocks,
  flagged,
  hiddenSheets,
  includedHiddenSheets,
  sent,
  beside = false,
}: {
  documentId: string;
  versionId: string;
  blocks: EvidenceBlock[];
  flagged: Set<string>;
  hiddenSheets: string[];
  includedHiddenSheets: string[];
  /** Whether the file itself is in analysis. When it is not, every passage is on the margin ground. */
  sent: boolean;
  /** Set beside the original: no outline column, and images one click away. */
  beside?: boolean;
}) {
  const runs = groupPassages(blocks);
  /** A passage from a hidden sheet nobody ticked: badged, because it differs from its neighbours. */
  const hiddenUnsent = (block: EvidenceBlock) => {
    const sheet = hiddenSheetOf(block, hiddenSheets);
    return Boolean(sheet && !includedHiddenSheets.includes(sheet));
  };
  /** Any passage that is not sent, for the muted ground — the whole file when it is left out. */
  const notSent = (block: EvidenceBlock) => !sent || hiddenUnsent(block);
  const headings = blocks.filter((block) => block.kind === "heading");
  // One heading is not an outline, and a single entry beside the passages
  // only took 15rem from them.
  const outline = headings.length >= 2 && !beside;

  return (
    <div className={cx("grid items-start gap-6", outline && "lg:grid-cols-[15rem_minmax(0,1fr)]")}>
      {outline && (
        <nav
          aria-label="Document outline"
          className={cx(
            "border-line bg-surface-sunken grid gap-2 rounded-md border border-solid p-4",
            // Pinned beside the passages at `lg`, clear of the fixed header, and
            // scrolling on its own when the outline is longer than the screen.
            "lg:sticky lg:top-[calc(var(--header-height)+var(--space-4))] lg:max-h-[calc(100vh-var(--header-height)-var(--space-8))] lg:overflow-auto",
          )}
        >
          <h3 className="text-label text-ink-muted m-0">Outline</h3>
          <ol className="m-0 grid list-none gap-1 p-0">
            {headings.map((block) => (
              <li key={block.id}>
                <a className="text-body text-ink grid min-h-6 py-0.5 no-underline hover:underline" href={`#block-${block.id}`}>
                  <span className="[overflow-wrap:anywhere]">{block.text?.trim() || block.label}</span>
                  <span className="text-meta text-ink-muted">
                    {block.label}{hiddenUnsent(block) ? " · not sent" : ""}
                  </span>
                </a>
              </li>
            ))}
          </ol>
        </nav>
      )}
      <ol className="border-line bg-surface m-0 grid min-w-0 list-none overflow-hidden rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
        {runs.map((run) => {
          if (run.type === "grid") {
            const [first] = run.blocks;
            return first ? <PassageGrid key={first.id} run={run} flagged={flagged} notSent={notSent(first)} badge={hiddenUnsent(first)} /> : null;
          }
          const { block } = run;
          const muted = notSent(block);
          return (
            <li
              id={`block-${block.id}`}
              key={block.id}
              className={cx(
                "grid min-w-0 gap-1.5 px-4 py-4 [overflow-wrap:anywhere] sm:px-6",
                muted && NOT_SENT,
                flagged.has(block.id) && "shadow-[inset_3px_0_0_var(--warning-edge)]",
                "target:bg-accent-wash target:shadow-[inset_3px_0_0_var(--accent)]",
              )}
            >
              <p className="text-meta m-0 flex flex-wrap items-center gap-x-2 gap-y-1">
                <Location block={block} />
                <RunNotes notSent={hiddenUnsent(block)} flagged={flagged.has(block.id)} />
              </p>
              {block.kind === "heading" ? (
                <h3 className={cx("font-serif text-document-lead m-0 font-semibold", muted ? "text-ink-muted" : "text-ink")}>{block.text}</h3>
              ) : null}
              {block.kind !== "heading" && block.kind !== "image" ? (
                <p className={cx("font-serif text-document m-0 max-w-[var(--measure-document)] whitespace-pre-wrap", muted ? "text-ink-muted" : "text-ink-soft")}>
                  {block.text}
                </p>
              ) : null}
              {block.kind === "image" && beside ? (
                <Disclosure label="Show the image">
                  <EvidenceImage documentId={documentId} versionId={versionId} block={block} />
                </Disclosure>
              ) : null}
              {block.kind === "image" && !beside ? <EvidenceImage documentId={documentId} versionId={versionId} block={block} /> : null}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
