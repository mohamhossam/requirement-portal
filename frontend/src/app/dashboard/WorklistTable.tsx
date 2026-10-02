import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import type { RequirementWorklistItem, WorklistSort } from "../../api/client";
import { Badge } from "../../components/ui/Badge";
import { cx } from "../../components/ui/cx";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  type SortDirection,
} from "../../components/ui/Table";
import { stagePath } from "../stagePath";
import { actorLabel, jobLabels, nextActionLabels, stageLabels, statusBadge, statusLabels, updatedLabel } from "./labels";

/**
 * The worklist, as a table (docs/ux-plan.md Phase 1; docs/design-system.md §11).
 *
 * It was a list of links dressed as a table, with the column headings hidden
 * from assistive technology and sorting only through a dropdown (ux-plan §3.12).
 * A real table gives each value its column header, and the two columns the API
 * can order by — Requirement (title) and Updated — are sort buttons exposing
 * `aria-sort`.
 *
 * The row is still one click, which is the interaction worth keeping: the title
 * is a link stretched over the whole row by a pseudo-element, so the table keeps
 * cell semantics and a person can still hit anywhere on the line. The row, not
 * the title, shows the focus ring. The link is named by the title alone and
 * described by the status and the next action, so tabbing through reads "High-
 * speed business bundles — Needs answers. Next: Answer open questions" instead
 * of thirty-five run-together words.
 *
 * Below `md` the Owner, Status, Updated and Next action cells fold into the Requirement cell
 * as secondary lines. One DOM at every width, and nothing scrolls sideways.
 *
 * The next action is ink, not indigo. The accent is spent once on this screen,
 * on the Next block above the table; fifteen indigo rows had been fifteen
 * accents (§4.4 rule 1).
 */
const FOLD = "max-md:hidden";

function direction(sort: WorklistSort, column: "title" | "updated"): SortDirection | null {
  if (column === "title") return sort === "title_asc" ? "asc" : sort === "title_desc" ? "desc" : null;
  return sort === "updated_asc" ? "asc" : sort === "updated_desc" ? "desc" : null;
}

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * Status, stage and what is still open — one cell, because they answer one
 * question: how far has this got, and what is holding it?
 */
function Progress({ item, statusId }: { item: RequirementWorklistItem; statusId?: string }) {
  const badge = statusBadge[item.workflow_status];
  const Icon = badge.icon;
  const { epics, features, stories } = item.artifact_counts;
  // Unresolved and stale are the product's most important facts (PRODUCT.md
  // Principle 1): amber, in words, whenever they are not zero.
  const flags = [
    item.unresolved_items > 0 && `${item.unresolved_items} unresolved`,
    item.stale_items > 0 && `${item.stale_items} stale`,
  ].filter(Boolean);
  return (
    <span className="grid min-w-0 justify-items-start gap-1">
      <Badge id={statusId} tone={badge.tone} icon={<Icon aria-hidden={true} className="shrink-0" size={12} />}>
        {statusLabels[item.workflow_status]}
      </Badge>
      <span className="text-meta text-ink-soft">
        {stageLabels[item.current_stage]}
        {/* Counts only once there is a backlog to count; before that they are a
            line of zeros. */}
        {epics + features + stories > 0 && (
          <span className="text-ink-muted tabular-nums">
            {" "}· {count(features, "Feature", "Features")} · {count(stories, "Story", "Stories")}
          </span>
        )}
      </span>
      {flags.length > 0 && <span className="text-meta text-warning font-semibold">{flags.join(" · ")}</span>}
    </span>
  );
}

export function WorklistTable({
  items,
  sort,
  onSort,
}: {
  items: RequirementWorklistItem[];
  sort: WorklistSort;
  onSort: (sort: WorklistSort) => void;
}) {
  const titleSort = direction(sort, "title");
  const updatedSort = direction(sort, "updated");
  return (
    <Table caption="Requirements worklist" framed={false} className="table-fixed">
      <colgroup>
        <col />
        {/* About 38rem of fixed columns, so the title — the thing a person scans
            for — keeps the rest: roughly 370px at 1280, 560px at 1440. */}
        <col className="w-[9.5rem] max-md:hidden" />
        <col className="w-[10rem] max-md:hidden" />
        <col className="w-[7rem] max-md:hidden" />
        <col className="w-[11.5rem] max-md:hidden" />
      </colgroup>
      <TableHead>
        <tr>
          <TableHeaderCell sort={titleSort} onSort={() => onSort(titleSort === "asc" ? "title_desc" : "title_asc")}>
            Requirement
          </TableHeaderCell>
          <TableHeaderCell className={FOLD}>Owner</TableHeaderCell>
          <TableHeaderCell className={FOLD}>Status</TableHeaderCell>
          <TableHeaderCell
            className={FOLD}
            sort={updatedSort}
            onSort={() => onSort(updatedSort === "desc" ? "updated_asc" : "updated_desc")}
          >
            Updated
          </TableHeaderCell>
          <TableHeaderCell align="end" className={FOLD}>Next action</TableHeaderCell>
        </tr>
      </TableHead>
      <TableBody columns={5}>
        {items.map((item) => {
          const statusId = `worklist-${item.id}-status`;
          const nextId = `worklist-${item.id}-next`;
          return (
            <TableRow
              key={item.id}
              interactive
              data-worklist-row=""
              className="relative has-[a:focus-visible]:[outline:3px_solid_var(--focus)] has-[a:focus-visible]:[outline-offset:-3px]"
            >
              <TableCell className="py-3">
                <span className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1">
                  <Link
                    aria-describedby={`${statusId} ${nextId}`}
                    className="text-title text-ink line-clamp-2 min-w-0 no-underline after:absolute after:inset-0 after:content-[''] hover:underline focus-visible:outline-none"
                    to={stagePath(item)}
                  >
                    {item.title}
                  </Link>
                  <span className="text-meta text-ink-muted min-w-0 truncate">
                    <code className="text-mono text-ink-faint mr-2">{item.id.slice(0, 8)}</code>
                    {item.description}
                  </span>
                  {/* The columns this row folds away below `md`. The link's
                      description points at the Status cell's badge, which still
                      counts while that cell is folded away: an element named
                      directly by aria-describedby is read whether it shows or not. */}
                  <span className="text-meta text-ink-muted grid grid-cols-[minmax(0,1fr)] gap-1 md:hidden">
                    <span>
                      {item.owner?.display_name ?? "Unowned legacy"} · {updatedLabel(item.updated_at)}
                    </span>
                    <Progress item={item} />
                    <span className="text-body text-ink flex items-center gap-1 font-semibold">
                      {nextActionLabels[item.next_action]}
                      <ChevronRight className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
                    </span>
                  </span>
                </span>
              </TableCell>
              <TableCell className={FOLD}>
                <span className="grid min-w-0 gap-0.5">
                  <span className="text-ink truncate">{item.owner?.display_name ?? "Unowned legacy"}</span>
                  <span className="text-meta text-ink-muted truncate">Last: {actorLabel(item)}</span>
                </span>
              </TableCell>
              <TableCell className={FOLD}>
                <Progress item={item} statusId={statusId} />
              </TableCell>
              <TableCell className={cx(FOLD, "text-meta text-ink-muted tabular-nums")}>
                <time dateTime={item.updated_at}>{updatedLabel(item.updated_at)}</time>
              </TableCell>
              <TableCell className={cx(FOLD, "text-right")}>
                <span className="grid justify-items-end gap-0.5" id={nextId}>
                  <span className="text-ink flex min-w-0 items-center gap-1 font-semibold">
                    {/* The space is its own text node: inside the hidden span it is
                        trimmed, and "Next:Analyse requirement" is what gets read. */}
                    <span className="sr-only">Next:</span>{" "}
                    <span className="min-w-0 truncate">{nextActionLabels[item.next_action]}</span>
                    <ChevronRight className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
                  </span>
                  {item.active_ai_operation && (
                    <span className="text-meta text-ink-muted truncate">{jobLabels[item.active_ai_operation]}</span>
                  )}
                </span>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
