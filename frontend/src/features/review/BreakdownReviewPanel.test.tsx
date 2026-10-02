import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type BreakdownReview } from "../../api/client";
import { queryKeys } from "../../app/queryKeys";
import { renderWithJobs } from "../../test/renderWithClient";
import { BreakdownReviewPanel } from "./BreakdownReviewPanel";

const storySource = {
  kind: "story" as const,
  item_id: "story-1",
  label: "As a customer, I want to place an order, so that I can receive service.",
};

const fixture: BreakdownReview = {
  requirement_id: "req-1",
  version: 1,
  generated_at: "2026-09-03T08:00:00Z",
  ruleset_version: "breakdown-review-v1",
  evidence_fingerprint: "fingerprint-1",
  fresh: true,
  unresolved_blocker_count: 1,
  unresolved_warning_count: 1,
  dependencies: [
    {
      id: "dependency-1",
      description: "Eligibility must be confirmed before ordering.",
      source: { kind: "analysis", item_id: "req-1", label: "Requirement analysis" },
      evidence_kind: "potential",
    },
    {
      id: "dependency-2",
      description: "BCRM → RTF: order hand-off.",
      source: storySource,
      evidence_kind: "catalogued",
    },
  ],
  risks: [
    {
      id: "risk-1",
      severity: "blocking",
      description: "Story fails two INVEST criteria.",
      source: storySource,
    },
  ],
  flags: [
    {
      id: "flag-quality",
      category: "quality",
      severity: "blocking",
      title: "Story quality needs attention",
      detail: "Story fails two INVEST criteria.",
      source: storySource,
      resolution_policy: "decision",
      status: "open",
      resolution_decision_id: null,
    },
    {
      id: "flag-architecture",
      category: "architecture",
      severity: "warning",
      title: "Architecture mapping required",
      detail: "No architecture mapping has been recorded.",
      source: storySource,
      resolution_policy: "source_action",
      status: "open",
      resolution_decision_id: null,
    },
  ],
  recommendations: [
    {
      id: "recommendation-1",
      action: "Consider a paths split",
      rationale: "Deliver the primary path first.",
      source: storySource,
    },
  ],
  quality_assessments: [
    {
      story_id: "story-1",
      status: "split_recommended",
      failure_count: 2,
      findings: [
        { criterion: "independent", passed: true, message: "Independent.", source: "semantic" },
        { criterion: "negotiable", passed: true, message: "Negotiable.", source: "semantic" },
        { criterion: "valuable", passed: true, message: "Valuable.", source: "semantic" },
        { criterion: "estimable", passed: false, message: "Unknown integration.", source: "semantic" },
        { criterion: "small", passed: false, message: "Multiple paths.", source: "semantic" },
        { criterion: "testable", passed: true, message: "Testable.", source: "deterministic" },
      ],
      recommendations: [{ pattern: "paths", reason: "Deliver the primary path first." }],
      provenance: {
        generated_at: "2026-09-03T08:00:00Z",
        model: "fake",
        prompt_version: "quality-v1",
      },
    },
  ],
  decisions: [],
  status: "generated",
  submitted_fingerprint: null,
  approval_history: [],
  comments: [],
};

function renderPanel(review: BreakdownReview = fixture) {
  vi.spyOn(api, "getBreakdownReview").mockResolvedValue(review);
  vi.spyOn(api, "getApprovalWorkflow").mockResolvedValue(null);
  vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
  return renderWithJobs(
    <MemoryRouter>
      <BreakdownReviewPanel requirementId="req-1" />
    </MemoryRouter>,
  );
}

describe("BreakdownReviewPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows concern counts, evidence distinctions and recommendations", async () => {
    renderPanel();

    expect(await screen.findByRole("heading", { name: "Concerns to resolve" })).toBeVisible();
    expect(screen.getByText("Concerns blocking approval", { selector: "dt" }).nextElementSibling).toHaveTextContent("1");
    expect(screen.getByText("Inferred")).toBeVisible();
    expect(screen.getByText("In the catalogue")).toBeVisible();
    expect(screen.getByText("Story quality needs attention")).toBeVisible();
    expect(screen.getByText("Consider a paths split")).toBeVisible();
    expect(screen.getByText("Source action required")).toBeVisible();
    // The strip links to the sign-off it cannot summarise.
    expect(screen.getByRole("link", { name: "Sign-off status" })).toHaveAttribute("href", "#approval-workflow-title");
  });

  it("moves focus into a concern's form and back to its button on cancel (WCAG 2.4.3)", async () => {
    const user = userEvent.setup();
    renderPanel();
    const flag = (await screen.findByText("Story quality needs attention")).closest("li")!;
    const trigger = within(flag).getByRole("button", { name: "Resolve with decision" });
    // Says which concern it acts on, since two can share a title.
    expect(trigger).toHaveAccessibleDescription(/Story fails two INVEST criteria/);

    await user.click(trigger);
    expect(within(flag).getByLabelText(/^Decision/)).toHaveFocus();

    await user.click(within(flag).getByRole("button", { name: "Cancel" }));
    expect(within(flag).getByRole("button", { name: "Resolve with decision" })).toHaveFocus();
  });

  it("shows a failed resolution inside the concern that caused it", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "resolveReviewFlag").mockRejectedValue(new Error("The review changed. Refresh and try again."));
    renderPanel();
    const flag = (await screen.findByText("Story quality needs attention")).closest("li")!;
    await user.click(within(flag).getByRole("button", { name: "Resolve with decision" }));
    await user.type(within(flag).getByLabelText(/^Decision/), "Accept");
    await user.type(within(flag).getByLabelText(/^Rationale/), "Scheduled.");
    await user.click(within(flag).getByRole("button", { name: "Confirm resolution" }));

    expect(await within(flag).findByText("The review changed. Refresh and try again.")).toBeVisible();
  });

  it("puts the evidence before the sign-off (ux-plan §3.6)", async () => {
    vi.spyOn(api, "getBreakdownReview").mockResolvedValue(fixture);
    vi.spyOn(api, "getApprovalWorkflow").mockResolvedValue({
      requirement_id: "req-1",
      review_version: 1,
      status: "generated",
      subject_fingerprint: "breakdown-fingerprint",
      submitted_fingerprint: null,
      completion: { epic_approved: 0, epic_total: 1, features_approved: 0, features_total: 1, stories_approved: 0, stories_total: 1 },
      artifacts: [],
      readiness_reasons: [],
      blocking_reasons: ["1 blocking review flag(s) remain open."],
      can_submit: false,
      can_approve_breakdown: false,
      can_comment: true,
      breakdown_approvals: [],
      comments: [],
    });
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    renderWithJobs(
      <MemoryRouter>
        <BreakdownReviewPanel requirementId="req-1" />
      </MemoryRouter>,
    );

    await screen.findByRole("heading", { name: "Sign off this backlog" });
    const order = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    expect(order).toEqual([
      "Where this review stands",
      "Concerns to resolve",
      "Evidence",
      "Decision log",
      "Sign off this backlog",
      "History and comments",
    ]);
    // A gated act is not the accent: nothing on this screen can be pressed yet.
    expect(screen.getByRole("button", { name: "Submit for review" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Submit for review" })).not.toHaveClass("bg-accent");
  });

  it("never shows a raw enum string (ux-plan §3.7)", async () => {
    renderPanel();
    await screen.findByRole("heading", { name: "Concerns to resolve" });

    for (const raw of ["all", "blocking", "warning", "resolved", "potential", "catalogued", "generated", "open"]) {
      expect(screen.queryByText(raw)).not.toBeInTheDocument();
    }
    expect(screen.getByText("Not yet submitted")).toBeVisible();
    expect(screen.getByRole("button", { name: /^All/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("filters flags without changing the summary counts", async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByText("Story quality needs attention");

    await user.click(screen.getByRole("button", { name: /^Worth resolving/ }));

    expect(screen.queryByText("Story quality needs attention")).not.toBeInTheDocument();
    expect(screen.getByText("Architecture mapping required")).toBeVisible();
    expect(screen.getByText("Concerns blocking approval", { selector: "dt" }).nextElementSibling).toHaveTextContent("1");
  });

  it("records an explicit flag resolution and disables mutations when stale", async () => {
    const user = userEvent.setup();
    const resolved: BreakdownReview = {
      ...fixture,
      unresolved_blocker_count: 0,
      flags: fixture.flags.map((flag) =>
        flag.id === "flag-quality"
          ? { ...flag, status: "resolved", resolution_decision_id: "decision-1" }
          : flag,
      ),
      decisions: [
        {
          id: "decision-1",
          decision: "Accept the bounded risk",
          rationale: "A follow-up is scheduled.",
          recorded_at: "2026-09-03T08:10:00Z",
          recorded_by: null,
          target_flag_id: "flag-quality",
        },
      ],
    };
    const resolve = vi.spyOn(api, "resolveReviewFlag").mockResolvedValue(resolved);
    const rendered = renderPanel();
    const flagTitle = await screen.findByText("Story quality needs attention");
    const flag = flagTitle.closest("li");
    expect(flag).not.toBeNull();

    await user.click(within(flag!).getByRole("button", { name: "Resolve with decision" }));
    await user.type(within(flag!).getByLabelText(/^Decision/), "Accept the bounded risk");
    await user.type(within(flag!).getByLabelText(/^Rationale/), "A follow-up is scheduled.");
    await user.click(within(flag!).getByRole("button", { name: "Confirm resolution" }));

    expect(resolve).toHaveBeenCalledWith("req-1", "flag-quality", {
      decision: "Accept the bounded risk",
      rationale: "A follow-up is scheduled.",
      expected_fingerprint: "fingerprint-1",
      expected_version: 1,
    });
    expect(await within(flag!).findByText("Resolved")).toBeVisible();

    rendered.queryClient.setQueryData(queryKeys.breakdownReview("req-1"), {
      ...resolved,
      fresh: false,
    });
    expect(await screen.findByText("This review is stale.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Record a decision" })).toBeDisabled();
  });
});
