import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { errorMessage } from "../../api/errors";
import { knowledgeApi, type ArchitectureJob } from "../../api/knowledge";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Badge, Button } from "../../components/ui";
import { catalogueKeys } from "./keys";
import { JOB_LABEL, jobError } from "./labels";

/**
 * A background job's state, polled until it ends. It says what is happening in
 * words (never a percentage the server cannot know) and offers the one action
 * that fits: cancel while queued, retry once failed.
 */
export function JobStatus({
  job,
  label,
  hints = {},
  onFinished,
}: {
  job: ArchitectureJob;
  label: string;
  /** What a status means for this kind of job, said under the badge. */
  hints?: Partial<Record<ArchitectureJob["status"], string>>;
  /** Called when the job ends while on screen, not for one that had already ended. */
  onFinished?: (job: ArchitectureJob) => void;
}) {
  const client = useQueryClient();
  const current = useQuery({
    queryKey: catalogueKeys.job(job.id),
    queryFn: () => knowledgeApi.job(job.id),
    initialData: job,
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "") ? 2000 : false,
  });
  const retry = useMutation({ mutationFn: () => knowledgeApi.retryJob(job.id),
    onSuccess: (data) => client.setQueryData(catalogueKeys.job(job.id), data) });
  const cancel = useMutation({ mutationFn: () => knowledgeApi.cancelJob(job.id),
    onSuccess: (data) => client.setQueryData(catalogueKeys.job(job.id), data) });
  const status = current.data.status;
  const previous = useRef<string>(job.status);
  useEffect(() => {
    if (previous.current === status) return;
    previous.current = status;
    if (["succeeded", "failed", "cancelled"].includes(status)) onFinished?.(current.data);
  }, [status, current.data, onFinished]);

  const tone = JOB_LABEL[status];
  return (
    <div className="grid gap-2">
      <p className="text-body text-ink-soft m-0 flex flex-wrap items-center gap-2" role="status" aria-live="polite">
        <span>{label}:</span>
        <Badge tone={tone.tone}>{tone.label}</Badge>
        {status === "failed" && current.data.error_category && (
          <span className="text-meta text-ink-muted">Reason: {jobError(current.data.error_category)}</span>
        )}
      </p>
      {hints[status] && <p className="text-meta text-ink-muted m-0">{hints[status]}</p>}
      {(status === "failed" || status === "queued") && (
        <div className="flex flex-wrap gap-2">
          {status === "failed" && (
            <Button size="sm" onClick={() => retry.mutate()} loading={retry.isPending} loadingLabel="Retrying…">
              Try again
            </Button>
          )}
          {status === "queued" && (
            <Button size="sm" variant="ghost" onClick={() => cancel.mutate()} loading={cancel.isPending}
              loadingLabel="Cancelling…">
              Cancel
            </Button>
          )}
        </div>
      )}
      {(retry.error || cancel.error) && <ErrorNotice message={errorMessage(retry.error ?? cancel.error)} />}
    </div>
  );
}
