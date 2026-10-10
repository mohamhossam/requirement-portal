import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LockKeyhole } from "lucide-react";
import { useEffect } from "react";

import { api, type EpicInput, type FeatureInput } from "../../api/client";
import { errorMessage } from "../../api/errors";
import { BreakdownWorkspace } from "../../features/breakdown/BreakdownWorkspace";
import { Card } from "../../components/ui";
import { ArchitectureRemapBanner } from "../../features/architecture/ArchitectureRemapBanner";
import { runArchitectureMapping } from "../../features/architecture/runMappingJob";
import { useRequirementJobs } from "../../features/jobs/useRequirementJobs";
import { queryKeys } from "../queryKeys";
import { invalidateWorkspaceKeys } from "../workspaceInvalidation";
import type { RequirementWorkspace } from "./useRequirementWorkspace";

/**
 * The generated backlog. Its reads live here so that they only happen on this
 * stage, which `review-flow.spec.ts` asserts by watching for backlog requests
 * on the Capture, Clarify, Knowledge and Confirm routes. Within the stage the
 * Epic and the Features are fetched together rather than in sequence.
 */
export function BreakdownView({ id, workspace }: { id: string; workspace: RequirementWorkspace }) {
  const { analysis, canManageContent, refresh } = workspace;
  const queryClient = useQueryClient();
  const jobs = useRequirementJobs(id);

  const epic = useQuery({
    queryKey: queryKeys.epic(id),
    queryFn: ({ signal }) => api.getEpic(id, { signal }),
    refetchOnMount: "always",
  });
  /**
   * Features no longer wait for the Epic. The gate spared one request on a
   * requirement with no Epic yet and cost a round trip on every one that has
   * an Epic, which is every requirement a person is actually reviewing. Route
   * scoping is unchanged and is what `review-flow.spec.ts` asserts: this view
   * only mounts on the Backlog stage, so no other stage reads the backlog.
   */
  const features = useQuery({
    queryKey: queryKeys.features(id),
    queryFn: ({ signal }) => api.getFeatures(id, { signal }),
    refetchOnMount: "always",
  });

  useEffect(() => () => {
    void Promise.all([queryKeys.epic(id), queryKeys.features(id)].map((queryKey) =>
      queryClient.invalidateQueries({ queryKey, refetchType: "none" })));
  }, [id, queryClient]);

  const generateEpic = useMutation({
    meta: { action: "Generating the Epic" },
    mutationFn: (force: boolean) => jobs.startJob({
      operation: "generate_epic", force, context_token: analysis.data?.epic_context_token ?? "",
    }),
  });
  const editEpic = useMutation({
    meta: { action: "Saving the Epic" },
    mutationFn: ({ input, expectedVersion }: { input: EpicInput; expectedVersion: number }) =>
      api.editEpic(id, { ...input, expected_version: expectedVersion }),
    onError: async () => invalidateWorkspaceKeys(queryClient, [queryKeys.epic(id)]),
    onSuccess: async () => refresh("epic"),
  });
  const approveEpic = useMutation({
    meta: { action: "Approving the Epic" },
    mutationFn: () => api.approveEpic(id, epic.data!.version, epic.data!.content_fingerprint),
    onSuccess: async () => refresh("epic-approval"),
  });
  const generateFeatures = useMutation({
    meta: { action: "Generating the Features" },
    mutationFn: () => jobs.startJob({
      operation: "generate_features", force: false, context_token: epic.data?.feature_context_token ?? "",
    }),
  });
  const editFeature = useMutation({
    meta: { action: "Saving the Feature" },
    mutationFn: ({ featureId, input, expectedVersion }: { featureId: string; input: FeatureInput; expectedVersion: number }) =>
      api.editFeature(id, featureId, { ...input, expected_version: expectedVersion }),
    onError: async () => invalidateWorkspaceKeys(queryClient, [queryKeys.features(id)]),
    onSuccess: async () => refresh("features"),
  });
  const approveFeature = useMutation({
    meta: { action: "Approving the Feature" },
    mutationFn: (featureId: string) => {
      const value = features.data?.features.find((item) => item.id === featureId);
      return api.approveFeature(id, featureId, value!.version, value!.content_fingerprint);
    },
    onSuccess: async () => refresh("feature-approval"),
  });
  const mapArchitecture = useMutation({
    meta: { action: "Mapping the architecture" },
    mutationFn: () => runArchitectureMapping(id),
    onSuccess: async () => refresh("architecture"),
  });

  const running = new Set(jobs.active.map((job) => job.operation));
  const epicError = generateEpic.error ?? editEpic.error ?? approveEpic.error;
  const featureError = editFeature.error ?? approveFeature.error;
  const featureErrorId = editFeature.variables?.featureId ?? approveFeature.variables ?? "";

  return (
    <>
      {!analysis.data?.human_confirmed && (
        // A locked state, not a status: sunken and neutral, with the lock as
        // its glyph. The uppercase "Breakdown locked" eyebrow above the heading
        // said the same thing twice and was the last of that label style here.
        <Card
          as="section"
          inset
          aria-labelledby="breakdown-title"
          className="flex items-start gap-4"
        >
          <LockKeyhole aria-hidden="true" className="text-ink-muted mt-0.5 shrink-0" size={20} />
          <div className="grid gap-1">
            <h2 className="text-title text-ink m-0" id="breakdown-title">Confirm the analysis to change the backlog</h2>
            <p className="text-body text-ink-soft m-0 max-w-[var(--measure-document)]">
              What is here stays readable. Confirm the current analysis before generating an Epic, and bring out-of-date items up to date before changing them.
            </p>
          </div>
        </Card>
      )}
      <ArchitectureRemapBanner
        mappedWith={(features.data?.features ?? []).flatMap((item) =>
          item.architecture ? [item.architecture.knowledge_version] : [])}
        canRemap={canManageContent}
        busy={mapArchitecture.isPending}
        onRemap={() => mapArchitecture.mutate()}
      />
      <BreakdownWorkspace
        requirementId={id} epic={epic.data ?? null} features={features.data ?? null}
        analysis={analysis.data ?? null}
        epicLoading={epic.isPending}
        featuresLoading={Boolean(epic.data) && features.isPending}
        epicError={epic.isError ? errorMessage(epic.error) : epicError ? errorMessage(epicError) : null}
        featuresError={features.isError ? errorMessage(features.error) : generateFeatures.error ? errorMessage(generateFeatures.error) : null}
        canManage={canManageContent}
        epicBusy={generateEpic.isPending || running.has("generate_epic") || editEpic.isPending || approveEpic.isPending}
        featureBusy={generateFeatures.isPending || running.has("generate_features")}
        busyFeatureId={editFeature.isPending ? editFeature.variables?.featureId ?? null
          : approveFeature.isPending ? approveFeature.variables ?? null : null}
        featureErrors={featureError ? { [featureErrorId]: errorMessage(featureError) } : {}}
        onEditEpic={(input, expectedVersion) => editEpic.mutateAsync({ input, expectedVersion })}
        onApproveEpic={() => approveEpic.mutate()}
        onGenerateEpic={(force) => generateEpic.mutate(force)}
        onEditFeature={(featureId, input, expectedVersion) => editFeature.mutateAsync({ featureId, input, expectedVersion })}
        onApproveFeature={(featureId) => approveFeature.mutate(featureId)}
        onGenerateFeatures={() => generateFeatures.mutate()}
        onMapArchitecture={() => mapArchitecture.mutate()}
        architectureBusy={mapArchitecture.isPending}
        architectureError={mapArchitecture.error ? errorMessage(mapArchitecture.error) : null}
      />
    </>
  );
}
