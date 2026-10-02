import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type RequirementWorklistItem } from "../api/client";
import { RequirementEntryRedirect } from "./RequirementEntryRedirect";

const item: RequirementWorklistItem = {
  id: "req-1",
  title: "Requirement",
  description: "Need",
  status: "draft",
  desired_outcome: "Outcome",
  customer_context: null,
  channels: [],
  systems: [],
  business_rules: [],
  constraints: [],
  version: 1,
  analysis_eligibility: { eligible: true, missing_fields: [] },
  workflow_status: "ready_for_review",
  current_stage: "confirm",
  next_action: "confirm_analysis",
  answered_items: 2,
  unresolved_items: 0,
  stale_items: 0,
  artifact_counts: { epics: 0, features: 0, stories: 0 },
  updated_at: "2026-09-03T08:00:00Z",
  owner: null,
  reviewer_count: 0,
  active_ai_operation: null,
  last_activity: null,
};

describe("RequirementEntryRedirect", () => {
  afterEach(() => vi.restoreAllMocks());

  it("redirects the compatibility route to the persisted current stage", async () => {
    vi.spyOn(api, "listRequirements").mockResolvedValue({
      requirements: [item],
      attention: [],
      total: 1,
      offset: 0,
      limit: 100,
      has_more: false,
      status_counts: { draft: 0, needs_answers: 0, reanalysing: 0, ready_for_review: 1, approved: 0, needs_revision: 0, stale: 0, knowledge_review: 0, duplicate: 0 },
      owner_facets: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/requirements/req-1"]}>
          <Routes>
            <Route path="/requirements/:id" element={<RequirementEntryRedirect />} />
            <Route path="/requirements/:id/confirm" element={<p>Confirmation route</p>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByText("Confirmation route")).toBeVisible();
  });
});
