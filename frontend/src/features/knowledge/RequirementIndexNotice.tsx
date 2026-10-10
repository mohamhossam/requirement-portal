import { useMutation, useQuery } from "@tanstack/react-query";

import { api } from "../../api/client";
import { ApiError, errorMessage, errorReference } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, Card } from "../../components/ui";

/**
 * The requirement being prepared for the knowledge check.
 *
 * It used to speak the machinery — "passages", "the embedding model changed",
 * "an operator must rebuild the Requirement index" — to a business owner who
 * only needs to know whether to wait, retry, or ask somebody.
 */
export function RequirementIndexNotice({ requirementId }: { requirementId: string }) {
  const index = useQuery({
    queryKey: queryKeys.scope("requirement-index", requirementId),
    queryFn: ({ signal }) => api.getRequirementIndex(requirementId, { signal }),
    refetchInterval: 2000,
  });
  const retry = useMutation({
    mutationFn: () => api.retryRequirementIndex(requirementId),
    onSuccess: () => { void index.refetch(); },
  });
  // Someone who is not on this requirement cannot read its preparation state,
  // and has nothing to do about it: a red "We couldn't complete that action"
  // on arrival reported a failure they never caused.
  if (index.isError && index.error instanceof ApiError && index.error.status === 403) return null;
  if (index.isError) return <ErrorNotice message={errorMessage(index.error)} reference={errorReference(index.error)} />;
  if (!index.data || index.data.state === "ready") return null;
  const stuck = index.data.state === "failed" || index.data.state === "rebuild_required";
  return (
    <Card
      aria-label="Knowledge preparation"
      className="grid gap-2"
      inset={!stuck}
      padding="compact"
      tone={stuck ? "warning" : "default"}
    >
      <h2 className="text-title text-ink m-0">
        {stuck ? "The knowledge check cannot start yet" : "Getting the knowledge check ready"}
      </h2>
      <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]" role="status">
        {index.data.state === "failed"
          ? "Preparing this requirement failed three times. Retry to carry on from where it stopped."
          : index.data.state === "rebuild_required"
            ? "The search model was changed, so an administrator has to rebuild the search index before this requirement can be checked."
            : "This requirement is being prepared in the background. The check and answer suggestions start when it is ready."}
      </p>
      {index.data.total_chunks > 0 && (
        <p className="text-meta text-ink-muted m-0 tabular-nums">
          {index.data.completed_chunks} of {index.data.total_chunks} sections prepared.
        </p>
      )}
      {index.data.retryable && (
        <Button className="w-fit" disabled={retry.isPending} onClick={() => retry.mutate()}>
          Retry knowledge preparation
        </Button>
      )}
      {retry.isError && <ErrorNotice message={errorMessage(retry.error)} reference={errorReference(retry.error)} />}
    </Card>
  );
}
