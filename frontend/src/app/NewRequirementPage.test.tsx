import { jobFixture } from "../test/jobFixture";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, type DocumentDetail, type Requirement, type RequirementDraft } from "../api/client";
import { NewRequirementPage } from "./NewRequirementPage";

function renderPage(initialEntry = "/requirements/new") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/" element={<p>Dashboard opened</p>} />
          <Route path="/requirements/new" element={<NewRequirementPage />} />
          <Route path="/requirements/:id/*" element={<p>Review workspace opened</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("NewRequirementPage", () => {
  const draft: RequirementDraft = {
    id: "draft-1",
    title: "",
    description: "",
    desired_outcome: "",
    customer_context: "",
    channels: [],
    systems: [],
    business_rules: [],
    constraints: [],
    version: 1,
    updated_at: "2026-09-03T08:00:00Z",
    analysis_eligibility: { eligible: false, missing_fields: ["title", "description"] },
  };
  const requirement = (id: string, title: string, description: string): Requirement => ({
    id,
    title,
    description,
    desired_outcome: "Observable outcome",
    customer_context: null,
    channels: [],
    systems: [],
    business_rules: [],
    constraints: [],
    version: 1,
    updated_at: null,
    status: "draft",
    analysis_context_token: "generation-context-v2:analysis",
    analysis_eligibility: { eligible: true, missing_fields: [] },
  });

  beforeEach(() => {
    vi.spyOn(api, "listAttachmentIngestions").mockResolvedValue([]);
    vi.spyOn(api, "listRequirementDrafts").mockResolvedValue([]);
    vi.spyOn(api, "getRequirementDraft").mockResolvedValue(draft);
    vi.spyOn(api, "listDraftDocuments").mockResolvedValue([]);
    vi.spyOn(api, "createRequirementDraft").mockResolvedValue(draft);
    vi.spyOn(api, "saveRequirementDraft").mockImplementation(async (_id, input, version) => ({
      ...draft,
      ...input,
      version: version + 1,
      analysis_eligibility: { eligible: true, missing_fields: [] },
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it("puts a complete worked example beside the form, and says what happens next", async () => {
    renderPage();

    expect(screen.getByRole("heading", { level: 1, name: "New requirement" })).toBeVisible();
    // docs/ux-plan.md §3.12: the example sat after the form, behind a closed
    // <details>, for the one user who most needs it. Now it is beside the form
    // (the Help menu links to #example) and every field is shown filled in.
    const example = screen.getByRole("complementary", { name: "An example, filled in" });
    expect(example).toHaveAttribute("id", "example");
    for (const label of ["Requirement title", "Business need", "Desired outcome", "Who is affected", "Channels",
      "Systems involved", "Rules that must hold", "Deadlines and limits"]) {
      expect(within(example).getByText(label)).toBeInTheDocument();
    }
    expect(within(example).getByText(/Nothing is generated until you confirm it/)).toBeInTheDocument();
    // No numbered sections ("01 Describe the need").
    expect(screen.queryByText(/^0[123]$/)).not.toBeInTheDocument();
  });

  it("says why analysis cannot start, beside the button, and the button explains itself", async () => {
    const promote = vi.spyOn(api, "promoteRequirementDraft");
    renderPage();
    const readiness = await screen.findByText("Not ready for analysis");
    expect(readiness.closest("p")).toHaveTextContent("Add a title and describe the need.");
    const analyse = screen.getByRole("button", { name: "Save and analyse" });
    // Pressable, not disabled: pressing it names what is missing, beside each field.
    expect(analyse).not.toBeDisabled();
    await userEvent.click(analyse);
    expect(await screen.findByRole("group", { name: "Check the requirement details" }))
      .toHaveTextContent("Add a short title for this requirement.");
    expect(promote).not.toHaveBeenCalled();
  });

  it("resumes an attachment-only draft and waits for files before analysis", async () => {
    vi.mocked(api.getRequirementDraft).mockResolvedValue({ ...draft, title: "Design source" });
    let finishDocuments: (documents: DocumentDetail[]) => void = () => undefined;
    vi.mocked(api.listDraftDocuments).mockImplementationOnce(() => new Promise((resolve) => { finishDocuments = resolve; }));
    vi.spyOn(api, "promoteRequirementDraft").mockResolvedValue(requirement("req-design", "Design source", ""));
    vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    renderPage("/requirements/new?draft=draft-1");
    expect(await screen.findByLabelText(/Requirement title/)).toHaveValue("Design source");
    // Files still processing: gated by the readiness line beside it, not disabled.
    await waitFor(() => expect(screen.getByRole("button", { name: "Save and analyse" })).toHaveAttribute("aria-disabled", "true"));
    expect(screen.getByRole("button", { name: "Save and analyse" })).toHaveAccessibleDescription(/Files are still processing/);
    finishDocuments([{
      id: "document-1", version: 2, requirement_id: null, draft_id: "draft-1", requires_attention: false,
      included_in_analysis: true, included_version_id: "version-1", version_count: 1,
      hidden_worksheets: [], included_hidden_worksheets: [], versions: [],
      current_version: { id: "version-1", number: 1, filename: "design.png", mime_type: "image/png", size_bytes: 100,
        checksum_sha256: "a".repeat(64), extraction_status: "ready", extraction_error: null,
        created_at: draft.updated_at, analysis_readiness: "ready", extraction_warnings: [],
        evidence_summary: { section_count: 0, table_count: 0, image_count: 1, worksheet_count: 0, block_count: 1 } },
    }]);
    await screen.findByText("Ready for analysis");
    expect(screen.getByLabelText(/Business need/)).toHaveValue("");
    await userEvent.click(screen.getByRole("button", { name: "Save and analyse" }));
    expect(await screen.findByText("Review workspace opened")).toBeVisible();
    expect(api.promoteRequirementDraft).toHaveBeenCalledWith("draft-1", 1);
  });

  it("starts blank even when an older draft exists", async () => {
    const olderDraft = { ...draft, id: "draft-older", title: "Existing requirement" };
    vi.mocked(api.listRequirementDrafts).mockResolvedValue([olderDraft]);
    localStorage.setItem("activeRequirementDraftId", olderDraft.id);

    renderPage();

    expect(await screen.findByLabelText(/Requirement title/)).toHaveValue("");
    expect(api.listRequirementDrafts).not.toHaveBeenCalled();
    expect(api.getRequirementDraft).not.toHaveBeenCalled();
  });

  it("resumes a draft only from an explicit resume link", async () => {
    vi.mocked(api.getRequirementDraft).mockResolvedValue({
      ...draft,
      id: "draft-resume",
      title: "Explicitly resumed requirement",
    });

    renderPage("/requirements/new?draft=draft-resume");

    expect(await screen.findByLabelText(/Requirement title/)).toHaveValue(
      "Explicitly resumed requirement",
    );
    expect(api.getRequirementDraft).toHaveBeenCalledWith("draft-resume");
  });

  it("keeps the form interactive while autosave is running", async () => {
    let finishCreate: (value: RequirementDraft) => void = () => undefined;
    vi.mocked(api.createRequirementDraft).mockImplementationOnce(
      () => new Promise((resolve) => { finishCreate = resolve; }),
    );
    renderPage();
    const title = await screen.findByLabelText(/Requirement title/);

    await userEvent.type(title, "A genuinely new requirement");
    await waitFor(() => expect(api.createRequirementDraft).toHaveBeenCalledTimes(1));

    expect(title).toHaveFocus();
    expect(title).toHaveValue("A genuinely new requirement");
    expect(screen.getByText("Not ready for analysis")).toBeVisible();

    finishCreate({ ...draft, title: "A genuinely new requirement" });
    expect(await screen.findByText(/^Saved /)).toBeVisible();
  });

  it("serializes upload preparation behind an in-flight draft autosave", async () => {
    let finishCreate: (saved: RequirementDraft) => void = () => undefined;
    vi.mocked(api.createRequirementDraft).mockImplementationOnce(() => new Promise((resolve) => { finishCreate = resolve; }));
    const upload = vi.spyOn(api, "submitAttachment").mockRejectedValue(new Error("Synthetic upload failure"));
    renderPage();
    await userEvent.type(await screen.findByLabelText(/Requirement title/), "One draft");
    await waitFor(() => expect(api.createRequirementDraft).toHaveBeenCalledTimes(1));
    await userEvent.upload(screen.getByLabelText("Attach files", { exact: true }), new File(["Need"], "need.md", { type: "text/markdown" }));
    expect(upload).not.toHaveBeenCalled();
    finishCreate({ ...draft, title: "One draft" });
    await screen.findByText("Synthetic upload failure");
    expect(api.createRequirementDraft).toHaveBeenCalledTimes(1);
    expect(upload).toHaveBeenCalledWith("draft-1", true, expect.any(File), expect.any(String), true, undefined);
  });

  it("saves, analyses, and opens the requirement workspace", async () => {
    vi.spyOn(api, "promoteRequirementDraft").mockResolvedValue(
      requirement("req-created-1234", "High-speed bundles", "Make eligible bundles orderable."),
    );
    vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    renderPage();

    await userEvent.type(await screen.findByLabelText(/Requirement title/), "High-speed bundles");
    await userEvent.type(
      screen.getByLabelText(/Business need/),
      "Make eligible bundles orderable.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Save and analyse" }));

    expect(await screen.findByText("Review workspace opened")).toBeVisible();
    expect(localStorage.getItem("lastRequirementId")).toBe("req-created-1234");
    expect(api.startAiJob).toHaveBeenCalledWith("req-created-1234", {
      operation: "analyse_requirement",
      context_token: "generation-context-v2:analysis",
      force: false,
    });
  });

  it("keeps the saved requirement available when analysis fails", async () => {
    vi.spyOn(api, "promoteRequirementDraft").mockResolvedValue(
      requirement("req-safe-1234", "Safe draft", "A preserved source."),
    );
    vi.spyOn(api, "startAiJob").mockRejectedValue(new Error("provider offline"));
    renderPage();
    await userEvent.type(await screen.findByLabelText(/Requirement title/), "Safe draft");
    await userEvent.type(screen.getByLabelText(/Business need/), "A preserved source.");
    await userEvent.click(screen.getByRole("button", { name: "Save and analyse" }));
    expect(await screen.findByRole("heading", { name: /Nothing was lost/ })).toBeVisible();
    expect(screen.getByRole("link", { name: "Open saved requirement" })).toHaveAttribute("href", "/requirements/req-safe-1234/capture");
    expect(screen.getByRole("button", { name: "Retry analysis" })).toBeVisible();
  });

  it("saves a draft without starting analysis", async () => {
    const analyse = vi.spyOn(api, "startAiJob");
    renderPage();
    await userEvent.type(await screen.findByLabelText(/Requirement title/), "Draft source");
    await userEvent.type(screen.getByLabelText(/Business need/), "Save this only.");
    await userEvent.click(screen.getByRole("button", { name: "Save draft and exit" }));
    expect(await screen.findByText("Dashboard opened")).toBeVisible();
    expect(analyse).not.toHaveBeenCalled();
  });

  it("announces an autosave failure and lets the author retry", async () => {
    const create = vi.mocked(api.createRequirementDraft);
    create.mockRejectedValueOnce(new Error("offline"));
    renderPage();

    await userEvent.type(await screen.findByLabelText(/Requirement title/), "Recoverable draft");
    expect(await screen.findByText(/Draft save failed/, {}, { timeout: 2500 })).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: /Retry save/ }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/^Saved /)).toBeVisible();
  });
});
