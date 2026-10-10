import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, type ReactNode } from "react";
import { api, type AiJob, type AiJobStartInput } from "../../api/client";
import { ApiError } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { contextTokenKeys, invalidateWorkspaceKeys, jobCompletionKeys } from "../../app/workspaceInvalidation";
import { useToast } from "../../components/useToast";
import { activeJobStatuses, jobObservationKey, observeJobs, registerStartedJob } from "./jobObservation";
import { activeRunKey, jobPollInterval, jobToast } from "./jobPolicy";
import { createStartKeys } from "./startKeys";
import { RequirementJobsContext } from "./useRequirementJobs";

const OUT_OF_DATE_MESSAGE = "This page was out of date and has been refreshed. Try again.";

function useJobsController(requirementId: string) {
  const client = useQueryClient();
  const toast = useToast();
  // When the current run started being watched, for pacing the poll.
  const watching = useRef({ since: 0, run: "" });
  const startKeys = useRef(createStartKeys()).current;
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
      const items = await api.listAiJobs(requirementId, false, { signal });
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
    const tokenKeys = contextTokenKeys(requirementId, input);
    if (tokenKeys.length && !("context_token" in input && input.context_token.trim())) {
      // The token was never loaded: the request could only be refused, so refresh instead.
      await invalidateWorkspaceKeys(client, tokenKeys);
      throw new Error(OUT_OF_DATE_MESSAGE);
    }
    const ownKey = idempotencyKey === undefined;
    let job: AiJob;
    try {
      job = await api.startAiJob(requirementId, input, idempotencyKey ?? startKeys.keyFor(input));
    } catch (error) {
      if (ownKey) startKeys.settle(input, error);
      // A 409 means what the page showed has changed: reload it before the next try.
      if (error instanceof ApiError && error.status === 409) await invalidateWorkspaceKeys(client, tokenKeys);
      throw error;
    }
    if (ownKey) startKeys.settle(input);
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
