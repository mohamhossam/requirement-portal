import { focusManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Link, MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, type Requirement, type RequirementAccess } from "../api/client";
import { ApiError } from "../api/errors";
import { analysisFixture, epicFixture, featureSetFixture } from "../test/fixtures";
import { RequirementPage } from "./RequirementPage";

const requirement: Requirement = {
  id: "req-1", title: "Broadband requirement", description: "Enable business broadband ordering.",
  desired_outcome: "Customers can order broadband", customer_context: null, channels: [], systems: [],
  business_rules: [], constraints: [], version: 1, updated_at: null, status: "draft",
  analysis_eligibility: { eligible: true, missing_fields: [] }, analysis_context_token: "analysis-context",
};
const access: RequirementAccess = {
  requirement_id: "req-1", version: 1, owner: null, reviewers: [], changes: [],
  can_claim_owner: false, can_manage_assignments: true, can_confirm_analysis: true,
  can_export_approved_revisions: true, can_manage_content: true, can_govern: true,
};

function renderPage(view: "clarify" | "confirm" | "breakdown") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 10_000 } } });
  const ui = (currentView: typeof view) => <QueryClientProvider client={client}><MemoryRouter initialEntries={[`/requirements/req-1/${view}`]}><Routes><Route path="/requirements/:id/*" element={<RequirementPage view={currentView} />} /></Routes></MemoryRouter></QueryClientProvider>;
  const rendered = render(ui(view));
  return { client, ...rendered, changeView: (nextView: typeof view) => rendered.rerender(ui(nextView)) };
}

describe("Requirement workspace reads", () => {
  beforeEach(() => {
    vi.spyOn(api, "getRequirement").mockResolvedValue(requirement);
    vi.spyOn(api, "getAssignments").mockResolvedValue(access);
    vi.spyOn(api, "searchActors").mockResolvedValue([]);
    vi.spyOn(api, "getAnalysis").mockResolvedValue({ ...analysisFixture, requirement_id: "req-1" });
    vi.spyOn(api, "listAnalysisRounds").mockResolvedValue([]);
    vi.spyOn(api, "getKnowledgeReview").mockResolvedValue({ status: "required", ready: false, current: false, input_fingerprint: "input", screen_id: null, provenance: null, findings: [], reference_conflict_ids: [] });
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    vi.spyOn(api, "getEpic").mockResolvedValue(null);
    vi.spyOn(api, "getFeatures").mockResolvedValue(null);
    vi.spyOn(api, "getStories").mockResolvedValue(null);
    vi.spyOn(api, "getRevisionHistory");
  });
  afterEach(() => { vi.restoreAllMocks(); focusManager.setFocused(undefined); });

  it.each(["clarify", "confirm"] as const)("does not read backlog or revision history on %s", async (view) => {
    renderPage(view);
    await screen.findByRole("button", { name: "Start a new analysis" });
    await waitFor(() => expect(api.listAnalysisRounds).toHaveBeenCalledTimes(1));
    expect(api.getEpic).not.toHaveBeenCalled();
    expect(api.getFeatures).not.toHaveBeenCalled();
    expect(api.getStories).not.toHaveBeenCalled();
    expect(api.getRevisionHistory).not.toHaveBeenCalled();
    expect(api.listAiJobs).toHaveBeenCalledTimes(1);
  });

  it("shows the empty Features state when the Epic is absent", async () => {
    renderPage("breakdown");
    expect(await screen.findByText("No Epic yet")).toBeVisible();
    expect(screen.queryByText("No Features yet")).not.toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Loading Features" })).not.toBeInTheDocument();
    // Both backlog reads issue together. Features used to wait on the Epic,
    // which spared this one request on an empty backlog and cost a round trip
    // on every populated one — the common case. The empty state is still
    // driven by the Epic, which is what this asserts.
    expect(api.getEpic).toHaveBeenCalledTimes(1);
    expect(api.getFeatures).toHaveBeenCalledTimes(1);
  });

  it("reads an existing backlog despite an unconfirmed analysis", async () => {
    const stale = { reason: "requirement_changed" as const, since: "2026-09-18T12:00:00Z" };
    vi.mocked(api.getEpic).mockResolvedValue({ ...epicFixture, stale });
    vi.mocked(api.getFeatures).mockResolvedValue({ ...featureSetFixture, features: featureSetFixture.features.map((feature) => ({ ...feature, stale })) });
    vi.spyOn(api, "listStoryProposals").mockResolvedValue([]);
    renderPage("breakdown");
    expect((await screen.findAllByRole("link", { name: /Digital ordering/ }))[0]).toBeVisible();
    expect(screen.getByText("Confirm the analysis to change the backlog")).toBeVisible();
    expect(api.getEpic).toHaveBeenCalledTimes(1);
    expect(api.getFeatures).toHaveBeenCalledTimes(1);
  });

  it("displays a real Epic read error rather than treating it as absent", async () => {
    vi.mocked(api.getEpic).mockRejectedValue(new ApiError(503, "Epic service unavailable"));
    renderPage("breakdown");
    expect(await screen.findByText("Epic service unavailable")).toBeVisible();
    expect(screen.queryByText("No Epic yet")).not.toBeInTheDocument();
    // A failed Epic read no longer suppresses the Features read; the two are
    // independent requests and the error shown is still the Epic's own.
    expect(api.getFeatures).toHaveBeenCalledTimes(1);
  });

  it("confirms re-analysis without claiming an unloaded backlog count", async () => {
    renderPage("clarify");
    await userEvent.click(await screen.findByRole("button", { name: "Start a new analysis" }));
    expect(screen.getByText(/not saved as a draft or sent is discarded/)).toBeVisible();
    expect(screen.getByText(/remain in revision history/)).toBeVisible();
    expect(api.getEpic).not.toHaveBeenCalled();
    expect(api.getFeatures).not.toHaveBeenCalled();
  });

  it("refreshes a missing analysis token instead of starting the analysis", async () => {
    vi.mocked(api.getRequirement).mockResolvedValue({ ...requirement, analysis_context_token: "" });
    vi.mocked(api.getAnalysis).mockResolvedValue(null);
    const start = vi.spyOn(api, "startAiJob");
    renderPage("clarify");
    await userEvent.click(await screen.findByRole("button", { name: "Analyse this requirement" }));
    expect(await screen.findByText(/This page was out of date and has been refreshed/)).toBeVisible();
    expect(start).not.toHaveBeenCalled();
    await waitFor(() => expect(api.getRequirement).toHaveBeenCalledTimes(2));
  });

  it("reloads the Requirement when the analysis start is refused as changed", async () => {
    vi.mocked(api.getAnalysis).mockResolvedValue(null);
    const start = vi.spyOn(api, "startAiJob").mockRejectedValue(
      new ApiError(409, "The Requirement changed. Reload it.", "stale_generation_context"),
    );
    renderPage("clarify");
    await userEvent.click(await screen.findByRole("button", { name: "Analyse this requirement" }));
    expect(await screen.findByText("The Requirement changed. Reload it.")).toBeVisible();
    expect(start).toHaveBeenCalledWith("req-1", {
      operation: "analyse_requirement", force: false, context_token: "analysis-context",
    }, expect.any(String));
    await waitFor(() => expect(api.getRequirement).toHaveBeenCalledTimes(2));
  });

  it("refreshes Breakdown when returning with a fresh cache", async () => {
    const page = renderPage("breakdown");
    await screen.findByText("No Epic yet");
    page.changeView("clarify");
    await screen.findByRole("button", { name: "Start a new analysis" });
    vi.mocked(api.getEpic).mockResolvedValue(epicFixture);
    vi.mocked(api.getFeatures).mockResolvedValue(featureSetFixture);
    vi.spyOn(api, "listStoryProposals").mockResolvedValue([]);
    page.changeView("breakdown");
    expect((await screen.findAllByRole("link", { name: /Digital ordering/ }))[0]).toBeVisible();
    // Features now tracks the Epic one for one, on both visits to the stage.
    expect(api.getEpic).toHaveBeenCalledTimes(2);
    expect(api.getFeatures).toHaveBeenCalledTimes(2);
  });

  it("displays a genuine Feature read failure", async () => {
    vi.mocked(api.getEpic).mockResolvedValue(epicFixture);
    vi.mocked(api.getFeatures).mockRejectedValue(new ApiError(403, "Feature access denied"));
    renderPage("breakdown");
    expect(await screen.findByText("Feature access denied")).toBeVisible();
    expect(screen.queryByText("No Features yet")).not.toBeInTheDocument();
  });

  it("preserves the normal freshness window when browser focus returns", async () => {
    const { client } = renderPage("breakdown");
    await screen.findByText("No Epic yet");
    await waitFor(() => expect(client.isFetching()).toBe(0));
    focusManager.setFocused(false);
    focusManager.setFocused(true);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(api.getEpic).toHaveBeenCalledTimes(1);
  });
  it("resets artifact drafts when changing requirements within the same app", async () => {
    vi.mocked(api.getEpic).mockResolvedValue(epicFixture);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/requirements/req-1/breakdown"]}>
      <Link to="/requirements/req-1/breakdown">First workspace</Link><Link to="/requirements/req-2/breakdown">Second workspace</Link>
      <Routes><Route path="/requirements/:id/*" element={<RequirementPage view="breakdown" />} /></Routes>
    </MemoryRouter></QueryClientProvider>);
    await userEvent.click(await screen.findByRole("button", { name: /^Edit$/ }));
    await userEvent.clear(screen.getByLabelText("Epic name"));
    await userEvent.type(screen.getByLabelText("Epic name"), "Unsaved first requirement");
    await userEvent.click(screen.getByRole("link", { name: "Second workspace" }));
    expect(await screen.findByRole("heading", { name: epicFixture.name })).toBeVisible();
    expect(screen.queryByLabelText("Epic name")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "First workspace" }));
    await userEvent.click(await screen.findByRole("button", { name: /^Edit$/ }));
    expect(screen.getByLabelText("Epic name")).toHaveValue(epicFixture.name);
  });

});
