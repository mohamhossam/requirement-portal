import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { journey, type JourneyState } from "./journey";
import { StageRail } from "./StageRail";

const state: JourneyState = {
  eligible: true,
  hasAnalysis: true,
  blockingCount: 2,
  knowledgeReady: false,
  humanConfirmed: false,
  isDuplicate: false,
};

function show(viewingPath?: string) {
  return render(
    <MemoryRouter>
      <StageRail steps={journey("req-1", state)} viewingPath={viewingPath} />
    </MemoryRouter>,
  );
}

/**
 * Matched on the label rather than the whole name: `complete` and `blocked`
 * append their meaning to the accessible name, so an exact-string lookup would
 * find the step only while its status happened not to say anything.
 */
const link = (label: string) => screen.getByRole("link", { name: new RegExp(`^${label}\\b`) });
const step = (label: string) => link(label).closest("li")!;

describe("StageRail", () => {
  it("gives all six steps a link of their own", () => {
    show();
    const nav = screen.getByRole("navigation", { name: "Requirement workflow" });
    // Six, not five. Review & approve is step 6 rather than a button in a page
    // header (docs/ux-plan.md §3.2, §4).
    expect(within(nav).getAllByRole("link")).toHaveLength(6);
    expect(link("Clarify")).toHaveAttribute("href", "/requirements/req-1/clarify");
    expect(link("Backlog")).toHaveAttribute("href", "/requirements/req-1/breakdown");
    expect(link("Review & approve")).toHaveAttribute("href", "/requirements/req-1/review");
  });

  it("says what complete and blocked mean instead of only showing it", () => {
    show();
    // The check mark is decorative and the muted grey is invisible to a screen
    // reader, so without this the six steps are six identical links.
    expect(link("Source")).toHaveAccessibleName("Source — completed");
    expect(link("Backlog")).toHaveAccessibleName("Backlog — not available yet");
    // The step being waited on says so through aria-current, not twice.
    expect(link("Clarify")).toHaveAccessibleName("Clarify");
  });

  it("keeps the ordinal out of the accessible name", () => {
    show();
    // The list already carries order; "3 Knowledge" only adds a number to read past.
    expect(link("Knowledge")).toHaveAccessibleName("Knowledge");
  });

  it("marks the step the journey is waiting on", () => {
    show();
    expect(step("Clarify")).toHaveClass("current");
    expect(step("Clarify")).toHaveAttribute("aria-current", "step");
    expect(step("Source")).toHaveClass("complete");
  });

  it("shows steps that cannot help yet as blocked, still reachable", () => {
    show();
    expect(step("Backlog")).toHaveClass("blocked");
    expect(step("Review & approve")).toHaveClass("blocked");
    expect(link("Backlog")).toBeInTheDocument();
  });

  it("marks where you are separately from what is owed", () => {
    show("/requirements/req-1/breakdown");
    // On Backlog before confirmation these come apart, which is the point.
    expect(step("Backlog")).toHaveClass("viewing");
    expect(step("Backlog")).toHaveAttribute("aria-current", "page");
    // Both markers stand, because they say different things: "page" is where you
    // are, "step" is what the journey still wants.
    expect(step("Clarify")).toHaveClass("current");
    expect(step("Clarify")).toHaveAttribute("aria-current", "step");
  });

  it("marks nothing as viewed on a route outside the journey", () => {
    // History is a panel, not a step (§4), so /revisions is not in the rail.
    const { container } = show("/requirements/req-1/revisions");
    expect(container.querySelectorAll("li.viewing")).toHaveLength(0);
  });
});
