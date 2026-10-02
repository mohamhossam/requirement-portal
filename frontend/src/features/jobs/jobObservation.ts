import type { QueryClient } from "@tanstack/react-query";
import type { AiJob } from "../../api/client";
import { queryKeys } from "../../app/queryKeys";

export const activeJobStatuses = new Set<AiJob["status"]>(["queued", "running", "cancellation_requested"]);
type Observations = { initialized: boolean; statuses: Record<string, AiJob["status"]> };
export const jobObservationKey = (id: string) => queryKeys.scope("ai-job-observations", id);

export function observeJobs(client: QueryClient, id: string, jobs: AiJob[], authoritative = true): AiJob[] {
  const previous = client.getQueryData<Observations>(jobObservationKey(id));
  const statuses = { ...previous?.statuses };
  const terminal = jobs.filter((job) => {
    const status = statuses[job.id];
    // Retries receive new identities; a late read must not regress a terminal job.
    if (!status || activeJobStatuses.has(status)) statuses[job.id] = job.status;
    return !activeJobStatuses.has(job.status) &&
      (status ? activeJobStatuses.has(status) : Boolean(previous?.initialized));
  });
  client.setQueryData<Observations>(jobObservationKey(id), { initialized: authoritative || Boolean(previous?.initialized), statuses });
  return terminal;
}

export function registerStartedJob(client: QueryClient, id: string, job: AiJob) {
  registerPendingJob(client, id, job.id);
  client.setQueryData<AiJob[]>(queryKeys.aiJobs(id), (jobs) =>
    [job, ...(jobs ?? []).filter((item) => item.id !== job.id)],
  );
}

export function registerPendingJob(client: QueryClient, id: string, jobId: string) {
  const key = jobObservationKey(id);
  const previous = client.getQueryData<Observations>(key);
  // Detect fast completions even when the start/retry response is already terminal.
  client.setQueryData<Observations>(key, {
    initialized: previous?.initialized ?? false,
    statuses: { ...previous?.statuses, [jobId]: previous?.statuses[jobId] ?? "queued" },
  });
}
