import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  api,
  type ClarificationAnswerInput,
  type ClarificationQuestion,
  type ClarificationResolutionInput,
  type ClarificationSeverity,
  type IntentProposal,
  type IntentProposalStatus,
} from "../../api/client";
import { errorMessage } from "../../api/errors";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { EmptyState } from "../../components/EmptyState";
import { ErrorNotice } from "../../components/ErrorNotice";
import { Skeleton } from "../../components/Skeleton";
import { Button } from "../../components/ui";
import { missingLabel } from "../../features/documents/labels";
import { SourceImpactPanel } from "../../features/documents/SourceImpactPanel";
import { AnalysisPanel } from "../../features/analysis/AnalysisPanel";
import { useRequirementJobs } from "../../features/jobs/useRequirementJobs";
import { queryKeys } from "../queryKeys";
import type { RequirementWorkspace } from "./useRequirementWorkspace";

/**
 * Analyse, clarify and confirm are one screen, in two modes.
 *
 * The confirm route used to add a second copy of the facts, rules and
 * constraints above the panel; the panel's settled column is that summary. What
 * `view` changes now is the order: Clarify leads with the questions, Confirm
 * leads with the sign-off (docs/slices/redesign-phase-2-clarify-confirm.md —
 * one screen, two modes, both routes and the six-step rail kept).
 *
 * Its reads and writes live here, so mounting is what gates them:
 * RequirementPage.test.tsx asserts that opening any other stage does not fetch
 * analysis rounds or answer suggestions.
 */
export function AnalysisView({
  id,
  view,
  workspace,
}: {
  id: string;
  view: "clarify" | "confirm";
  workspace: RequirementWorkspace;
}) {
  const { analysis, assignments, knowledgeReview, team, canManageContent, canConfirmAnalysis, refresh } = workspace;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const jobs = useRequirementJobs(id);
  const [confirmReanalysis, setConfirmReanalysis] = useState(false);
  const data = analysis.data ?? null;

  const rounds = useQuery({
    queryKey: queryKeys.analysisRounds(id),
    queryFn: () => api.listAnalysisRounds(id),
    enabled: Boolean(data),
    refetchOnMount: "always",
  });
  const suggestions = useQueries({
    queries: (data?.questions ?? []).map((question) => ({
      queryKey: queryKeys.answerSuggestions(id, question.id),
      queryFn: () => api.getAnswerSuggestions(id, question.id),
      refetchOnMount: "always" as const,
    })),
  });

  // Leaving marks this stage's reads stale without refetching them now.
  useEffect(() => () => {
    void Promise.all(
      [queryKeys.analysisRounds(id), queryKeys.scope("answer-suggestions", id)].map((queryKey) =>
        queryClient.invalidateQueries({ queryKey, refetchType: "none" }),
      ),
    );
  }, [id, queryClient]);

  const analyse = useMutation({
    meta: { action: "Starting the analysis" },
    mutationFn: (force: boolean) => jobs.startJob({
      operation: "analyse_requirement", force,
      context_token: workspace.requirement.data?.analysis_context_token ?? "",
    }),
  });
  const saveDraft = useMutation({
    meta: { action: "Saving your draft answer" },
    mutationFn: ({ question, answer }: { question: ClarificationQuestion; answer: string }) =>
      api.saveClarificationDraft(id, question.id, answer, question.version),
    onSuccess: async () => refresh("question"),
  });
  const resolveQuestions = useMutation({
    meta: { action: "Resolving the questions" },
    mutationFn: (answers: ClarificationResolutionInput[]) =>
      jobs.startJob({ operation: "resolve_clarification_questions", answers }),
  });
  const classifyQuestion = useMutation({
    meta: { action: "Reclassifying the question" },
    mutationFn: ({ question, severity, isBlocker }: { question: ClarificationQuestion; severity: ClarificationSeverity; isBlocker: boolean }) =>
      api.classifyClarificationQuestion(id, question.id, {
        severity, is_blocker: isBlocker, expected_version: question.version,
      }),
    onSuccess: async () => refresh("question"),
  });
  const assignQuestion = useMutation({
    meta: { action: "Assigning the question" },
    mutationFn: ({ question, actorId }: { question: ClarificationQuestion; actorId: string | null }) =>
      api.assignClarificationQuestion(id, question.id, actorId, question.version),
    onSuccess: async () => refresh("question"),
  });
  const askQuestion = useMutation({
    meta: { action: "Adding the question" },
    mutationFn: ({ subject, assigneeId }: { subject: string; assigneeId: string | null }) =>
      api.askClarificationQuestion(id, {
        subject, rationale: null, severity: "medium", is_blocker: false,
        assignee_id: assigneeId, expected_analysis_version: data?.version ?? 0,
      }),
    onSuccess: async () => Promise.all([refresh("question"), queryClient.invalidateQueries({ queryKey: queryKeys.aiJobs(id) })]),
  });
  const clarify = useMutation({
    meta: { action: "Refining the analysis" },
    mutationFn: (answers: ClarificationAnswerInput[]) => jobs.startJob({
      operation: "clarify_requirement_analysis", answers, expected_analysis_version: data?.version ?? 0,
    }),
  });
  const confirmAnalysis = useMutation({
    meta: { action: "Confirming the analysis" },
    mutationFn: () => api.confirmAnalysis(id, data?.version ?? 0),
    onSuccess: async () => {
      await refresh("analysis");
      void navigate(`/requirements/${id}/breakdown/epic`);
    },
  });
  const suggestAnswers = useMutation({
    meta: { action: "Finding answer suggestions" },
    mutationFn: (question: ClarificationQuestion) => jobs.startJob({
      operation: "suggest_clarification_answers", question_id: question.id, expected_version: question.version,
    }),
  });
  const decideIntent = useMutation({
    meta: { action: "Recording the intent decision" },
    mutationFn: ({ proposal, decision, replacement, successMeasures, rationale }: { proposal: IntentProposal; decision: IntentProposalStatus; replacement?: string; successMeasures?: string[]; rationale?: string }) =>
      api.decideIntentProposal(id, proposal.id, {
        decision, replacement_statement: replacement, success_measures: successMeasures,
        rationale,
        expected_version: proposal.version,
      }),
    onSuccess: async () => Promise.all([refresh("analysis"), queryClient.invalidateQueries({ queryKey: queryKeys.aiJobs(id) })]),
  });

  const running = new Set(jobs.active.map((job) => job.operation));
  const analysing = analyse.isPending || running.has("analyse_requirement");
  const questionBusy = saveDraft.isPending || resolveQuestions.isPending || classifyQuestion.isPending ||
    assignQuestion.isPending || askQuestion.isPending ||
    jobs.active.some(
      (job) => !["screen_requirement_knowledge", "suggest_clarification_answers", "screen_prior_art"].includes(job.operation),
    );
  const questionError = saveDraft.error ?? resolveQuestions.error ?? classifyQuestion.error ??
    assignQuestion.error ?? askQuestion.error;
  const suggestionsByQuestion = Object.fromEntries(
    (data?.questions ?? []).map((question, index) => [question.id, suggestions[index]?.data ?? null]),
  );
  const requestAnalysis = () => (data ? setConfirmReanalysis(true) : analyse.mutate(false));
  // The server refuses to analyse an incomplete Requirement; say what it needs before a click.
  const eligibility = workspace.requirement.data?.analysis_eligibility;
  const ineligibleReason = eligibility && !eligibility.eligible
    ? `Still needed: ${missingLabel(eligibility.missing_fields)}.`
    : undefined;

  return (
    <>
      {/* No panel heading, and no eyebrow.
       *
       * docs/ux-plan.md §3.4 counted five labels above the first question on
       * this route: the header context line, the "Requirement workspace"
       * eyebrow, a "Clarification Required" h1, this panel's
       * "Analyse / Clarify / Confirm" eyebrow, and a "Structured understanding"
       * h2. The shell fixed its three — the h1 is the requirement's own title
       * now — and these were the remaining two. design-system.md §14 lists "a
       * fifth title on a stage route" as an anti-pattern by name, and the
       * eyebrow was worse than redundant: it named three stages at once while
       * the rail said which one you were actually on.
       *
       * The panel's own two column headings carry the structure from here. */}
      <section aria-label="Analysis" className="grid gap-4">
        {/* "Start a new analysis", not "Re-analyse".
         *
         * This control discards the current round and every answer typed
         * against it. The panel's send button is called "Send N answers and
         * re-analyse". Two controls a few hundred pixels apart both read
         * "re-analyse", one preserves the work and one destroys it, and the
         * person most likely to reach for the wrong one is the person who has
         * just finished typing and is looking for the one that sends. The name
         * now says which act this is. */}
        {data && (
          <div className="flex justify-end">
            <Button
              blockedReason={ineligibleReason}
              disabled={!canManageContent || analysing}
              icon={<RefreshCw size={16} aria-hidden="true" />}
              loading={analysing}
              loadingLabel="Analysing…"
              onClick={requestAnalysis}
            >
              Start a new analysis
            </Button>
          </div>
        )}

        {analysis.isPending ? <Skeleton label="Loading the analysis" /> : data ? (
          <>
            {/* The confirmation summary used to render here, on /confirm only:
             *  a second copy of the facts, rules and constraints that the panel
             *  already shows. §3.5 — "one screen, a different screen, then the
             *  same first screen again with a box added". The panel's settled
             *  column is that summary, on both routes. */}
            <AnalysisPanel
              view={view}
              analysis={data}
              rounds={rounds.data ?? []}
              team={team}
              busy={!canManageContent || clarify.isPending || confirmAnalysis.isPending || decideIntent.isPending || questionBusy}
              error={questionError ? errorMessage(questionError)
                : decideIntent.error ? errorMessage(decideIntent.error)
                : clarify.error ? errorMessage(clarify.error)
                : confirmAnalysis.error ? errorMessage(confirmAnalysis.error) : null}
              onClarify={(answers) => clarify.mutate(answers)}
              onSaveDraft={(question, answer) => saveDraft.mutate({ question, answer })}
              onResolveBatch={(answers) => resolveQuestions.mutate(answers)}
              suggestions={suggestionsByQuestion}
              suggestionsBusy={suggestAnswers.isPending || running.has("suggest_clarification_answers")}
              onSuggestAnswers={(question) => suggestAnswers.mutate(question)}
              onClassify={canManageContent ? (question, severity, isBlocker) => classifyQuestion.mutate({ question, severity, isBlocker }) : undefined}
              onAssign={canManageContent ? (question, actorId) => assignQuestion.mutate({ question, actorId }) : undefined}
              onAsk={canManageContent ? (subject, assigneeId) => askQuestion.mutate({ subject, assigneeId }) : undefined}
              onConfirm={() => confirmAnalysis.mutate()}
              canConfirm={canConfirmAnalysis && Boolean(knowledgeReview.data?.ready)}
              canDecideIntent={canConfirmAnalysis}
              onDecideIntent={(proposal, decision, replacement, successMeasures, rationale) =>
                decideIntent.mutate({ proposal, decision, replacement, successMeasures, rationale })}
              confirmPermissionReason={
                canConfirmAnalysis && !knowledgeReview.data?.ready
                  ? "Complete the current Requirement knowledge screen and resolve every finding before confirmation."
                  : assignments.data?.owner
                    ? `Only ${assignments.data.owner.actor.display_name}, the Requirement Owner, can confirm this analysis.`
                    : "Claim this legacy Requirement before confirming its analysis."
              }
            />
          </>
        ) : (
          <EmptyState title="No analysis yet"
            message="Analyse the current source to separate evidence from uncertainty."
            action={
              <Button
                blockedReason={ineligibleReason}
                disabled={!canManageContent || analysing}
                loading={analysing}
                loadingLabel="Analysing…"
                onClick={requestAnalysis}
                variant="primary"
              >
                Analyse this requirement
              </Button>
            } />
        )}
        {analyse.error && <ErrorNotice message={errorMessage(analyse.error)} />}
        {/* After the analysis, not before it. Above, it put a lineage tool
            between a person and the first question on every visit; the gate
            points here by name when changed reference evidence is what blocks
            confirmation. */}
        {data ? <SourceImpactPanel key={id} requirementId={id} canDecide={canConfirmAnalysis} /> : null}
      </section>

      {/* The dialog leads with the loss.
       *
       * It used to open on "A new analysis will replace the current candidate"
       * and then discuss backlog items and revision history — true, and not the
       * thing about to be destroyed. A new round issues new question IDs, so
       * every answer typed against the current questions is orphaned, and the
       * unsaved-changes guard never fires because this is not a navigation.
       * PRODUCT.md Principle 4 is "Nothing human is silently lost"; a dialog
       * that does not name the loss is still silent about it.
       *
       * The warning is unconditional rather than counting the pending answers,
       * because that count lives in AnalysisPanel's own state and lifting it up
       * here would be the state-logic change CLAUDE.md puts out of bounds. It
       * is phrased so it reads correctly whether or not anything is pending. */}
      {confirmReanalysis && (
        <ConfirmDialog
          title="Start a new analysis?"
          message="Anything typed into an answer box and not saved as a draft or sent is discarded, because the new round replaces the questions it belongs to. Saved drafts and answers you have already sent stay on the record, and generated backlog items remain in revision history."
          confirmLabel="Discard and start a new analysis"
          onCancel={() => setConfirmReanalysis(false)}
          onConfirm={() => { setConfirmReanalysis(false); analyse.mutate(true); }}
        />
      )}
    </>
  );
}
