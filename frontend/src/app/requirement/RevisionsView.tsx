import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { api } from "../../api/client";
import { ApiError, errorMessage, errorReference } from "../../api/errors";
import { Skeleton } from "../../components/Skeleton";
import { ErrorState } from "../../components/states";
import { PublicationPanel } from "../../features/publication/PublicationPanel";
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

  const approved = [...(revisions.data?.breakdown_revisions ?? [])].reverse().find((item) => item.exportable)?.number ?? null;
  const preview = useQuery({
    queryKey: queryKeys.publication(id, approved ?? 0),
    queryFn: ({ signal }) => api.getPublicationPreview(id, approved ?? 0, { signal }),
    enabled: approved !== null,
    // "Not set up" and "not publishable" are answers, not failures to retry.
    retry: false,
  });
  const unavailable =
    preview.error instanceof ApiError && preview.error.code === "publication_unavailable" ? preview.error.detail : null;
  const record = useQuery({
    queryKey: queryKeys.publicationStatus(id),
    queryFn: ({ signal }) => api.getPublicationStatus(id, { signal }),
    enabled: approved !== null && preview.isSuccess,
    retry: false,
  });
  // What was sent changes what the next publish does, so both are read again afterwards.
  const refreshPublication = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.publication(id, approved ?? 0) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.publicationStatus(id) });
  };
  const publish = useMutation({
    meta: { action: "Publishing the backlog" },
    mutationFn: ({ revision, fingerprint }: { revision: number; fingerprint: string }) =>
      api.publishBreakdownRevision(id, revision, fingerprint),
    onSettled: refreshPublication,
  });
  const retry = useMutation({
    meta: { action: "Retrying the publication" },
    mutationFn: () => api.retryPublication(id),
    onSuccess: () => publish.reset(),
    onSettled: refreshPublication,
  });
  const report = retry.data ?? (publish.data && publish.variables?.revision === approved ? publish.data : null);
  const actionError = retry.error ?? publish.error;

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
      {approved !== null && (
        <div className="mt-8">
          <PublicationPanel
            key={approved}
            canPublish={workspace.canGovern}
            onPublish={(fingerprint) => {
              retry.reset();
              publish.mutate({ revision: approved, fingerprint });
            }}
            onRetry={() => retry.mutate()}
            retrying={retry.isPending}
            status={record.data ?? null}
            preview={preview.data ?? null}
            previewError={
              preview.error && !unavailable
                ? { message: errorMessage(preview.error), reference: errorReference(preview.error) }
                : null
            }
            previewLoading={preview.isPending}
            publishError={
              actionError ? { message: errorMessage(actionError), reference: errorReference(actionError) } : null
            }
            publishing={publish.isPending}
            report={report && report.revision === approved ? report : null}
            revision={approved}
            unavailable={unavailable}
          />
        </div>
      )}
    </>
  );
}
