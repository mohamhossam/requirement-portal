import { Search } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { RequirementList, WorkflowStatus, WorklistSort } from "../../api/client";
import { Pill } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Checkbox } from "../../components/ui/Checkbox";
import { cx } from "../../components/ui/cx";
import { CONTROL, SEARCH_FRAME, SEARCH_INPUT } from "./controls";
import { counterStatuses, statusLabels } from "./labels";

/**
 * One row of controls, and one row of filters under it.
 *
 * It was four stacked bands — a heading, a nine-chip counter grid 100px tall, a
 * saved-view admin bar and a search row — which put 890px between the top of
 * the page and the first requirement. Statuses nobody has are not shown: eight
 * of the nine chips read `0`, which is not information. The controls share the
 * worklist field recipe (./controls.ts).
 */
export function WorklistToolbar({
  total,
  counts,
  statuses,
  onToggleStatus,
  search,
  onSearch,
  ownerId,
  onOwner,
  ownerFacets,
  assignedToMe,
  onAssigned,
  sort,
  onSort,
  hasFilters,
  onClearFilters,
  views,
}: {
  total: number | undefined;
  counts: RequirementList["status_counts"] | undefined;
  statuses: WorkflowStatus[];
  onToggleStatus: (status: WorkflowStatus) => void;
  search: string;
  onSearch: (value: string) => void;
  ownerId: string;
  onOwner: (value: string) => void;
  ownerFacets: RequirementList["owner_facets"];
  assignedToMe: boolean;
  onAssigned: (value: boolean) => void;
  sort: WorklistSort;
  onSort: (value: WorklistSort) => void;
  hasFilters: boolean;
  onClearFilters: () => void;
  views: ReactNode;
}) {
  const [showEveryStatus, setShowEveryStatus] = useState(false);
  const worth = (status: WorkflowStatus) =>
    showEveryStatus || statuses.includes(status) || (counts?.[status] ?? 0) > 0;
  const shown = counterStatuses.filter(worth);
  const hidden = counterStatuses.length - shown.length;

  return (
    <div className="border-line grid gap-3 border-0 border-b border-solid p-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className={SEARCH_FRAME}>
          <Search className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
          <span className="sr-only">Search requirements</span>
          <input
            className={SEARCH_INPUT}
            type="search"
            value={search}
            placeholder="Search ID, title, or description"
            onChange={(event) => onSearch(event.target.value)}
          />
        </label>
        <label className="contents">
          <span className="sr-only">Owner</span>
          <select className={cx(CONTROL, "w-auto max-w-full cursor-pointer")} value={ownerId} onChange={(event) => onOwner(event.target.value)}>
            <option value="">All owners</option>
            {ownerFacets.map((facet) => (
              <option key={facet.actor.id} value={facet.actor.id}>
                {facet.actor.display_name} ({facet.count})
              </option>
            ))}
          </select>
        </label>
        <Checkbox
          label="Assigned to me"
          checked={assignedToMe}
          onChange={(event) => onAssigned(event.target.checked)}
          fieldClassName="px-1"
        />
        {/* The Updated column, and with it that sort, folds away below `md`;
            above it the column headers are the sort control. */}
        <label className="contents">
          <span className="sr-only">Sort</span>
          <select
            className={cx(CONTROL, "w-auto max-w-full cursor-pointer md:hidden")}
            value={sort}
            onChange={(event) => onSort(event.target.value as WorklistSort)}
          >
            <option value="updated_desc">Recently updated</option>
            <option value="updated_asc">Oldest updated</option>
            <option value="title_asc">Title A–Z</option>
            <option value="title_desc">Title Z–A</option>
          </select>
        </label>
        <div className="ml-auto">{views}</div>
      </div>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by status">
        {shown.map((status) => (
          <Pill
            key={status}
            active={statuses.includes(status)}
            count={counts?.[status] ?? 0}
            onClick={() => onToggleStatus(status)}
          >
            {statusLabels[status]}
          </Pill>
        ))}
        {hidden > 0 && (
          <Button variant="text" onClick={() => setShowEveryStatus(true)}>
            {hidden} more
          </Button>
        )}
        {hasFilters && (
          <Button variant="text" onClick={onClearFilters}>
            Clear filters
          </Button>
        )}
        <span className="text-meta text-ink-muted ml-auto tabular-nums" aria-live="polite">
          {total === undefined ? "Loading…" : `${total} matching`}
        </span>
      </div>
    </div>
  );
}
