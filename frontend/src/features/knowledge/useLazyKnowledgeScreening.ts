import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { api } from "../../api/client";
import { queryKeys } from "../../app/queryKeys";
import { registerPendingJob } from "../jobs/jobObservation";

type Options = {
  requirementId: string;
  fingerprint: string | undefined;
  enabled: boolean;
};

export function useLazyKnowledgeScreening({
  requirementId,
  fingerprint,
  enabled,
}: Options) {
  const queryClient = useQueryClient();
  const attempted = useRef<string | null>(null);
  const ensure = useMutation({
    // Runs on its own; the knowledge panel shows the outcome in place.
    meta: { toastOnError: false },
    mutationFn: () => api.ensureKnowledgeScreen(requirementId),
    onSuccess: async (result) => {
      if (result.job_id && (result.outcome === "scheduled" || result.outcome === "already_scheduled")) {
        registerPendingJob(queryClient, requirementId, result.job_id);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.aiJobs(requirementId) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.knowledgeReview(requirementId) }),
      ]);
    },
  });

  useEffect(() => {
    if (!enabled || !fingerprint || ensure.isPending) return;
    const key = `${requirementId}:${fingerprint}`;
    if (attempted.current === key) return;
    attempted.current = key;
    ensure.mutate();
  }, [enabled, ensure, fingerprint, requirementId]);

  return ensure;
}
