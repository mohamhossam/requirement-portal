import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type ApprovalWorkflow } from "../../api/client";
import { renderWithJobs } from "../../test/renderWithClient";
import { ApprovalWorkflowPanel } from "./ApprovalWorkflowPanel";

const workflow: ApprovalWorkflow = {
  requirement_id: "req-1",
  review_version: 1,
  status: "generated",
  subject_fingerprint: "breakdown-fingerprint",
  submitted_fingerprint: null,
  completion: {
    epic_approved: 1,
    epic_total: 1,
    features_approved: 1,
    features_total: 1,
    stories_approved: 0,
    stories_total: 1,
  },
  artifacts: [
    {
      target: { kind: "story", item_id: "story-1" },
      parent_id: "feature-1",
      label: "As a customer, I want to order, so that I receive service.",
      status: "generated",
      fingerprint: "story-fingerprint",
      version: 1,
      current_approval: null,
      approval_history: [],
    },
  ],
  readiness_reasons: [],
  blocking_reasons: [],
  can_submit: true,
  can_approve_breakdown: false,
  can_comment: true,
  breakdown_approvals: [],
  comments: [],
};

function renderPanel(value: ApprovalWorkflow = workflow) {
  vi.spyOn(api, "getApprovalWorkflow").mockResolvedValue(value);
  vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
  return renderWithJobs(<ApprovalWorkflowPanel requirementId="req-1" flags={[]} />);
}

describe("ApprovalWorkflowPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows lifecycle completion and submits the exact current fingerprint", async () => {
    const user = userEvent.setup();
    const submit = vi
      .spyOn(api, "submitForReview")
      .mockResolvedValue({ ...workflow, status: "under_review", can_submit: false });
    renderPanel();

    expect(await screen.findByRole("heading", { name: "Sign off this backlog" })).toBeVisible();
    expect(screen.getByText("0 of 1")).toBeVisible();
    // The one action that can be taken carries the accent; the gated one does not.
    expect(screen.getByRole("button", { name: "Submit for review" })).toHaveClass("bg-accent");
    expect(screen.getByRole("button", { name: "Final approval" })).not.toHaveClass("bg-accent");
    expect(screen.getByRole("listitem", { current: "step" })).toHaveTextContent("Not yet submitted");
    await user.click(screen.getByRole("button", { name: "Submit for review" }));
    expect(screen.getByRole("dialog", { name: "Submit this backlog?" })).toBeVisible();
    // The dialog says what it covers, and its button names the act.
    expect(screen.getByText(/0 of 1 Stories, 1 of 1 Features and 1 of 1 Epic approved · 0 concerns still open/)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Submit backlog" }));

    expect(submit).toHaveBeenCalledWith("req-1", "breakdown-fingerprint", 1);
    expect(await screen.findByRole("listitem", { current: "step" })).toHaveTextContent("Under review");
    expect((await screen.findAllByText(/under review/i))[0]).toBeVisible();
  });

  it("explains disabled actions and preserves a failed comment draft", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "addReviewComment").mockRejectedValue(new Error("unavailable"));
    renderPanel({
      ...workflow,
      readiness_reasons: ["Every Story needs a current attributed approval."],
      can_submit: false,
    });

    expect(await screen.findByText("Every Story needs a current attributed approval.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Submit for review" })).toBeDisabled();
    const draft = screen.getByLabelText(/^Comment/);
    await user.type(draft, "Please verify the failure path.");
    await user.click(screen.getByRole("button", { name: "Add comment" }));

    expect(await screen.findByText("unavailable")).toBeVisible();
    expect(draft).toHaveValue("Please verify the failure path.");
  });

  it("puts each Story's readiness on its row and says when an approval no longer counts", async () => {
    const approval = {
      id: "approval-feature-1",
      decision: "approved" as const,
      rationale: null,
      recorded_at: "2026-09-26T09:00:00Z",
      recorded_by: { id: "owner", display_name: "Amina Owner", email: null },
      subject_fingerprint: "old",
      target: { kind: "feature" as const, item_id: "feature-1" },
    };
    vi.spyOn(api, "getApprovalWorkflow").mockResolvedValue({
      ...workflow,
      completion: { ...workflow.completion, features_approved: 0 },
      artifacts: [
        ...workflow.artifacts,
        {
          target: { kind: "feature", item_id: "feature-1" },
          parent_id: null,
          label: "Human-reviewed ordering",
          status: "approved",
          fingerprint: "feature-fingerprint",
          version: 2,
          current_approval: null,
          approval_history: [approval],
        },
      ],
    });
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    renderWithJobs(
      <MemoryRouter>
        <ApprovalWorkflowPanel
          requirementId="req-1"
          flags={[]}
          quality={[{
            story_id: "story-1",
            status: "split_recommended",
            failure_count: 2,
            findings: [],
            recommendations: [],
            provenance: { generated_at: "2026-09-26T09:00:00Z", model: "fake", prompt_version: "quality-v1" },
          }]}
        />
      </MemoryRouter>,
    );

    const row = (await screen.findByText("As a customer, I want to order, so that I receive service.")).closest("li")!;
    expect(within(row).getByText(/Split recommended · 2 of 0 checks failed/)).toBeVisible();
    expect(within(row).getByRole("button", { name: "Approve" })).toHaveAccessibleDescription(
      "As a customer, I want to order, so that I receive service.",
    );

    const history = screen.getByRole("list", { name: "Approvals" });
    expect(within(history).getByText("No longer current")).toBeVisible();
    expect(within(history).getByText("Human-reviewed ordering")).toBeVisible();
    expect(screen.getByRole("link", { name: /Approve the Epic and Features in Backlog/ })).toHaveAttribute(
      "href",
      "/requirements/req-1/breakdown",
    );
  });
});
