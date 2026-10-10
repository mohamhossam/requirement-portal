import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { api, type OwnedDocumentDetail } from "../api/client";
import { ApiError } from "../api/errors";
import { DocumentDetailPage } from "./DocumentDetailPage";

afterEach(() => vi.restoreAllMocks());

type Version = OwnedDocumentDetail["versions"][number];
type Block = Version["evidence_blocks"][number];

const BUNDLES = { kind: "requirement" as const, id: "requirement-1", title: "High-speed business bundles" };
const INVOICES = { kind: "draft" as const, id: "draft-1", title: "Invoice discount display" };

function sourceDocument(overrides: Partial<OwnedDocumentDetail> = {}, version: Partial<Version> = {}): OwnedDocumentDetail {
  const detail: Version = {
    id: "version-1", number: 1, filename: "evidence.docx",
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    size_bytes: 100, checksum_sha256: "b".repeat(64), extraction_status: "ready",
    extraction_error: null, created_at: "2026-09-03T12:00:00Z",
    extracted_text: '<img src=x onerror="alert(1)">',
    extraction_version: "structured-evidence-v1",
    evidence_summary: { section_count: 1, table_count: 0, image_count: 0, worksheet_count: 0, block_count: 1 },
    extraction_warnings: [],
    analysis_readiness: "ready",
    evidence_blocks: [{ id: "block-1", kind: "paragraph", ordinal: 1, section_path: ["Description"], label: "Description", text: '<img src=x onerror="alert(1)">', asset_id: null }],
    ...version,
  };
  const current: OwnedDocumentDetail["current_version"] = {
    id: detail.id, number: detail.number, filename: detail.filename, mime_type: detail.mime_type,
    size_bytes: detail.size_bytes, checksum_sha256: detail.checksum_sha256,
    extraction_status: detail.extraction_status, extraction_error: detail.extraction_error,
    created_at: detail.created_at, analysis_readiness: detail.analysis_readiness,
    evidence_summary: detail.evidence_summary, extraction_warnings: detail.extraction_warnings,
  };
  return {
    id: "document-1",
    version: 1,
    requirement_id: "requirement-1",
    draft_id: null,
    requires_attention: false,
    included_in_analysis: false,
    included_version_id: null,
    version_count: 1,
    hidden_worksheets: [],
    included_hidden_worksheets: [],
    current_version: current,
    versions: [detail],
    owner: BUNDLES,
    ...overrides,
  };
}

function renderPage(document: OwnedDocumentDetail) {
  vi.spyOn(api, "getDocument").mockResolvedValue(document);
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/documents/document-1"]}>
        <Routes><Route path="/documents/:documentId" element={<DocumentDetailPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

it("renders DOCX and TXT extraction as inert plain text", async () => {
  const rendered = renderPage(sourceDocument());

  expect(await screen.findByText('<img src=x onerror="alert(1)">')).toBeVisible();
  expect(rendered.container.querySelector("img")).toBeNull();
});

it("puts what to check before the decision, and says what including the file means", async () => {
  renderPage(sourceDocument({}, {
    analysis_readiness: "ready_with_warnings",
    extraction_warnings: [{ code: "table", severity: "warning", message: "Verify the table against the original.", block_id: "block-1" }],
  }));

  const card = (await screen.findByRole("heading", { name: "Use in analysis" })).closest("section")!;
  const warning = within(card).getByText(/Verify the table against the original/);
  const decision = within(card).getByRole("checkbox", { name: "Include in analysis" });
  expect(warning.compareDocumentPosition(decision) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(decision).toHaveAccessibleDescription(/sent to the configured AI provider/);
  expect(within(card).getByRole("link", { name: "Show in the file" })).toHaveAttribute("href", "#block-block-1");
  expect(within(card).getByText("Check this")).toBeVisible();
  expect(screen.queryByText("WARNING")).toBeNull();
});

it("names the requirement the file is attached to and the file's type in words", async () => {
  renderPage(sourceDocument());

  expect(await screen.findByRole("link", { name: "High-speed business bundles" })).toHaveAttribute("href", "/requirements/requirement-1/capture");
  expect(screen.getAllByText(/Word document/).length).toBeGreaterThan(0);
  expect(screen.queryByText(/application\/vnd/)).toBeNull();
});

it("lists the outline in the document's own words", async () => {
  const blocks: Block[] = [
    { id: "h-1", kind: "heading", ordinal: 1, section_path: [], label: "Paragraph 1", text: "Eligibility", asset_id: null },
    { id: "p-1", kind: "paragraph", ordinal: 2, section_path: [], label: "Paragraph 2", text: "Only covered areas qualify.", asset_id: null },
    { id: "h-2", kind: "heading", ordinal: 3, section_path: [], label: "Paragraph 3", text: "Launch", asset_id: null },
  ];
  renderPage(sourceDocument({}, { evidence_blocks: blocks }));

  const outline = await screen.findByRole("navigation", { name: "Document outline" });
  expect(within(outline).getByRole("heading", { name: "Outline" })).toBeVisible();
  expect(within(outline).getByRole("link", { name: /Eligibility/ })).toHaveAttribute("href", "#block-h-1");
});

it("offers the hidden worksheets, and changes the selection through the existing call", async () => {
  const setHidden = vi.spyOn(api, "setHiddenWorksheetInclusion").mockResolvedValue(sourceDocument());
  renderPage(sourceDocument({ hidden_worksheets: ["Margin model"] }));

  await userEvent.click(await screen.findByRole("checkbox", { name: "Margin model" }));
  expect(setHidden).toHaveBeenCalledWith("requirement-1", "document-1", ["Margin model"], 1);
});

it("says a left-out file's passages are what analysis would read, not what it reads", async () => {
  renderPage(sourceDocument());

  expect(await screen.findByRole("heading", { name: "What analysis would read" })).toBeVisible();
  expect(screen.getByText(/nothing below is sent/)).toBeVisible();
  expect(screen.getByText("None, it is left out")).toBeVisible();
});

it("names the version analysis reads", async () => {
  const v1 = sourceDocument().versions[0]!;
  renderPage(sourceDocument(
    { included_in_analysis: true, included_version_id: "version-1", version_count: 2,
      versions: [v1, { ...v1, id: "version-2", number: 2 }] },
    { id: "version-2", number: 2 },
  ));

  expect(await screen.findByText("Used by analysis")).toBeVisible();
  expect(screen.getByText("Version 1", { selector: "dd" })).toBeVisible();
});

it("says a missing document is missing, without its id or a retry", async () => {
  vi.spyOn(api, "getDocument").mockRejectedValue(new ApiError(404, "Document '00000000' not found"));
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/documents/missing"]}>
        <Routes><Route path="/documents/:documentId" element={<DocumentDetailPage />} /></Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByRole("heading", { name: "This document isn’t here" })).toBeVisible();
  expect(screen.queryByText(/00000000/)).toBeNull();
  expect(screen.queryByRole("button", { name: /Try again/ })).toBeNull();
});

it("tells a person what to do with a file that could not be read, and offers no include box", async () => {
  renderPage(sourceDocument({ requires_attention: true }, {
    analysis_readiness: "blocked", extraction_status: "failed", extraction_error: "DOCX extraction produced no usable text.",
    evidence_blocks: [],
  }));

  expect(await screen.findByText("Nothing in this file could be read.")).toBeVisible();
  expect(screen.getByText(/It blocks analysis of this requirement until you/)).toBeVisible();
  // The fix is inside the card, as the page's one primary action.
  expect(screen.getByRole("button", { name: "Upload a readable version" })).toBeVisible();
  expect(screen.getByRole("button", { name: "Leave out of analysis" })).toBeVisible();
  // The reader's own words are kept, behind a disclosure.
  expect(screen.getByText("What the reader reported")).toBeVisible();
  expect(screen.getByText("DOCX extraction produced no usable text.")).toBeInTheDocument();
  expect(screen.queryByRole("checkbox", { name: "Include in analysis" })).toBeNull();
  expect(screen.queryByRole("heading", { name: "What analysis reads" })).toBeNull();
});

it("sends a draft's file back to the draft for the decision", async () => {
  renderPage(sourceDocument({ requirement_id: null, draft_id: "draft-1", owner: INVOICES }));

  expect(await screen.findByRole("link", { name: "Open the draft" })).toHaveAttribute("href", "/requirements/new?draft=draft-1");
  expect(screen.getByText("Left out on the draft.")).toBeVisible();
  expect(screen.queryByRole("checkbox", { name: "Include in analysis" })).toBeNull();
});

it("keeps notes on how a file type is read out of what to check, and calls the file ready", async () => {
  renderPage(sourceDocument({}, {
    analysis_readiness: "ready_with_warnings",
    extraction_warnings: [{ code: "word_prose_structure", severity: "warning", message: "Word headings use neutral paragraph locations.", block_id: null }],
  }));

  const card = (await screen.findByRole("heading", { name: "Use in analysis" })).closest("section")!;
  expect(within(card).getByText("Ready")).toBeVisible();
  expect(within(card).queryByRole("heading", { name: /What to check/ })).toBeNull();
  expect(within(card).getByText("How this file type is read (1)")).toBeVisible();
});

it("names hidden sheets by their own title and marks their passages as not sent", async () => {
  const blocks: Block[] = [
    { id: "s-1", kind: "heading", ordinal: 1, section_path: ["Worksheet 1"], label: "Worksheet 1", text: "Price list", asset_id: null },
    { id: "r-1", kind: "worksheet_range", ordinal: 2, section_path: ["Worksheet 1"], label: "Worksheet 1!1:1", text: "A1=Plan | B1=Monthly", asset_id: null },
    { id: "r-2", kind: "worksheet_range", ordinal: 3, section_path: ["Worksheet 1"], label: "Worksheet 1!2:2", text: "A2=Starter | B2=29", asset_id: null },
    { id: "s-2", kind: "heading", ordinal: 4, section_path: ["Hidden worksheet: Worksheet 2"], label: "Hidden worksheet: Worksheet 2", text: "Margin model", asset_id: null },
    { id: "r-3", kind: "worksheet_range", ordinal: 5, section_path: ["Hidden worksheet: Worksheet 2"], label: "Worksheet 2!1:1", text: "A1=Plan | B1=Margin", asset_id: null },
  ];
  const rendered = renderPage(sourceDocument({ hidden_worksheets: ["Worksheet 2"] }, { evidence_blocks: blocks }));

  expect(await screen.findByRole("checkbox", { name: "Margin model" })).toHaveAccessibleDescription("Worksheet 2 in the workbook");
  expect(screen.getAllByText("Not sent · hidden sheet")).toHaveLength(2);
  // The visible sheet's rows are a table, and the passage anchor survives on its first row.
  const table = screen.getByRole("table", { name: "Worksheet 1, rows 1–2" });
  expect(within(table).getByRole("columnheader", { name: "B" })).toBeVisible();
  expect(within(table).getByRole("cell", { name: "Starter" })).toBeVisible();
  expect(rendered.container.querySelector("#block-r-2")?.tagName).toBe("TR");
});

it("shows what analysis reads from a PDF beside the original", async () => {
  vi.spyOn(api, "getDocumentPdf").mockResolvedValue(new Blob(["%PDF"], { type: "application/pdf" }));
  const original = { create: URL.createObjectURL, revoke: URL.revokeObjectURL };
  URL.createObjectURL = () => "blob:pdf";
  URL.revokeObjectURL = () => undefined;
  try {
    renderPage(sourceDocument({ included_in_analysis: true, included_version_id: "version-1" }, { mime_type: "application/pdf", filename: "rules.pdf" }));

    expect(await screen.findByRole("heading", { name: "Original" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "What analysis reads" })).toBeVisible();
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeVisible();
  } finally {
    URL.createObjectURL = original.create;
    URL.revokeObjectURL = original.revoke;
  }
});
