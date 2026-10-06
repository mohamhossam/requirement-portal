import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { vi } from "vitest";

import { analysisFixture } from "../../test/fixtures";
import type { ClarificationQuestion, IntentProposal, RequirementAnalysis } from "../../api/client";
import { AnalysisPanel } from "./AnalysisPanel";

const questionFixture: ClarificationQuestion = {
  id: "question-1",
  analysis_id: "analysis-1",
  kind: "open_question",
  subject: "Who owns fallout?",
  rationale: "Ownership is not stated.",
  severity: "medium",
  is_blocker: true,
  source: "ai",
  status: "open",
  version: 1,
  asked_by: null,
  asked_at: null,
  assignee: null,
  assignment_history: [],
  draft_answer: null,
  draft_updated_by: null,
  draft_updated_at: null,
  answer: null,
  answered_by: null,
  answered_at: null,
  classification_changed_by: null,
  classification_changed_at: null,
  replaces_question_id: null,
};

const pendingProposal: IntentProposal = {
  reference_evidence: [],
  reference_conflict: false,
  id: "intent-1",
  kind: "desired_outcome",
  statement: "SMB customers can complete the requested journey.",
  rationale: "This is the observable value implied by the need.",
  success_measures: ["The journey can be completed."],
  status: "pending",
  version: 1,
  effective_statement: null,
  effective_success_measures: [],
  decisions: [],
  evidence_references: [],
};

it("requires rationale for reference decisions and blocks stale acceptance", async () => {
  const user = userEvent.setup();
  const onDecide = vi.fn();
  const reference: IntentProposal = { ...pendingProposal, kind: "business_rule", success_measures: [],
    reference_evidence: [{ document_id: "policy", title: "Coverage policy", version_id: "v1", version_number: 1,
      revision_id: "r1", publication_id: "pub1", approval_fingerprint: "a".repeat(64), block_id: "b1",
      location: "Page 7", excerpt: "Coverage required.", start_offset: 0, end_offset: 18, lineage_hash: "b".repeat(64) }],
  };
  const analysis = { ...analysisFixture, business_intent: { ...analysisFixture.business_intent, proposals: [reference] } };
  const props = { analysis, busy: false, error: null, onClarify: vi.fn(), onConfirm: vi.fn(), canDecideIntent: true, onDecideIntent: onDecide };
  const { rerender } = render(<AnalysisPanel {...props} />);
  expect(screen.getByRole("button", { name: "Accept as written" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  await user.type(screen.getByLabelText("Applicability rationale"), "Applies to this offer");
  await user.click(screen.getByRole("button", { name: "Accept as written" }));
  expect(onDecide).toHaveBeenCalledWith(reference, "accepted", undefined, undefined, "Applies to this offer");
  rerender(<AnalysisPanel {...props} analysis={{ ...analysis, stale_reference_proposal_ids: [reference.id] }} />);
  expect(screen.getByRole("heading", { name: "Reference applicability — reconciliation required" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Accept as written" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();
});

it("flags a cited document past its review date beside the citation, without blocking the decision", () => {
  const reference: IntentProposal = { ...pendingProposal, kind: "business_rule", success_measures: [],
    reference_evidence: [{ document_id: "policy", title: "Coverage policy", version_id: "v1", version_number: 1,
      revision_id: "r1", publication_id: "pub1", approval_fingerprint: "a".repeat(64), block_id: "b1",
      location: "Page 7", excerpt: "Coverage required.", start_offset: 0, end_offset: 18, lineage_hash: "b".repeat(64) }],
  };
  const analysis = {
    ...analysisFixture,
    business_intent: { ...analysisFixture.business_intent, proposals: [reference] },
    overdue_reference_reviews: { policy: "2020-01-02" },
  };
  render(<AnalysisPanel analysis={analysis} busy={false} error={null} onClarify={vi.fn()} onConfirm={vi.fn()} canDecideIntent onDecideIntent={vi.fn()} />);
  expect(screen.getByText(/Review overdue since .*2020/)).toBeVisible();
  expect(screen.getByLabelText("Applicability rationale")).toBeEnabled();
});

it("shows human support with answer attribution and no invented document link", () => {
  const statement = "DEL serves single-user lines; PABX serves multi-user plans.";
  const { container } = render(<AnalysisPanel analysis={{
    ...analysisFixture,
    known_facts: [{ statement, evidence_references: [] }],
    clarification_evidence: [{ evidence_key: `known_fact:${statement.toLowerCase()}`, clarification_numbers: [1] }],
    clarifications: [{ kind: "open_question", subject: "How do DEL and PABX differ?", answer: statement,
      question_id: "resolved-question", answered_by: { id: "owner-1", display_name: "Olivia Owner", email: null },
      answered_at: "2026-09-18T10:00:00Z", source_suggestion_id: null }],
  }} busy={false} error={null} onClarify={vi.fn()} onConfirm={vi.fn()} />);
  expect(screen.getByRole("button", { name: `Where this came from: ${statement}` })).toHaveTextContent("1 human answer");
  expect(screen.getAllByText(/How do DEL and PABX differ\?/).length).toBeGreaterThan(0);
  expect(container.querySelector('a[href^="/documents/"]')).toBeNull();
});

type DecidedProposalStatus = Exclude<IntentProposal["status"], "pending">;

function decidedProposal(status: DecidedProposalStatus): IntentProposal {
  const finalStatement =
    status === "rejected"
      ? null
      : status === "edited"
        ? "SMB customers can finish ordering online."
        : pendingProposal.statement;
  const successMeasures = status === "rejected" ? [] : pendingProposal.success_measures;
  return {
    ...pendingProposal,
    status,
    version: 2,
    effective_statement: finalStatement,
    effective_success_measures: successMeasures,
    decisions: [
      {
        status,
        final_statement: finalStatement,
        success_measures: successMeasures,
        decided_by: { id: "owner-1", display_name: "Olivia Owner", email: null },
        decided_at: "2026-09-05T12:00:00Z",
        version: 2,
      },
    ],
  };
}

function analysisWithProposal(
  proposal: IntentProposal,
  humanConfirmed = false,
): RequirementAnalysis {
  return {
    ...analysisFixture,
    assumptions: [],
    open_questions: [],
    ambiguities: [],
    potential_dependencies: [],
    human_confirmed: humanConfirmed,
    confirmed_at: humanConfirmed ? "2026-09-05T12:05:00Z" : null,
    confirmed_by: humanConfirmed
      ? { id: "owner-1", display_name: "Olivia Owner", email: null }
      : null,
    business_intent: {
      desired_outcome:
        proposal.status === "pending" || proposal.status === "rejected"
          ? null
          : {
              statement: proposal.effective_statement ?? proposal.statement,
              origin: "proposal",
              proposal_id: proposal.id,
            },
      accepted_business_rules: [],
      accepted_constraints: [],
      proposals: [proposal],
    },
  };
}

/**
 * Open a question's row.
 *
 * Each question is a collapsed `<details>` now, so everything below the summary
 * — the answer field, the suggestions, the classification controls — is hidden
 * from the accessibility tree until it is opened. `getByRole` and `toBeVisible`
 * both honour that, which is the point.
 */
function openQuestion(subject: string | RegExp): void {
  const details = screen.getByText(subject).closest("details");
  if (!details) throw new Error(`no question row for ${String(subject)}`);
  details.open = true;
}

describe("AnalysisPanel", () => {
  it("separates what is settled from what is still open", () => {
    render(<AnalysisPanel analysis={analysisFixture} busy={false} error={null} onClarify={vi.fn()} onConfirm={vi.fn()} />);

    expect(screen.getByText("Drafted by the analysis")).toBeInTheDocument();

    /* Two named regions, one per column. The settled one carries the extracted
       material; the open one carries everything still owed. */
    const settled = screen.getByRole("region", { name: "What is settled" });
    const open = screen.getByRole("region", { name: "What is still open" });

    expect(
      within(within(settled).getByRole("region", { name: "Known facts" })).getByText(
        "Business broadband is in scope.",
      ),
    ).toBeInTheDocument();
    expect(
      within(within(settled).getByRole("region", { name: "Business rules" })).getByText(
        "Eligibility must be checked before ordering.",
      ),
    ).toBeInTheDocument();
    expect(
      within(within(settled).getByRole("region", { name: "Constraints" })).getByText(
        "Only XGPON coverage areas qualify.",
      ),
    ).toBeInTheDocument();

    /* This fixture predates stable question IDs, so the open column shows the
       legacy batch form, which still groups by kind. */
    expect(
      within(within(open).getByRole("region", { name: /Assumptions/ })).getByText(
        "Existing coverage data is current.",
      ),
    ).toBeInTheDocument();
    expect(
      within(within(open).getByRole("region", { name: /Open questions/ })).getByText(
        "Who owns fallout?",
      ),
    ).toBeInTheDocument();
    expect(
      within(within(open).getByRole("region", { name: /Ambiguities/ })).getByText(
        "Available in channel",
      ),
    ).toBeInTheDocument();
    expect(
      within(within(open).getByRole("region", { name: /Potential dependencies/ })).getByText(
        "GIS coverage service",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Confirmed$/)).not.toBeInTheDocument();
  });

  it("separates questions that block confirmation from the rest", () => {
    const nonBlocking = {
      ...questionFixture,
      id: "question-2",
      kind: "assumption" as const,
      subject: "Coverage data is current",
      is_blocker: false,
    };
    render(
      <AnalysisPanel
        analysis={{
          ...analysisFixture,
          analysis_id: "analysis-1",
          round_number: 1,
          questions: [questionFixture, nonBlocking],
        }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    /* Grouped by what stands in the way, not by the analysis's own taxonomy:
       the kind is a badge on the card, because a reviewer triaging a batch
       needs to know what blocks them before they need to know its category. */
    const blocking = screen.getByRole("region", { name: "Must be answered first" });
    const rest = screen.getByRole("region", { name: "Worth answering, not blocking" });

    expect(within(blocking).getByText("Who owns fallout?")).toBeInTheDocument();
    expect(within(blocking).getByText(/Open question/)).toBeInTheDocument();
    expect(within(rest).getByText("Coverage data is current")).toBeInTheDocument();
    expect(within(rest).getByText(/Assumption/)).toBeInTheDocument();
  });

  it("keeps a question's working material closed until its row is opened", async () => {
    const user = userEvent.setup();
    render(
      <AnalysisPanel
        analysis={{ ...analysisFixture, analysis_id: "analysis-1", questions: [questionFixture] }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    /* The row carries what triage compares — the question, its kind, its
       severity and its owner — and nothing else. */
    expect(screen.getByText("Who owns fallout?")).toBeVisible();
    expect(screen.getByText(/Open question/)).toBeVisible();
    /* Rendered but not visible: a closed <details> keeps its content in the
       DOM and hides it, which is what keeps the list scannable. */
    expect(screen.getByLabelText("Your answer")).not.toBeVisible();

    const row = screen.getByText("Who owns fallout?").closest("details")!;
    await user.click(row.querySelector("summary")!);

    expect(row.open).toBe(true);
    expect(screen.getByLabelText("Your answer")).toBeVisible();
  });

  it("lets two questions be open at once", async () => {
    const user = userEvent.setup();
    const second = { ...questionFixture, id: "question-2", subject: "Which channel owns support?" };
    render(
      <AnalysisPanel
        analysis={{
          ...analysisFixture,
          analysis_id: "analysis-1",
          questions: [questionFixture, second],
        }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    /* Rows are deliberately NOT an exclusive accordion. As one, opening the
       second row threw the row just clicked 656-689px above the viewport,
       because the sibling collapsing above it took its own height out of the
       flow. Comparing two questions is also half of triage. */
    const first = screen.getByText("Who owns fallout?").closest("details")!;
    const other = screen.getByText("Which channel owns support?").closest("details")!;

    await user.click(first.querySelector("summary")!);
    await user.click(other.querySelector("summary")!);

    expect(first.open).toBe(true);
    expect(other.open).toBe(true);
  });

  it("submits only answered uncertainties for re-analysis", async () => {
    const user = userEvent.setup();
    const onClarify = vi.fn();
    render(<AnalysisPanel analysis={analysisFixture} busy={false} error={null} onClarify={onClarify} onConfirm={vi.fn()} />);

    const answerInputs = screen.getAllByLabelText("Your answer");
    await user.type(answerInputs[1]!, "Customer Operations owns fallout.");
    await user.click(screen.getByRole("button", { name: "Send these answers and re-analyse" }));

    expect(onClarify).toHaveBeenCalledWith([
      {
        kind: "open_question",
        subject: "Who owns fallout?",
        answer: "Customer Operations owns fallout.",
      },
    ]);
  });

  it("shows saved human clarifications separately from AI extraction", () => {
    render(
      <AnalysisPanel
        analysis={{
          ...analysisFixture,
          clarifications: [
            {
              kind: "open_question",
              subject: "Who owns fallout?",
              answer: "Customer Operations.",
            },
          ],
        }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    const history = screen.getByRole("heading", { name: "Answers already given (1)" }).closest("section");
    expect(history).not.toBeNull();
    expect(within(history!).getByText("Customer Operations.")).toBeInTheDocument();
  });

  it("offers explicit confirmation only after the answer loop is resolved", async () => {
    const onConfirm = vi.fn();
    render(
      <AnalysisPanel
        analysis={{
          ...analysisFixture,
          assumptions: [],
          open_questions: [],
          ambiguities: [],
          potential_dependencies: [],
        }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={onConfirm}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Confirm this analysis" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("requires the owner to resolve each AI intent proposal", async () => {
    const user = userEvent.setup();
    const onDecideIntent = vi.fn();
    render(
      <AnalysisPanel
        analysis={analysisWithProposal(pendingProposal)}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        canDecideIntent
        onDecideIntent={onDecideIntent}
      />,
    );

    expect(screen.getByText("No agreed outcome yet.", { exact: false })).toBeVisible();
    /* Gated, not disabled: §11 keeps the action visible and says why, which is
       what carries the reason into the control's own aria-describedby. */
    const confirm = screen.getByRole("button", { name: "Confirm this analysis" });
    expect(confirm).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByText(/needs a decision, and this requirement needs an agreed outcome/),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Save my wording" })).toBeDisabled();
    await user.clear(screen.getByLabelText("Your wording"));
    await user.type(screen.getByLabelText("Your wording"), "SMB customers can finish ordering online.");
    await user.click(screen.getByRole("button", { name: "Save my wording" }));
    expect(onDecideIntent).toHaveBeenCalledWith(
      pendingProposal,
      "edited",
      "SMB customers can finish ordering online.",
      ["The journey can be completed."],
    );
  });

  it.each(["accepted", "edited", "rejected"] as const)(
    "shows a %s proposal as settled until revision is requested",
    (status) => {
      render(
        <AnalysisPanel
          analysis={analysisWithProposal(decidedProposal(status))}
          busy={false}
          error={null}
          onClarify={vi.fn()}
          onConfirm={vi.fn()}
          canDecideIntent
          onDecideIntent={vi.fn()}
        />,
      );

      expect(screen.getByRole("button", { name: "Change this decision" })).toBeVisible();
      expect(screen.queryByRole("button", { name: "Accept as written" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Save my wording" })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
      expect(screen.queryByLabelText("Your wording")).not.toBeInTheDocument();
    },
  );

  it("requires an explicit, changed revision and closes it after a version refresh", async () => {
    const user = userEvent.setup();
    const accepted = decidedProposal("accepted");
    const onDecideIntent = vi.fn();
    const view = render(
      <AnalysisPanel
        analysis={analysisWithProposal(accepted)}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        canDecideIntent
        onDecideIntent={onDecideIntent}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Change this decision" }));
    expect(screen.getByRole("button", { name: "Accept as written" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Save my wording" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject" })).toBeEnabled();

    const wording = screen.getByLabelText("Your wording");
    await user.clear(wording);
    await user.type(wording, "Eligible SMB customers can order online.");
    await user.click(screen.getByRole("button", { name: "Save my wording" }));
    expect(onDecideIntent).toHaveBeenCalledWith(
      accepted,
      "edited",
      "Eligible SMB customers can order online.",
      ["The journey can be completed."],
    );
    expect(wording).toHaveValue("Eligible SMB customers can order online.");

    view.rerender(
      <AnalysisPanel
        analysis={analysisWithProposal(accepted)}
        busy={false}
        error="The decision could not be saved."
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        canDecideIntent
        onDecideIntent={onDecideIntent}
      />,
    );
    expect(screen.getByLabelText("Your wording")).toHaveValue(
      "Eligible SMB customers can order online.",
    );

    const refreshed = {
      ...decidedProposal("edited"),
      version: 3,
      effective_statement: "Eligible SMB customers can order online.",
    };
    view.rerender(
      <AnalysisPanel
        analysis={analysisWithProposal(refreshed)}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        canDecideIntent
        onDecideIntent={onDecideIntent}
      />,
    );

    expect(screen.getByRole("button", { name: "Change this decision" })).toBeVisible();
    expect(screen.queryByLabelText("Your wording")).not.toBeInTheDocument();
    expect(screen.getAllByText("Eligible SMB customers can order online.")).toHaveLength(2);
  });

  it("explains why a non-owner cannot change a settled decision", () => {
    render(
      <AnalysisPanel
        analysis={analysisWithProposal(decidedProposal("accepted"))}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        canDecideIntent={false}
        confirmPermissionReason="Only the Requirement Owner can decide business intent."
        onDecideIntent={vi.fn()}
      />,
    );

    /* Gated, not disabled: the control keeps its place in the tab order and
       carries the reason through aria-describedby (design-system.md §11). */
    expect(screen.getByRole("button", { name: "Change this decision" })).toHaveAttribute(
      "aria-disabled",
      "true",
    );
    expect(
      screen.getByText("Only the Requirement Owner can decide business intent."),
    ).toBeVisible();
  });

  it("cancels a revision and restores the persisted decision", async () => {
    const user = userEvent.setup();
    render(
      <AnalysisPanel
        analysis={analysisWithProposal(decidedProposal("edited"))}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        canDecideIntent
        onDecideIntent={vi.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Change this decision" }));
    await user.clear(screen.getByLabelText("Your wording"));
    await user.type(screen.getByLabelText("Your wording"), "Discard this wording.");
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("button", { name: "Change this decision" }));

    expect(screen.getByLabelText("Your wording")).toHaveValue(
      "SMB customers can finish ordering online.",
    );
  });

  it("does not allow proposal revision after final analysis confirmation", () => {
    render(
      <AnalysisPanel
        analysis={analysisWithProposal(decidedProposal("accepted"), true)}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        canDecideIntent
        onDecideIntent={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Change this decision" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Your wording")).not.toBeInTheDocument();
  });

  it("supports assignment, classification, draft saving, and batch resolution", async () => {
    const user = userEvent.setup();
    const onSaveDraft = vi.fn();
    const onResolveBatch = vi.fn();
    const onClassify = vi.fn();
    const onAssign = vi.fn();
    render(
      <AnalysisPanel
        analysis={{ ...analysisFixture, analysis_id: "analysis-1", round_number: 1, questions: [questionFixture] }}
        team={[{ id: "reviewer", display_name: "Ravi Reviewer", email: "ravi@example.test" }]}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        onSaveDraft={onSaveDraft}
        onResolveBatch={onResolveBatch}
        onClassify={onClassify}
        onAssign={onAssign}
      />,
    );

    await user.selectOptions(screen.getByLabelText("Who answers: Who owns fallout?"), "reviewer");
    await user.selectOptions(screen.getByLabelText("How much it matters"), "high");
    await user.click(screen.getByLabelText("Blocks confirmation"));
    await user.type(screen.getByLabelText("Your answer"), "Customer Operations");
    await user.click(screen.getByRole("button", { name: "Save as a draft" }));
    await user.click(screen.getByRole("button", { name: "Send 1 answer and re-analyse" }));

    expect(onAssign).toHaveBeenCalledWith(questionFixture, "reviewer");
    expect(onClassify).toHaveBeenCalledWith(questionFixture, "high", true);
    expect(onClassify).toHaveBeenCalledWith(questionFixture, "medium", false);
    expect(onSaveDraft).toHaveBeenCalledWith(questionFixture, "Customer Operations");
    expect(onResolveBatch).toHaveBeenCalledWith([
      {
        question_id: questionFixture.id,
        answer: "Customer Operations",
        expected_version: questionFixture.version,
      },
    ]);
    expect(screen.queryByRole("button", { name: "Send and re-analyse" })).not.toBeInTheDocument();
  });

  it("submits typed answers and saved drafts through one batch action", async () => {
    const user = userEvent.setup();
    const onResolveBatch = vi.fn();
    const drafted = {
      ...questionFixture,
      id: "question-draft",
      subject: "Which channel owns support?",
      version: 2,
      status: "in_progress" as const,
      draft_answer: "Customer Care",
    };
    render(
      <AnalysisPanel
        analysis={{
          ...analysisFixture,
          analysis_id: "analysis-1",
          round_number: 1,
          questions: [questionFixture, drafted],
        }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        onResolveBatch={onResolveBatch}
      />,
    );

    await user.type(screen.getAllByLabelText("Your answer")[0]!, "Operations");
    expect(screen.getByText("2 answers ready to send")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: "Send 2 answers and re-analyse" }),
    );

    expect(onResolveBatch).toHaveBeenCalledOnce();
    expect(onResolveBatch).toHaveBeenCalledWith([
      { question_id: "question-1", answer: "Operations", expected_version: 1 },
      { question_id: "question-draft", answer: "Customer Care", expected_version: 2 },
    ]);
  });

  it("fills an editable draft from a grounded suggestion and records its origin", async () => {
    const user = userEvent.setup();
    const onSuggestAnswers = vi.fn();
    const onResolveBatch = vi.fn();
    render(
      <AnalysisPanel
        analysis={{ ...analysisFixture, analysis_id: "analysis-1", questions: [questionFixture] }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        onResolveBatch={onResolveBatch}
        onSuggestAnswers={onSuggestAnswers}
        suggestions={{
          [questionFixture.id]: {
            id: "suggestions-1",
            question_id: questionFixture.id,
            overdue_reference_reviews: {},
            suggestions: [{
              id: "suggestion-1",
              source: "trusted_knowledge",
              reference_evidence: [],
              answer: "Customer Operations owns fallout.",
              rationale: "A confirmed requirement assigns that role.",
              evidence: [{
                chunk_id: "chunk-1",
                requirement_id: "req-evidence",
                field: "clarification:open_question",
                excerpt: "Customer Operations owns fallout.",
                evidence_path: "/requirements/req-evidence/clarify",
                fingerprint: "evidence-fingerprint",
              }],
            }],
            provenance: {
              model: "grounded-test",
              prompt_version: "suggestions-v1",
              generated_at: "2026-09-05T12:00:00Z",
            },
          },
        }}
      />,
    );

    openQuestion("Who owns fallout?");
    expect(screen.getByText("Trusted knowledge")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Look again" }));
    expect(onSuggestAnswers).toHaveBeenCalledWith(questionFixture);
    await user.click(screen.getByRole("button", { name: /Customer Operations owns fallout/ }));
    const answer = screen.getByLabelText("Your answer");
    expect(answer).toHaveValue("Customer Operations owns fallout.");
    await user.type(answer, " Confirmed by the owner.");
    await user.click(screen.getByRole("button", { name: "Send 1 answer and re-analyse" }));

    expect(onResolveBatch).toHaveBeenCalledWith([{
      question_id: questionFixture.id,
      answer: "Customer Operations owns fallout. Confirmed by the owner.",
      expected_version: questionFixture.version,
      source_suggestion_id: "suggestion-1",
    }]);
  });

  it("shows automatic suggestion loading, empty, and unavailable states", () => {
    const { rerender } = render(
      <AnalysisPanel
        analysis={{ ...analysisFixture, analysis_id: "analysis-1", questions: [questionFixture] }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        suggestionsBusy
      />,
    );

    openQuestion("Who owns fallout?");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking this analysis and trusted knowledge",
    );
    expect(screen.getByRole("button", { name: "Looking…" })).toBeDisabled();

    rerender(
      <AnalysisPanel
        analysis={{ ...analysisFixture, analysis_id: "analysis-1", questions: [questionFixture] }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        suggestions={{
          [questionFixture.id]: {
            id: "suggestions-empty",
            question_id: questionFixture.id,
            overdue_reference_reviews: {},
            suggestions: [],
            provenance: {
              model: "grounded-test",
              prompt_version: "suggestions-v2",
              generated_at: "2026-09-07T12:00:00Z",
            },
          },
        }}
      />,
    );
    openQuestion("Who owns fallout?");
    expect(screen.getByText(/Nothing in the evidence answers this/)).toBeVisible();

    rerender(
      <AnalysisPanel
        analysis={{ ...analysisFixture, analysis_id: "analysis-1", questions: [questionFixture] }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    openQuestion("Who owns fallout?");
    expect(screen.getByText(/None yet\. Answer directly/)).toBeVisible();
  });

  it("shows reconciliation counts, replacement provenance, and archived drafts", async () => {
    const oldQuestion = {
      ...questionFixture,
      id: "question-old",
      status: "superseded" as const,
      draft_answer: "Unconfirmed Operations note",
    };
    const revisedQuestion = {
      ...questionFixture,
      id: "question-revised",
      subject: "Which team owns order fallout?",
      replaces_question_id: oldQuestion.id,
    };
    const questionChanges = [
      {
        action: "replaced" as const,
        question_id: oldQuestion.id,
        rationale: "The ownership gap needs more precise wording.",
        replacement_question_id: revisedQuestion.id,
      },
      {
        action: "retired" as const,
        question_id: "question-retired",
        rationale: "The confirmed answer resolved this gap.",
        replacement_question_id: null,
      },
    ];
    render(
      <AnalysisPanel
        analysis={{
          ...analysisFixture,
          analysis_id: "analysis-2",
          round_number: 2,
          questions: [revisedQuestion],
          question_changes: questionChanges,
        }}
        rounds={[{
          analysis: {
            ...analysisFixture,
            analysis_id: "analysis-2",
            round_number: 2,
            question_changes: questionChanges,
          },
          questions: [oldQuestion, revisedQuestion],
        }]}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    // Four labelled counts, neutral, with a way to the full history.
    const summary = screen.getByRole("status", { name: "Since the last round" });
    expect(summary).toHaveTextContent(/Kept\s*0\s*Retired\s*1\s*Revised\s*1\s*New\s*0/);
    expect(within(summary).getByRole("link", { name: "See every round" })).toHaveAttribute("href", "#round-history");
    expect(screen.getByText(/Revised last round/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Every earlier round (1)"));
    await userEvent.click(screen.getByText("Round 2"));
    expect(screen.getByText("The ownership gap needs more precise wording.")).toBeVisible();
    expect(screen.getByText("Draft kept: Unconfirmed Operations note")).toBeVisible();
  });

  it("shows immutable round provenance and lets team members ask someone", async () => {
    const onAsk = vi.fn();
    render(
      <AnalysisPanel
        analysis={{ ...analysisFixture, analysis_id: "analysis-2", round_number: 2, questions: [] }}
        rounds={[{
          analysis: {
            ...analysisFixture,
            analysis_id: "analysis-1",
            round_number: 1,
            source_requirement_version: 3,
            provenance: {
              model: "provider-model",
              prompt_version: "analysis-v2",
              generated_at: "2026-09-03T12:00:00Z",
            },
          },
          questions: [questionFixture],
        }]}
        team={[{ id: "reviewer", display_name: "Ravi Reviewer", email: null }]}
        busy={false}
        error="The question changed. Refresh and try again."
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
        onAsk={onAsk}
      />,
    );

    await userEvent.click(screen.getByText("Every earlier round (1)"));
    await userEvent.click(screen.getByText("Round 1"));
    expect(screen.getByText("provider-model · analysis-v2", { exact: false })).toBeVisible();
    expect(screen.getByText("The question changed. Refresh and try again.")).toBeVisible();
    await userEvent.type(screen.getByLabelText("What is missing?"), "Who validates launch? ");
    await userEvent.selectOptions(screen.getByLabelText("Ask"), "reviewer");
    await userEvent.click(screen.getByRole("button", { name: "Add this question" }));
    expect(onAsk).toHaveBeenCalledWith("Who validates launch?", "reviewer");
  });
  it("puts the questions before the decisions owed, and ends Clarify at the gate", () => {
    render(
      <AnalysisPanel
        analysis={{
          ...analysisFixture,
          analysis_id: "analysis-order",
          round_number: 1,
          questions: [questionFixture],
          business_intent: { ...analysisFixture.business_intent, proposals: [pendingProposal] },
        }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    const questions = screen.getByRole("region", { name: "Must be answered first" });
    const decisions = screen.getByRole("region", { name: "Decisions the Requirement Owner owes" });
    const gate = screen.getByRole("heading", { name: "Not ready to confirm" });
    // The first viewport's job is the questions: they precede the 400px
    // decision cards, and the gate comes last, where the work leads.
    expect(questions.compareDocumentPosition(decisions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(decisions.compareDocumentPosition(gate) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(gate.tagName).toBe("H3");
  });

  it("leads Confirm with the sign-off, as a section of its own", () => {
    render(
      <AnalysisPanel
        view="confirm"
        analysis={{ ...analysisFixture, analysis_id: "analysis-confirm", round_number: 1, questions: [questionFixture] }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    const gate = screen.getByRole("heading", { name: "Not ready to confirm" });
    const questions = screen.getByRole("region", { name: "Must be answered first" });
    expect(gate.compareDocumentPosition(questions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(gate.tagName).toBe("H2");
    // Rendered once, not in both places.
    expect(screen.getAllByRole("button", { name: /Confirm this analysis/ })).toHaveLength(1);
  });

  it("does not spend the accent on a confirm that is gated", () => {
    render(
      <AnalysisPanel
        analysis={{ ...analysisFixture, analysis_id: "analysis-gated", round_number: 1, questions: [questionFixture] }}
        busy={false}
        error={null}
        onClarify={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );
    const confirm = screen.getByRole("button", { name: /Confirm this analysis/ });
    expect(confirm).toHaveAttribute("aria-disabled", "true");
    expect(confirm.className).not.toMatch(/\bbg-accent\b/);
  });
});
