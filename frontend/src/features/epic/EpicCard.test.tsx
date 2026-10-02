import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { analysisFixture, epicFixture, featureSetFixture } from "../../test/fixtures";
import { EpicCard } from "./EpicCard";

const baseProps = {
  analysis: { ...analysisFixture, human_confirmed: true },
  features: featureSetFixture,
  busy: false,
  error: null,
  canManage: true,
  onEdit: vi.fn(),
  onApprove: vi.fn(),
  onRegenerate: vi.fn(),
};

describe("EpicCard", () => {
  it("disables approval and explains stale state", () => {
    render(<EpicCard {...baseProps} epic={{ ...epicFixture, stale: { reason: "requirement_changed", since: "2026-01-01T13:00:00Z" } }} />);
    // Gated, not disabled: it keeps its tab stop and says why.
    expect(screen.getByRole("button", { name: "Approve" })).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Reconcile this item because its source requirement changed.")).toBeInTheDocument();
  });

  it("disables repeat approval for an approved Epic", () => {
    render(<EpicCard {...baseProps} epic={{ ...epicFixture, status: "approved" }} />);
    expect(screen.getByRole("button", { name: "Approved" })).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByText(
        "This version is already approved. Regenerate or edit it before approving again.",
      ),
    ).toBeInTheDocument();
  });

  it("regenerates untouched output without force", async () => {
    const onRegenerate = vi.fn();
    render(<EpicCard {...baseProps} epic={epicFixture} onRegenerate={onRegenerate} />);
    await userEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(onRegenerate).toHaveBeenCalledWith(false);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("names human-owned loss and sends force only after confirmation", async () => {
    const onRegenerate = vi.fn();
    render(<EpicCard {...baseProps} epic={{ ...epicFixture, status: "approved" }} onRegenerate={onRegenerate} />);
    await userEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(screen.getByRole("dialog", { name: "Replace this Epic?" })).toHaveTextContent("mark 2 Features out of date");
    expect(onRegenerate).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Replace Epic" }));
    expect(onRegenerate).toHaveBeenCalledWith(true);
  });

  it("labels provenance as the original AI generation", async () => {
    render(<EpicCard {...baseProps} epic={epicFixture} />);
    expect(screen.getByText("Original AI generation")).toBeInTheDocument();
  });
});

it("keeps a rejected draft and submits its opening version after a refetch", async () => {
  const onEdit = vi.fn().mockRejectedValue(new Error("Conflict"));
  const { rerender } = render(<EpicCard {...baseProps} epic={{ ...epicFixture, version: 3 }} onEdit={onEdit} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit" }));
  await userEvent.clear(screen.getByLabelText("Epic name"));
  await userEvent.type(screen.getByLabelText("Epic name"), "My unsaved title");
  rerender(<EpicCard {...baseProps} epic={{ ...epicFixture, version: 4 }} onEdit={onEdit} />);
  await userEvent.click(screen.getByRole("button", { name: "Save Epic" }));
  expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ name: "My unsaved title" }), 3);
  expect(screen.getByLabelText("Epic name")).toHaveValue("My unsaved title");
});

it("shows who approved the Epic, and what approving covers before it is signed", () => {
  const { rerender } = render(<EpicCard {...baseProps} focused epic={{ ...epicFixture, status: "generated" }} />);
  expect(screen.getByText("Needs approval")).toBeInTheDocument();
  expect(screen.getByText(/Approving signs off this Epic as it reads now/)).toBeInTheDocument();

  rerender(
    <EpicCard
      {...baseProps}
      focused
      epic={{
        ...epicFixture,
        status: "approved",
        current_approval: {
          id: "approval-1",
          decision: "approved",
          rationale: null,
          recorded_at: "2026-09-26T09:00:00Z",
          recorded_by: { id: "owner", display_name: "Amina Owner", email: null },
          subject_fingerprint: "fp",
          target: { kind: "epic", item_id: epicFixture.id },
        },
      }}
    />,
  );
  expect(screen.getByText(/^Approved by Amina Owner · /)).toBeInTheDocument();
  expect(screen.queryByText(/Approving signs off/)).not.toBeInTheDocument();
});

it("moves focus into the editor and back to Edit on cancel (WCAG 2.4.3)", async () => {
  render(<EpicCard {...baseProps} focused epic={epicFixture} />);
  await userEvent.click(screen.getByRole("button", { name: "Edit" }));
  expect(screen.getByLabelText("Epic name")).toHaveFocus();
  await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.getByRole("button", { name: "Edit" })).toHaveFocus();
});
