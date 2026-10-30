import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Story } from "../../api/client";
import { storyFixture } from "../../test/fixtures";
import { StorySizePanel } from "./StorySizePanel";

const provenance = { generated_at: "2026-10-30T12:00:00Z", model: "fake", prompt_version: "fake-story-estimate-v1" };
const estimate = {
  points: 3,
  basis: "team_entered" as const,
  decided_by: { id: "ba-1", display_name: "Business Analyst", email: null, roles: [] },
  decided_at: "2026-10-30T12:00:00Z",
};
const sized: Story = { ...storyFixture, version: 2, estimate };

type Props = Parameters<typeof StorySizePanel>[0];

function props(overrides: Partial<Props> = {}): Props {
  return {
    story: storyFixture,
    suggestion: null,
    provenance: null,
    busy: false,
    error: null,
    disabled: false,
    canSuggest: true,
    suggesting: false,
    onSuggest: vi.fn(),
    onSize: vi.fn(),
    ...overrides,
  };
}

describe("StorySizePanel", () => {
  it("asks the size question in business language and says what a point is", () => {
    render(<StorySizePanel {...props()} />);

    expect(screen.getByRole("heading", { name: "How big is this Story, compared with the others?" })).toBeInTheDocument();
    expect(screen.getByText(/relative effort against the other Stories in this Feature/)).toBeInTheDocument();
    expect(screen.getByText(/not\s+hours or days/)).toBeInTheDocument();
  });

  it("offers the AI suggestion as the one action, described by its reasoning", async () => {
    const onSize = vi.fn();
    render(
      <StorySizePanel
        {...props({
          suggestion: { story_id: "story-1", points: 5, rationale: "Twice the eligibility check." },
          provenance,
          onSize,
        })}
      />,
    );

    expect(screen.getByText("AI suggests 5 points")).toBeInTheDocument();
    expect(screen.getByText(/a suggestion until someone accepts it/)).toBeInTheDocument();
    // The select waits behind "Choose another size"; one decision at a time.
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    const accept = screen.getByRole("button", { name: "Accept 5 points" });
    expect(accept).toHaveAccessibleDescription("Twice the eligibility check.");

    await userEvent.click(accept);
    expect(onSize).toHaveBeenCalledWith({ points: 5, basis: "accepted_suggestion" });
  });

  it("says when the AI could not size a Story, and lets the team choose instead", async () => {
    render(
      <StorySizePanel
        {...props({
          suggestion: { story_id: "story-1", points: null, rationale: "The refund rule is not decided." },
          provenance,
        })}
      />,
    );

    expect(screen.getByText("The AI could not size this Story")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Accept/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Choose a size" }));
    expect(screen.getByRole("combobox", { name: "Size in story points" })).toBeInTheDocument();
  });

  it("offers a way to get a suggestion when there is none", async () => {
    const onSuggest = vi.fn();
    render(<StorySizePanel {...props({ onSuggest })} />);

    expect(screen.getByText(/Not sized yet\. There is no suggestion for it yet\./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Suggest sizes" }));
    expect(onSuggest).toHaveBeenCalled();
  });

  it("says an earlier suggestion went out of date, with the way back", () => {
    render(<StorySizePanel {...props({ suggestionStale: true })} />);

    expect(screen.getByText(/made before these Stories changed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suggest sizes again" })).toBeInTheDocument();
  });

  it("lets the team enter its own size from the suggestion, saving only on the button", async () => {
    const onSize = vi.fn();
    render(
      <StorySizePanel
        {...props({ suggestion: { story_id: "story-1", points: 5, rationale: "Medium." }, provenance, onSize })}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Choose another size" }));
    // The reasoning stays beside the picker while the person decides against it.
    expect(screen.getByText(/^The AI suggested 5 points: Medium.$/)).toBeVisible();
    const select = screen.getByRole("combobox", { name: "Size in story points" });
    // Starts from the suggestion, so agreeing needs no extra step.
    expect(select).toHaveValue("5");
    await userEvent.selectOptions(select, "8");
    expect(onSize).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Save size" }));
    expect(onSize).toHaveBeenCalledWith({ points: 8, basis: "team_entered" });
  });

  it("collapses a confirmed size to who decided it and when, with a way to change or clear it", async () => {
    const onSize = vi.fn();
    render(<StorySizePanel {...props({ story: sized, onSize })} />);

    expect(screen.getByText("3 points")).toBeInTheDocument();
    expect(screen.getByText(/^Set by Business Analyst · /)).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Change size" }));
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Size in story points" }), "");
    await userEvent.click(screen.getByRole("button", { name: "Clear size" }));
    expect(onSize).toHaveBeenCalledWith({ points: null, basis: "team_entered" });
  });

  it("asks before changing an approved Story's size, because it reopens the approval", async () => {
    const onSize = vi.fn();
    render(
      <StorySizePanel
        {...props({
          // Approved before anyone sized it: the trap the dialog exists for.
          story: { ...storyFixture, status: "approved" },
          suggestion: { story_id: "story-1", points: 5, rationale: "Bigger than it looks." },
          provenance,
          onSize,
        })}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Accept 5 points" }));
    // Named for the act: a first size on an approved Story, not a "change".
    const dialog = screen.getByRole("dialog", { name: "Size an approved Story?" });
    expect(dialog).toHaveTextContent("reopens the approval");
    expect(onSize).not.toHaveBeenCalled();

    // Consequential, not destructive: the confirm is not the red danger button.
    const confirm = within(dialog).getByRole("button", { name: "Set size" });
    expect(confirm).not.toHaveClass("bg-danger");
    await userEvent.click(confirm);
    expect(onSize).toHaveBeenCalledWith({ points: 5, basis: "accepted_suggestion" });
  });

  it("moves focus into the picker when it opens and back to the heading on Cancel", async () => {
    render(
      <StorySizePanel
        {...props({ suggestion: { story_id: "story-1", points: 5, rationale: "Medium." }, provenance })}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Choose another size" }));
    expect(screen.getByRole("combobox", { name: "Size in story points" })).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByRole("heading", { name: /How big is this Story/ })).toHaveFocus();
  });

  it("records choosing the AI's own number as accepting it", async () => {
    const onSize = vi.fn();
    render(
      <StorySizePanel
        {...props({ suggestion: { story_id: "story-1", points: 5, rationale: "Medium." }, provenance, onSize })}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Choose another size" }));
    expect(screen.getByRole("option", { name: "5 points (AI suggestion)" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save size" }));
    expect(onSize).toHaveBeenCalledWith({ points: 5, basis: "accepted_suggestion" });
  });

  it("keeps an overridden suggestion as a footnote, not a call to accept", () => {
    render(
      <StorySizePanel
        {...props({
          story: sized,
          suggestion: { story_id: "story-1", points: 5, rationale: "Bigger than it looks." },
          provenance,
        })}
      />,
    );

    expect(screen.getByText("The AI suggested 5 points")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Accept/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/until someone accepts it/)).not.toBeInTheDocument();
  });

  it("shows the other Stories while the size is open, and offers a split when the AI could not size it", async () => {
    const onSplit = vi.fn();
    render(
      <StorySizePanel
        {...props({
          suggestion: { story_id: "story-1", points: null, rationale: "Too large; split it first." },
          provenance,
          onSplit,
          siblings: [{ id: "story-2", gist: "place an eligible order online", points: 3, suggested: null }],
        })}
      />,
    );

    expect(screen.getByText("The Stories in this Feature, smallest first:")).toBeInTheDocument();
    const ladder = screen.getAllByRole("listitem").map((item) => item.textContent);
    // The sized sibling first; this Story, with no size, placed last and marked as current.
    expect(ladder).toEqual(["place an eligible order online — 3 points", "This Story — Not sized yet"]);
    expect(screen.getByText(/^This Story/).closest("li")).toHaveAttribute("aria-current", "true");
    expect(screen.getByText(/choose a size yourself, or split the Story first/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Suggest a split" }));
    expect(onSplit).toHaveBeenCalled();
  });

  it("returns focus to the heading and announces the size once it is saved", async () => {
    const onSize = vi.fn();
    const { rerender } = render(
      <StorySizePanel
        {...props({ suggestion: { story_id: "story-1", points: 2, rationale: "Small." }, provenance, onSize })}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Accept 2 points" }));
    rerender(
      <StorySizePanel
        {...props({
          story: { ...storyFixture, version: 2, estimate: { ...estimate, points: 2, basis: "accepted_suggestion" } },
          suggestion: { story_id: "story-1", points: 2, rationale: "Small." },
          provenance,
          onSize,
        })}
      />,
    );

    expect(screen.getByRole("heading", { name: /How big is this Story/ })).toHaveFocus();
    expect(screen.getByRole("status")).toHaveTextContent("Size set to 2 points.");
    expect(screen.getByText(/^AI suggestion accepted by Business Analyst · /)).toBeInTheDocument();
  });

  it("stays reachable while blocked and is described by the card's reason", () => {
    render(
      <StorySizePanel
        {...props({
          disabled: true,
          describedBy: "story-story-1-gated",
          suggestion: { story_id: "story-1", points: 5, rationale: "Small." },
          provenance,
        })}
      />,
    );

    // Gated, not disabled: it keeps its tab stop and is described by the reason.
    const accept = screen.getByRole("button", { name: "Accept 5 points" });
    expect(accept).toHaveAttribute("aria-disabled", "true");
    expect(accept).not.toBeDisabled();
    expect(accept.getAttribute("aria-describedby")?.split(" ")).toContain("story-story-1-gated");
  });
});
