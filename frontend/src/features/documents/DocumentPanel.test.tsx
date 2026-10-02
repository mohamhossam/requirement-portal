import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api, type DocumentDetail, type DocumentSummary } from "../../api/client";
import { DocumentPanel } from "./DocumentPanel";

const version = {
  id: "version-1",
  number: 1,
  filename: "policy.txt",
  mime_type: "text/plain",
  size_bytes: 12,
  checksum_sha256: "a".repeat(64),
  extraction_status: "ready" as const,
  extraction_error: null,
  created_at: "2026-09-03T12:00:00Z",
  analysis_readiness: "ready" as const,
  evidence_summary: { section_count: 1, table_count: 0, image_count: 0, worksheet_count: 0, block_count: 1 },
  extraction_warnings: [],
};
const summary: DocumentSummary = {
  id: "document-1",
  version: 1,
  requirement_id: "requirement-1",
  draft_id: null,
  requires_attention: false,
    included_in_analysis: false,
  included_version_id: null,
  version_count: 1,
  current_version: version,
  hidden_worksheets: [],
  included_hidden_worksheets: [],
};
const detail: DocumentDetail = {
  ...summary,
  versions: [{ ...version, extracted_text: "Policy text", extraction_version: "structured-evidence-v1", evidence_blocks: [] }],
};

function renderPanel(scope: { kind: "requirement" | "draft"; id: string }, businessNeed = false, onStateChange = vi.fn()) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><DocumentPanel scope={scope} businessNeed={businessNeed} onStateChange={onStateChange} /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("DocumentPanel", () => {
  beforeEach(() => {
    vi.spyOn(api, "listAttachmentIngestions").mockResolvedValue([]);
    vi.spyOn(api, "listRequirementDocuments").mockResolvedValue([summary]);
    vi.spyOn(api, "listDraftDocuments").mockResolvedValue([]);
  });
  afterEach(() => vi.restoreAllMocks());

  it("includes and removes requirement evidence through real controls", async () => {
    const include = vi.spyOn(api, "setDocumentInclusion").mockResolvedValue({
      ...detail,
      included_in_analysis: true,
      included_version_id: version.id,
    });
    const remove = vi.spyOn(api, "removeDocument").mockResolvedValue();
    renderPanel({ kind: "requirement", id: "requirement-1" });

    await userEvent.click(await screen.findByRole("checkbox", { name: "Include" }));
    expect(include).toHaveBeenCalledWith("requirement-1", "document-1", true, summary.version);
    await userEvent.click(screen.getByRole("button", { name: "Remove policy.txt" }));
    // Removal asks first, with the safe answer focused.
    const dialog = screen.getByRole("dialog", { name: "Remove policy.txt?" });
    expect(within(dialog).getByRole("button", { name: "Cancel" })).toHaveFocus();
    expect(remove).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove file" }));
    expect(remove).toHaveBeenCalledWith("requirement-1", "document-1", summary.version);
  });

  it("restores processing controls and supports explicit cancel and retry", async () => {
    const queued = { id: "job", version: 1, filename: "queued.txt", stage: "queued" as const, error: null, attached_document_id: null, excluded: false };
    vi.mocked(api.listAttachmentIngestions).mockResolvedValue([queued]);
    const control = vi.spyOn(api, "controlAttachment").mockImplementation(async (_source, _draft, _id, _version, action) => {
      const updated = { ...queued, version: 2, stage: action === "cancellation" ? "cancelled" as const : "queued" as const };
      vi.mocked(api.listAttachmentIngestions).mockResolvedValue([updated]);
      return updated;
    });
    renderPanel({ kind: "requirement", id: "requirement-1" });
    await userEvent.click(await screen.findByRole("button", { name: "Cancel processing queued.txt" }));
    expect(control).toHaveBeenCalledWith("requirement-1", false, "job", 1, "cancellation");
    await userEvent.click(await screen.findByRole("button", { name: "Retry processing queued.txt" }));
    expect(control).toHaveBeenCalledWith("requirement-1", false, "job", 2, "retry");
  });

  it("keeps an extraction failure visible after upload", async () => {
    vi.mocked(api.listDraftDocuments).mockResolvedValue([]);
    const failed = { id: "ingestion", version: 4, filename: "broken.pdf", stage: "failed" as const, error: "PDF text extraction failed.", attached_document_id: null, excluded: false };
    vi.spyOn(api, "submitAttachment").mockImplementation(async () => {
      vi.mocked(api.listAttachmentIngestions).mockResolvedValue([failed]);
      return failed;
    });
    renderPanel({ kind: "draft", id: "draft-1" });

    await userEvent.upload(
      screen.getByLabelText("Add file"),
      new File(["%PDF-corrupt"], "broken.pdf", { type: "application/pdf" }),
    );

    await screen.findByText("PDF text extraction failed.");
    expect(screen.getByRole("button", { name: "Retry processing broken.pdf" })).toBeEnabled();
  });
});


describe("Business need uploads", () => {
  beforeEach(() => { vi.spyOn(api, "listAttachmentIngestions").mockResolvedValue([]); });
  afterEach(() => vi.restoreAllMocks());
  it("uploads multiple files with inclusion enabled and reports usable source", async () => {
    const attached = { ...detail, requires_attention: false, included_in_analysis: true, included_version_id: version.id };
    const list = vi.spyOn(api, "listDraftDocuments").mockResolvedValue([]);
    const upload = vi.spyOn(api, "submitAttachment").mockImplementation(async () => {
      list.mockResolvedValue([attached]); return { id: "ingestion", version: 4, filename: "policy.txt", stage: "ready_for_review", attached_document_id: detail.id, excluded: false, error: null };
    });
    const state = vi.fn();
    renderPanel({ kind: "draft", id: "draft-1" }, true, state);
    const markdown = new File(["# Need"], "need.md", { type: "text/markdown" });
    const image = new File(["image"], "design.png", { type: "image/png" });
    await userEvent.upload(screen.getByLabelText("Attach files"), [markdown, image]);
    await waitFor(() => expect(upload).toHaveBeenCalledTimes(2));
    expect(upload).toHaveBeenNthCalledWith(1, "draft-1", true, markdown, expect.any(String), true, undefined);
    expect(upload).toHaveBeenNthCalledWith(2, "draft-1", true, image, expect.any(String), true, undefined);
    await waitFor(() => expect(state).toHaveBeenLastCalledWith({ hasIncludedAttachment: true, busy: false, blocked: false }));
    expect(screen.getByRole("checkbox", { name: "Include in analysis" })).toBeChecked();
  });

  it("accepts dropped files and retains transport failures until explicit exclusion", async () => {
    vi.spyOn(api, "listDraftDocuments").mockResolvedValue([]);
    const upload = vi.spyOn(api, "submitAttachment").mockRejectedValue(new Error("Storage unavailable"));
    const state = vi.fn();
    renderPanel({ kind: "draft", id: "draft-1" }, true, state);
    const file = new File(["# Need"], "need.md", { type: "text/markdown" });
    await waitFor(() => expect(state).toHaveBeenLastCalledWith({ hasIncludedAttachment: false, busy: false, blocked: false }));
    fireEvent.drop(screen.getByText("Drop files here or use Attach files"), { dataTransfer: { files: [file] } });
    await screen.findByText("Storage unavailable");
    expect(upload).toHaveBeenCalledWith("draft-1", true, file, expect.any(String), true, undefined);
    await waitFor(() => expect(state).toHaveBeenLastCalledWith({ hasIncludedAttachment: false, busy: false, blocked: true }));
    await userEvent.click(screen.getByRole("button", { name: "Dismiss need.md" }));
    await waitFor(() => expect(state).toHaveBeenLastCalledWith({ hasIncludedAttachment: false, busy: false, blocked: false }));
  });

  it("persists explicit exclusion of failed extraction through draft-scoped API", async () => {
    const failed = { ...detail, requires_attention: true, current_version: { ...version, analysis_readiness: "blocked" as const, extraction_status: "failed" as const, extraction_error: "Corrupt image" } };
    const list = vi.spyOn(api, "listDraftDocuments").mockResolvedValue([failed]);
    const exclude = vi.spyOn(api, "setDraftDocumentInclusion").mockImplementation(async () => {
      list.mockResolvedValue([{ ...failed, requires_attention: false }]); return { ...failed, requires_attention: false };
    });
    const state = vi.fn();
    renderPanel({ kind: "draft", id: "draft-1" }, true, state);
    await userEvent.click(await screen.findByRole("button", { name: "Leave out of analysis policy.txt" }));
    expect(exclude).toHaveBeenCalledWith("draft-1", detail.id, false, detail.version);
    await waitFor(() => expect(state).toHaveBeenLastCalledWith({ hasIncludedAttachment: false, busy: false, blocked: false }));
  });
});

describe("attachment labels", () => {
  beforeEach(() => {
    vi.spyOn(api, "listAttachmentIngestions").mockResolvedValue([]);
    vi.spyOn(api, "listRequirementDocuments").mockResolvedValue([summary]);
  });
  afterEach(() => vi.restoreAllMocks());
  it("says what a file holds in words, and nothing for an empty summary", () => {
    renderPanel({ kind: "requirement", id: "requirement-1" });
    return screen.findByText("policy.txt").then(() => {
      expect(screen.getByText("Ready")).toBeVisible();
      expect(screen.getByText("12 B · Version 1 · 1 section")).toBeVisible();
      expect(document.body.textContent).not.toMatch(/_|0 tables|0 images/);
    });
  });
});
