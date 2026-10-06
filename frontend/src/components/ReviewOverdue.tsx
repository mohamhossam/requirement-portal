import { CalendarClock } from "lucide-react";

import { reviewOverdue } from "./reviewDates";

const DAY = new Intl.DateTimeFormat(undefined, { timeZone: "UTC", day: "numeric", month: "short", year: "numeric" });

/**
 * "Review overdue since 1 Oct 2026": the knowledge portal has not re-confirmed this cited
 * source by its review date (Knowledge Center D). A flag beside the citation, never a reason
 * to hide or refuse it.
 */
export function ReviewOverdue({ dueOn, subject = "source" }: { dueOn: string | null | undefined; subject?: string }) {
  if (!dueOn || !reviewOverdue(dueOn)) return null;
  return (
    <span className="text-meta text-ink-soft inline-flex items-center gap-1">
      <CalendarClock aria-hidden="true" className="text-warning shrink-0" size={14} />
      <span>
        Review overdue since {DAY.format(new Date(`${dueOn}T00:00:00Z`))}
        <span className="sr-only">: the knowledge portal has not re-confirmed this {subject} since.</span>
      </span>
    </span>
  );
}
