import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { featureSetFixture } from "../../test/fixtures";
import { renderWithJobs } from "../../test/renderWithClient";
import { FeatureTree } from "./FeatureTree";

describe("FeatureTree", () => {
  beforeEach(() => {
    vi.spyOn(api, "getStories").mockResolvedValue(null);
    vi.spyOn(api, "listStoryProposals").mockResolvedValue([]);
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows review fields and no set-regeneration action", () => {
    renderWithJobs(
      <FeatureTree requirementId="req-1" featureSet={featureSetFixture} canManage busyFeatureId={null} errors={{}} onEdit={vi.fn()} onApprove={vi.fn()} />,
    );
    expect(screen.getByText("Digital ordering")).toBeInTheDocument();
    expect(screen.getByText("Journey stage")).toBeInTheDocument();
    expect(screen.getByText("Ordering is a distinct journey stage.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /regenerate all/i })).not.toBeInTheDocument();
  });

  it("disables repeat approval for an approved Feature", () => {
    renderWithJobs(
      <FeatureTree requirementId="req-1" featureSet={featureSetFixture} canManage busyFeatureId={null} errors={{}} onEdit={vi.fn()} onApprove={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: "Approved" })).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByText(
        "This version is already approved. Regenerate or edit it before approving again.",
      ),
    ).toBeInTheDocument();
  });

  it("edits one Feature while leaving its sibling visible", async () => {
    renderWithJobs(
      <FeatureTree requirementId="req-1" featureSet={featureSetFixture} canManage busyFeatureId={null} errors={{}} onEdit={vi.fn()} onApprove={vi.fn()} />,
    );
    const editButtons = screen.getAllByRole("button", { name: "Edit" });
    await userEvent.click(editButtons[0]!);
    expect(screen.getByDisplayValue("Digital ordering")).toBeInTheDocument();
    expect(screen.getByText("Service fulfilment")).toBeInTheDocument();
  });
});
