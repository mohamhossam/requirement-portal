import type { AiJob } from "../../api/client";
import type { ToastInput } from "../../components/useToast";
import { activeJobStatuses } from "./jobObservation";
import { completionLabel } from "./jobLabels";

/**
 * How often to ask about work in flight, from how long this client has been
 * watching the current run. A job that just appeared is polled briskly because
 * it may finish at once; one that has been grinding for a while will not finish
 * any sooner for being asked five times a second. The previous flat 1s made a
 * ten-minute analysis cost roughly 600 requests.
 *
 * Elapsed watch time is measured on this client rather than from the job's
 * started_at, so clock skew cannot mispace it and a job that sat queued for an
 * hour before starting still gets a brisk first look.
 *
 * React Query already suspends the interval while the tab is unfocused
 * (refetchIntervalInBackground defaults to false), so that needs nothing here.
 */
const POLL_STEPS = [
  { watchedUnder: 10_000, interval: 1_000 },
  { watchedUnder: 60_000, interval: 2_000 },
];
const POLL_SLOWEST = 5_000;

export function jobPollInterval(watchedMs: number): number {
  return POLL_STEPS.find((step) => watchedMs < step.watchedUnder)?.interval ?? POLL_SLOWEST;
}

/** Identifies the current run, so new work restarts the pacing. */
export function activeRunKey(jobs: AiJob[] | undefined): string {
  return (jobs ?? [])
    .filter((job) => activeJobStatuses.has(job.status))
    .map((job) => job.id)
    .sort()
    .join(",");
}

/**
 * What to say when a job reaches a terminal state, or null to stay quiet.
 *
 * Automatic background screening succeeds constantly and nobody asked for it,
 * so only its failures are worth interrupting for. Cancellations are the
 * person's own doing; the status panel already surfaces the screening ones that
 * need action.
 */
export function jobToast(job: AiJob): ToastInput | null {
  const what = completionLabel(job.operation);
  if (job.status === "failed") {
    return {
      tone: "error",
      title: `${what} failed`,
      message: job.failure?.message ?? "The operation did not complete.",
      key: `job-${job.operation}`,
    };
  }
  if (job.status === "succeeded" && job.origin === "user") {
    const resource = job.result_resources?.[0];
    return {
      tone: "success",
      title: `${what} finished`,
      to: resource?.path,
      linkLabel: resource ? "Open result" : undefined,
      key: `job-${job.operation}`,
    };
  }
  return null;
}
