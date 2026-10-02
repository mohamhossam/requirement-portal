import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { api, type LibraryDocument, type ReferenceChunk } from "../api/client";
import { LibraryPage } from "./LibraryPage";

afterEach(() => vi.restoreAllMocks());

it("labels unified results and clears them when the query changes", async () => {
  vi.spyOn(api, "listLibrary").mockResolvedValue([]);
  vi.spyOn(api, "searchUnifiedKnowledge").mockResolvedValue([{
    source_type: "requirement", source_id: "req-1", title: "Requirement · business need",
    excerpt: "SMB bundle ordering", evidence_path: "/requirements/req-1/capture",
    requirement_evidence: null, reference_evidence: null,
  }]);
  const user = userEvent.setup();
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><LibraryPage /></MemoryRouter>
  </QueryClientProvider>);
  await user.selectOptions(screen.getByLabelText("Search in"), "all");
  await user.type(screen.getByLabelText("Search text"), "bundles");
  await user.click(screen.getByRole("button", { name: "Search knowledge" }));
  expect(await screen.findByText("Requirement evidence")).toBeVisible();
  expect(screen.getByRole("link", { name: "Requirement · business need" })).toHaveAttribute("href", "/requirements/req-1/capture");
  await user.type(screen.getByLabelText("Search text"), " new");
  expect(screen.queryByRole("region", { name: "Unified search results" })).not.toBeInTheDocument();
});

it("keeps the exact citation distinct from bounded surrounding context", async () => {
  const chunk: ReferenceChunk = {
    id: "chunk-1",
    document_id: "document-1",
    document_title: "Eligibility policy",
    version_id: "version-1",
    version_number: 1,
    revision_id: "revision-1",
    publication_id: "publication-1",
    approval_fingerprint: "a".repeat(64),
    parent_id: "parent-1",
    block_id: "block-2",
    heading_path: ["Eligibility"],
    location: "Line 2",
    original_text: "XGPON coverage is required.",
    search_text: "Eligibility policy XGPON coverage is required.",
    content_hash: "b".repeat(64),
    language: "en",
    token_count: 48,
    chunking_policy: "structure-512-768-v1",
    start_offset: 0,
    end_offset: 28,
    context_text: "Line 1\nEligibility\n\nLine 2\nXGPON coverage is required.",
    context_locations: ["Line 1", "Line 2"],
    context_token_count: 76,
    child_strategy: "passage",
    field_context: "",
  };
  vi.spyOn(api, "listLibrary").mockResolvedValue([]);
  vi.spyOn(api, "searchKnowledge").mockResolvedValue([chunk]);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/documents/library"]}>
        <LibraryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await user.type(screen.getByLabelText("Search text"), "XGPON");
  await user.click(screen.getByRole("button", { name: "Search published passages" }));

  expect(await screen.findByText("Exact citable passage")).toBeVisible();
  expect(screen.getByText("XGPON coverage is required.")).toBeVisible();
  expect(screen.getByText(/Surrounding approved context · 2 passages/)).toBeVisible();
  expect(screen.getByText(/Line 1\s+Eligibility/)).toBeInTheDocument();
});

function readyBuildDocument(): LibraryDocument {
  const actor = { id: { value: "owner" }, display_name: "Policy owner" };
  const at = "2026-09-21T12:00:00Z";
  const publication = {
    id: "build", version_id: "file", revision_id: "review", fingerprint: "a".repeat(64),
    approved_by: actor, approved_at: at, chunking_policy: "table-fields-512-768-v2",
    built_at: at, chunk_count: 1, chunk_manifest: "b".repeat(64), requires_activation: true,
    indexing_attempts: 1, index_identity: "test-model:table-v2", replaces_publication_id: "old",
  };
  return {
    id: "policy", title: "Coverage policy", owner: actor, version: 7, can_edit: true,
    review_fingerprint: "c".repeat(64), build_fingerprint: "a".repeat(64), published_id: "old",
    publications: [{ ...publication, id: "old", activated_at: at, requires_activation: false }, publication],
    versions: [{
      id: "file", number: 1, filename: "policy.txt", mime_type: "text/plain", size_bytes: 20,
      checksum: "f".repeat(64), uploaded_at: at, uploaded_by: actor, idempotency_key: "upload",
      stage: "ready_for_review", attempt: 1, assets: [], warning_details: [], warnings: [], blocking_warnings: [],
      blocks: [{ id: "block", ordinal: 1, kind: "paragraph", section_path: [], label: "Line 1", content_fingerprint: "e".repeat(64), text: "Coverage required." }],
      revisions: [{ id: "review", created_at: at, created_by: actor, explanation: "Checked", passages: [{ block_id: "block", text: "Coverage required.", included: true, exclusion_reason: "" }] }],
    }],
  };
}

function renderReadyBuild(document: LibraryDocument) {
  vi.spyOn(api, "listLibrary").mockResolvedValue([document]);
  vi.spyOn(api, "getLibraryDocument").mockResolvedValue(document);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/documents/library/policy"]}>
    <Routes><Route path="/documents/library/:libraryId" element={<LibraryPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>);
}

it("requires a handover acknowledgement and preserves unsaved reviews", async () => {
  const document = readyBuildDocument();
  renderReadyBuild(document);
  vi.spyOn(api, "searchActors").mockResolvedValue([{ id: "next-owner", display_name: "Next owner", email: null }]);
  vi.spyOn(api, "libraryOwnershipHistory").mockResolvedValue([]);
  const transfer = vi.spyOn(api, "transferLibraryOwnership").mockRejectedValue(new Error("Document changed. Reload before transferring."));
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Manage ownership" }));
  await user.selectOptions(await screen.findByLabelText("New document owner"), "next-owner");
  await user.type(screen.getByLabelText("Reason for ownership transfer"), "New custodian");
  const button = screen.getByRole("button", { name: "Transfer ownership" });
  expect(button).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: "I understand that I will lose private access and management of this document." }));
  expect(button).toBeEnabled();
  await user.click(button);
  expect(transfer).toHaveBeenCalledWith(document, "next-owner", "New custodian");
  expect(await screen.findByText("Document changed. Reload before transferring.")).toBeVisible();
  await user.type(screen.getByRole("textbox", { name: "Reviewed text" }), "Unsaved correction");
  expect(button).toBeDisabled();
  expect(screen.getByText("Save your passage changes before transferring ownership.")).toBeVisible();
});

it("loads dependency details on demand and explains stale rejected history", async () => {
  const document = readyBuildDocument();
  renderReadyBuild(document);
  const dependencies = vi.spyOn(api, "libraryDependencies").mockResolvedValue({ next_offset: null, items: [{
    requirement_id: "req", requirement_title: "Order coverage", analysis_id: "analysis", round_number: 1,
    current_analysis: false, proposal_id: "proposal", statement: "Check coverage", status: "rejected", publication_current: false,
    citation: { document_id: "policy", title: "Coverage policy", version_id: "file", version_number: 1,
      revision_id: "review", publication_id: "old", approval_fingerprint: "a".repeat(64), block_id: "block",
      location: "Line 1", excerpt: "Coverage required.", start_offset: 0, end_offset: 18, lineage_hash: "b".repeat(64) },
  }] });
  const user = userEvent.setup();
  const open = await screen.findByRole("button", { name: "View dependencies" });
  expect(dependencies).not.toHaveBeenCalled();
  await user.click(open);
  expect(await screen.findByRole("link", { name: "Order coverage" })).toHaveAttribute("href", "/requirements/req/clarify");
  expect(screen.getByText("Historical analysis · Round 1 · Rejected")).toBeVisible();
  expect(screen.getByText(/Cited publication was withdrawn or replaced/)).toBeVisible();
  expect(screen.queryByText(/Reconcile this reference in the Requirement/)).not.toBeInTheDocument();
  await user.click(screen.getByText("Recorded citation"));
  expect(screen.getByText(/Publication: old/)).toBeVisible();
});

it("clears the handover recipient and acknowledgement when searching again", async () => {
  renderReadyBuild(readyBuildDocument());
  vi.spyOn(api, "searchActors").mockResolvedValueOnce([{ id: "next-owner", display_name: "Next owner", email: null }]).mockRejectedValue(new Error("User search unavailable"));
  vi.spyOn(api, "libraryOwnershipHistory").mockResolvedValue([]);
  const transfer = vi.spyOn(api, "transferLibraryOwnership");
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Manage ownership" }));
  await user.selectOptions(await screen.findByLabelText("New document owner"), "next-owner");
  await user.type(screen.getByLabelText("Reason for ownership transfer"), "New custodian");
  const acknowledgement = screen.getByRole("checkbox", { name: "I understand that I will lose private access and management of this document." });
  await user.click(acknowledgement);
  const button = screen.getByRole("button", { name: "Transfer ownership" });
  expect(button).toBeEnabled();
  await user.type(screen.getByLabelText("Find a workspace user"), "other");
  expect(button).toBeDisabled();
  expect(acknowledgement).not.toBeChecked();
  expect(await screen.findByText("User search unavailable")).toBeVisible();
  await user.click(acknowledgement);
  await user.click(button);
  expect(transfer).not.toHaveBeenCalled();
});

it("requires acknowledgement and submits the exact ready manifest", async () => {
  const document = readyBuildDocument();
  renderReadyBuild(document);
  const activate = vi.spyOn(api, "activateLibraryBuild").mockResolvedValue(document);
  const user = userEvent.setup();
  const button = await screen.findByRole("button", { name: "Activate built version" });
  expect(button).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: "I understand that previous citations will need reconciliation." }));
  await user.click(button);
  expect(activate).toHaveBeenCalledWith(document, "build", "b".repeat(64));
});

it("preserves unsaved passage text and blocks activation even after acknowledgement", async () => {
  renderReadyBuild(readyBuildDocument());
  const activate = vi.spyOn(api, "activateLibraryBuild");
  const user = userEvent.setup();
  await screen.findByRole("button", { name: "Activate built version" });
  await user.click(screen.getByRole("checkbox", { name: "I understand that previous citations will need reconciliation." }));
  const text = screen.getByRole("textbox", { name: "Reviewed text" });
  await user.clear(text);
  await user.type(text, "My unsaved correction");
  expect(screen.getByRole("button", { name: "Activate built version" })).toBeDisabled();
  expect(screen.getByText("Save your passage changes before previewing, building or activating.")).toBeVisible();
  expect(text).toHaveValue("My unsaved correction");
  await user.upload(screen.getByLabelText("Replacement file"), new File(["Replacement"], "replacement.txt", { type: "text/plain" }));
  expect(screen.getByRole("button", { name: "Upload new immutable version" })).toBeDisabled();
  expect(screen.getByText("Save your passage changes before uploading a replacement. Your unsaved review stays on this page.")).toBeVisible();
  expect(activate).not.toHaveBeenCalled();
});
