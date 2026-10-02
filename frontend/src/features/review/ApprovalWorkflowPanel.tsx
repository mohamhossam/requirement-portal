import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, Circle, CircleAlert, CircleDot } from "lucide-react";
import { useRef, useState, useId } from "react";
import { Link } from "react-router-dom";

import {
  api,
  type ApprovalTargetKind,
  type ApprovalWorkflow,
  type ReviewFlag,
  type StoryQuality,
} from "../../api/client";
import { invalidateWorkspaceKeys } from "../../app/workspaceInvalidation";
import { errorMessage } from "../../api/errors";
import { queryKeys } from "../../app/queryKeys";
import { ErrorNotice } from "../../components/ErrorNotice";
import { useRequirementJobs } from "../jobs/useRequirementJobs";
import { Skeleton } from "../../components/Skeleton";
import { Disclosure } from "../../components/Disclosure";
import { StoryQualityPanel } from "../stories/StoryQualityPanel";
import { Badge, Button, Card, cx, Modal, ModalBody, ModalFooter, ModalHeader, Select, Textarea } from "../../components/ui";
import {
  BREAKDOWN_STATUS_LABEL,
  DECISION_LABEL,
  LIFECYCLE,
  TARGET_KIND_LABEL,
  when,
} from "./labels";

type PendingAction =
  | { kind: "submit" }
  | { kind: "final" }
  | { kind: "reject"; storyId: string; featureId: string }
  | null;

/**
 * Sign-off, then history — the last two sections of Review & approve.
 *
 * Rendered by `BreakdownReviewPanel` *after* the evidence. `docs/ux-plan.md`
 * §3.6 found this panel mounted first, so the approve buttons sat above
 * everything they were meant to be pressed on. Within it the order is the same
 * argument at a smaller scale: where the backlog is in its lifecycle, what has
 * been approved so far, what still stands in the way, the per-Story decisions,
 * and only then Submit and Final approval.
 *
 * After the first critique: each Story row carries that Story's readiness
 * verdict; what stands in the way sits directly above the two buttons it
 * gates, and names the Epic and Feature approvals this screen cannot give;
 * history names what each approval was of and says when one no longer counts;
 * every failure shows beside the control that caused it.
 *
 * Presentation only (`CLAUDE.md`). The query, the six mutations, the pending
 * dialog state and the comment draft are unchanged from the panel this
 * replaces.
 */

function Heading({
  id,
  title,
  description,
}: {
  id: string;
  title: string;
  description?: string;
}) {
  return (
    <header className="grid gap-1">
      <h2 className="text-headline text-ink m-0" id={id}>{title}</h2>
      {description && (
        <p className="text-ink-muted text-body m-0 max-w-[var(--measure-document)]">{description}</p>
      )}
    </header>
  );
}

export function ApprovalWorkflowPanel({
  requirementId,
  flags,
  quality = [],
}: {
  requirementId: string;
  flags: ReviewFlag[];
  /**
   * Each Story's readiness checks, from the review this panel is rendered
   * under. Shown on the Story's own decision row, so the evidence for a
   * decision sits beside it rather than a screen above it.
   */
  quality?: StoryQuality[];
}) {
  const queryClient = useQueryClient();
  const governanceTitleId = useId();
  const governanceConfirmRef = useRef<HTMLButtonElement>(null);
  const jobs = useRequirementJobs(requirementId);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [rationale, setRationale] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [commentTarget, setCommentTarget] = useState(`breakdown:${requirementId}`);
  const workflow = useQuery({
    queryKey: queryKeys.approvalWorkflow(requirementId),
    queryFn: () => api.getApprovalWorkflow(requirementId),
    refetchOnMount: "always",
  });

  const accept = async (value: ApprovalWorkflow) => {
    queryClient.setQueryData(queryKeys.approvalWorkflow(requirementId), value);
    await invalidateWorkspaceKeys(queryClient, [queryKeys.breakdownReview(requirementId), queryKeys.revisions(requirementId), queryKeys.requirementLists(), queryKeys.scope("stories", requirementId)]);
  };
  const submit = useMutation({
    mutationFn: (fingerprint: string) =>
      api.submitForReview(requirementId, fingerprint, workflow.data!.review_version),
    onSuccess: async (value) => {
      setPendingAction(null);
      setRationale("");
      await accept(value);
    },
  });
  const finalApproval = useMutation({
    mutationFn: (fingerprint: string) =>
      api.approveBreakdown(
        requirementId,
        fingerprint,
        workflow.data!.review_version,
        rationale || undefined,
      ),
    onSuccess: async (value) => {
      setPendingAction(null);
      setRationale("");
      await accept(value);
    },
  });
  const approveStory = useMutation({
    mutationFn: ({ storyId, featureId, fingerprint, version }: { storyId: string; featureId: string; fingerprint: string; version: number }) =>
      api.approveStory(requirementId, featureId, storyId, version, fingerprint),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.approvalWorkflow(requirementId) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.scope("stories", requirementId) });
    },
  });
  const rejectStory = useMutation({
    mutationFn: ({ storyId, featureId, fingerprint, version }: { storyId: string; featureId: string; fingerprint: string; version: number }) =>
      api.rejectStory(
        requirementId,
        featureId,
        storyId,
        fingerprint,
        version,
        workflow.data!.review_version,
        rationale,
      ),
    onSuccess: async () => {
      setPendingAction(null);
      setRationale("");
      await queryClient.invalidateQueries({ queryKey: queryKeys.approvalWorkflow(requirementId) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.breakdownReview(requirementId) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.scope("stories", requirementId) });
    },
  });
  const comment = useMutation({
    mutationFn: () => {
      const separator = commentTarget.indexOf(":");
      const kind = commentTarget.slice(0, separator) as ApprovalTargetKind;
      const targetId = commentTarget.slice(separator + 1);
      return api.addReviewComment(
        requirementId,
        kind,
        targetId,
        commentBody,
        workflow.data!.review_version,
      );
    },
    onSuccess: async (value) => {
      setCommentBody("");
      await accept(value);
    },
  });

  if (workflow.isPending) return <Skeleton label="Loading the approval workflow" bars={2} />;
  if (workflow.isError) return <ErrorNotice message={errorMessage(workflow.error)} />;
  if (!workflow.data) return null;

  const data = workflow.data;
  const aiBusy = jobs.active.length > 0;
  const storyArtifacts = data.artifacts.filter((item) => item.target.kind === "story");
  const dialogBusy = submit.isPending || finalApproval.isPending || rejectStory.isPending;
  const completion = data.completion;
  const gateReasons = [...data.readiness_reasons, ...data.blocking_reasons];
  const history = data.artifacts.flatMap((item) => item.approval_history).concat(data.breakdown_approvals);
  const canSubmit = data.can_submit && !aiBusy;
  const canApprove = data.can_approve_breakdown && !aiBusy;
  const currentStage = LIFECYCLE.indexOf(data.status);
  const dialogError = submit.error ?? finalApproval.error ?? rejectStory.error;
  const artifactById = new Map(data.artifacts.map((item) => [item.target.item_id, item]));
  const qualityByStory = new Map(quality.map((item) => [item.story_id, item]));
  const unlisted = quality.filter((item) => !storyArtifacts.some((story) => story.target.item_id === item.story_id));
  const openConcerns = flags.filter((flag) => flag.status === "open").length;
  // This screen approves Stories. The Epic and Features are approved in the
  // Backlog, and the gate demands them too, so it says where to go.
  const upstreamOwed = completion.epic_approved < completion.epic_total || completion.features_approved < completion.features_total;
  const showGate = gateReasons.length > 0 || upstreamOwed;
  /**
   * An approval counts while it is its item's current approval. Editing the
   * item after it lapses it — approval follows the content — and history used
   * to list the lapsed one as plainly as the rest, beside a completion count
   * that did not include it.
   */
  const lapsed = (approval: (typeof history)[number]) => {
    if (approval.decision !== "approved" || approval.target.kind === "breakdown") return false;
    const artifact = artifactById.get(approval.target.item_id);
    return Boolean(artifact) && artifact!.current_approval?.id !== approval.id;
  };
  const anyLapsed = history.some(lapsed);
  const recap =
    `${completion.stories_approved} of ${completion.stories_total} Stories, ` +
    `${completion.features_approved} of ${completion.features_total} Features and ` +
    `${completion.epic_approved} of ${completion.epic_total} Epic approved · ` +
    `${openConcerns} ${openConcerns === 1 ? "concern" : "concerns"} still open.`;

  return (
    <>
      <section className="grid grid-cols-[minmax(0,1fr)] gap-6" aria-labelledby="approval-workflow-title">
        <Heading
          id="approval-workflow-title"
          title="Sign off this backlog"
          description="Reviewers decide each Story; the Requirement Owner submits the backlog and grants final approval."
        />

        <Card padding="snug" className="grid gap-5">
          {/* The current stage is marked by glyph, weight and `aria-current` —
              not by the accent, which is kept for the one action on this
              screen that can be taken (design-system §4.4 rule 1). Only the
              current stage is claimed: Needs revision is a loop back, not a
              stage every backlog passes, so ticking the ones "before" it would
              say something the workflow does not know. */}
          <ol aria-label="Approval lifecycle" className="m-0 flex list-none flex-wrap gap-x-6 gap-y-2 p-0">
            {LIFECYCLE.map((stage, index) => {
              const current = index === currentStage;
              const passed = data.status === "approved" && index < currentStage && stage !== "needs_revision";
              const Glyph = current ? CircleDot : passed ? Check : Circle;
              return (
                <li
                  key={stage}
                  aria-current={current ? "step" : undefined}
                  className={cx(
                    "text-body inline-flex items-center gap-1.5",
                    current ? "text-ink font-semibold" : "text-ink-muted",
                  )}
                >
                  <Glyph aria-hidden="true" size={15} />
                  {BREAKDOWN_STATUS_LABEL[stage]}
                </li>
              );
            })}
          </ol>

          <dl
            aria-label="Approval completion"
            className="m-0 flex flex-wrap gap-x-8 gap-y-2 [border-top:1px_solid_var(--line)] pt-4"
          >
            {(
              [
                ["Epic approved", completion.epic_approved, completion.epic_total],
                ["Features approved", completion.features_approved, completion.features_total],
                ["Stories approved", completion.stories_approved, completion.stories_total],
              ] as const
            ).map(([label, approved, total]) => (
              <div key={label} className="flex items-baseline gap-1.5">
                <dt className="text-meta text-ink-muted">{label}</dt>
                <dd className="text-body text-ink m-0 font-semibold tabular-nums">
                  {approved} of {total}
                </dd>
              </div>
            ))}
          </dl>
        </Card>

        {storyArtifacts.length > 0 && (
          <section aria-labelledby="story-approval-title" className="grid gap-3">
            <div className="grid gap-1">
              <h3 className="text-title text-ink m-0" id="story-approval-title">Story decisions</h3>
              {data.status !== "under_review" && (
                <p className="text-meta text-ink-muted m-0">
                  Reviewers can reject a Story once the backlog is submitted for review.
                </p>
              )}
            </div>
            <ul
              aria-labelledby="story-approval-title"
              className="border-line bg-surface m-0 grid list-none rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]"
            >
              {storyArtifacts.map((item) => {
                const labelId = `story-${item.target.item_id}-label`;
                const checks = qualityByStory.get(item.target.item_id);
                return (
                  <li key={item.target.item_id} className="grid gap-3 px-5 py-4">
                    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
                      <div className="grid min-w-0 flex-[1_1_24rem] justify-items-start gap-1.5">
                        <span className="text-document text-ink max-w-[68ch] font-serif" id={labelId}>{item.label}</span>
                        <span className="flex flex-wrap gap-2">
                          {item.current_approval ? (
                            <Badge tone="success">Approved by {item.current_approval.recorded_by.display_name}</Badge>
                          ) : item.status === "needs_revision" ? (
                            <Badge tone="danger">Needs revision</Badge>
                          ) : (
                            <Badge tone="neutral">Awaiting a decision</Badge>
                          )}
                          {checks && <ReadinessBadge quality={checks} />}
                        </span>
                      </div>
                      <div className="flex shrink-0 flex-wrap gap-2">
                        <Button variant="secondary" type="button" aria-describedby={labelId} disabled={!data.can_comment || aiBusy || approveStory.isPending || item.current_approval !== null} onClick={() => approveStory.mutate({ storyId: item.target.item_id, featureId: item.parent_id ?? "", fingerprint: item.fingerprint, version: item.version })}>Approve</Button>
                        <Button variant="secondary" type="button" aria-describedby={labelId} disabled={!data.can_comment || aiBusy || data.status !== "under_review" || rejectStory.isPending} onClick={() => setPendingAction({ kind: "reject", storyId: item.target.item_id, featureId: item.parent_id ?? "" })}>Reject</Button>
                      </div>
                    </div>
                    {checks && (
                      <Disclosure label="Readiness checks">
                        <StoryQualityPanel quality={checks} focused title={item.label} />
                      </Disclosure>
                    )}
                  </li>
                );
              })}
            </ul>
            {approveStory.error && <ErrorNotice message={errorMessage(approveStory.error)} />}
            {unlisted.length > 0 && (
              <Disclosure label={`Readiness checks for ${unlisted.length} more ${unlisted.length === 1 ? "Story" : "Stories"}`}>
                <div className="grid gap-4">
                  {unlisted.map((item) => <StoryQualityPanel key={item.story_id} quality={item} focused title={`Story ${item.story_id.slice(0, 8)}`} />)}
                </div>
              </Disclosure>
            )}
          </section>
        )}

        {/* What stands in the way, directly above the two acts it gates — it
            was 500px above them, under the lifecycle, and the buttons pointed
            back up at it through `aria-describedby` across the whole list. */}
        <div className="grid gap-4 [border-top:1px_solid_var(--line)] pt-5">
          {showGate && (
            <Card padding="compact" as="div" tone="warning" className="flex items-start gap-3" id="approval-gate">
              <CircleAlert aria-hidden="true" className="text-warning mt-0.5 shrink-0" size={18} />
              <div className="text-body grid gap-2">
                <strong className="text-warning">Before this backlog can move on</strong>
                {gateReasons.length > 0 && (
                  <ul className="text-ink-soft m-0 grid gap-1 pl-5">
                    {gateReasons.map((reason) => <li key={reason}>{reason}</li>)}
                  </ul>
                )}
                {upstreamOwed && (
                  <Link
                    className="text-accent inline-flex min-h-6 items-center gap-1 justify-self-start underline underline-offset-2"
                    to={`/requirements/${requirementId}/breakdown`}
                  >
                    Approve the Epic and Features in Backlog <ArrowRight aria-hidden="true" size={14} />
                  </Link>
                )}
              </div>
            </Card>
          )}
          {aiBusy && (
            <p className="text-meta text-ink-muted m-0">
              Sign-off is paused while an AI job is changing this Requirement.
            </p>
          )}
          {/* The filled accent goes to whichever act can be taken now and
              never to a button that cannot be pressed (the Phase 2 rule for
              the Confirm gate). */}
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant={canSubmit && !canApprove ? "primary" : "secondary"}
              type="button"
              disabled={!canSubmit}
              aria-describedby={!canSubmit && showGate ? "approval-gate" : undefined}
              onClick={() => setPendingAction({ kind: "submit" })}
            >
              Submit for review
            </Button>
            <Button
              variant={canApprove ? "primary" : "secondary"}
              type="button"
              disabled={!canApprove}
              aria-describedby={!canApprove && showGate ? "approval-gate" : undefined}
              onClick={() => setPendingAction({ kind: "final" })}
            >
              Final approval
            </Button>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-[minmax(0,1fr)] gap-6" aria-labelledby="approval-history-title">
        <Heading id="approval-history-title" title="History and comments" />

        <Card padding="snug" className="grid gap-3">
          <h3 className="text-title text-ink m-0" id="approval-list-title">Approvals</h3>
          {anyLapsed && (
            <p className="text-meta text-ink-muted m-0 max-w-[var(--measure-document)]">
              An approval stops counting when its item is edited afterwards, so it has to be approved again.
            </p>
          )}
          {history.length ? (
            <ol aria-labelledby="approval-list-title" className="m-0 grid list-none p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
              {history.map((approval) => {
                const target = approval.target.kind === "breakdown" ? null : artifactById.get(approval.target.item_id);
                return (
                  <li key={approval.id} className="grid min-w-0 gap-1 py-3 first:pt-0 last:pb-0">
                    <p className="text-body m-0 flex flex-wrap items-center gap-x-2 gap-y-1">
                      <strong className={lapsed(approval) ? "text-ink-muted" : "text-ink"}>
                        {TARGET_KIND_LABEL[approval.target.kind]} {DECISION_LABEL[approval.decision]}
                      </strong>
                      <span className="text-ink-muted">
                        by {approval.recorded_by.display_name} ·{" "}
                        <time className="tabular-nums" dateTime={approval.recorded_at}>{when(approval.recorded_at)}</time>
                      </span>
                      {lapsed(approval) && <Badge tone="neutral">No longer current</Badge>}
                    </p>
                    {target && <p className="text-meta text-ink-muted m-0 truncate">{target.label}</p>}
                    {approval.rationale && (
                      <p className="text-document text-ink-soft m-0 max-w-[68ch] font-serif">{approval.rationale}</p>
                    )}
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="text-body text-ink-muted m-0">No attributed approvals recorded yet.</p>
          )}
        </Card>

        <Card padding="snug" className="grid grid-cols-[minmax(0,1fr)] gap-4">
          <h3 className="text-title text-ink m-0" id="review-comments-title">Comments</h3>
          {data.comments.length ? (
            <ol aria-labelledby="review-comments-title" className="m-0 grid list-none p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
              {data.comments.map((item) => (
                <li key={item.id} className="grid gap-1 py-3 first:pt-0 last:pb-0">
                  <p className="text-body m-0">
                    <strong className="text-ink">{item.recorded_by.display_name}</strong>
                    <span className="text-ink-muted">
                      {" "}on {TARGET_KIND_LABEL[item.target.kind]} ·{" "}
                      <time className="tabular-nums" dateTime={item.recorded_at}>{when(item.recorded_at)}</time>
                    </span>
                  </p>
                  <p className="text-document text-ink-soft m-0 max-w-[68ch] font-serif">{item.body}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-body text-ink-muted m-0">No comments yet.</p>
          )}
          <form
            className="grid max-w-[var(--measure-interface)] gap-3 [border-top:1px_solid_var(--line)] pt-4"
            onSubmit={(event) => { event.preventDefault(); comment.mutate(); }}
          >
            <Select label="About" value={commentTarget} onChange={(event) => setCommentTarget(event.target.value)}>
              <option value={`breakdown:${requirementId}`}>{TARGET_KIND_LABEL.breakdown}</option>
              {data.artifacts.map((item) => (
                <option key={`${item.target.kind}:${item.target.item_id}`} value={`${item.target.kind}:${item.target.item_id}`}>
                  {TARGET_KIND_LABEL[item.target.kind]}: {item.label}
                </option>
              ))}
              {flags.map((flag) => (
                <option key={`flag:${flag.id}`} value={`flag:${flag.id}`}>{TARGET_KIND_LABEL.flag}: {flag.title}</option>
              ))}
            </Select>
            <Textarea
              label="Comment"
              className="text-document font-serif"
              required
              value={commentBody}
              onChange={(event) => setCommentBody(event.target.value)}
              rows={3}
            />
            {comment.error && <ErrorNotice message={errorMessage(comment.error)} />}
            <div>
              <Button variant="secondary" type="submit" disabled={!data.can_comment || aiBusy || comment.isPending}>
                {comment.isPending ? "Adding…" : "Add comment"}
              </Button>
            </div>
          </form>
        </Card>
      </section>

      {pendingAction && (
        <Modal variant="dialog" labelledBy={governanceTitleId} onClose={() => setPendingAction(null)} initialFocus={governanceConfirmRef}>
          <form onSubmit={(event) => {
            event.preventDefault();
            const fingerprint = data.subject_fingerprint ?? "";
            if (pendingAction.kind === "submit") submit.mutate(fingerprint);
            else if (pendingAction.kind === "final") finalApproval.mutate(fingerprint);
            else rejectStory.mutate({
              storyId: pendingAction.storyId,
              featureId: pendingAction.featureId,
              fingerprint,
              version: data.artifacts.find(
                (item) => item.target.kind === "story" && item.target.item_id === pendingAction.storyId
              )!.version,
            });
          }}>
            <ModalHeader
              id={governanceTitleId}
              title={pendingAction.kind === "submit" ? "Submit this backlog?" : pendingAction.kind === "final" ? "Grant final approval?" : "Reject this Story?"}
              description={pendingAction.kind === "submit" ? "The backlog is locked for review exactly as it stands now." : pendingAction.kind === "final" ? "You are approving the complete submitted backlog as Requirement Owner." : "The Story stays visible and the backlog moves to Needs revision."}
            />
            <ModalBody>
              {/* The highest-stakes click on the screen said nothing about
                  what it covered. Now it says what is approved and what is
                  still open, from counts this panel already holds. */}
              {pendingAction.kind !== "reject" && (
                <p className="text-body text-ink m-0 tabular-nums">{recap}</p>
              )}
              {pendingAction.kind !== "submit" && (
                <Textarea
                  label={pendingAction.kind === "reject" ? "Reason" : "Rationale (optional)"}
                  className="text-document font-serif"
                  required={pendingAction.kind === "reject"}
                  value={rationale}
                  onChange={(event) => setRationale(event.target.value)}
                  rows={3}
                />
              )}
              {dialogError && <ErrorNotice message={errorMessage(dialogError)} />}
            </ModalBody>
            <ModalFooter>
              <Button variant="text" type="button" disabled={dialogBusy} onClick={() => setPendingAction(null)}>Cancel</Button>
              <Button ref={governanceConfirmRef} variant="primary" type="submit" disabled={dialogBusy || !data.subject_fingerprint}>
                {dialogBusy
                  ? "Saving…"
                  : pendingAction.kind === "submit" ? "Submit backlog" : pendingAction.kind === "final" ? "Grant final approval" : "Reject Story"}
              </Button>
            </ModalFooter>
          </form>
        </Modal>
      )}
    </>
  );
}

/** The Story's readiness verdict, in words, on its decision row. */
function ReadinessBadge({ quality }: { quality: StoryQuality }) {
  if (quality.status === "passes" && quality.failure_count === 0) {
    return <Badge tone="success">Ready to build</Badge>;
  }
  const failed = `${quality.failure_count} of ${quality.findings.length} checks failed`;
  return (
    <Badge tone="warning">
      {quality.status === "split_recommended" ? "Split recommended" : "Needs attention"} · {failed}
    </Badge>
  );
}
