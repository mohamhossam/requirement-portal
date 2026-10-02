import { keepPreviousData, useInfiniteQuery } from "@tanstack/react-query";
import { ListFilter, Sparkles } from "lucide-react";
import { useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  api,
  type ActivityAction,
  type ActivityCategory,
  type ActivityEvent,
  type ActivityListParams,
} from "../api/client";
import { errorMessage } from "../api/errors";
import { PageHeader } from "../components/shell";
import { AsyncState } from "../components/states";
import { Button } from "../components/ui/Button";
import { cx } from "../components/ui/cx";
import { FOCUS_RING } from "../components/ui/recipes";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui/Table";
import { ActivityFilters, type ActivityFilterChange, type ActivityFilterState } from "./activity/ActivityFilters";
import {
  actionLabels,
  actionTone,
  automaticActions,
  categoryIcons,
  categoryLabels,
  dateRangeError,
  dayKey,
  dayLabel,
  localZoneName,
  sourceView,
  utcDate,
} from "./activity/labels";
import { queryKeys } from "./queryKeys";
import { useDocumentTitle } from "./useDocumentTitle";

const PAGE_SIZE = 100;
const FOLD = "max-md:hidden";
const COLUMNS = 5;

const tones = {
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
} as const;

/**
 * What happened, in the same words the filter uses, then the record's own
 * sentence when it adds something — the question's subject, who took
 * ownership. The category is the glyph and a quiet label, and is dropped when
 * the list is already filtered to it.
 */
function Happened({ item, showCategory }: { item: ActivityEvent; showCategory: boolean }) {
  const Category = categoryIcons[item.category];
  const tone = actionTone[item.action];
  const label = actionLabels[item.action];
  const detail = item.summary.trim().toLowerCase() === label.toLowerCase() ? null : item.summary;
  return (
    <span className="grid min-w-0 gap-0.5">
      <span className="text-ink inline-flex min-w-0 items-start gap-1.5">
        {tone && <tone.icon aria-hidden="true" className={cx("mt-0.5 shrink-0", tones[tone.tone])} size={14} />}
        <span className="[overflow-wrap:anywhere]">{label}</span>
      </span>
      {detail && <span className="text-meta text-ink-soft [overflow-wrap:anywhere]">{detail}</span>}
      {showCategory && (
        <span className="text-meta text-ink-muted inline-flex items-center gap-1">
          <Category aria-hidden="true" className="shrink-0" size={12} />
          {categoryLabels[item.category]}
        </span>
      )}
    </span>
  );
}

function Actor({ item }: { item: ActivityEvent }) {
  if (item.actor) return <span className="text-ink-soft">{item.actor.display_name}</span>;
  if (automaticActions.has(item.action)) {
    return (
      <span className="text-ink-soft inline-flex items-center gap-1">
        <Sparkles aria-hidden="true" className="text-ink-muted shrink-0" size={12} />
        Requirement AI
      </span>
    );
  }
  return <span className="text-ink-muted">Not recorded</span>;
}

/** The record the event was read from — in words, with a reference to quote. */
function Evidence({ item }: { item: ActivityEvent }) {
  const [first, ...rest] = item.sources;
  if (!first) return <span className="text-ink-muted">None recorded</span>;
  const source = sourceView(first);
  return (
    <span className="text-meta text-ink-muted grid gap-0.5">
      <span>
        {source.label}
        {source.reference && <span className="text-ink-soft font-mono whitespace-nowrap"> {source.reference}</span>}
      </span>
      {rest.length > 0 && <span>and {rest.length} more</span>}
    </span>
  );
}

/** "By Amina Owner", inline — or plainly that no person was recorded. */
function ByLine({ item }: { item: ActivityEvent }) {
  if (!item.actor && !automaticActions.has(item.action)) return <span className="text-ink-muted">No person recorded</span>;
  return (
    <span className="text-ink-muted">
      By <Actor item={item} />
    </span>
  );
}

function RequirementLink({ item }: { item: ActivityEvent }) {
  return (
    <Link
      className="text-accent inline-block min-h-6 py-0.5 no-underline [overflow-wrap:anywhere] hover:underline"
      to={item.resource_path}
    >
      {item.requirement_title}
    </Link>
  );
}

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });
const fullFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "full", timeStyle: "long" });

export function ActivityPage() {
  useDocumentTitle("Activity");
  const [searchParams, setSearchParams] = useSearchParams();
  const read = (key: string) => searchParams.get(key) ?? "";

  // A report cell links here with exact week boundaries (occurred_from /
  // occurred_before). They show in the date fields as the days they are, and
  // give way to whatever the person picks there.
  const occurredFrom = read("occurred_from");
  const occurredBefore = read("occurred_before");
  const state: ActivityFilterState = {
    requirementId: read("requirement_id"),
    actorId: read("actor_id"),
    category: (searchParams.get("category") as ActivityCategory | null) || null,
    action: (searchParams.get("action") as ActivityAction | null) || null,
    start: read("start") || (occurredFrom ? utcDate(occurredFrom) : ""),
    end: read("end") || (occurredBefore ? utcDate(occurredBefore) : ""),
  };

  const params: ActivityListParams = {
    requirementId: state.requirementId || undefined,
    categories: state.category && !state.action ? [state.category] : undefined,
    actions: state.action ? [state.action] : undefined,
    actorId: state.actorId || undefined,
    occurredFrom: read("start") ? `${read("start")}T00:00:00Z` : occurredFrom || undefined,
    occurredBefore: read("end") ? `${read("end")}T00:00:00Z` : occurredBefore || undefined,
    limit: PAGE_SIZE,
  };

  const activity = useInfiniteQuery({
    queryKey: queryKeys.activity(params),
    initialPageParam: 0,
    queryFn: ({ pageParam }) => api.listActivity({ ...params, offset: pageParam }),
    getNextPageParam: (page) => (page.has_more ? page.offset + page.items.length : undefined),
    placeholderData: keepPreviousData,
  });

  const items = useMemo(() => activity.data?.pages.flatMap((page) => page.items) ?? [], [activity.data]);
  const total = activity.data?.pages[0]?.total ?? 0;

  const days = useMemo(() => {
    const groups: Array<{ key: string; label: string; items: ActivityEvent[] }> = [];
    for (const item of items) {
      const date = new Date(item.occurred_at);
      const key = dayKey(date);
      const last = groups.at(-1);
      if (last?.key === key) last.items.push(item);
      else groups.push({ key, label: dayLabel(date), items: [item] });
    }
    return groups;
  }, [items]);

  const knownActors = useMemo(
    () => new Map(items.flatMap((item) => (item.actor ? [[item.actor.id, item.actor.display_name] as const] : []))),
    [items],
  );
  const knownRequirements = useMemo(
    () => new Map(items.map((item) => [item.requirement_id, item.requirement_title] as const)),
    [items],
  );

  // Filters replace the history entry rather than adding one per change, so
  // Back leaves the page instead of stepping through every keystroke.
  const update = (change: ActivityFilterChange) => {
    const next = new URLSearchParams(searchParams);
    const put = (key: string, value: string | null) => (value ? next.set(key, value) : next.delete(key));
    if (change.key === "requirement") put("requirement_id", change.value);
    if (change.key === "actor") put("actor_id", change.value);
    if (change.key === "what") {
      put("category", change.category);
      put("action", change.action);
    }
    if (change.key === "start") {
      put("start", change.value);
      next.delete("occurred_from");
    }
    if (change.key === "end") {
      put("end", change.value);
      next.delete("occurred_before");
    }
    setSearchParams(next, { replace: true });
  };
  const clear = () => setSearchParams({}, { replace: true });

  const filtered = Boolean(
    state.requirementId || state.actorId || state.category || state.action || state.start || state.end,
  );
  const rangeError = dateRangeError(state);
  const zone = localZoneName();
  const status = activity.isPending ? "pending" : activity.isError ? "error" : items.length === 0 ? "empty" : "ready";
  const count = new Intl.NumberFormat();

  // The Load more button goes away once the last page is in, so focus moves to
  // the first row that arrived instead of falling back to the page.
  const loadMore = async () => {
    const shown = items.length;
    const result = await activity.fetchNextPage();
    const next = result.data?.pages.flatMap((entry) => entry.items)[shown];
    if (next) {
      window.requestAnimationFrame(() =>
        document.querySelector<HTMLElement>(`[data-event-id="${CSS.escape(next.id)}"] > td`)?.focus(),
      );
    }
  };

  return (
    <>
      <PageHeader
        title="Activity"
        description="Who did what, and when, across every requirement. Each entry names the record it was read from."
      />
      <div className="border-line bg-surface min-w-0 rounded-md border border-solid">
        <div className="border-line grid gap-4 border-0 border-b border-solid p-4">
          <ActivityFilters
            knownActors={knownActors}
            knownRequirements={knownRequirements}
            onChange={update}
            state={state}
          />
          <div className="flex min-h-6 flex-wrap items-center gap-x-4 gap-y-1">
            <p aria-live="polite" className="text-meta text-ink-muted m-0 tabular-nums" role="status">
              {activity.isPending
                ? "Loading activity…"
                : activity.isError
                  ? ""
                  : activity.isPlaceholderData
                    ? "Updating…"
                    : total === items.length
                      ? `${count.format(total)} ${total === 1 ? "event" : "events"}`
                      : `Showing ${count.format(items.length)} of ${count.format(total)} events`}
            </p>
            <p className="text-meta text-ink-muted m-0">
              Times are in your time zone ({zone}). From and Before are whole days in UTC; Before is not included.
            </p>
            {filtered && status === "ready" && (
              <Button className="ml-auto" onClick={clear} variant="text">
                Clear filters
              </Button>
            )}
          </div>
        </div>
        <AsyncState
          empty={{
            title: rangeError ? "The dates leave no days to show" : filtered ? "Nothing matches these filters" : "No activity yet",
            message: rangeError
              ? "Before is the first day left out, so it has to be later than From."
              : filtered
                ? "Try a different requirement, person or kind of activity, or clear the filters."
                : "Entries appear here as soon as the first requirement is captured.",
            icon: filtered ? <ListFilter aria-hidden="true" size={20} /> : undefined,
            action: filtered ? (
              <Button onClick={clear} variant="secondary">
                Clear filters
              </Button>
            ) : undefined,
          }}
          error={{ title: "We couldn’t load the activity", message: errorMessage(activity.error) }}
          headingLevel="h2"
          loading={{ label: "Loading activity", variant: "row", bars: 6 }}
          onRetry={() => void activity.refetch()}
          status={status}
        >
          <div aria-busy={activity.isPlaceholderData || undefined}>
            <Table caption="Activity, newest first" className="md:table-fixed" framed={false}>
              <colgroup>
                <col className="w-[5.5rem]" />
                <col className="md:w-[34%]" />
                <col className="max-md:hidden" />
                <col className="w-[10.5rem] max-md:hidden" />
                {/* Last, so hiding its cells below lg cannot shift the cells before
                    it into the wrong columns; zero width, because a fixed table keeps
                    a hidden <col>'s width. Below lg the person is named under Evidence. */}
                <col className="w-[12rem] max-lg:w-0" />
              </colgroup>
              <TableHead className="max-md:hidden" sticky={false}>
                <tr>
                  <TableHeaderCell>Time</TableHeaderCell>
                  <TableHeaderCell>What happened</TableHeaderCell>
                  <TableHeaderCell>Requirement</TableHeaderCell>
                  <TableHeaderCell>Evidence</TableHeaderCell>
                  <TableHeaderCell className="max-lg:hidden">By</TableHeaderCell>
                </tr>
              </TableHead>
              {days.map((day, dayIndex) => (
                <TableBody key={day.key} columns={COLUMNS}>
                  <tr>
                    <th
                      className="bg-surface [border-top:1px_solid_var(--line)] px-3 pt-5 pb-2 text-left"
                      colSpan={COLUMNS}
                      scope="colgroup"
                    >
                      <h2 className="text-title text-ink m-0">
                        {day.label}
                        <span className="text-meta text-ink-muted ml-2 font-normal tabular-nums">
                          {day.items.length} {day.items.length === 1 ? "event" : "events"}
                          {/* The oldest day on screen may continue on the next page. */}
                          {dayIndex === days.length - 1 && activity.hasNextPage && " shown so far"}
                        </span>
                      </h2>
                    </th>
                  </tr>
                  {day.items.map((item) => {
                    const at = new Date(item.occurred_at);
                    return (
                      <TableRow data-event-id={item.id} key={item.id}>
                        <TableCell className={cx("text-meta text-ink-muted align-top tabular-nums", FOCUS_RING)} tabIndex={-1}>
                          <time dateTime={item.occurred_at} title={fullFormat.format(at)}>
                            {timeFormat.format(at)}
                          </time>
                        </TableCell>
                        <TableCell className="align-top">
                          <span className="grid gap-2">
                            <Happened item={item} showCategory={!state.category} />
                            {/* Below md the three right-hand columns fold in here. */}
                            <span className="text-meta grid gap-1 md:hidden">
                              <RequirementLink item={item} />
                              <ByLine item={item} />
                              <Evidence item={item} />
                            </span>
                          </span>
                        </TableCell>
                        <TableCell className={cx(FOLD, "align-top")}>
                          <RequirementLink item={item} />
                        </TableCell>
                        <TableCell className={cx(FOLD, "align-top")}>
                          <span className="grid gap-1">
                            <Evidence item={item} />
                            <span className="text-meta lg:hidden">
                              <ByLine item={item} />
                            </span>
                          </span>
                        </TableCell>
                        <TableCell className="align-top max-lg:hidden">
                          <Actor item={item} />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              ))}
            </Table>
          </div>
          {activity.hasNextPage && (
            <div className="border-line flex flex-wrap items-center gap-3 border-0 border-t border-solid p-4">
              <Button
                disabled={activity.isFetchingNextPage}
                onClick={() => void loadMore()}
                variant="secondary"
              >
                {activity.isFetchingNextPage
                  ? "Loading more…"
                  : `Show ${count.format(Math.min(PAGE_SIZE, total - items.length))} more`}
              </Button>
              <span className="text-meta text-ink-muted tabular-nums">
                {count.format(total - items.length)} older {total - items.length === 1 ? "event" : "events"} not shown
              </span>
            </div>
          )}
        </AsyncState>
      </div>
    </>
  );
}
