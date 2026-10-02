import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { api, type RequirementAccess } from "../../api/client";
import { renderWithClient } from "../../test/renderWithClient";
import { RequirementAccessPanel } from "./RequirementAccessPanel";

const owner = { id: "owner", display_name: "Amina Owner", email: "amina@example.test" };
const reviewer = { id: "reviewer", display_name: "Ravi Reviewer", email: "ravi@example.test" };
const access: RequirementAccess = {
  requirement_id: "requirement-1",
  version: 2,
  owner: { actor: owner, role: "owner", assigned_at: "2026-09-03T12:00:00Z", assigned_by: owner },
  reviewers: [],
  changes: [],
  can_claim_owner: false,
  can_manage_assignments: true,
  can_confirm_analysis: true,
  can_export_approved_revisions: true,
  can_manage_content: true,
  can_govern: true,
};

afterEach(() => vi.restoreAllMocks());

it("lets the owner assign a known reviewer", async () => {
  vi.spyOn(api, "searchActors").mockResolvedValue([owner, reviewer]);
  const assign = vi.spyOn(api, "assignReviewer").mockResolvedValue({
    ...access,
    reviewers: [{ actor: reviewer, role: "reviewer", assigned_at: "2026-09-03T12:01:00Z", assigned_by: owner }],
  });
  renderWithClient(<RequirementAccessPanel requirementId="requirement-1" access={access} />);

  await screen.findByRole("option", { name: "Ravi Reviewer" });
  await userEvent.selectOptions(screen.getByLabelText("Known actor"), "reviewer");
  await userEvent.click(screen.getByRole("button", { name: "Add reviewer" }));

  expect(assign).toHaveBeenCalledWith("requirement-1", "reviewer", access.version);
});

it("explains why assignment controls are unavailable to a reviewer", () => {
  vi.spyOn(api, "searchActors").mockResolvedValue([]);
  renderWithClient(<RequirementAccessPanel requirementId="requirement-1" access={{ ...access, can_manage_assignments: false, can_confirm_analysis: false }} />);
  expect(screen.getByText(/Only Amina Owner/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Add reviewer" })).not.toBeInTheDocument();
});
