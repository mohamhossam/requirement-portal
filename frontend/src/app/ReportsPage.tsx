import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Check, CircleAlert } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { api, type OperationalReport } from "../api/client";
import { errorMessage } from "../api/errors";
import { PageHeader } from "../components/shell";
import { AsyncState, asyncStatus } from "../components/states";
import { Pill } from "../components/ui/Badge";
import { ButtonLink } from "../components/ui/Button";
import { Disclosure } from "../components/Disclosure";
import { cx } from "../components/ui/cx";
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from "../components/ui/Table";
import { sourceView, utcDayLabel } from "./activity/labels";
import { queryKeys } from "./queryKeys";
import { ThroughputChart, type ThroughputSeries } from "./reports/ThroughputChart";
import { useDocumentTitle } from "./useDocumentTitle";

type Weeks = 4 | 12 | 26;
type Week = OperationalReport["weekly"][number];

const metricLink = (action: string, start: string, end: string) =>
  `/activity?action=${action}&occurred_from=${encodeURIComponent(start)}&occurred_before=${encodeURIComponent(end)}`;

/**
 * The five weekly measures, each with the activity it counts. "Artifact" and
 * "breakdown" are the method's words; a Product Owner approves backlog items
 * one by one, then approves the backlog as a whole.
 */
const METRICS: Array<{ key: string; label: string; noun: [string, string]; action: string; value: (week: Week) => number }> = [
  { key: "created", label: "Requirements created", noun: ["requirement created", "requirements created"], action: "requirement_created", value: (week) => week.requirements_created.value },
  { key: "analysis", label: "Analysis rounds", noun: ["analysis round", "analysis rounds"], action: "analysis_generated", value: (week) => week.analysis_rounds.value },
  { key: "resolved", label: "Questions resolved", noun: ["question resolved", "questions resolved"], action: "question_resolved", value: (week) => week.clarifications_resolved.value },
  { key: "items", label: "Backlog items approved", noun: ["backlog item approved", "backlog items approved"], action: "artifact_approved", value: (week) => week.artifact_approvals.value },
  { key: "backlogs", label: "Backlogs approved", noun: ["backlog approved", "backlogs approved"], action: "breakdown_approved", value: (week) => week.breakdown_approvals.value },
];

const daysOpen = (openedAt: string, now: string) =>
  Math.floor((new Date(now).getTime() - new Date(openedAt).getTime()) / 86_400_000);

function ageLabel(openedAt: string, now: string) {
  const days = daysOpen(openedAt, now);
  if (days < 1) return "Opened today";
  return days === 1 ? "1 day" : `${days} days`;
}

function medianLabel(hours: number | null) {
  if (hours === null) return "No question resolved yet";
  if (hours < 1) return "Under an hour";
  if (hours < 48) return `${Math.round(hours)} ${Math.round(hours) === 1 ? "hour" : "hours"}`;
  return `${Math.round(hours / 24)} days`;
}

const SECTION = "border-line bg-surface grid min-w-0 gap-4 rounded-md border border-solid p-4 sm:p-6";

export function ReportsPage() {
  useDocumentTitle("Reports");
  const [searchParams, setSearchParams] = useSearchParams();
  const initial = Number(searchParams.get("weeks") ?? 12);
  const weeks: Weeks = initial === 4 || initial === 26 ? initial : 12;
  const report = useQuery({
    queryKey: queryKeys.reports(weeks),
    queryFn: () => api.getOperationalReport(weeks),
  });
  const choose = (value: Weeks) => setSearchParams({ weeks: String(value) });

  const data = report.data;

  return (
    <>
      <PageHeader
        title="Reports"
        description="What is stuck, and whether the portfolio is moving. Every count opens the activity behind it."
        actions={
          <div aria-label="Reporting window" className="flex flex-wrap items-center gap-2" role="group">
            <span aria-hidden="true" className="text-label text-ink-muted">
              Window
            </span>
            {([4, 12, 26] as Weeks[]).map((value) => (
              <Pill active={weeks === value} key={value} onClick={() => choose(value)}>
                {value} weeks
              </Pill>
            ))}
          </div>
        }
      />
      <AsyncState
        error={{ title: "We couldn’t load the report", message: errorMessage(report.error) }}
        headingLevel="h2"
        loading={{ label: "Loading the report", variant: "panel", bars: 4 }}
        onRetry={() => void report.refetch()}
        status={asyncStatus(report)}
      >
        {data && (
          <div className="grid min-w-0 gap-6">
            <Blockers data={data} />
            <Clarification data={data} />
            <Throughput data={data} />
          </div>
        )}
      </AsyncState>
    </>
  );
}

/** First, because it is the only part of this page a person can act on today. */
function Blockers({ data }: { data: OperationalReport }) {
  const blockers = data.oldest_blockers;
  const oldest = blockers[0];
  // A column of "Not recorded" says nothing; show it only when someone is named.
  const anyOpener = blockers.some((item) => item.actor);
  return (
    <section
      aria-labelledby="blockers-title"
      className={cx(SECTION, blockers.length > 0 && "border-l-danger border-l-[3px]")}
    >
      <div className="grid gap-1">
        <h2 className="text-headline text-ink m-0 flex items-center gap-2" id="blockers-title">
          {blockers.length > 0 ? (
            <CircleAlert aria-hidden="true" className="text-danger shrink-0" size={20} />
          ) : (
            <Check aria-hidden="true" className="text-success shrink-0" size={20} />
          )}
          {blockers.length > 0 ? "Blocking now" : "Nothing is blocking"}
        </h2>
        <p className="text-body text-ink-muted m-0 max-w-[68ch]">
          {oldest
            ? `${blockers.length} open ${blockers.length === 1 ? "blocker" : "blockers"} — blocking questions and open blocking review flags, oldest first. ${
                daysOpen(oldest.opened_at, data.generated_at) < 1
                  ? "All of them were opened today."
                  : `The oldest has been open ${ageLabel(oldest.opened_at, data.generated_at)}.`
              }`
            : "No requirement has an open blocking question or an open blocking review flag."}
        </p>
      </div>
      {blockers.length > 0 && (
        <Table caption="Open blockers, oldest first" className="table-fixed">
          <colgroup>
            <col />
            <col className="w-[8.5rem]" />
            {anyOpener && <col className="w-[11rem] max-md:hidden" />}
          </colgroup>
          <TableHead sticky={false}>
            <tr>
              <TableHeaderCell>Blocker</TableHeaderCell>
              <TableHeaderCell align="end">Open for</TableHeaderCell>
              {anyOpener && <TableHeaderCell className="max-md:hidden">Opened by</TableHeaderCell>}
            </tr>
          </TableHead>
          <TableBody columns={anyOpener ? 3 : 2}>
            {blockers.map((item) => (
              <TableRow key={item.id}>
                <TableCell className="py-3">
                  <span className="grid min-w-0 gap-0.5">
                    <Link
                      className="text-accent inline-block min-h-6 py-0.5 font-semibold no-underline [overflow-wrap:anywhere] hover:underline"
                      to={item.resource_path}
                    >
                      {item.title}
                    </Link>
                    <span className="text-meta text-ink-muted [overflow-wrap:anywhere]">
                      {sourceView(item.source).label} · {item.requirement_title}
                    </span>
                  </span>
                </TableCell>
                <TableCell className="align-top" numeric>
                  {daysOpen(item.opened_at, data.generated_at) < 1 ? (
                    <time className="text-ink font-semibold" dateTime={item.opened_at}>
                      Opened today
                    </time>
                  ) : (
                    <span className="grid gap-0.5">
                      <span className="text-ink font-semibold">{ageLabel(item.opened_at, data.generated_at)}</span>
                      <time className="text-meta text-ink-muted" dateTime={item.opened_at}>
                        since {utcDayLabel(item.opened_at)}
                      </time>
                    </span>
                  )}
                </TableCell>
                {anyOpener && (
                  <TableCell className="align-top max-md:hidden">
                    {item.actor ? item.actor.display_name : <span className="text-ink-muted">Not recorded</span>}
                  </TableCell>
                )}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </section>
  );
}

function Clarification({ data }: { data: OperationalReport }) {
  const { opened, resolved, resolution_percentage: percentage, median_resolution_hours: median } = data.clarification;
  return (
    <section aria-labelledby="clarification-title" className={SECTION}>
      <h2 className="text-headline text-ink m-0" id="clarification-title">
        Resolution rate
      </h2>
      {opened.value === 0 ? (
        <p className="text-body text-ink-muted m-0">No questions were opened in this window.</p>
      ) : (
        <p className="text-body text-ink-soft m-0 max-w-[68ch]">
          <span className="text-headline text-ink tabular-nums">
            {resolved.value} of {opened.value}
          </span>{" "}
          questions opened in this window are resolved now ({Math.round(percentage)}%).
        </p>
      )}
      <dl className="m-0 grid gap-x-8 gap-y-3 sm:grid-cols-[auto_auto] sm:justify-start">
        <div className="grid gap-0.5">
          <dt className="text-label text-ink-muted">Median time to resolve</dt>
          <dd className="text-body text-ink m-0">{medianLabel(median)}</dd>
        </div>
        <div className="grid gap-0.5">
          <dt className="text-label text-ink-muted">Window</dt>
          <dd className="text-body text-ink m-0">
            {utcDayLabel(data.window_start)} to {utcDayLabel(data.window_end)}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function Throughput({ data }: { data: OperationalReport }) {
  const series: ThroughputSeries[] = METRICS.map((metric) => ({
    key: metric.key,
    label: metric.label,
    values: data.weekly.map((week) => ({ weekStart: week.week_start, value: metric.value(week) })),
  }));
  const newestFirst = [...data.weekly].reverse();
  return (
    <section aria-labelledby="throughput-title" className={SECTION}>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h2 className="text-headline text-ink m-0" id="throughput-title">
            Weekly throughput
          </h2>
          <p className="text-body text-ink-muted m-0 max-w-[68ch]">
            Weeks run Monday to Sunday in UTC. Each chart has its own scale; the outlined column is this week,
            still in progress.
          </p>
        </div>
      </div>
      <ThroughputChart series={series} weeks={data.weeks} />
      <Disclosure label="Weekly numbers, each linked to the activity it counts">
        <Table caption="Weekly counts, newest week first. Each count opens the activity it counts." className="min-w-[44rem]">
          <TableHead sticky={false}>
            <tr>
              <TableHeaderCell>Week of</TableHeaderCell>
              {METRICS.map((metric) => (
                <TableHeaderCell align="end" key={metric.key}>
                  {metric.label}
                </TableHeaderCell>
              ))}
            </tr>
          </TableHead>
          <TableBody columns={METRICS.length + 1}>
            {newestFirst.map((week) => (
              <TableRow key={week.week_start}>
                <th className="text-body text-ink px-3 py-2 text-left font-semibold whitespace-nowrap tabular-nums" scope="row">
                  {utcDayLabel(week.week_start)}
                </th>
                {METRICS.map((metric) => {
                  const value = metric.value(week);
                  return (
                    <TableCell key={metric.key} numeric>
                      {value === 0 ? (
                        <span className="text-ink-muted">0</span>
                      ) : (
                        <Link
                          aria-label={`${value} ${metric.noun[value === 1 ? 0 : 1]}, week of ${utcDayLabel(week.week_start)}`}
                          className="text-accent inline-grid min-h-6 min-w-6 place-items-center px-1 font-semibold hover:underline"
                          to={metricLink(metric.action, week.week_start, week.week_end)}
                        >
                          {value}
                        </Link>
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Disclosure>
      <div>
        <ButtonLink icon={<ArrowRight aria-hidden="true" size={16} />} to="/activity" variant="secondary">
          Open the activity log
        </ButtonLink>
      </div>
    </section>
  );
}
