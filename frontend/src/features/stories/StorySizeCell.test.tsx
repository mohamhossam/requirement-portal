import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Story } from "../../api/client";
import { storyFixture } from "../../test/fixtures";
import { StorySizeCell } from "./StorySizeCell";

const suggestion = { story_id: "story-1", points: 3, rationale: "About the same as checking eligibility." };
const estimate = {
  points: 3,
  basis: "accepted_suggestion" as const,
  decided_by: { id: "ba-1", display_name: "Business Analyst", email: null, roles: [] },
  decided_at: "2026-10-30T12:00:00Z",
};

type Props = Parameters<typeof StorySizeCell>[0];
const base = (overrides: Partial<Props> = {}): Props => ({
  story: storyFixture,
  suggestion,
  busy: false,
  error: null,
  disabled: false,
  onSize: vi.fn(),
  ...overrides,
});

describe("StorySizeCell", () => {
  it("accepts the AI's size from the list row, naming the Story", async () => {
    const onSize = vi.fn();
    render(<StorySizeCell {...base({ onSize })} />);

    expect(screen.getByText("AI suggests 3 points")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Accept 3 points: / }));
    expect(onSize).toHaveBeenCalledWith({ points: 3, basis: "accepted_suggestion" });
  });

  it("opens the reason below the row without moving the Accept button", async () => {
    render(<StorySizeCell {...base()} />);

    const why = screen.getByRole("button", { name: "Why?" });
    expect(why).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("About the same as checking eligibility.")).not.toBeVisible();
    await userEvent.click(why);
    expect(why).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("About the same as checking eligibility.")).toBeVisible();
  });

  it("announces the saved size and keeps focus on the row it was decided on", async () => {
    const onSize = vi.fn();
    const { rerender } = render(<StorySizeCell {...base({ onSize })} />);

    await userEvent.click(screen.getByRole("button", { name: /^Accept 3 points/ }));
    const saved: Story = { ...storyFixture, version: 2, estimate };
    rerender(<StorySizeCell {...base({ story: saved, onSize })} />);

    expect(screen.getByRole("status")).toHaveTextContent(/^Size set to 3 points for /);
    expect(screen.getByText("3 points").closest("[tabindex='-1']")).toHaveFocus();
    expect(screen.getByText("AI suggestion accepted by Business Analyst")).toBeInTheDocument();
  });

  it("says on the row when a size was not saved", () => {
    render(<StorySizeCell {...base({ error: "The Story changed. Reload it." })} />);
    expect(screen.getByText(/The size for this Story was not saved: The Story changed\. Reload it\./)).toBeInTheDocument();
  });

  it("asks first, in the words of the act, when accepting would reopen an approved Story", async () => {
    const onSize = vi.fn();
    render(<StorySizeCell {...base({ story: { ...storyFixture, status: "approved" }, onSize })} />);

    await userEvent.click(screen.getByRole("button", { name: /^Accept 3 points/ }));
    const dialog = screen.getByRole("dialog", { name: "Size an approved Story?" });
    expect(onSize).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole("button", { name: "Set size" }));
    expect(onSize).toHaveBeenCalled();
  });

  it("says plainly when a Story has no size and nothing to accept", () => {
    const { rerender } = render(<StorySizeCell {...base({ suggestion: null })} />);
    expect(screen.getByText("Not sized yet")).toBeInTheDocument();

    rerender(<StorySizeCell {...base({ suggestion: { ...suggestion, points: null } })} />);
    expect(screen.getByText("Not sized yet · the AI could not size it")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Accept/ })).not.toBeInTheDocument();
  });
});
