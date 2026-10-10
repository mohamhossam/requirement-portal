import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowRight, CheckCircle2, RefreshCcw, ShieldAlert, TriangleAlert, Wrench } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { api, type BreakdownReview, type ReviewFlag } from "../../api/client";
import { invalidateWorkspaceKeys } from "../../app/workspaceInvalidation";
import { useRequirementJobs } from "../jobs/useRequirementJobs";
import { errorMessage, errorReference } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { ApprovalWorkflowPanel } from "./ApprovalWorkflowPanel";
import { Skeleton } from "../../components/Skeleton";
import { Badge, Button, ButtonLink, Card, cx, Input, Pill, Textarea } from "../../components/ui";
import {
  BREAKDOWN_STATUS_LABEL,
  BREAKDOWN_STATUS_TONE,
  CATEGORY_LABEL,
  EVIDENCE_KIND_LABEL,
  EVIDENCE_KIND_TONE,
  FILTER_LABEL,
  RISK_SEVERITY_LABEL,
  SEVERITY_LABEL,
  when,
  type FlagFilter,
} from "./labels";

/**
 * Review & approve — step 6, the Product Owner's screen.
 *
 * ## The order, and why it is the whole point
 *
 * `docs/ux-plan.md` §3.6: the screen this replaces mounted the approval
 * workflow *first*, so a person read the lifecycle stepper, the completion
 * counts, Submit and Final approval, per-Story approve and reject, the approval
 * history and the comments — and only then the concerns, the dependencies, the
 * risks and the quality evidence those buttons were supposed to be pressed on.
 * "The approve buttons render above the evidence you would approve on."
 *
 * Now it reads as one document, top to bottom, in the order the work happens:
 *
 *   1. where the review stands — a neutral strip, counts to scan
 *   2. concerns to resolve — the flags, the work
 *   3. evidence — dependencies, risks, recommendations
 *   4. the decision log
 *   5. sign-off — lifecycle, per-Story decisions with each Story's quality,
 *      then what stands in the way directly above Submit / Final approval
 *   6. history and comments
 *
 * The first critique (`.impeccable/critique/`, 20/40) found the strip saying
 * "Blocks approval 0" while sign-off was gated, anonymous quality cards a
 * screen away from the Story decisions, and focus dropped to `<body>` by every
 * inline form. Those are fixed here and in `ApprovalWorkflowPanel`.
 *
 * One column rather than a sticky sign-off aside: an aside would put the
 * buttons beside the evidence again, and it would need the approval workflow
 * split across two rendered regions — either a portal or two instances of its
 * mutations. Decided before starting (the Phase 3 slice).
 *
 * ## What is not this file's to change
 *
 * `CLAUDE.md`: presentation only. The query, the four mutations, their
 * variables and their invalidation are unchanged from the screen this
 * replaces; so are `FlagAction`'s and `DecisionForm`'s local drafts.
 * `ApprovalWorkflowPanel` keeps its own query and mutations and is simply
 * rendered after the evidence instead of before it.
 */

function sourceHref(requirementId: string, flag: ReviewFlag) {
  if (flag.source.kind === "analysis") return `/requirements/${requirementId}/clarify`;
  if (flag.source.kind === "epic") return `/requirements/${requirementId}/breakdown/epic`;
  return `/requirements/${requirementId}/breakdown#${flag.source.kind}-${flag.source.item_id}`;
}

/** A section of the review: an `h2` under the requirement's own `h1`. */
function ReviewSection({
  id,
  title,
  description,
  actions,
  children,
}: {
  id: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="grid gap-4">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h2 className="text-headline text-ink m-0" id={id}>{title}</h2>
          {description && (
            <p className="text-ink-muted text-body m-0 max-w-[var(--measure-document)]">{description}</p>
          )}
        </div>
        {actions}
      </header>
      {children}
    </section>
  );
}

/**
 * Focus follows an inline form: to its first field when it opens, back to the
 * button that opened it when it closes (WCAG 2.4.3). Both the button and the
 * form unmount in turn, so without this the browser parks focus on `<body>`
 * and a keyboard user is thrown to the top of a 3,000px page on every concern.
 */
function useFormFocus(open: boolean) {
  const trigger = useRef<HTMLButtonElement>(null);
  const field = useRef<HTMLInputElement & HTMLTextAreaElement>(null);
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) field.current?.focus();
    else if (wasOpen.current) trigger.current?.focus();
    wasOpen.current = open;
  }, [open]);
  return { trigger, field };
}

function FlagAction({
  flag,
  disabled,
  busy,
  error,
  describedBy,
  onResolve,
  onAnswer,
}: {
  flag: ReviewFlag;
  disabled: boolean;
  busy: boolean;
  /** This concern's own failed save, shown in its form rather than at the top of the page. */
  error: string | null;
  /** The concern's title and detail, so eight look-alike buttons say which one they act on. */
  describedBy: string;
  onResolve: (decision: string, rationale: string) => void;
  onAnswer: (answer: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [decision, setDecision] = useState("");
  const [rationale, setRationale] = useState("");
  const { trigger, field } = useFormFocus(open);

  if (flag.status === "resolved") {
    return (
      <span className="text-success text-body inline-flex min-h-9 items-center gap-1.5 font-semibold">
        <CheckCircle2 aria-hidden="true" size={16} /> Resolved
      </span>
    );
  }
  if (flag.resolution_policy === "source_action") {
    // Not resolvable here, and it says where it is: the link to the source is
    // the action, so this is a statement rather than a disabled button.
    return (
      <span className="text-ink-soft text-body inline-flex min-h-9 items-center gap-1.5 font-semibold">
        <Wrench aria-hidden="true" size={16} /> Source action required
      </span>
    );
  }
  if (!open) {
    return (
      <Button ref={trigger} variant="secondary" type="button" disabled={disabled} aria-describedby={describedBy} onClick={() => setOpen(true)}>
        {flag.resolution_policy === "clarification" ? "Answer question" : "Resolve with decision"}
      </Button>
    );
  }

  const answering = flag.resolution_policy === "clarification";
  return (
    <form
      aria-describedby={describedBy}
      className="grid w-full max-w-[var(--measure-interface)] gap-3 [border-top:1px_solid_var(--line)] pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (answering) onAnswer(rationale);
        else onResolve(decision, rationale);
      }}
    >
      {/* What resolving means, said once where it is decided: the decision is
          recorded against this concern and appears in the decision log. */}
      <p className="text-meta text-ink-muted m-0">
        {answering
          ? "Your answer goes back to the analysis, which runs again with it."
          : "Your decision settles this concern and is kept in the decision log."}
      </p>
      {!answering && (
        <Input
          ref={field}
          label="Decision"
          value={decision}
          onChange={(event) => setDecision(event.target.value)}
          required
        />
      )}
      <Textarea
        ref={answering ? field : undefined}
        label={answering ? "Answer" : "Rationale"}
        className="text-document font-serif"
        value={rationale}
        onChange={(event) => setRationale(event.target.value)}
        rows={3}
        required
      />
      {error && <ErrorNotice message={error} />}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="primary" type="submit" disabled={busy || disabled}>
          {busy ? "Saving…" : answering ? "Save answer and re-analyse" : "Confirm resolution"}
        </Button>
        <Button variant="text" type="button" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

const flagIds = (flag: ReviewFlag) => ({
  title: `review-flag-${flag.id}-title`,
  detail: `review-flag-${flag.id}-detail`,
});

function FlagRow({
  flag,
  requirementId,
  action,
}: {
  flag: ReviewFlag;
  requirementId: string;
  action: ReactNode;
}) {
  const open = flag.status === "open";
  return (
    <Card
      as="li"
      className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3"
      tone={!open ? "default" : flag.severity === "blocking" ? "danger" : "warning"}
    >
      <div className="grid min-w-0 flex-[1_1_28rem] gap-2">
        <p className="text-meta text-ink-muted m-0 flex flex-wrap items-center gap-2">
          {open && (
            <Badge tone={flag.severity === "blocking" ? "danger" : "warning"}>
              {SEVERITY_LABEL[flag.severity]}
            </Badge>
          )}
          <span>{CATEGORY_LABEL[flag.category]}</span>
        </p>
        <h3 className={cx("text-title m-0", open ? "text-ink" : "text-ink-soft")} id={flagIds(flag).title}>{flag.title}</h3>
        <p className="text-document text-ink-soft m-0 max-w-[68ch] font-serif" id={flagIds(flag).detail}>{flag.detail}</p>
        <Link
          className="text-meta text-ink-muted hover:text-ink inline-flex min-h-6 max-w-full items-center gap-1 underline underline-offset-2"
          to={sourceHref(requirementId, flag)}
        >
          <span className="truncate">{flag.source.label}</span>
          <ArrowRight aria-hidden="true" className="shrink-0" size={13} />
        </Link>
      </div>
      {action}
    </Card>
  );
}

/**
 * A decision about something no single concern covers. Closed until asked for:
 * an empty, always-open form under an empty log was the loudest thing in the
 * section and said nothing. Its drafts survive closing, like a concern's.
 */
function DecisionForm({
  disabled,
  busy,
  error,
  onSubmit,
}: {
  disabled: boolean;
  busy: boolean;
  error: string | null;
  onSubmit: (decision: string, rationale: string) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [decision, setDecision] = useState("");
  const [rationale, setRationale] = useState("");
  const { trigger, field } = useFormFocus(open);

  if (!open) {
    return (
      <div>
        <Button ref={trigger} variant="secondary" type="button" disabled={disabled} onClick={() => setOpen(true)}>
          Record a decision
        </Button>
      </div>
    );
  }

  return (
    <form
      aria-labelledby="record-decision-title"
      className="grid max-w-[var(--measure-interface)] gap-3 [border-top:1px_solid_var(--line)] pt-4"
      onSubmit={(event) => {
        event.preventDefault();
        void onSubmit(decision, rationale).then(() => {
          setDecision("");
          setRationale("");
          setOpen(false);
        }).catch(() => undefined);
      }}
    >
      <h3 className="text-title text-ink m-0" id="record-decision-title">Record a decision</h3>
      <Input ref={field} label="Decision" value={decision} onChange={(event) => setDecision(event.target.value)} required />
      <Textarea
        label="Rationale"
        className="text-document font-serif"
        value={rationale}
        onChange={(event) => setRationale(event.target.value)}
        rows={3}
        required
      />
      {error && <ErrorNotice message={error} />}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" type="submit" disabled={disabled || busy}>
          {busy ? "Recording…" : "Record decision"}
        </Button>
        <Button variant="text" type="button" onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

/** One labelled count in the summary strip, with a glyph when it is owed. */
function Count({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "danger" | "warning";
}) {
  const owed = tone && value > 0;
  const Glyph = tone === "danger" ? ShieldAlert : TriangleAlert;
  return (
    <div className="flex items-baseline gap-1.5">
      <dt className="text-meta text-ink-muted">{label}</dt>
      <dd
        className={cx(
          "text-body m-0 inline-flex items-center gap-1 font-semibold tabular-nums",
          owed ? (tone === "danger" ? "text-danger" : "text-warning") : "text-ink",
        )}
      >
        {owed && <Glyph aria-hidden="true" className="self-center" size={14} />}
        {value}
      </dd>
    </div>
  );
}

export function BreakdownReviewPanel({
  requirementId,
  canGenerate = true,
  canManage = true,
}: {
  requirementId: string;
  canGenerate?: boolean;
  canManage?: boolean;
}) {
  const queryClient = useQueryClient();
  const jobs = useRequirementJobs(requirementId);
  const [filter, setFilter] = useState<FlagFilter>("all");
  const review = useQuery({
    queryKey: queryKeys.breakdownReview(requirementId),
    queryFn: ({ signal }) => api.getBreakdownReview(requirementId, { signal }),
    refetchOnMount: "always",
  });
  const update = async (value: BreakdownReview) => {
    queryClient.setQueryData(queryKeys.breakdownReview(requirementId), value);
    await invalidateWorkspaceKeys(queryClient, [queryKeys.approvalWorkflow(requirementId), queryKeys.revisions(requirementId), queryKeys.requirementLists()]);
  };
  const generate = useMutation({
    mutationFn: () => jobs.startJob({ operation: "generate_breakdown_review" }),

  });
  const resolve = useMutation({
    mutationFn: ({ flagId, decision, rationale }: { flagId: string; decision: string; rationale: string }) =>
      api.resolveReviewFlag(requirementId, flagId, {
        decision,
        rationale,
        expected_fingerprint: review.data?.evidence_fingerprint ?? "",
        expected_version: review.data?.version ?? 0,
      }),
    onSuccess: update,
  });
  const answer = useMutation({
    mutationFn: ({ flagId, value }: { flagId: string; value: string }) =>
      jobs.startJob({
        operation: "resolve_review_open_question",
        flag_id: flagId,
        answer: value,
        expected_fingerprint: review.data?.evidence_fingerprint ?? "",
        expected_version: review.data?.version ?? 0,
      }),

  });
  const record = useMutation({
    mutationFn: ({ decision, rationale }: { decision: string; rationale: string }) =>
      api.recordReviewDecision(requirementId, {
        decision,
        rationale,
        expected_fingerprint: review.data?.evidence_fingerprint ?? "",
        expected_version: review.data?.version ?? 0,
      }),
    onSuccess: update,
  });

  if (review.isPending) return <Skeleton label="Loading the breakdown review" />;
  if (review.isError) return <ErrorNotice message={errorMessage(review.error)} reference={errorReference(review.error)} />;
  if (!review.data) {
    return (
      <div className="grid gap-4">
        <EmptyState
          title="No breakdown review yet"
          message={canGenerate ? "Generate one evidence-backed view of uncertainty, dependencies, architecture impact and Story quality." : "Analyse the Requirement before generating its review."}
          action={canGenerate ? <Button variant="primary" type="button" disabled={generate.isPending} onClick={() => generate.mutate()}>{generate.isPending ? "Generating review…" : "Generate breakdown review"}</Button> : <ButtonLink variant="primary" to={`/requirements/${requirementId}/clarify`}>Go to analysis</ButtonLink>}
        />
        {generate.error && <ErrorNotice message={errorMessage(generate.error)} reference={errorReference(generate.error)} />}
      </div>
    );
  }

  const data = review.data;
  const filteredFlags = data.flags.filter((flag) => {
    if (filter === "resolved") return flag.status === "resolved";
    if (filter === "blocking" || filter === "warning") {
      return flag.status === "open" && flag.severity === filter;
    }
    return true;
  });
  const busyFlag = resolve.variables?.flagId ?? answer.variables?.flagId;
  // Each failure is shown beside what caused it, read from the mutation that
  // already holds it: a concern's save in that concern's form, a decision in
  // the decision form. Only a failed refresh belongs at the top.
  const flagError = (flagId: string) => {
    if (resolve.error && resolve.variables?.flagId === flagId) return errorMessage(resolve.error);
    if (answer.error && answer.variables?.flagId === flagId) return errorMessage(answer.error);
    return null;
  };

  // Counted from the flags rather than the summary counts, so every pill agrees
  // with the list it filters to.
  const filterCounts: Record<FlagFilter, number> = {
    all: data.flags.length,
    blocking: data.flags.filter((flag) => flag.status === "open" && flag.severity === "blocking").length,
    warning: data.flags.filter((flag) => flag.status === "open" && flag.severity === "warning").length,
    resolved: data.flags.filter((flag) => flag.status === "resolved").length,
  };
  const evidenceCount = data.dependencies.length + data.risks.length + data.recommendations.length;

  return (
    <section className="grid grid-cols-[minmax(0,1fr)] gap-10" aria-label="Breakdown review">
      <div className="grid gap-4">
      {/* 1. Where it stands. Neutral: it reports, it does not approve — green
          is reserved for approved (design-system §4.4 rule 3). Only a count
          that is owed takes a status colour, and then with a glyph. */}
      <section
        aria-labelledby="review-standing-title"
        className="border-line bg-surface-sunken grid gap-3 rounded-md border border-solid px-4 py-3"
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          <h2 className="text-label text-ink m-0" id="review-standing-title">Where this review stands</h2>
          {/* The counts are named as concerns, because that is all they count.
              "Blocks approval 0" read as "nothing blocks approval" while the
              sign-off was still gated on Story and Feature approvals — which
              this panel does not load, so it links to where they are. */}
          <dl className="m-0 flex flex-wrap gap-x-5 gap-y-1" aria-label="Review counts">
            <div className="flex items-baseline gap-1.5">
              <dt className="text-meta text-ink-muted">Backlog</dt>
              <dd className="m-0">
                {BREAKDOWN_STATUS_TONE[data.status] === "neutral"
                  // A neutral badge is Margin Grey, the same ground as this
                  // strip, so its chip vanished. Plain text says it as well.
                  ? <span className="text-body text-ink font-semibold">{BREAKDOWN_STATUS_LABEL[data.status]}</span>
                  : <Badge tone={BREAKDOWN_STATUS_TONE[data.status]}>{BREAKDOWN_STATUS_LABEL[data.status]}</Badge>}
              </dd>
            </div>
            <Count label="Concerns blocking approval" value={data.unresolved_blocker_count} tone="danger" />
            <Count label="Concerns worth resolving" value={data.unresolved_warning_count} tone="warning" />
          </dl>
        </div>
        {/* Provenance on the left, the two things to do with this review on
            the right: one row, so neither wraps onto a line of its own. */}
        <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
          <p className="text-meta text-ink-muted m-0">
            Refreshed <time className="tabular-nums" dateTime={data.generated_at}>{when(data.generated_at)}</time>
            {" · "}review rules <span className="font-mono">{data.ruleset_version}</span>
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <a
              className="text-accent text-meta inline-flex min-h-6 items-center gap-1 underline underline-offset-2"
              href="#approval-workflow-title"
            >
              Sign-off status <ArrowDown aria-hidden="true" size={13} />
            </a>
            <Button
              size="sm"
              variant="secondary"
              type="button"
              icon={<RefreshCcw size={14} aria-hidden="true" />}
              disabled={generate.isPending || !canGenerate || !canManage}
              onClick={() => generate.mutate()}
            >
              {generate.isPending ? "Refreshing…" : "Refresh review"}
            </Button>
          </div>
        </div>
      </section>

      {!data.fresh && (
        <Card padding="compact" as="div" tone="warning" className="flex items-start gap-3" role="status">
          <TriangleAlert aria-hidden="true" className="text-warning mt-0.5 shrink-0" size={18} />
          <p className="text-body m-0 grid gap-0.5">
            <strong className="text-warning">This review is stale.</strong>
            <span className="text-ink-soft">Refresh it before recording or resolving decisions.</span>
          </p>
        </Card>
      )}
      {generate.error && <ErrorNotice message={errorMessage(generate.error)} reference={errorReference(generate.error)} />}
      </div>

      {/* 2. The work. */}
      <ReviewSection
        id="review-flags-title"
        title="Concerns to resolve"
        description="What the review found. Anything marked Blocks approval must be settled before final approval."
      >
        {data.flags.length > 0 && (
          <div aria-label="Filter concerns" className="flex flex-wrap gap-2" role="group">
            {(["all", "blocking", "warning", "resolved"] as const)
              // Only a filter with something behind it (§11) — but never hide
              // the one that is on, or a person loses the way back.
              .filter((value) => value === "all" || filterCounts[value] > 0 || filter === value)
              .map((value) => (
                <Pill
                  key={value}
                  active={filter === value}
                  count={filterCounts[value]}
                  onClick={() => setFilter(value)}
                >
                  {FILTER_LABEL[value]}
                </Pill>
              ))}
          </div>
        )}
        {filteredFlags.length ? (
          <ul className="m-0 grid list-none gap-3 p-0">
            {filteredFlags.map((flag) => (
              <FlagRow
                key={flag.id}
                flag={flag}
                requirementId={requirementId}
                action={
                  <FlagAction
                    flag={flag}
                    disabled={!canManage || !data.fresh}
                    busy={busyFlag === flag.id}
                    error={flagError(flag.id)}
                    describedBy={`${flagIds(flag).title} ${flagIds(flag).detail}`}
                    onResolve={(decision, rationale) => resolve.mutate({ flagId: flag.id, decision, rationale })}
                    onAnswer={(value) => answer.mutate({ flagId: flag.id, value })}
                  />
                }
              />
            ))}
          </ul>
        ) : (
          <p className="text-body text-ink-muted m-0">
            {data.flags.length ? "No concerns match this filter." : "The review found no concerns."}
          </p>
        )}
      </ReviewSection>

      {/* 3. The evidence. Three boxes each saying nothing was found is three
          boxes of nothing; emptiness is still worth reporting — the review did
          look — so it is reported once, in a line. */}
      <ReviewSection id="review-evidence-title" title="Evidence">
        {evidenceCount === 0 ? (
          <p className="text-body text-ink-muted m-0">No dependencies, risks or recommendations identified.</p>
        ) : (
          <Card padding="snug" className="grid gap-x-8 gap-y-6 [grid-template-columns:repeat(auto-fit,minmax(16rem,1fr))]">
            {data.dependencies.length > 0 && (
              <EvidenceList id="dependencies-title" title="Dependencies">
                {data.dependencies.map((item) => (
                  <EvidenceItem
                    key={item.id}
                    badge={<Badge tone={EVIDENCE_KIND_TONE[item.evidence_kind]}>{EVIDENCE_KIND_LABEL[item.evidence_kind]}</Badge>}
                    source={item.source.label}
                  >
                    {item.description}
                  </EvidenceItem>
                ))}
              </EvidenceList>
            )}
            {data.risks.length > 0 && (
              <EvidenceList id="risks-title" title="Risks">
                {data.risks.map((item) => (
                  <EvidenceItem
                    key={item.id}
                    badge={<Badge tone={item.severity === "blocking" ? "danger" : "warning"}>{RISK_SEVERITY_LABEL[item.severity]}</Badge>}
                    source={item.source.label}
                  >
                    {item.description}
                  </EvidenceItem>
                ))}
              </EvidenceList>
            )}
            {data.recommendations.length > 0 && (
              <EvidenceList id="recommendations-title" title="Recommendations">
                {data.recommendations.map((item) => (
                  <EvidenceItem key={item.id} source={item.source.label} note={item.rationale}>
                    {item.action}
                  </EvidenceItem>
                ))}
              </EvidenceList>
            )}
          </Card>
        )}
      </ReviewSection>

      {/* Story quality is not a section of its own any more. It was four
          anonymous cards 1,000px above the Story decisions they inform; each
          Story's verdict now sits on that Story's decision row, beside the
          label it was missing and before the buttons it is evidence for. */}

      {/* 4. What was decided, and a way to add to it. */}
      <ReviewSection
        id="review-decisions-title"
        title="Decision log"
        description="Resolving a concern records its decision here. Record one yourself for anything else the backlog depends on."
      >
        <Card padding="snug" className="grid grid-cols-[minmax(0,1fr)] gap-4">
          {data.decisions.length ? (
            <ol className="m-0 grid list-none p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
              {data.decisions.map((item) => (
                <li key={item.id} className="grid gap-1 py-4 first:pt-0 last:pb-0">
                  <strong className="text-title text-ink">{item.decision}</strong>
                  <p className="text-document text-ink-soft m-0 max-w-[68ch] font-serif">{item.rationale}</p>
                  <p className="text-meta text-ink-muted m-0">
                    {item.recorded_by?.display_name ?? "Recorded before people were tracked"}
                    {" · "}
                    <time className="tabular-nums" dateTime={item.recorded_at}>{when(item.recorded_at)}</time>
                  </p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-body text-ink-muted m-0">No decisions recorded.</p>
          )}
          <DecisionForm disabled={!canManage || !data.fresh} busy={record.isPending} error={record.error ? errorMessage(record.error) : null} onSubmit={(decision, rationale) => record.mutateAsync({ decision, rationale }).then(() => undefined)} />
        </Card>
      </ReviewSection>

      {/* 5 and 6. Last, because it is decided on everything above it. The
          quality results travel down as a prop, as the concerns already do:
          the sign-off panel knows each Story's label, this one does not. */}
      <ApprovalWorkflowPanel requirementId={requirementId} flags={data.flags} quality={data.quality_assessments} />

      <span className="sr-only" aria-live="polite">{generate.isPending || resolve.isPending || answer.isPending || record.isPending ? "Saving review changes" : ""}</span>
    </section>
  );
}

function EvidenceList({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="grid content-start gap-3">
      <h3 className="text-title text-ink m-0" id={id}>{title}</h3>
      <ul className="m-0 grid list-none p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">{children}</ul>
    </section>
  );
}

function EvidenceItem({
  badge,
  source,
  note,
  children,
}: {
  badge?: ReactNode;
  source: string;
  note?: string;
  children: ReactNode;
}) {
  return (
    <li className="grid justify-items-start gap-1 py-3 first:pt-0 last:pb-0">
      {badge}
      {/* Generated prose, so the document face (the Register Rule). */}
      <span className="text-document text-ink font-serif">{children}</span>
      {note && <span className="text-body text-ink-soft">{note}</span>}
      <span className="text-meta text-ink-muted">{source}</span>
    </li>
  );
}
