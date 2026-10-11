import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ClarificationQuestion, ProductImpact, RequirementAnalysis } from "../../api/client";
import { analysisFixture } from "../../test/fixtures";
import { AnalysisPanel } from "./AnalysisPanel";

const impact: ProductImpact = {
  release_id: "rel-2026-10",
  suggested_verdict: "change_existing_offering",
  verdict_validated: false,
  reason: "Business Fiber already covers static IPs; the requirement adds a quota.",
  assessed_at: "2026-10-10T10:00:00Z",
  offering_id: "offering:business-fiber",
  offering_name: "Business Fiber",
  proposal: "Add a static IP quota to Business Fiber.",
  new_values: [],
  draft: null,
  needs: [
    { concept_id: "cap:static-ip", label: "Static IP", path: "Connectivity › Addressing", covered: true, weak: false },
    { concept_id: "cap:quota", label: "Usage quota", path: "Billing › Limits", covered: false, weak: true },
  ],
  gaps: [{ kind: "capability", concept_id: "cap:quota", label: "Usage quota", reason: "No system realises it.", system_id: null }],
  systems: [{
    id: "bcrm", name: "BCRM", role: "primary", change_type: "modify",
    paths: [[
      { kind: "facet", id: "need", label: "Need" },
      { kind: "concept", id: "cap:static-ip", label: "Static IP" },
      { kind: "system", id: "bcrm", label: "BCRM" },
    ]],
  }],
  owners: [{ concept_id: "cap:static-ip", system_id: "bcrm", squads: ["Sales squad"], people: ["Mona Adel"], open_seats: 1 }],
  questions: [],
  uncertainty: null,
  model: "fake",
  prompt_version: "assess-v1",
  decision: null,
  verdict: null,
  rationale: null,
  decided_by: null,
  decided_at: null,
};

const ready: RequirementAnalysis = {
  ...analysisFixture,
  analysis_id: "analysis-impact",
  // Nothing else stands in the way, so the gate's reason is the impact's.
  open_questions: [],
  assumptions: [],
  ambiguities: [],
  potential_dependencies: [],
  product_impact_status: "assessed",
  product_impact: impact,
};

const panel = (analysis: RequirementAnalysis, onDecide = vi.fn()) => (
  <AnalysisPanel
    analysis={analysis}
    busy={false}
    error={null}
    onClarify={vi.fn()}
    onConfirm={vi.fn()}
    canDecideIntent
    onDecideIntent={vi.fn()}
    onDecideProductImpact={onDecide}
  />
);

describe("ProductImpactCard", () => {
  it("shows the suggested verdict, coverage, gaps, systems and owners", () => {
    render(panel(ready));
    const card = screen.getByRole("region", { name: "Product impact" });
    expect(within(card).getByText("Change to an existing offering")).toBeVisible();
    expect(within(card).getByText(/A suggestion\. Its accuracy has not been proven/)).toBeVisible();
    expect(within(card).getByText("Business Fiber")).toBeVisible();
    expect(within(card).getByText("1 of 2 capabilities already covered")).toBeVisible();
    expect(within(card).getByText("Weak link: check it")).toBeVisible();
    expect(within(card).getByText("No system realises it.", { exact: false })).toBeVisible();
    expect(within(card).getByText("Primary system")).toBeVisible();
    expect(within(card).getByText("Changed")).toBeVisible();
    expect(within(card).getByText("Need › Static IP › BCRM")).toBeVisible();
    expect(within(card).getByText(/Sales squad · Mona Adel · 1 open seat/)).toBeVisible();
  });

  it("drops the suggestion note once the live gate has validated the verdict", () => {
    render(panel({ ...ready, product_impact: { ...impact, verdict_validated: true } }));
    expect(screen.queryByText(/Its accuracy has not been proven/)).toBeNull();
  });

  it("blocks confirmation until the verdict is decided, then accepts it", async () => {
    const user = userEvent.setup();
    const onDecide = vi.fn();
    render(panel(ready, onDecide));
    expect(screen.getByRole("heading", { name: "Not ready to confirm" })).toBeVisible();
    expect(screen.getByRole("button", { name: /Confirm this analysis/ }))
      .toHaveAccessibleDescription(/Decide the product impact/);
    await user.click(screen.getByRole("button", { name: "Accept the suggestion" }));
    expect(onDecide).toHaveBeenCalledWith({ decision: "accepted" });
  });

  it("asks for another verdict and a reason before overriding", async () => {
    const user = userEvent.setup();
    const onDecide = vi.fn();
    render(panel(ready, onDecide));
    await user.click(screen.getByRole("button", { name: "Choose another verdict" }));
    const select = screen.getByLabelText("Verdict");
    // The suggestion itself is not an override.
    expect(within(select).queryByRole("option", { name: "Change to an existing offering" })).toBeNull();
    const save = screen.getByRole("button", { name: "Save this verdict" });
    expect(save).toBeDisabled();
    await user.selectOptions(select, "new_plan");
    expect(save).toBeDisabled();
    await user.type(screen.getByLabelText(/Why the suggestion is wrong/), "It is sold as a new plan.");
    await user.click(save);
    expect(onDecide).toHaveBeenCalledWith({
      decision: "overridden", verdict: "new_plan", rationale: "It is sold as a new plan.",
    });
  });

  it("can mark the verdict unknown, and cannot accept a verdict that was not suggested", async () => {
    const user = userEvent.setup();
    const onDecide = vi.fn();
    render(panel({ ...ready, product_impact: { ...impact, suggested_verdict: null } }, onDecide));
    expect(screen.getByText(/No verdict yet: the catalogue needs answers first/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Accept the suggestion" })).toHaveAttribute("aria-disabled", "true");
    await user.click(screen.getByRole("button", { name: "Mark as unknown" }));
    expect(onDecide).toHaveBeenCalledWith({ decision: "unknown" });
  });

  it("settles a decided impact beside the outcome and no longer blocks on it", () => {
    render(panel({
      ...ready,
      product_impact: {
        ...impact, decision: "accepted", verdict: "change_existing_offering",
        decided_by: { id: "owner", display_name: "Owner One", email: null },
        decided_at: "2026-10-10T11:00:00Z",
      },
    }));
    const card = screen.getByRole("region", { name: "Product impact" });
    expect(within(card).getByText("Suggestion accepted")).toBeVisible();
    expect(within(card).getByText(/Decided by Owner One/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Ready to confirm" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Change this decision" })).toBeVisible();
  });

  it("shows the drafted offering for a new product line, and whether it is sent", () => {
    const line: ProductImpact = {
      ...impact,
      suggested_verdict: "new_product_line",
      draft: {
        offering_id: "cloud-video-surveillance-for-shops",
        offering_name: "Cloud video surveillance for shops",
        based_on: "offering:business-fiber",
        components: [
          { name: "Managed access point", system_ids: ["bcrm", "wfms"] },
          { name: "Cloud video surveillance", system_ids: [] },
        ],
        questions: ["Which system will realise Cloud video surveillance?"],
        journey_name: "Fulfilment",
        journey_steps: 2,
      },
    };
    const { rerender } = render(panel({ ...ready, product_impact: line }));
    const drafted = screen.getByRole("region", { name: "Drafted offering" });
    expect(drafted).toHaveTextContent(
      "The knowledge portal drafted Cloud video surveillance for shops from Business Fiber. " +
        "If the verdict stays a new offering, it goes to the catalogue's curators with the approved backlog.",
    );
    const components = within(drafted).getByRole("list", { name: "Its components" });
    expect(within(components).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Managed access pointby BCRM, wfms",
      "Cloud video surveillanceNo system yet",
    ]);
    expect(within(drafted).getByText("Its journey, Fulfilment, has 2 steps.")).toBeVisible();
    expect(within(drafted).getByText("Which system will realise Cloud video surveillance?", { exact: false })).toBeVisible();

    const decided = {
      decided_by: { id: "owner", display_name: "Owner One", email: null },
      decided_at: "2026-10-10T11:00:00Z",
    };
    rerender(panel({ ...ready, product_impact: { ...line, ...decided, decision: "accepted", verdict: "new_product_line" } }));
    expect(screen.getByRole("region", { name: "Drafted offering" })).toHaveTextContent(
      "It goes to the catalogue's curators with the approved backlog, for them to edit and accept.",
    );
    rerender(panel({
      ...ready,
      product_impact: {
        ...line, ...decided, decision: "overridden", verdict: "change_existing_offering",
        rationale: "Business Fiber can carry it.",
      },
    }));
    expect(screen.getByRole("region", { name: "Drafted offering" })).toHaveTextContent(
      "It is not sent, because the decided verdict is not a new offering.",
    );
  });

  it("shows nothing with no knowledge portal, and a notice when it was unreachable", () => {
    const { rerender } = render(panel({ ...ready, product_impact: null, product_impact_status: "not_connected" }));
    expect(screen.queryByRole("region", { name: "Product impact" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Ready to confirm" })).toBeVisible();
    rerender(panel({ ...ready, product_impact: null, product_impact_status: "unavailable" }));
    expect(screen.getByRole("status", { name: "Product impact not assessed" })).toBeVisible();
  });

  it("offers a catalogue question's answers as choices that fill the answer", async () => {
    const user = userEvent.setup();
    const question: ClarificationQuestion = {
      id: "catalogue-1", analysis_id: "analysis-impact", kind: "open_question",
      subject: "Which offering does this change?", rationale: "The knowledge portal needs this.",
      severity: "medium", is_blocker: true, source: "catalogue", status: "open", version: 1,
      asked_by: null, asked_at: null, assignee: null, assignment_history: [], draft_answer: null,
      draft_updated_by: null, draft_updated_at: null, answer: null, answered_by: null, answered_at: null,
      classification_changed_by: null, classification_changed_at: null, replaces_question_id: null,
      options: ["Business Fiber", "Business ADSL"],
    };
    render(panel({ ...ready, questions: [question] }));
    await user.click(screen.getByText("Which offering does this change?"));
    const choices = screen.getByRole("group", { name: /Answers the catalogue knows/ });
    await user.click(within(choices).getByRole("button", { name: "Business ADSL" }));
    expect(screen.getByLabelText("Your answer")).toHaveValue("Business ADSL");
    expect(within(choices).getByRole("button", { name: "Business ADSL" })).toHaveAttribute("aria-pressed", "true");
  });
});
