import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, type RequirementDraft, type RequirementList, type RequirementWorklistItem, type RequirementDraftList } from "../api/client";
import { DashboardPage } from "./DashboardPage";

function renderDashboard(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
}

const item = (id: string, title: string): RequirementWorklistItem => ({
  id,
  title,
  description: `Description for ${title}`,
  status: "draft",
  desired_outcome: `Outcome for ${title}`,
  customer_context: null,
  channels: [],
  systems: [],
  business_rules: [],
  constraints: [],
  version: 1,
  analysis_eligibility: { eligible: true, missing_fields: [] },
  workflow_status: "draft",
  current_stage: "capture",
  next_action: "analyse",
  answered_items: 0,
  unresolved_items: 0,
  stale_items: 0,
  artifact_counts: { epics: 0, features: 0, stories: 0 },
  updated_at: "2026-09-02T12:00:00Z",
  owner: null,
  reviewer_count: 0,
  active_ai_operation: null,
  last_activity: null,
});

const response = (requirements: RequirementWorklistItem[]): RequirementList => ({
  requirements,
  attention: [],
  total: requirements.length,
  offset: 0,
  limit: 20,
  has_more: false,
  status_counts: { draft: requirements.length, needs_answers: 0, reanalysing: 0, ready_for_review: 0, approved: 0, needs_revision: 0, stale: 0, knowledge_review: 0, duplicate: 0 },
  owner_facets: [],
});

const twoRequirements = response([
  item("req-newer-1234", "Newer requirement"),
  item("req-older-9876", "Older requirement"),
]);

/** `GET /requirements/drafts` with these drafts on its first page. */
const drafts = (items: RequirementDraft[]): RequirementDraftList => ({
  drafts: items, total: items.length, offset: 0, limit: 1, has_more: false,
});

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.spyOn(api, "listRequirementDrafts").mockResolvedValue(drafts([]));
    vi.spyOn(api, "listSavedViews").mockResolvedValue([]);
  });
  afterEach(() => vi.restoreAllMocks());

  it("lists enriched requirements and their textual next action", async () => {
    vi.spyOn(api, "listRequirements").mockResolvedValue(twoRequirements);
    renderDashboard(<DashboardPage />);
    expect(await screen.findByRole("link", { name: /Newer requirement/ })).toHaveAttribute("href", "/requirements/req-newer-1234/capture");
    expect(screen.getAllByText("Analyse requirement").length).toBeGreaterThan(0);
  });

  it("names a worklist row by its title and describes it by what you triage on", async () => {
    const owned = {
      ...item("req-owned-1234", "Owned requirement"),
      owner: { id: "fake-owner", display_name: "Amina Owner", email: "amina@example.test" },
    };
    vi.spyOn(api, "listRequirements").mockResolvedValue(response([owned, item("req-free-9876", "Unowned requirement")]));
    renderDashboard(<DashboardPage />);
    // Each value has its own column header now, so the link is the title alone,
    // described by the two things a person triages on: status and next step.
    const link = await screen.findByRole("link", { name: "Owned requirement" });
    expect(link).toHaveAccessibleDescription("Draft Next: Analyse requirement");
    const row = link.closest("tr")!;
    expect(within(row).getByText("Amina Owner")).toBeInTheDocument();
    expect(within(screen.getByRole("link", { name: "Unowned requirement" }).closest("tr")!).getByText("Unowned legacy")).toBeInTheDocument();
  });

  it("exposes the worklist as a table whose headers sort it", async () => {
    const list = vi.spyOn(api, "listRequirements").mockResolvedValue(twoRequirements);
    renderDashboard(<DashboardPage />);
    const table = await screen.findByRole("table", { name: "Requirements worklist" });
    // A header row and one row per requirement.
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    const requirement = within(table).getByRole("columnheader", { name: /Requirement/ });
    const updated = within(table).getByRole("columnheader", { name: /Updated/ });
    expect(requirement).toHaveAttribute("aria-sort", "none");
    expect(updated).toHaveAttribute("aria-sort", "descending");

    await userEvent.click(within(requirement).getByRole("button"));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "title_asc" }), { signal: expect.any(AbortSignal) }));
    // A new order is a new query, so the table is re-rendered: find it again.
    const resorted = await screen.findByRole("table", { name: "Requirements worklist" });
    expect(within(resorted).getByRole("columnheader", { name: /Requirement/ })).toHaveAttribute("aria-sort", "ascending");
    expect(within(resorted).getByRole("columnheader", { name: /Updated/ })).toHaveAttribute("aria-sort", "none");
  });

  it("offers to resume the last requirement opened, from the worklist it already loaded", async () => {
    localStorage.setItem("lastRequirementId", "req-older-9876");
    const list = vi.spyOn(api, "listRequirements").mockResolvedValue(twoRequirements);
    renderDashboard(<DashboardPage />);
    const resume = await screen.findByRole("link", { name: /^Resume Older requirement/ });
    expect(resume).toHaveAttribute("href", "/requirements/req-older-9876/capture");
    // No request of its own: the worklist call is the only one.
    expect(list).toHaveBeenCalledTimes(1);
    localStorage.removeItem("lastRequirementId");
  });

  it("offers no resume link when the last requirement is not in the loaded worklist", async () => {
    localStorage.setItem("lastRequirementId", "req-elsewhere-0000");
    vi.spyOn(api, "listRequirements").mockResolvedValue(twoRequirements);
    renderDashboard(<DashboardPage />);
    await screen.findByRole("link", { name: "Newer requirement" });
    expect(screen.queryByRole("link", { name: /^Resume / })).not.toBeInTheDocument();
    localStorage.removeItem("lastRequirementId");
  });

  it("uses an explicit draft id for the resume action", async () => {
    const resumable: RequirementDraft = {
      id: "draft-resume-1234",
      title: "Saved intake",
      description: "",
      desired_outcome: "",
      customer_context: "",
      channels: [],
      systems: [],
      business_rules: [],
      constraints: [],
      version: 1,
      updated_at: "2026-09-03T08:00:00Z",
      analysis_eligibility: {
        eligible: false,
        missing_fields: ["description", "desired_outcome"],
      },
    };
    vi.mocked(api.listRequirementDrafts).mockResolvedValue(drafts([resumable]));
    vi.spyOn(api, "listRequirements").mockResolvedValue(response([]));

    renderDashboard(<DashboardPage />);

    expect(await screen.findByRole("link", { name: "Resume Saved intake" })).toHaveAttribute(
      "href",
      "/requirements/new?draft=draft-resume-1234",
    );
  });

  it("passes search, status, and sort controls to the server query", async () => {
    const list = vi.spyOn(api, "listRequirements").mockResolvedValue(twoRequirements);
    renderDashboard(<DashboardPage />);
    await screen.findByText("Newer requirement");
    await userEvent.type(screen.getByRole("searchbox", { name: "Search requirements" }), "older");
    await userEvent.click(screen.getByRole("button", { name: /Draft/ }));
    await userEvent.selectOptions(screen.getByLabelText("Sort"), "title_asc");
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ q: "older", workflowStatus: ["draft"], sort: "title_asc" }), { signal: expect.any(AbortSignal) }));
  });

  it("filters by owner and assignments to the current actor", async () => {
    const owner = { id: "fake-owner", display_name: "Amina Owner", email: "amina@example.test" };
    const list = vi.spyOn(api, "listRequirements").mockResolvedValue({
      ...twoRequirements,
      owner_facets: [{ actor: owner, count: 2 }],
    });
    renderDashboard(<DashboardPage />);
    await screen.findByText("Newer requirement");
    await userEvent.selectOptions(screen.getByLabelText("Owner"), "fake-owner");
    await userEvent.click(screen.getByRole("checkbox", { name: "Assigned to me" }));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({
      ownerId: "fake-owner",
      assignedToMe: true,
    }), { signal: expect.any(AbortSignal) }));
  });

  it("collapses the real attention band", async () => {
    const urgent = { ...item("urgent-1", "Clarify eligibility"), workflow_status: "needs_answers" as const, current_stage: "clarify" as const, next_action: "answer_questions" as const, unresolved_items: 2 };
    vi.spyOn(api, "listRequirements").mockResolvedValue({ ...response([urgent]), attention: [urgent] });
    renderDashboard(<DashboardPage />);
    const toggle = await screen.findByRole("button", { name: /Needs attention/ });
    const band = toggle.closest("section");
    expect(band).not.toBeNull();
    expect(within(band!).getByText("Answer open questions")).toBeVisible();
    await userEvent.click(toggle);
    expect(within(band!).queryByText("Answer open questions")).not.toBeInTheDocument();
  });

  it("shows an empty state when there are no requirements", async () => {
    vi.spyOn(api, "listRequirements").mockResolvedValue(response([]));
    renderDashboard(<DashboardPage />);
    expect(await screen.findByText("No requirements yet")).toBeInTheDocument();
  });

  it("loads the next server page without replacing current rows", async () => {
    const first = { ...response([item("req-1", "First page")]), total: 2, has_more: true, limit: 1 };
    const second = { ...response([item("req-2", "Second page")]), total: 2, offset: 1, limit: 1 };
    vi.spyOn(api, "listRequirements").mockImplementation((params) =>
      Promise.resolve(params?.offset === 1 ? second : first),
    );
    renderDashboard(<DashboardPage />);
    await screen.findByText("First page");
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByText("Second page")).toBeVisible();
    expect(screen.getByText("First page")).toBeVisible();
  });

  it("applies every criterion from a saved view and resets to its first page", async () => {
    vi.mocked(api.listSavedViews).mockResolvedValue([{
      id: "view-1",
      name: "My questions",
      criteria: {
        query: "eligibility",
        workflow_statuses: ["needs_answers"],
        sort: "title_desc",
        owner_id: "fake-owner",
        assigned_to_me: true,
      },
      version: 1,
      created_at: "2026-09-04T09:00:00Z",
      updated_at: "2026-09-04T09:00:00Z",
    }]);
    const list = vi.spyOn(api, "listRequirements").mockResolvedValue(twoRequirements);
    renderDashboard(<DashboardPage />);
    await screen.findByText("Newer requirement");

    await userEvent.selectOptions(screen.getByLabelText("Saved view"), "view-1");

    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({
      q: "eligibility",
      workflowStatus: ["needs_answers"],
      sort: "title_desc",
      ownerId: "fake-owner",
      assignedToMe: true,
      offset: 0,
    }), { signal: expect.any(AbortSignal) }));
  });
});
