import { api, type ArchitectureMappingJob } from "../../api/client";

const POLL_INTERVAL_MS = 1500;

const wait = (milliseconds: number) =>
  new Promise<void>((resolve) => {
    setTimeout(resolve, milliseconds);
  });

/**
 * Map a Requirement's backlog to the architecture catalogue as a durable job
 * (ADR-0105), resolving once the job succeeds.
 *
 * The job keeps running on the server if the page goes away; this only waits
 * for it. Offline it finishes inside the starting request, so nothing is polled.
 */
export async function runArchitectureMapping(
  requirementId: string,
  pause: (milliseconds: number) => Promise<void> = wait,
): Promise<ArchitectureMappingJob> {
  let job = await api.startArchitectureMappingJob(requirementId);
  while (job.status === "queued" || job.status === "running") {
    await pause(POLL_INTERVAL_MS);
    job = await api.getArchitectureMappingJob(requirementId, job.id);
  }
  if (job.status === "succeeded") return job;
  throw new Error(
    job.status === "cancelled"
      ? "Architecture mapping was cancelled."
      : `Architecture mapping did not finish${job.error_category ? ` (${job.error_category})` : ""}. Try again.`,
  );
}
