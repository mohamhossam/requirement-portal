import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { api, type DocumentSummary, type Requirement, type RequirementDraft } from "../api/client";
import { renderWithClient } from "../test/renderWithClient";
import { DocumentsPage } from "./DocumentsPage";

afterEach(() => vi.restoreAllMocks());

function file(
  id: string,
  filename: string,
  overrides: Partial<DocumentSummary> = {},
  version: Partial<DocumentSummary["current_version"]> = {},
): DocumentSummary {
  return {
    id, version: 1, requirement_id: "requirement-1", draft_id: null, requires_attention: false,
    included_in_analysis: true, included_version_id: null, version_count: 1,
    hidden_worksheets: [], included_hidden_worksheets: [],
    current_version: {
      id: `${id}-v1`, number: 1, filename, mime_type: "application/pdf", size_bytes: 2048,
      checksum_sha256: "a".repeat(64), extraction_status: "ready", extraction_error: null,
      created_at: "2026-09-03T12:00:00Z", analysis_readiness: "ready",
      evidence_summary: { section_count: 1, table_count: 0, image_count: 0, worksheet_count: 0, block_count: 1 },
      extraction_warnings: [],
      ...version,
    },
    ...overrides,
  };
}

const catalogue = [
  file("doc-1", "brief.pdf", {}, { created_at: "2026-09-01T12:00:00Z" }),
  file("doc-2", "contract.docx", { requires_attention: true, included_in_analysis: false }, {
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    analysis_readiness: "blocked", created_at: "2026-09-03T12:00:00Z",
  }),
  file("doc-3", "notes.md", { requirement_id: null, draft_id: "draft-1" }, { mime_type: "text/markdown", created_at: "2026-09-02T12:00:00Z" }),
];

function renderPage() {
  vi.spyOn(api, "listDocuments").mockResolvedValue(catalogue);
  vi.spyOn(api, "getRequirement").mockResolvedValue({ id: "requirement-1", title: "High-speed business bundles" } as Requirement);
  vi.spyOn(api, "listRequirementDrafts").mockResolvedValue([{ id: "draft-1", title: "Invoice discount display" } as RequirementDraft]);
  renderWithClient(<MemoryRouter><DocumentsPage /></MemoryRouter>);
}

const fileNames = () => within(screen.getByRole("table", { name: "Documents" }))
  .getAllByRole("link").filter((link) => link.getAttribute("href")?.startsWith("/documents/"))
  .map((link) => link.textContent);

it("lists each file as a row, newest first, with its type, readiness and owner in words", async () => {
  renderPage();

  expect(await screen.findByRole("link", { name: "contract.docx" })).toHaveAttribute("href", "/documents/doc-2");
  expect(fileNames()).toEqual(["contract.docx", "notes.md", "brief.pdf"]);
  expect(screen.getAllByText(/Word document/).length).toBeGreaterThan(0);
  expect(screen.queryByText(/application\//)).toBeNull();
  expect(screen.getAllByText("Could not be read").length).toBeGreaterThan(0);
  expect((await screen.findAllByRole("link", { name: "High-speed business bundles" }))[0]).toHaveAttribute("href", "/requirements/requirement-1/capture");
  expect((await screen.findAllByRole("link", { name: /Invoice discount display/ }))[0]).toHaveAttribute("href", "/requirements/new?draft=draft-1");
});

it("filters to the files that need a decision, and searches by name", async () => {
  renderPage();
  await screen.findByRole("link", { name: "contract.docx" });

  await userEvent.click(screen.getByRole("button", { name: /Blocks analysis/ }));
  expect(fileNames()).toEqual(["contract.docx"]);

  expect(screen.getByText("Showing 1 of 3")).toBeVisible();
  // One name for the state, on the pill and on the row; it is not also "left out".
  expect(screen.getAllByText("Blocks analysis").length).toBeGreaterThan(1);
  expect(screen.queryByText("Not usable")).toBeNull();
  expect(screen.queryByRole("button", { name: /Left out 2/ })).toBeNull();

  await userEvent.click(screen.getByRole("button", { name: /^All/ }));
  const search = screen.getByRole("searchbox", { name: "Search files and requirements" });
  await userEvent.type(search, "notes");
  expect(fileNames()).toEqual(["notes.md"]);

  // A requirement's name finds its files.
  await userEvent.clear(search);
  await userEvent.type(search, "high-speed");
  expect(fileNames()).toEqual(["contract.docx", "brief.pdf"]);

  await userEvent.clear(search);
  await userEvent.type(search, "nothing like it");
  expect(screen.getByText(/No files match/)).toBeVisible();
});

it("sorts by name from the column header, exposing the direction", async () => {
  renderPage();
  await screen.findByRole("link", { name: "contract.docx" });

  await userEvent.click(screen.getByRole("button", { name: "File" }));
  // The file blocking analysis stays pinned first; the rest sort by name.
  expect(fileNames()).toEqual(["contract.docx", "brief.pdf", "notes.md"]);
  expect(screen.getByRole("columnheader", { name: "File" })).toHaveAttribute("aria-sort", "ascending");
});

it("says how to start when there are no documents", async () => {
  vi.spyOn(api, "listDocuments").mockResolvedValue([]);
  renderWithClient(<MemoryRouter><DocumentsPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "No documents yet" })).toBeVisible();
  expect(screen.getByRole("link", { name: "New requirement" })).toHaveAttribute("href", "/requirements/new");
});

it("filters to one requirement's files", async () => {
  renderPage();
  await screen.findAllByRole("link", { name: "High-speed business bundles" });

  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Attached to" }), "/requirements/new?draft=draft-1");
  expect(fileNames()).toEqual(["notes.md"]);
});

it("tells apart two requirements with the same title in the filter", async () => {
  vi.spyOn(api, "listDocuments").mockResolvedValue([
    file("a", "one.pdf", { requirement_id: "11111111-aaaa" }),
    file("b", "two.pdf", { requirement_id: "22222222-bbbb" }),
  ]);
  vi.spyOn(api, "getRequirement").mockResolvedValue({ title: "Same name" } as Requirement);
  renderWithClient(<MemoryRouter><DocumentsPage /></MemoryRouter>);

  const select = await screen.findByRole("combobox", { name: "Attached to" });
  await screen.findAllByRole("link", { name: "Same name" });
  expect(within(select).getByRole("option", { name: "Same name · 11111111" })).toBeInTheDocument();
  expect(within(select).getByRole("option", { name: "Same name · 22222222" })).toBeInTheDocument();
});
