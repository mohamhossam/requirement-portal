import { Circle, CircleAlert, LoaderCircle } from "lucide-react";
import { errorMessage } from "../../api/errors";
import type { AiJob } from "../../api/client";
import { useRequirementJobs } from "./useRequirementJobs";
import { elapsedLabel, operationLabel } from "./jobLabels";
import { Button } from "../../components/ui/Button";


const generationOperations = new Set(["generate_features", "generate_stories", "regenerate_story", "regenerate_story_set", "propose_story_change"]);

const phaseLabels: Record<string, string> = {
  preparing: "Preparing generation context",
  generating: "Generating draft",
  checking: "Checking draft",
  refining: "Refining draft",
  saving: "Saving checked draft",
  preparing_analysis: "Preparing evidence",
  planning_evidence: "Planning evidence packets",
  analyzing_evidence: "Analyzing evidence",
  consolidating_findings: "Consolidating findings",
  validating_evidence_references: "Validating evidence references",
  waiting_to_retry: "Waiting to try again",
  completed: "Completed",
};

/** A queued job waiting out a provider or platform outage before it runs again. */
function retryTime(job: AiJob): string | null {
  if (job.status !== "queued" || !job.next_attempt_at) return null;
  return new Date(job.next_attempt_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function latestInterventions(jobs: AiJob[]): AiJob[] {
  const latestByOperation = new Map<AiJob["operation"], AiJob>();
  const newestFirst = [...jobs].sort(
    (left, right) => Date.parse(right.created_at) - Date.parse(left.created_at),
  );
  for (const job of newestFirst) {
    const actionableCancellation =
      job.status === "cancelled" && job.operation === "screen_requirement_knowledge";
    if ((job.status !== "cancelled" || actionableCancellation) && !latestByOperation.has(job.operation)) {
      latestByOperation.set(job.operation, job);
    }
  }
  return [...latestByOperation.values()]
    .filter(
      (job) =>
        job.status === "failed" ||
        (job.status === "cancelled" && job.operation === "screen_requirement_knowledge"),
    )
    .slice(0, 2);
}

export function AiJobStatusPanel({ requirementId, featureNames = {}, focused = false }: { requirementId: string; featureNames?: Record<string, string>; focused?: boolean }) {
  const { jobs, active, cancel, retry, targets } = useRequirementJobs(requirementId);
  const interventions = latestInterventions(jobs.data ?? []);
  const label = (job: NonNullable<typeof jobs.data>[number]) => {
    const target = targets[job.id];
    const name = target?.featureId ? featureNames[target.featureId] : null;
    const operation = job.operation === "resolve_clarification_questions" && job.item_count
      ? `Resolving ${job.item_count} question${job.item_count === 1 ? "" : "s"}`
      : operationLabel(job.operation);
    return name ? `${operation} · ${name}` : operation;
  };
  const headline = (job: AiJob) => {
    if (retryTime(job)) return `${label(job)} will try again`;
    if (job.status === "queued") return `${label(job)} queued`;
    if (!focused && (job.operation === "analyse_requirement" || generationOperations.has(job.operation)) && job.phase) return phaseLabels[job.phase] ?? label(job);
    return label(job);
  };
  const description = (job: AiJob) => {
    const retryAt = retryTime(job);
    if (retryAt) return `The AI provider or a connected service was unavailable. It tries again at ${retryAt}.`;
    if (job.status === "queued") return focused ? "Waiting for an AI worker." : "Waiting for an AI worker. User-requested work is processed before automatic background screening.";
    if (focused) return `${job.phase ? `${phaseLabels[job.phase] ?? job.phase} · ` : ""}Work continues in the background.`;
    if (job.operation === "analyse_requirement" && job.current_section_label) return `Current section: ${job.current_section_label}`;
    return "You can safely leave this page. Work continues in the background.";
  };
  if (active.length === 0 && interventions.length === 0 && !jobs.error) return null;

  return (
    <section
      aria-label="AI work on this requirement"
      aria-live="polite"
      className="border-line bg-surface-sunken grid gap-3 rounded-md border border-solid px-4 py-3"
    >
      {active.map((job) => (
        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3" key={job.id}>
          {/* The one spinner in the system (DESIGN.md): a running AI job, whose
              duration nobody knows. Under reduced motion a complete ring stands
              in — an arc stopped mid-turn reads as broken, not as busy. */}
          <span aria-hidden="true" className="text-accent mt-0.5 grid size-4 place-items-center">
            <LoaderCircle className="animate-spin motion-reduce:hidden" size={16} />
            <Circle className="hidden motion-reduce:block" size={16} />
          </span>
          <span className="grid min-w-0 gap-1">
            <strong className="text-body text-ink font-semibold">{headline(job)}</strong>
            <span className="text-meta text-ink-muted">{description(job)}</span>
            {job.status === "running" && elapsedLabel(job) ? (
              <span aria-hidden="true" className="text-meta text-ink-muted tabular-nums">
                Running for {elapsedLabel(job)}
              </span>
            ) : null}
            {(job.operation === "analyse_requirement" || generationOperations.has(job.operation)) && job.total_units ? (
              <progress
                aria-label={job.operation === "analyse_requirement" ? "Analysis progress" : "Generation progress"}
                className="h-2 w-full max-w-[24rem] accent-[var(--accent)]"
                max={job.total_units}
                value={job.completed_units}
              />
            ) : null}
          </span>
          <Button disabled={cancel.isPending} onClick={() => cancel.mutate(job)} variant="text">
            Cancel
          </Button>
        </div>
      ))}
      {interventions.map((job) => (
        <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-3" key={job.id}>
          <CircleAlert aria-hidden="true" className="text-danger mt-0.5" size={16} />
          <span className="grid min-w-0 gap-1">
            <strong className="text-body text-danger font-semibold">
              {label(job)} {job.status === "cancelled" ? "stopped" : "failed"}
            </strong>
            <span className="text-meta text-ink-soft">
              {job.status === "cancelled"
                ? "Automatic screening remains stopped until a team member retries it."
                : job.failure?.message ?? "The operation did not complete."}
            </span>
          </span>
          {(job.status === "cancelled" || job.failure?.retryable) && (
            <Button disabled={retry.isPending} onClick={() => retry.mutate(job)} variant="text">
              Retry
            </Button>
          )}
        </div>
      ))}
      {(jobs.error || cancel.error || retry.error) && (
        <p className="text-danger text-meta m-0 font-semibold" role="alert">
          {errorMessage(jobs.error ?? cancel.error ?? retry.error)}
        </p>
      )}
    </section>
  );
}
