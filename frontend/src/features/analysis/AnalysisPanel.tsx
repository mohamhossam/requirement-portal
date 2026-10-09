import { Check, PenLine } from "lucide-react";
import { useState } from "react";

import type {
  Actor,
  AnalysisRound,
  AnswerSuggestionSet,
  ClarificationAnswerInput,
  ClarificationQuestion,
  ClarificationResolutionInput,
  ClarificationSeverity,
  IntentProposal,
  IntentProposalStatus,
  RequirementAnalysis,
} from "../../api/client";
import { useUnsavedGuard } from "../../app/useUnsavedChanges";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Button, Card, cx, Select, Textarea } from "../../components/ui";
import { AnalysisSourcesProvider } from "./AnalysisSources";
import { IntentProposalCard } from "./IntentProposalCard";
import type { IntentProposalDraft } from "./IntentProposalCard";
import { LegacyClarificationForm } from "./LegacyClarificationForm";
import type { LegacyEntry } from "./LegacyClarificationForm";
import { QuestionGroup } from "./QuestionCard";
import { RoundHistory } from "./RoundHistory";
import { ColumnHeading, SettledColumn } from "./SettledColumn";
import { StatusStrip } from "./StatusStrip";

/**
 * Clarify — the requirement's open questions.
 *
 * ## The structure, and what it refuses
 *
 * One document mid-completion: **what is settled on the left, what is still
 * open on the right**, and answering moves an item across. The screen it
 * replaces put a status strip, a provenance banner and the whole AI-intent
 * section above two equal finding columns, so the questions — the reason this
 * route exists — were the third thing on the page and the extracted facts held
 * first position for no reason a reviewer could act on. `docs/ux-plan.md` §5
 * Phase 2: "put the question list first".
 *
 * The left column is the reward for the work on the right. It is the only place
 * that answers §3.5's complaint that Clarify and Confirm are the same component
 * split by Knowledge: on `/confirm` this column *is* the confirmation summary,
 * so `AnalysisView` no longer renders a second copy of the facts, rules and
 * constraints below its own heading.
 *
 * ## Why a container query and not a breakpoint
 *
 * The viewport does not predict this column's width. A fixed 240px sidebar and
 * a 240px stage rail sit between the window and this panel, so the same 1280px
 * screen gives it ~690px here and ~970px on a route without the rail. Every one
 * of `docs/design-system.md` §10.2's three widths would be a guess at a number
 * the browser can measure exactly. The Three Widths Rule governs media queries —
 * this is not one, and a fourth breakpoint is precisely what asking the viewport
 * would have required.
 *
 * ## What is not this file's to change
 *
 * `CLAUDE.md`: presentation only. Every mutation, query, prop and callback is
 * the caller's; nothing here fetches, and the props below are unchanged from the
 * screen this replaces. The two additions the user approved are the label map
 * (`./labels`, for `ux-plan.md` §3.7's five raw-enum sites) and `useUnsavedGuard`,
 * which stops a typed answer being lost to a click on the stage rail — a guard
 * four other editors in this app already register and this one did not.
 */

/**
 * The intent proposals, and where they live.
 *
 * Pending proposals are open decisions, so they head the working column. Once
 * every one is decided the whole block belongs to the settled column, under the
 * outcome it produced — the one piece of content on this screen that actually
 * crosses from one side to the other.
 */
function useIntentDrafts() {
  const [drafts, setDrafts] = useState<Record<string, IntentProposalDraft>>({});
  useUnsavedGuard(drafts);
  return {
    drafts,
    open(proposal: IntentProposal, seed: Pick<IntentProposalDraft, "replacement" | "measures" | "rationale">) {
      setDrafts((current) => ({ ...current, [proposal.id]: { version: proposal.version, ...seed } }));
    },
    close(id: string) {
      setDrafts((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
    },
  };
}

function AnalysisPanelContent({
  analysis,
  rounds,
  team,
  busy,
  error,
  onClarify,
  onConfirm,
  onSaveDraft,
  onResolveBatch,
  suggestions,
  suggestionsBusy,
  onSuggestAnswers,
  onClassify,
  onAssign,
  onAsk,
  canConfirm = true,
  confirmPermissionReason,
  canDecideIntent,
  onDecideIntent,
  view = "clarify",
}: Required<
  Pick<AnalysisPanelProps, "analysis" | "busy" | "error" | "onClarify" | "onConfirm">
> &
  Omit<AnalysisPanelProps, "analysis" | "busy" | "error" | "onClarify" | "onConfirm">) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [answerSources, setAnswerSources] = useState<Record<string, string>>({});
  const [askSubject, setAskSubject] = useState("");
  const [askAssignee, setAskAssignee] = useState("");
  const intentDrafts = useIntentDrafts();
  const questions = analysis.questions ?? [];

  const legacyUnresolved: LegacyEntry[] = [
    ...analysis.assumptions.map((item) => ({ kind: "assumption" as const, primary: item.statement })),
    ...analysis.open_questions.map((item) => ({
      kind: "open_question" as const,
      primary: item.question,
      secondary: item.rationale,
    })),
    ...analysis.ambiguities.map((item) => ({
      kind: "ambiguity" as const,
      primary: item.statement,
      secondary: item.reason,
    })),
    ...analysis.potential_dependencies.map((item) => ({
      kind: "potential_dependency" as const,
      primary: item.statement,
    })),
  ];
  const unresolvedCount = questions.length || legacyUnresolved.length;
  const blocking = questions.filter((question) => question.is_blocker);
  const alsoOpen = questions.filter((question) => !question.is_blocker);
  const blockingCount = questions.length ? blocking.length : legacyUnresolved.length;
  const resolvedCount = analysis.clarifications.length;
  const proposals = analysis.business_intent.proposals;
  const pendingProposals = proposals.filter((item) => item.status === "pending");
  const questionChanges = analysis.question_changes ?? [];
  const intentReady =
    pendingProposals.length === 0 && Boolean(analysis.business_intent.desired_outcome);

  const readyAnswers = questions.flatMap((question) => {
    const answer = (answers[question.id] ?? question.draft_answer ?? "").trim();
    return answer
      ? [
          {
            question_id: question.id,
            answer,
            expected_version: question.version,
            ...(answerSources[question.id]
              ? { source_suggestion_id: answerSources[question.id] }
              : {}),
          },
        ]
      : [];
  });

  /* Typed-but-unsaved work, which is what a navigation would actually lose: an
     answer that already matches its saved draft is not dirty. `RequirementForm`,
     `EpicEditForm`, `FeatureEditForm` and `StoryEditForm` all register this and
     this screen — the one the plan calls the deepest daily work — did not. */
  useUnsavedGuard({
    typed: questions
      .map((question) => [question.id, answers[question.id] ?? ""] as const)
      .filter(([id, value]) => {
        const question = questions.find((item) => item.id === id);
        return value !== "" && value !== (question?.draft_answer ?? "");
      }),
    asking: askSubject.trim(),
    intent: Object.entries(intentDrafts.drafts).filter(([id, draft]) =>
      proposals.some(p => p.id === id && p.version === draft.version)),
  });

  /* Reuses the same derivation the resolve bar counts, so the two can never
     disagree about what "ready" means. */
  const pendingAnswers = questions.flatMap((question) => {
    const answer = (answers[question.id] ?? question.draft_answer ?? "").trim();
    return answer ? [{ id: question.id, subject: question.subject, answer }] : [];
  });

  const decided = proposals.filter((item) => item.status !== "pending");
  const intentCard = (proposal: IntentProposal) => (
    <IntentProposalCard
      analysis={analysis}
      busy={busy}
      canDecide={Boolean(canDecideIntent)}
      draft={
        intentDrafts.drafts[proposal.id]?.version === proposal.version
          ? intentDrafts.drafts[proposal.id]
          : undefined
      }
      key={proposal.id}
      onCloseDraft={() => intentDrafts.close(proposal.id)}
      onDecide={onDecideIntent}
      onDraft={(change) =>
        intentDrafts.open(proposal, {
          rationale: change.rationale ?? intentDrafts.drafts[proposal.id]?.rationale ?? "",
          replacement:
            change.replacement ??
            intentDrafts.drafts[proposal.id]?.replacement ??
            proposal.effective_statement ??
            proposal.statement,
          measures:
            change.measures ??
            intentDrafts.drafts[proposal.id]?.measures ??
            (proposal.effective_success_measures.length
              ? proposal.effective_success_measures
              : proposal.success_measures
            ).join("\n"),
        })
      }
      permissionReason={confirmPermissionReason}
      proposal={proposal}
    />
  );

  const outcome = analysis.business_intent.desired_outcome;
  const settledIntent = (
    <section aria-label="What this requirement is for" className="grid gap-2">
      <h3 className="text-label text-ink-muted m-0">What this requirement is for</h3>
      {outcome ? (
        /* A document block, not an accent. Settled understanding is not the
           next action, and the accent means exactly that (§4.1). */
        <div className="border-line bg-surface grid gap-1 rounded-md border border-solid p-3">
          <span className="text-document-lead text-ink font-serif">{outcome.statement}</span>
          <span className="text-ink-muted text-meta flex items-center gap-1.5">
            {outcome.origin === "source" ? (
              <>
                <PenLine size={12} aria-hidden="true" /> Written in the source
              </>
            ) : (
              <>
                <Check size={12} aria-hidden="true" /> Agreed by the Requirement Owner
              </>
            )}
          </span>
        </div>
      ) : (
        <p className="text-ink-muted text-body m-0">
          No agreed outcome yet. It is one of the decisions still open.
        </p>
      )}
      {pendingProposals.length === 0 && decided.length > 0 && (
        <div className="grid gap-2">{decided.map(intentCard)}</div>
      )}
    </section>
  );

  /* It pins only once there is something to send.
   *
   * Pinned from the top of the page it floated a disabled button over the work
   * — over the intent proposal's own Accept and Reject on a desktop capture, and
   * over the open column's heading on a phone — which is the obscured-content
   * half of WCAG 2.2 2.4.11 arriving through an action bar rather than through
   * fixed chrome. Nothing is owed until an answer exists, so until one does this
   * is an ordinary footer at the end of the column. Sticky never leaves the
   * flow, so it gains its pin without moving anything. */
  const pinned = readyAnswers.length > 0;

  const resolveBar = questions.length > 0 && (
    <div
      /* The hook for the 2.4.11 rule in base.css: while this is pinned, the
         document scroller reserves its height as scroll-padding-bottom, so a
         focused control is scrolled clear of it rather than left underneath. */
      data-resolve-pinned={pinned || undefined}
      className={cx(
        "bg-surface border-line flex flex-wrap items-center justify-between gap-3 rounded-md border border-solid p-3",
        pinned && "sticky bottom-0 z-[var(--z-base)]",
      )}
    >
      {/* Not a live region. The count changes on every keystroke, so announcing
          it would read "1 answer ready" over the top of the person typing. The
          number is beside the button that uses it, which is where it is read. */}
      <p className="text-body text-ink-muted m-0 tabular-nums">
        {readyAnswers.length === 0
          ? "No answers ready yet"
          : `${readyAnswers.length} answer${readyAnswers.length === 1 ? "" : "s"} ready to send`}
      </p>
      <Button
        disabled={busy || readyAnswers.length === 0}
        loading={busy}
        loadingLabel="Sending…"
        onClick={() => onResolveBatch?.(readyAnswers)}
        variant="primary"
      >
        {readyAnswers.length === 0
          ? "Send answers and re-analyse"
          : readyAnswers.length === 1
            ? "Send 1 answer and re-analyse"
            : `Send ${readyAnswers.length} answers and re-analyse`}
      </Button>
    </div>
  );

  /**
   * What stands between this analysis and a signature, in the order a person
   * hits it. `undefined` means nothing does.
   */
  const confirmBlockedBy = (analysis.stale_reference_proposal_ids ?? []).length
    ? "Reference evidence changed. Open source impact review to reconcile the affected content."
    : blockingCount
    ? `${blockingCount} question${blockingCount === 1 ? "" : "s"} must be answered first.`
    : !intentReady
      ? "Each item under “Decisions you owe” needs a decision, and this requirement needs an agreed outcome."
      : !canConfirm
        ? confirmPermissionReason
        : undefined;

  /**
   * The gate renders whenever the analysis is unconfirmed — including while it
   * is blocked.
   *
   * It used to be `!blockingCount && !human_confirmed`, so with four blockers
   * the whole block evaluated false and `/confirm` — the route whose entire job
   * is this signature — rendered no button, no heading and no reason, under a
   * page description that reads "…before confirmation". design-system.md §11
   * says it in as many words: "a gated primary action stays visible and explains
   * why rather than disappearing." `Button`'s `blockedReason` is what puts that
   * reason in the control's own `aria-describedby`, so the explanation reaches a
   * screen reader rather than only sitting nearby.
   *
   * The body says what confirming *does* — nothing on this screen said so
   * before, and it starts backlog generation — while the reason says what is
   * missing. Two different sentences, so neither is noise.
   */
  // Above the columns on /confirm, the gate is a section of its own under the
  // page h1; inside the open column it sits under that column's h2.
  const GateHeading = view === "confirm" ? "h2" : "h3";
  const confirmGate = !analysis.human_confirmed && (
    <Card className="grid gap-3" tone={confirmBlockedBy ? "warning" : "success"}>
      <GateHeading className="text-title text-ink m-0">
        {confirmBlockedBy ? "Not ready to confirm" : "Ready to confirm"}
      </GateHeading>
      <p className="text-ink-soft text-body m-0 max-w-[68ch]">
        {confirmBlockedBy
          ? "Confirming locks this analysis and starts backlog generation from it."
          : questions.length
            ? "Nothing blocking is left. The questions still open will travel on into the backlog review."
            : "Nothing is blocking this analysis."}
      </p>
      <div>
        {/* Secondary while gated. A full indigo fill on a control that does
            nothing is the accent spent on the one action you cannot take — the
            critique's P1 — while the send button you can press sat beside it
            looking quieter. The reason underneath says what is missing. */}
        <Button
          blockedReason={confirmBlockedBy}
          disabled={busy}
          loading={busy}
          loadingLabel="Confirming…"
          onClick={onConfirm}
          variant={confirmBlockedBy ? "secondary" : "primary"}
        >
          Confirm this analysis
        </Button>
      </div>
    </Card>
  );

  return (
    <div className="@container grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4 [overflow-wrap:anywhere]">
      <StatusStrip analysis={analysis} answered={resolvedCount} open={unresolvedCount} />

      {(analysis.round_number ?? 1) > 1 && questionChanges.length > 0 && (
        /* Four counts to scan, not a sentence to read, and neutral: it reports
           what the last round did, it does not approve anything — green is
           reserved for approved (§4.4 rule 3). */
        <section
          aria-label="Since the last round"
          className="border-line bg-surface-sunken flex flex-wrap items-center gap-x-6 gap-y-2 rounded-md border border-solid px-4 py-3"
          role="status"
        >
          <h3 className="text-label text-ink m-0">Since the last round</h3>
          <dl className="m-0 flex flex-wrap gap-x-5 gap-y-1">
            {(
              [
                ["Kept", "retained"],
                ["Retired", "retired"],
                ["Revised", "replaced"],
                ["New", "created"],
              ] as const
            ).map(([label, action]) => (
              <div key={action} className="flex items-baseline gap-1.5">
                <dt className="text-meta text-ink-muted">{label}</dt>
                <dd className="text-body text-ink m-0 font-semibold tabular-nums">
                  {questionChanges.filter((item) => item.action === action).length}
                </dd>
              </div>
            ))}
          </dl>
          <a className="text-accent text-meta ml-auto inline-flex min-h-6 items-center underline underline-offset-2" href="#round-history">
            See every round
          </a>
        </section>
      )}

      {/* Only a connected knowledge portal that could not be reached earns a
          notice: with none connected there was nothing to check (ADR-0104). */}
      {analysis.reference_grounding === "unavailable" && (
        <Card tone="warning" role="status" aria-label="References not checked">
          <h3 className="text-label text-ink m-0">References were not checked</h3>
          <p className="text-body text-ink m-0 mt-1">
            The knowledge portal could not be reached when this analysis ran, so it has no
            proposals from the published library. Run the analysis again to check them.
          </p>
        </Card>
      )}

      {/* Confirm mode: the Requirement Owner's one job, first. It sat at the
          foot of "What is still open", 1400px down, on the route whose whole
          purpose it is. */}
      {view === "confirm" && confirmGate}

      {/* `mt-4` on top of the wrapper's own `gap-4`: the two column headings are
          the first thing in their columns, so everything above them is this
          margin and everything below is their 8px padding plus the column's
          20px gap. At the default that read 16px above and 28px below — a
          heading closer to the section it leaves than the one it introduces.
          32 and 28 puts it the right way round. */}
      <div className="mt-4 grid min-w-0 grid-cols-[minmax(0,1fr)] items-start gap-6 @[42rem]:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        {/* Order, not source position: below the split the work comes first,
            because a reader who has to scroll past the settled column to reach
            a question is reading the page this one replaces. */}
        <SettledColumn
          analysis={analysis}
          pending={pendingAnswers}
          className={cx(
            "order-2 @[42rem]:order-1",
            "@[42rem]:sticky @[42rem]:top-[calc(var(--header-height)+var(--space-6))]",
            "@[42rem]:max-h-[calc(100dvh-var(--header-height)-var(--space-12))]",
            "@[42rem]:-mx-2 @[42rem]:overflow-y-auto @[42rem]:px-2",
          )}
          intent={settledIntent}
        />

        <section
          aria-labelledby="open-heading"
          className={cx(
            "order-1 grid min-w-0 content-start gap-5 @[42rem]:order-2",
            /* The pinned bar's 2.4.11 clearance is `scroll-padding-bottom` on
               the document (base.css, `:root:has([data-resolve-pinned])`).
               Measured by parking each of 44 focusable controls under the bar
               and focusing it: 0 left covered with the padding, 33 without.
               This `pb` is the other half — runway at the end of the column, so
               the last control has somewhere to scroll up to. The per-control
               `scroll-margin` that used to sit here is gone; the padding makes
               it redundant. */
            pinned && "pb-[calc(var(--space-16)+var(--space-12))]",
          )}
        >
          <ColumnHeading
            count={unresolvedCount === 0 ? "nothing open" : `${blockingCount} blocking`}
            id="open-heading"
          >
            What is still open
          </ColumnHeading>


          {questions.length > 0 ? (
            <>
              {blocking.length > 0 && (
                <QuestionGroup
                  analysis={analysis}
                  answers={answers}
                  answerSources={answerSources}
                  busy={busy}
                  id="blocking"
                  onAssign={onAssign}
                  onClassify={onClassify}
                  onSaveDraft={onSaveDraft}
                  onSuggestAnswers={onSuggestAnswers}
                  questions={blocking}
                  setAnswerSources={setAnswerSources}
                  setAnswers={setAnswers}
                  suggestions={suggestions ?? {}}
                  suggestionsBusy={Boolean(suggestionsBusy)}
                  team={team ?? []}
                  title="Must be answered first"
                  tone="warning"
                />
              )}
              {alsoOpen.length > 0 && (
                <QuestionGroup
                  analysis={analysis}
                  answers={answers}
                  answerSources={answerSources}
                  busy={busy}
                  id="also-open"
                  onAssign={onAssign}
                  onClassify={onClassify}
                  onSaveDraft={onSaveDraft}
                  onSuggestAnswers={onSuggestAnswers}
                  questions={alsoOpen}
                  setAnswerSources={setAnswerSources}
                  setAnswers={setAnswers}
                  suggestions={suggestions ?? {}}
                  suggestionsBusy={Boolean(suggestionsBusy)}
                  team={team ?? []}
                  title="Worth answering, not blocking"
                  tone="default"
                />
              )}
              {error && <ErrorNotice message={error} />}
              {resolveBar}
            </>
          ) : legacyUnresolved.length ? (
            <>
              <LegacyClarificationForm
                answers={answers}
                busy={busy}
                error={error}
                entries={legacyUnresolved}
                onClarify={onClarify}
                setAnswers={setAnswers}
              />
            </>
          ) : (
            <>
              {analysis.human_confirmed && (
                <p className="text-success text-body m-0 flex items-center gap-2">
                  <Check size={16} aria-hidden="true" />
                  The Requirement Owner has confirmed this analysis.
                </p>
              )}
              {error && <ErrorNotice message={error} />}
            </>
          )}

          {/* After the questions, not above them. They were first, as 400px
              cards, so the first viewport at 1440×900 held no question at all
              (critique 2026-09-21, P1). They are open decisions and they stay in
              this column; they no longer stand between a person and the list. */}
          {pendingProposals.length > 0 && (
            <section aria-label="Decisions the Requirement Owner owes" className="grid gap-3">
              <h3 className="text-label text-ink-muted m-0">
                Decisions you owe ({pendingProposals.length})
              </h3>
              {pendingProposals.map(intentCard)}
            </section>
          )}

          {/* Clarify ends here: the gate is where the work leads. On /confirm it
              leads the screen instead, above both columns. Every branch —
              questions, a legacy pre-question-ID analysis, nothing open — keeps
              it, because a gated primary action stays visible and explains why
              (design-system.md §11). */}
          {view !== "confirm" && confirmGate}

          {onAsk && (
            <form
              className="border-line grid gap-3 rounded-md border border-dashed p-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (askSubject.trim()) {
                  onAsk(askSubject.trim(), askAssignee || null);
                  setAskSubject("");
                  setAskAssignee("");
                }
              }}
            >
              <h3 className="text-title text-ink m-0">Ask someone else</h3>
              <Textarea
                hint="It joins the list above and blocks nothing until you say it does."
                label="What is missing?"
                onChange={(event) => setAskSubject(event.target.value)}
                placeholder="Example: Which customer segments can hold more than one active bundle?"
                rows={2}
                value={askSubject}
              />
              <Select
                label="Ask"
                onChange={(event) => setAskAssignee(event.target.value)}
                value={askAssignee}
              >
                <option value="">Nobody in particular</option>
                {team?.map((actor) => (
                  <option key={actor.id} value={actor.id}>
                    {actor.display_name}
                  </option>
                ))}
              </Select>
              <div>
                <Button disabled={busy || !askSubject.trim()} type="submit">
                  Add this question
                </Button>
              </div>
            </form>
          )}
        </section>
      </div>

      <RoundHistory rounds={rounds ?? []} />
    </div>
  );
}

export type AnalysisPanelProps = {
  analysis: RequirementAnalysis;
  /**
   * Which of the two routes this is. One screen, two modes (docs/slices/
   * redesign-phase-2-clarify-confirm.md): Clarify leads with the questions;
   * Confirm leads with the sign-off, and the questions follow.
   */
  view?: "clarify" | "confirm";
  rounds?: AnalysisRound[];
  team?: Actor[];
  busy: boolean;
  error: string | null;
  onClarify: (answers: ClarificationAnswerInput[]) => void;
  onConfirm: () => void;
  onSaveDraft?: (question: ClarificationQuestion, answer: string) => void;
  onResolveBatch?: (answers: ClarificationResolutionInput[]) => void;
  suggestions?: Record<string, AnswerSuggestionSet | null>;
  suggestionsBusy?: boolean;
  onSuggestAnswers?: (question: ClarificationQuestion) => void;
  onClassify?: (
    question: ClarificationQuestion,
    severity: ClarificationSeverity,
    isBlocker: boolean,
  ) => void;
  onAssign?: (question: ClarificationQuestion, actorId: string | null) => void;
  onAsk?: (subject: string, assigneeId: string | null) => void;
  canConfirm?: boolean;
  confirmPermissionReason?: string;
  canDecideIntent?: boolean;
  onDecideIntent?: (
    proposal: IntentProposal,
    decision: IntentProposalStatus,
    replacement?: string,
    successMeasures?: string[],
    rationale?: string,
  ) => void;
};

export function AnalysisPanel(props: AnalysisPanelProps) {
  const { analysis } = props;
  return (
    <AnalysisSourcesProvider
      documents={analysis.document_references}
      key={`${analysis.requirement_id}-${analysis.analysis_id}-${analysis.version}`}
    >
      <AnalysisPanelContent {...props} />
    </AnalysisSourcesProvider>
  );
}
