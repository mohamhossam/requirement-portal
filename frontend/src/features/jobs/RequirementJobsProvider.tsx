import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, type ReactNode } from "react";
import { api, type AiJob, type AiJobStartInput } from "../../api/client";
import { queryKeys } from "../../app/queryKeys";
import { invalidateWorkspaceKeys, jobCompletionKeys } from "../../app/workspaceInvalidation";
import { useToast } from "../../components/useToast";
import { activeJobStatuses, jobObservationKey, observeJobs, registerStartedJob } from "./jobObservation";
import { activeRunKey, jobPollInterval, jobToast } from "./jobPolicy";
import { RequirementJobsContext } from "./useRequirementJobs";

function useJobsController(requirementId: string) {
  const client = useQueryClient();
  const toast = useToast();
  // When the current run started being watched, for pacing the poll.
  const watching = useRef({ since: 0, run: "" });
  const targetKey = queryKeys.scope("job-targets", requirementId);
  const targets = useQuery({ queryKey: targetKey, queryFn: skipToken, initialData: {} as Record<string, { featureId?: string | null; storyId?: string | null }> });
  // Retain transition history for long-running jobs, then use normal cache GC after leaving.
  useQuery({ queryKey: jobObservationKey(requirementId), queryFn: skipToken, initialData: { initialized: false, statuses: {} } });
  const processJobs = (items: AiJob[], authoritative = true) => {
    const terminal = observeJobs(client, requirementId, items, authoritative);
    if (!terminal.length) return;
    // observeJobs reports each transition once, so this cannot double-announce.
    for (const job of terminal) {
      const notice = jobToast(job);
      if (notice) toast.show(notice);
    }
    void invalidateWorkspaceKeys(client, [
      queryKeys.requirementLists(), queryKeys.notifications(),
      ...terminal.flatMap(jobCompletionKeys),
    ]);
  };
  const jobs = useQuery({
    queryKey: queryKeys.aiJobs(requirementId),
    queryFn: async ({ signal }) => {
      const items = await api.listAiJobs(requirementId);
      signal.throwIfAborted();
      processJobs(items);
      return items;
    },
    enabled: Boolean(requirementId),
    refetchOnMount: "always",
    refetchInterval: (query) => {
      const run = activeRunKey(query.state.data);
      if (!run) {
        watching.current = { since: 0, run: "" };
        return false;
      }
      // Work appearing or completing restarts the pacing: something changed, so
      // it is worth another brisk look.
      if (run !== watching.current.run) watching.current = { since: Date.now(), run };
      return jobPollInterval(Date.now() - watching.current.since);
    },
  });
  const startJob = async (input: AiJobStartInput, idempotencyKey?: string) => {
    const job = await (idempotencyKey === undefined
      ? api.startAiJob(requirementId, input)
      : api.startAiJob(requirementId, input, idempotencyKey));
    registerStartedJob(client, requirementId, job);
    client.setQueryData(targetKey, (current: typeof targets.data) => ({ ...current, [job.id]: { featureId: "feature_id" in input ? input.feature_id : null, storyId: "story_id" in input ? input.story_id : null } }));
    processJobs([job], false);
    await client.invalidateQueries({ queryKey: queryKeys.aiJobs(requirementId) });
    return job;
  };
  const cancel = useMutation({
    mutationFn: (job: AiJob) => api.cancelAiJob(requirementId, job.id, job.version),
    onSuccess: async () => client.invalidateQueries({ queryKey: queryKeys.aiJobs(requirementId) }),
  });
  const retry = useMutation({
    mutationFn: (job: AiJob) => api.retryAiJob(requirementId, job.id, job.version),
    onSuccess: async (job, previous) => {
      client.setQueryData(targetKey, (current: typeof targets.data) => ({ ...current, [job.id]: current?.[previous.id] ?? {} }));
      registerStartedJob(client, requirementId, job);
      processJobs([job], false);
      await client.invalidateQueries({ queryKey: queryKeys.aiJobs(requirementId) });
    },
  });
  return { requirementId, jobs, targets: targets.data ?? {}, active: jobs.data?.filter((job) => activeJobStatuses.has(job.status)) ?? [], startJob, cancel, retry };
}

export type RequirementJobsState = ReturnType<typeof useJobsController>;

export function RequirementJobsProvider({ requirementId, children }: { requirementId: string; children: ReactNode }) {
  const state = useJobsController(requirementId);
  return <RequirementJobsContext.Provider value={state}>{children}</RequirementJobsContext.Provider>;
}
