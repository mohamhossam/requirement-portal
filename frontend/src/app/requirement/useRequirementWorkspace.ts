import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../api/client";
import { queryKeys } from "../queryKeys";
import { invalidateWorkspace, type WorkspaceChange } from "../workspaceInvalidation";

/**
 * The reads every stage of the workspace needs, and the permissions derived
 * from them. Stage-specific reads belong to the view that uses them, so that
 * mounting is what gates them.
 *
 * `refetchOnMount: "always"` here is deliberate and tested: re-entering a
 * section reads current data (RequirementPage.test.tsx "refreshes Breakdown
 * when returning with a fresh cache") while a window refocus does not
 * ("preserves the normal freshness window"). It pairs with each view
 * invalidating its own keys, without a refetch, as it unmounts.
 */
export function useRequirementWorkspace(id: string) {
  const queryClient = useQueryClient();

  const requirement = useQuery({
    queryKey: queryKeys.requirement(id),
    queryFn: () => api.getRequirement(id),
    enabled: Boolean(id),
    refetchOnMount: "always",
  });
  /**
   * These three used to wait on `requirement.isSuccess`. All three are
   * sub-resources of an id the client already holds from the URL, so the gate
   * only ever avoided three requests against a requirement that does not
   * exist — and charged a full round trip on every load where it does. On a
   * deep link into the Backlog that was the second of five dependent waves.
   * They now start with the requirement rather than after it.
   */
  const assignments = useQuery({
    queryKey: queryKeys.assignments(id),
    queryFn: () => api.getAssignments(id),
    enabled: Boolean(id),
    refetchOnMount: "always",
  });
  const analysis = useQuery({
    queryKey: queryKeys.analysis(id),
    queryFn: () => api.getAnalysis(id),
    enabled: Boolean(id),
    refetchOnMount: "always",
  });
  const knowledgeReview = useQuery({
    queryKey: queryKeys.knowledgeReview(id),
    queryFn: () => api.getKnowledgeReview(id),
    enabled: Boolean(id),
    refetchOnMount: "always",
  });
  // Similar past requirements (Knowledge Center E2): beside the review, never part of it.
  const priorArt = useQuery({
    queryKey: queryKeys.priorArt(id),
    queryFn: () => api.getPriorArt(id),
    enabled: Boolean(id),
    refetchOnMount: "always",
  });

  const access = assignments.data;
  const team = access
    ? [access.owner?.actor, ...access.reviewers.map((item) => item.actor)].filter(
        (actor): actor is NonNullable<typeof actor> => Boolean(actor),
      )
    : [];

  return {
    requirement,
    assignments,
    analysis,
    knowledgeReview,
    priorArt,
    team,
    canManageContent: access?.can_manage_content ?? false,
    canGovern: access?.can_govern ?? false,
    canConfirmAnalysis: access?.can_confirm_analysis ?? false,
    canExportApprovedRevisions: access?.can_export_approved_revisions ?? false,
    refresh: (change: WorkspaceChange) => invalidateWorkspace(queryClient, id, change),
  };
}

export type RequirementWorkspace = ReturnType<typeof useRequirementWorkspace>;
