import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "../../api/client";
import { errorMessage, errorReference } from "../../api/errors";
import { Skeleton } from "../../components/Skeleton";
import { ErrorState } from "../../components/states";
import { RevisionPanel } from "../../features/revisions/RevisionPanel";
import { queryKeys } from "../queryKeys";
import type { RequirementWorkspace } from "./useRequirementWorkspace";

/** The approved export, what changed between versions, and every version kept. */
export function RevisionsView({ id, workspace }: { id: string; workspace: RequirementWorkspace }) {
  const queryClient = useQueryClient();

  const revisions = useQuery({
    queryKey: queryKeys.revisions(id),
    queryFn: ({ signal }) => api.getRevisionHistory(id, { signal }),
    refetchOnMount: "always",
  });

  useEffect(() => () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.revisions(id), refetchType: "none" });
  }, [id, queryClient]);

  const compare = useMutation({
    meta: { action: "Comparing revisions" },
    mutationFn: ({ fromRevision, toRevision }: { fromRevision: number; toRevision: number }) =>
      api.compareBreakdownRevisions(id, fromRevision, toRevision),
  });
  const download = useMutation({
    meta: { action: "Downloading the revision" },
    mutationFn: ({ revision, format }: { revision: number; format: "json" | "xlsx" }) =>
      api.exportBreakdownRevision(id, revision, format),
  });

  return (
    <>
      {revisions.isPending ? <Skeleton label="Loading the history" variant="page" /> : revisions.data ? (
        <RevisionPanel
          key={revisions.data.breakdown_revisions.at(-1)?.number ?? 0}
          history={revisions.data}
          comparison={compare.data ?? null}
          busy={compare.isPending}
          error={compare.error ? errorMessage(compare.error) : null}
          exportError={download.error ? errorMessage(download.error) : null}
          exportingRevision={download.isPending ? download.variables?.revision ?? null : null}
          exported={download.isSuccess ? download.variables : null}
          reviewHref={`/requirements/${id}/review`}
          activityHref={`/activity?requirement_id=${encodeURIComponent(id)}`}
          canExportApprovedRevisions={workspace.canExportApprovedRevisions}
          onCompare={(fromRevision, toRevision) => compare.mutate({ fromRevision, toRevision })}
          onDownload={(revision, format) => download.mutate({ revision, format })}
        />
      ) : (
        <ErrorState
          headingLevel="h2"
          message={revisions.error ? errorMessage(revisions.error) : "The history is unavailable."}
          reference={errorReference(revisions.error)}
          onRetry={() => void revisions.refetch()}
          title="We couldn’t load the history"
        />
      )}
    </>
  );
}
