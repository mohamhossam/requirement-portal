import { useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import type {
  KnowledgeFinding,
  KnowledgeReview,
  KnowledgeScreenEnsure,
} from "../../api/client";
import { useAuth } from "../../auth/authContext";
import { Disclosure } from "../../components/Disclosure";
import { ErrorNotice } from "../../components/ErrorNotice";
import { ProvenanceDetails } from "../../components/ProvenanceDetails";
import {
  Badge,
  Button,
  Card,
  cx,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Textarea,
} from "../../components/ui";
import { when } from "../breakdown/labels";
import {
  approvalsLine,
  decisionLabel,
  fieldLabel,
  findingVerdict,
  KIND_LABEL,
  linkedRequirement,
  owedBy,
  REVIEW_DESCRIPTION,
  REVIEW_HEADING,
  RUNNING_DESCRIPTION,
  RUNNING_HEADING,
} from "./labels";

type Decision = "distinct" | "duplicate" | "propose_resolution" | "accept_resolution";

type Props = {
  requirementId: string;
  /** Named in the duplicate confirmation, so nobody closes the wrong one. */
  requirementTitle: string;
  /** This requirement's business need, set beside a match that cites only the other side. */
  requirementText: string;
  review: KnowledgeReview;
  running: boolean;
  ensureOutcome: KnowledgeScreenEnsure["outcome"] | null;
  ensureJobId: string | null;
  canDecide: boolean;
  busy: boolean;
  /** Screening and retry failures, reported at the top of the panel. */
  error: string | null;
  /** A failed decision, reported inside the finding it was made on. */
  decisionError: string | null;
  onRetry: (jobId: string) => void;
  onDecide: (finding: KnowledgeFinding, decision: Decision, text?: string) => void;
};

const QUOTE = "font-serif text-document text-ink m-0 max-w-[var(--measure-document)] whitespace-pre-line";
const INLINE_LINK = "text-accent inline-flex min-h-6 items-center underline underline-offset-2";

/**
 * A radio that matches the Checkbox primitive: token border, 20px mark, a 24px
 * target through its label. Still a native `<input type="radio">`, so arrow
 * keys move within the group without a line of script.
 */
function Choice({
  name,
  value,
  checked,
  onChange,
  children,
}: {
  name: string;
  value: string;
  checked: boolean;
  onChange: (value: string) => void;
  children: string;
}) {
  return (
    <label className="text-body text-ink grid min-h-6 cursor-pointer grid-cols-[auto_minmax(0,1fr)] items-start gap-2 leading-6">
      <span className="grid min-h-6 min-w-6 place-items-center">
        <input
          checked={checked}
          className={cx(
            "border-line-strong bg-surface size-5 cursor-pointer appearance-none rounded-full border border-solid",
            "hover:border-accent checked:border-accent checked:border-[6px]",
            "transition-[border] duration-[var(--motion-fast)] motion-reduce:transition-none",
          )}
          name={name}
          onChange={() => onChange(value)}
          type="radio"
          value={value}
        />
      </span>
      {children}
    </label>
  );
}

function FindingCard({
  requirementId,
  requirementTitle,
  requirementText,
  finding,
  canDecide,
  actorId,
  busy,
  deciding,
  primary,
  error,
  onDecide,
}: {
  requirementId: string;
  requirementTitle: string;
  requirementText: string;
  finding: KnowledgeFinding;
  canDecide: boolean;
  actorId: string | null;
  busy: boolean;
  /** This card's decision is the one in flight. */
  deciding: boolean;
  /** The first finding waiting on this person takes the screen's one filled action. */
  primary: boolean;
  error: string | null;
  onDecide: (finding: KnowledgeFinding, decision: Decision, text?: string) => void;
}) {
  const headingId = useId();
  const choiceName = useId();
  const dialogTitleId = useId();
  const [text, setText] = useState("");
  const [revision, setRevision] = useState("");
  const [choice, setChoice] = useState<"distinct" | "duplicate" | null>(null);
  const [confirming, setConfirming] = useState(false);
  const cancelRef = useRef<HTMLButtonElement>(null);

  const linked = linkedRequirement(finding, requirementId);
  const verdict = findingVerdict(finding, { canDecide, actorId });
  const duplicate = finding.kind === "possible_duplicate";
  const actionable = finding.status === "open" || finding.status === "resolution_pending";
  const isSubject = finding.subject_requirement_id === requirementId;
  const accepted = Boolean(actorId && finding.resolution_approvals.includes(actorId));
  const proposal = [...finding.decisions].reverse().find((decision) => decision.kind === "resolution_proposed");
  const action = primary ? "primary" : "secondary";
  // A title is a name, not evidence: the linked one already names the heading,
  // and this requirement's own is the page's h1.
  const evidence = finding.evidence.filter(
    (item) => !(item.field === "title" && (item.requirement_id === requirementId || (linked.title && item.requirement_id === linked.id))),
  );
  // The screener cites what it matched, which is often only the other side.
  // A contradiction cannot be judged from one statement, so this requirement's
  // own business need — already on the page's data — stands beside it.
  const ownText = requirementText.trim();
  const showOwn = Boolean(ownText) && !evidence.some((item) => item.requirement_id === requirementId);
  const side = (id: string) => (id === requirementId ? "This requirement" : id === linked.id ? linked.name : `Requirement ${id.slice(0, 8)}`);

  return (
    <Card as="article" aria-labelledby={headingId} className="grid min-w-0 gap-4" padding="fluid">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="text-title text-ink m-0 min-w-0 [overflow-wrap:anywhere]" id={headingId}>
          {KIND_LABEL[finding.kind]}{" "}
          <Link className="text-accent underline underline-offset-2" to={`/requirements/${linked.id}/knowledge`}>
            {linked.name}
          </Link>
        </h3>
        <Badge tone={verdict.tone}>{verdict.label}</Badge>
      </header>

      <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">{finding.rationale}</p>

      {(evidence.length > 0 || showOwn) && (
        <section aria-labelledby={`${headingId}-evidence`} className="grid gap-3">
          <h4 className="text-label text-ink m-0" id={`${headingId}-evidence`}>What matched</h4>
          <ul className="m-0 grid list-none gap-3 p-0">
            {showOwn && (
              <li className="bg-surface-sunken grid gap-2 rounded-sm px-4 py-3">
                <p className="text-meta text-ink-muted m-0">
                  <span className="text-ink font-semibold">This requirement</span> · Business need, for comparison
                </p>
                <blockquote className={QUOTE}>{ownText}</blockquote>
              </li>
            )}
            {evidence.map((item) => (
              <li className="bg-surface-sunken grid gap-2 rounded-sm px-4 py-3" key={item.chunk_id}>
                <p className="text-meta text-ink-muted m-0">
                  <span className="text-ink font-semibold">{side(item.requirement_id)}</span> · {fieldLabel(item.field)}
                </p>
                <blockquote className={QUOTE}>{item.excerpt}</blockquote>
                <Link className={cx(INLINE_LINK, "text-meta w-fit")} to={item.evidence_path}>
                  Open in context{" "}
                  <span className="sr-only">for {side(item.requirement_id)}, {fieldLabel(item.field)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {finding.resolution_statement && (
        // Divided, not boxed: a bordered box inside the finding's card was a
        // card in a card.
        <section
          aria-labelledby={`${headingId}-resolution`}
          className="grid gap-2 [border-top:1px_solid_var(--line)] pt-4"
        >
          <h4 className="text-label text-ink m-0" id={`${headingId}-resolution`}>
            {finding.status === "resolved" ? "Agreed resolution" : "Proposed resolution"}
          </h4>
          <p className={QUOTE}>{finding.resolution_statement}</p>
          <p className="text-meta text-ink-muted m-0">
            {proposal && (
              <>
                Proposed by {proposal.actor.display_name} ·{" "}
                <time className="tabular-nums" dateTime={proposal.recorded_at}>{when(proposal.recorded_at)}</time>.{" "}
              </>
            )}
            {approvalsLine(finding.resolution_approvals.length)}
          </p>
        </section>
      )}

      {actionable && !canDecide && (
        <p className="text-meta text-ink-muted m-0">
          Only the owners of these two requirements can decide this — People shows who owns this one. The evidence
          and history stay readable here.
        </p>
      )}

      {actionable && canDecide && duplicate && (
        <div className="grid gap-3 [border-top:1px_solid_var(--line)] pt-4">
          {isSubject ? (
            <fieldset className="m-0 grid gap-2 border-0 p-0">
              <legend className="text-label text-ink mb-2 p-0">Are these the same need?</legend>
              <Choice
                checked={choice === "distinct"}
                name={choiceName}
                onChange={() => setChoice("distinct")}
                value="distinct"
              >
                Different needs — keep both
              </Choice>
              <Choice
                checked={choice === "duplicate"}
                name={choiceName}
                onChange={() => setChoice("duplicate")}
                value="duplicate"
              >
                The same need — close this requirement
              </Choice>
            </fieldset>
          ) : (
            <p className="text-meta text-ink-muted m-0">
              If they are the same need, close {linked.title ? `“${linked.title}”` : "the other requirement"} from{" "}
              <Link className={INLINE_LINK} to={`/requirements/${linked.id}/knowledge`}>its own Knowledge step</Link>.
            </p>
          )}

          {(!isSubject || choice === "distinct") && (
            <div className="grid gap-3">
              <Textarea
                hint="Recorded in the decision history, where both owners can read it."
                label="Why they are different needs"
                onChange={(event) => setText(event.target.value)}
                rows={2}
                value={text}
              />
              <Button
                blockedReason={text.trim() ? undefined : "Say why they differ first."}
                className="w-fit"
                disabled={busy}
                loading={deciding}
                loadingLabel="Saving…"
                onClick={() => onDecide(finding, "distinct", text.trim())}
                variant={text.trim() ? action : "secondary"}
              >
                Mark as distinct
              </Button>
            </div>
          )}

          {isSubject && choice === "duplicate" && (
            <div className="grid gap-3">
              <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">
                “{requirementTitle}” will be closed as a duplicate of {linked.title ? `“${linked.title}”` : linked.name}.
                Its history stays readable, but no further analysis or backlog is generated from it.
              </p>
              <Button className="w-fit" disabled={busy} loading={deciding} loadingLabel="Closing…" onClick={() => setConfirming(true)}>
                Close as duplicate…
              </Button>
            </div>
          )}
        </div>
      )}

      {actionable && canDecide && !duplicate && finding.status === "open" && (
        <div className="grid gap-3 [border-top:1px_solid_var(--line)] pt-4">
          <Textarea
            hint="Say which rule applies where, or which one takes precedence. Both owners have to accept it."
            label="How the two requirements fit together"
            onChange={(event) => setText(event.target.value)}
            rows={3}
            value={text}
          />
          <Button
            blockedReason={text.trim() ? undefined : "Write the resolution first."}
            className="w-fit"
            disabled={busy}
            loading={deciding}
            loadingLabel="Proposing…"
            onClick={() => onDecide(finding, "propose_resolution", text.trim())}
            variant={text.trim() ? action : "secondary"}
          >
            Propose shared resolution
          </Button>
        </div>
      )}

      {actionable && canDecide && finding.status === "resolution_pending" && (
        <div className="grid gap-3 [border-top:1px_solid_var(--line)] pt-4">
          {accepted ? (
            <p className="text-body text-ink-soft m-0">You accepted this. It is waiting for the other owner.</p>
          ) : (
            <Button
              className="w-fit"
              disabled={busy}
              loading={deciding}
              loadingLabel="Accepting…"
              onClick={() => onDecide(finding, "accept_resolution")}
              variant={action}
            >
              Accept shared resolution
            </Button>
          )}
          <Disclosure label="Suggest different wording">
            <div className="grid gap-3">
              <Textarea
                hint="Replaces the proposal; both owners accept again."
                label="Revised resolution"
                onChange={(event) => setRevision(event.target.value)}
                rows={2}
                value={revision}
              />
              <Button
                blockedReason={revision.trim() ? undefined : "Write the revised wording first."}
                className="w-fit"
                disabled={busy}
                onClick={() => onDecide(finding, "propose_resolution", revision.trim())}
              >
                Propose revision
              </Button>
            </div>
          </Disclosure>
        </div>
      )}

      {error && <ErrorNotice message={error} />}

      {finding.decisions.length > 0 && (
        <Disclosure label={`Decision history (${finding.decisions.length})`}>
          <ol className="m-0 grid gap-2 pl-5">
            {finding.decisions.map((decision, index) => (
              <li className="text-body text-ink-soft" key={`${decision.recorded_at}-${index}`}>
                <span className="text-ink font-semibold">{decisionLabel(decision.kind)}</span> by{" "}
                {decision.actor.display_name} ·{" "}
                <time className="text-meta text-ink-muted tabular-nums" dateTime={decision.recorded_at}>
                  {when(decision.recorded_at)}
                </time>
                {decision.rationale ? <span className="block">{decision.rationale}</span> : null}
              </li>
            ))}
          </ol>
        </Disclosure>
      )}

      {confirming && (
        <Modal variant="dialog" labelledBy={dialogTitleId} onClose={() => setConfirming(false)} initialFocus={cancelRef}>
          <ModalHeader
            id={dialogTitleId}
            title="Close this requirement as a duplicate?"
            description="This cannot be undone from this screen."
          />
          <ModalBody>
            <p className="m-0">
              <strong className="text-ink">“{requirementTitle}”</strong> will be closed and will point to{" "}
              <strong className="text-ink">{linked.title ? `“${linked.title}”` : linked.name}</strong> instead.
            </p>
            <p className="m-0">
              Its analysis, answers and history stay readable. No further analysis, backlog or export can be made from it.
            </p>
          </ModalBody>
          <ModalFooter>
            {/* Cancel is focused on open: Enter, still held from the click that
                opened this, must not become the closure itself. */}
            <Button ref={cancelRef} variant="text" onClick={() => setConfirming(false)}>Cancel</Button>
            <Button
              variant="danger"
              onClick={() => {
                setConfirming(false);
                onDecide(finding, "duplicate");
              }}
            >
              Close as duplicate
            </Button>
          </ModalFooter>
        </Modal>
      )}
    </Card>
  );
}

export function KnowledgeReviewPanel(props: Props) {
  const auth = useAuth();
  const actorId = auth?.actor?.id ?? null;
  const [lastDecided, setLastDecided] = useState<string | null>(null);
  const who = { canDecide: props.canDecide, actorId };
  const findings = props.review.findings;
  const owed = findings.filter((finding) => owedBy(finding, who));
  const waiting = findings.filter(
    (finding) => finding.status === "resolution_pending" && !owedBy(finding, who),
  ).length;
  const open = findings.filter((finding) => finding.status === "open" || finding.status === "resolution_pending").length;

  const heading = props.running
    ? RUNNING_HEADING
    : props.review.status === "action_required" && owed.length > 0
      ? `${owed.length} ${owed.length === 1 ? "overlap needs" : "overlaps need"} your decision`
      : REVIEW_HEADING[props.review.status];
  const description = props.running ? RUNNING_DESCRIPTION : REVIEW_DESCRIPTION[props.review.status];
  const counts = [
    open > 0 && `${open} to settle`,
    owed.length > 0 && `${owed.length} waiting on you`,
    waiting > 0 && `${waiting} waiting on the other owner`,
  ].filter(Boolean);
  // A decision error whose finding has left the list has nowhere else to go.
  const strayDecisionError =
    props.decisionError && !findings.some((finding) => finding.id === lastDecided) ? props.decisionError : null;

  return (
    <section className="grid min-w-0 gap-4" aria-labelledby="knowledge-review-title">
      <header className="grid gap-1">
        <h2 className="text-headline text-ink m-0" id="knowledge-review-title">{heading}</h2>
        <p className="text-body text-ink-soft m-0 max-w-[var(--measure-interface)]">{description}</p>
        {!props.running && counts.length > 0 && (
          <p className="text-meta text-ink-muted m-0 tabular-nums">{counts.join(" · ")}</p>
        )}
      </header>

      {props.ensureOutcome === "manual_retry_required" && (
        <Card padding="compact" tone="warning" className="grid gap-3" role="status">
          <p className="text-body text-ink-soft m-0">
            The last check stopped without finishing. It will not start again by itself — not on refresh, and not
            when the service restarts.
          </p>
          <Button
            className="w-fit"
            disabled={props.busy || !props.ensureJobId}
            onClick={() => {
              const jobId = props.ensureJobId;
              if (jobId) props.onRetry(jobId);
            }}
          >
            Retry knowledge screening
          </Button>
        </Card>
      )}

      {props.error && <ErrorNotice message={props.error} />}
      {strayDecisionError && <ErrorNotice message={strayDecisionError} />}

      {findings.length ? (
        <ul aria-label="Overlaps with other requirements" className="m-0 grid list-none gap-4 p-0">
          {findings.map((finding) => (
            <li key={`${finding.id}-${finding.version}`}>
              <FindingCard
                actorId={actorId}
                busy={props.busy}
                canDecide={props.canDecide}
                deciding={props.busy && lastDecided === finding.id}
                error={lastDecided === finding.id ? props.decisionError : null}
                finding={finding}
                onDecide={(item, decision, text) => {
                  setLastDecided(item.id);
                  props.onDecide(item, decision, text);
                }}
                primary={owed[0]?.id === finding.id}
                requirementId={props.requirementId}
                requirementText={props.requirementText}
                requirementTitle={props.requirementTitle}
              />
            </li>
          ))}
        </ul>
      ) : (
        <p className="border-line text-body text-ink-muted m-0 rounded-md border border-dashed px-4 py-6 text-center">
          {props.running
            ? "Any overlaps will appear here when the check finishes."
            : props.review.status === "required" || props.review.status === "stale"
              ? "A current check is needed before the analysis can be confirmed."
              : "No overlaps or conflicts with other requirements."}
        </p>
      )}

      {props.review.provenance && (
        <ProvenanceDetails label="How this check was made" provenance={props.review.provenance} />
      )}
    </section>
  );
}
