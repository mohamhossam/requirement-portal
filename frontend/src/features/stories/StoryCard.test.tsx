import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { storyFixture, storyQualityFixture } from "../../test/fixtures";
import { renderWithKnowledge as render } from "../../test/renderWithKnowledge";
import { StoryCard } from "./StoryCard";

const baseProps = {
  story: storyFixture,
  position: 1,
  busy: false,
  error: null,
  selected: false,
  onToggleSelect: vi.fn(),
  onEdit: vi.fn(),
  onRegenerate: vi.fn(),
  onSplit: vi.fn(),
  onManualSplit: vi.fn(),
  disabledReason: null,
  quality: null,
};

describe("StoryCard", () => {
  it("shows the story voice, its status and Given/When/Then criteria", () => {
    render(<StoryCard {...baseProps} />);
    expect(screen.getByText(/^As a SMB customer, I want/)).toBeInTheDocument();
    // Disambiguates the status badge from the "Generated" timestamp in the
    // provenance disclosure. It was `.status`, which the rebuilt StatusBadge no
    // longer emits — the state is addressable as `data-status` now.
    expect(screen.getByText("Generated", { selector: "[data-status] span" })).toBeInTheDocument();
    expect(screen.getByText("an address in an XGPON area")).toBeInTheDocument();
    expect(screen.getByText("I see that I qualify")).toBeInTheDocument();
  });

  it("surfaces staleness and its reason", () => {
    render(
      <StoryCard
        {...baseProps}
        story={{
          ...storyFixture,
          stale: { reason: "feature_changed", since: "2026-01-01T13:00:00Z" },
        }}
      />,
    );
    // The verdict badge and the notice both name it, in the same words.
    expect(screen.getAllByText("Out of date")).toHaveLength(2);
    expect(screen.getByText(/parent Feature changed/)).toBeInTheDocument();
  });

  it("regenerates untouched output immediately, without confirmation", async () => {
    const onRegenerate = vi.fn();
    render(<StoryCard {...baseProps} onRegenerate={onRegenerate} />);
    await userEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(onRegenerate).toHaveBeenCalledWith(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("requires explicit confirmation before regenerating edited content", async () => {
    const onRegenerate = vi.fn();
    render(<StoryCard {...baseProps} story={{ ...storyFixture, status: "edited" }} onRegenerate={onRegenerate} />);
    await userEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(screen.getByRole("dialog", { name: "Replace this Story?" })).toBeInTheDocument();
    expect(onRegenerate).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Replace Story" }));
    expect(onRegenerate).toHaveBeenCalledWith(true);
  });

  it("edits the acceptance criteria and saves structured Given/When/Then", async () => {
    const onEdit = vi.fn();
    render(<StoryCard {...baseProps} onEdit={onEdit} />);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const thenField = screen.getByDisplayValue("I see that I qualify");
    await userEvent.clear(thenField);
    await userEvent.type(thenField, "I see a clear eligible result");
    await userEvent.click(screen.getByRole("button", { name: "Save Story" }));
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit.mock.calls[0]![0].acceptance_criteria[0].then).toBe(
      "I see a clear eligible result",
    );
  });

  it("rejects an edit that leaves no complete acceptance criterion", async () => {
    const onEdit = vi.fn();
    render(<StoryCard {...baseProps} onEdit={onEdit} />);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    await userEvent.clear(screen.getByDisplayValue("an address in an XGPON area"));
    await userEvent.clear(screen.getByDisplayValue("I run the eligibility check"));
    await userEvent.clear(screen.getByDisplayValue("I see that I qualify"));
    await userEvent.click(screen.getByRole("button", { name: "Save Story" }));
    expect(onEdit).not.toHaveBeenCalled();
    expect(screen.getByText(/at least one acceptance criterion/)).toBeInTheDocument();
  });

  it("shows all INVEST findings and actionable SPIDR recommendations", () => {
    render(<StoryCard {...baseProps} quality={storyQualityFixture} />);

    expect(screen.getByRole("region", { name: "INVEST quality review" })).toBeVisible();
    // The headline now carries its own count: 'Split recommended — 2 of 6
    // checks failed'. The bare number beside it was a kicker-and-tally pair.
    expect(screen.getByText(/Split recommended/)).toBeVisible();
    expect(screen.getByText("Estimable")).toBeVisible();
    expect(screen.getByText("An unresolved integration prevents estimation.")).toBeVisible();
    // The heading is the plain-language one now; SPIDR is named in the line
    // beneath it, where a business owner meets the term with its definition
    // rather than as a bare acronym (PRODUCT.md Principle 3).
    expect(screen.getByText("Ways to split it")).toBeVisible();
    expect(screen.getByText(/from the SPIDR method/)).toBeVisible();
    expect(screen.getByText("Time-box the integration uncertainty.")).toBeVisible();
  });

  it("disables every mutation control when the parent Feature is not ready", () => {
    render(<StoryCard {...baseProps} disabledReason="The Feature is out of date." />);

    expect(screen.getByRole("checkbox")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Edit" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Regenerate" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Split by hand" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Suggest a split" })).toBeDisabled();
  });
});
