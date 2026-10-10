import { Link } from "react-router-dom";

import { useMutation } from "@tanstack/react-query";

import { api, type KnowledgeFinding } from "../../api/client";
import { errorMessage, errorReference } from "../../api/errors";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Skeleton } from "../../components/Skeleton";
import { Card } from "../../components/ui";
import { useRequirementJobs } from "../../features/jobs/useRequirementJobs";
import { KnowledgeReviewPanel } from "../../features/knowledge/KnowledgeReviewPanel";
import { PriorArtPanel } from "../../features/priorArt/PriorArtPanel";
import { RequirementIndexNotice } from "../../features/knowledge/RequirementIndexNotice";
import type { useLazyKnowledgeScreening } from "../../features/knowledge/useLazyKnowledgeScreening";
import type { RequirementWorkspace } from "./useRequirementWorkspace";

const NOTICE_LINK = "text-accent text-body inline-flex min-h-6 w-fit items-center underline underline-offset-2";

/**
 * Possible duplicates and contradictions found in trusted evidence.
 *
 * The screening it reports on is started by the shell, not here: arriving at
 * confirmation also has to ensure a screen exists, so the trigger cannot belong
 * to this stage alone.
 */
export function KnowledgeView({
  id,
  workspace,
  screening,
}: {
  id: string;
  workspace: RequirementWorkspace;
  screening: ReturnType<typeof useLazyKnowledgeScreening> & { running: boolean };
}) {
  const { knowledgeReview, canConfirmAnalysis, refresh } = workspace;
  const staleReferences = workspace.analysis.data?.stale_reference_proposal_ids ?? [];
  const jobs = useRequirementJobs(id);

  const decide = useMutation({
    meta: { action: "Recording the knowledge decision" },
    mutationFn: ({ finding, decision, text }: {
      finding: KnowledgeFinding;
      decision: "distinct" | "duplicate" | "propose_resolution" | "accept_resolution";
      text?: string;
    }) => api.decideKnowledgeFinding(id, finding.id, {
      decision, expected_version: finding.version, text,
    }),
    onSuccess: async () => refresh("knowledge"),
  });

  if (knowledgeReview.isPending) return <Skeleton label="Loading the knowledge review" />;
  if (knowledgeReview.isError) return <ErrorNotice message={errorMessage(knowledgeReview.error)} reference={errorReference(knowledgeReview.error)} />;
  if (!knowledgeReview.data) return null;

  const conflicts = knowledgeReview.data.reference_conflict_ids?.length ?? 0;
  const retirement = knowledgeReview.data.corpus_retirement ?? null;

  return (
    <>
    <RequirementIndexNotice requirementId={id} />
    {retirement ? (
      <Card padding="compact" as="section" tone="accent" aria-labelledby="knowledge-retired" className="grid gap-2">
        <h2 className="text-title text-ink m-0" id="knowledge-retired">Retired from the knowledge corpus</h2>
        <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">
          {retirement.retired_by} retired it on{" "}
          {new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(retirement.retired_at))}:{" "}
          {retirement.reason}
        </p>
        <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">
          It is not screened against other requirements, and no suggestion cites it. It stays readable here. A
          knowledge admin can return it to the corpus.
        </p>
      </Card>
    ) : null}
    {/* Both of these are decided on Clarify, where the citations are. They used
        to be bare sections with their own h2 beside the panel's; they are
        notices now, and say where the decision is made. */}
    {staleReferences.length > 0 ? (
      <Card padding="compact" as="section" tone="warning" aria-labelledby="knowledge-stale-references" className="grid gap-2">
        <h2 className="text-title text-ink m-0" id="knowledge-stale-references">A cited document has changed</h2>
        <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">
          A document this analysis cites was replaced or withdrawn. Re-analyse and decide whether it still applies
          before the analysis is confirmed or a backlog is generated.
        </p>
        <Link className={NOTICE_LINK} to={`/requirements/${id}/clarify`}>Review outdated references on Clarify</Link>
      </Card>
    ) : null}
    {conflicts > 0 ? (
      <Card padding="compact" as="section" tone="warning" aria-labelledby="knowledge-reference-conflicts" className="grid gap-2">
        <h2 className="text-title text-ink m-0" id="knowledge-reference-conflicts">
          {conflicts === 1 ? "A published reference disagrees" : `${conflicts} published references disagree`} with the analysis
        </h2>
        <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">
          The owner records why each one applies to this requirement, or why it does not.
        </p>
        <Link className={NOTICE_LINK} to={`/requirements/${id}/clarify`}>Review reference proposals on Clarify</Link>
      </Card>
    ) : null}
    <KnowledgeReviewPanel
      requirementId={id}
      requirementTitle={workspace.requirement.data?.title ?? "This requirement"}
      requirementText={workspace.requirement.data?.description ?? ""}
      review={knowledgeReview.data}
      running={screening.running}
      ensureOutcome={screening.running ? null : screening.data?.outcome ?? null}
      ensureJobId={screening.data?.job_id ?? null}
      canDecide={canConfirmAnalysis}
      busy={decide.isPending || jobs.retry.isPending}
      error={
        screening.error ? errorMessage(screening.error)
        : jobs.retry.error ? errorMessage(jobs.retry.error) : null
      }
      decisionError={decide.error ? errorMessage(decide.error) : null}
      onRetry={(jobId) => {
        const job = jobs.jobs.data?.find((item) => item.id === jobId);
        if (job) jobs.retry.mutate(job);
      }}
      onDecide={(finding, decision, text) => decide.mutate({ finding, decision, text })}
    />
    {/* Beside the review, never inside it: prior art is reference, not a decision. */}
    {workspace.priorArt.data ? <PriorArtPanel priorArt={workspace.priorArt.data} /> : null}
    </>
  );
}
