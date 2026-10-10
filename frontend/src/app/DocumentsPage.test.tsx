import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { api, type DocumentList, type DocumentListItem, type DocumentListParams } from "../api/client";
import { AuthContext, type AuthState } from "../auth/authContext";
import { renderWithClient } from "../test/renderWithClient";
import { DocumentsPage } from "./DocumentsPage";

afterEach(() => vi.restoreAllMocks());

const BUNDLES = { kind: "requirement" as const, id: "requirement-1", title: "High-speed business bundles" };
const INVOICES = { kind: "draft" as const, id: "draft-1", title: "Invoice discount display" };

function file(
  id: string,
  filename: string,
  overrides: Partial<DocumentListItem> = {},
  version: Partial<DocumentListItem["current_version"]> = {},
): DocumentListItem {
  return {
    id, version: 1, requirement_id: "requirement-1", draft_id: null, requires_attention: false,
    included_in_analysis: true, included_version_id: null, version_count: 1,
    hidden_worksheets: [], included_hidden_worksheets: [], owner: BUNDLES,
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
  file("doc-3", "notes.md", { requirement_id: null, draft_id: "draft-1", owner: INVOICES }, {
    mime_type: "text/markdown", created_at: "2026-09-02T12:00:00Z",
  }),
];

const group = (item: DocumentListItem) =>
  item.requires_attention ? "attention" : item.included_in_analysis ? "included" : "excluded";

/** `GET /documents` as the API answers it: filtered, sorted and paged on the server. */
function serve(items: DocumentListItem[]) {
  return vi.spyOn(api, "listDocuments").mockImplementation(async (params: DocumentListParams = {}) => {
    const needle = params.q?.toLowerCase() ?? "";
    const [key, direction] = (params.sort ?? "added_desc").split("_");
    const sign = direction === "asc" ? 1 : -1;
    const rows = items
      .filter((item) => !params.filter || params.filter === "all" || group(item) === params.filter)
      .filter((item) => !params.owner || item.owner.id === params.owner)
      .filter((item) => !needle
        || item.current_version.filename.toLowerCase().includes(needle)
        || Boolean(item.owner.title?.toLowerCase().includes(needle)))
      .sort((a, b) => Number(b.requires_attention) - Number(a.requires_attention) || sign * (key === "name"
        ? a.current_version.filename.localeCompare(b.current_version.filename)
        : a.current_version.created_at.localeCompare(b.current_version.created_at)));
    const offset = params.offset ?? 0;
    const limit = params.limit ?? 50;
    const page = rows.slice(offset, offset + limit);
    const owners = [...new Map(items.map((item) => [item.owner.id, item.owner])).values()]
      .sort((a, b) => (a.title ?? "").localeCompare(b.title ?? ""));
    const count = (wanted: string) => items.filter((item) => group(item) === wanted).length;
    const answer: DocumentList = {
      documents: page, total: rows.length, offset, limit, has_more: offset + page.length < rows.length,
      counts: { attention: count("attention"), included: count("included"), excluded: count("excluded") },
      owners,
    };
    return answer;
  });
}

function renderPage(roles: string[] = [], items = catalogue) {
  const list = serve(items);
  const auth = { actor: { id: "a-1", display_name: "Amina", email: null, roles } } as unknown as AuthState;
  renderWithClient(<AuthContext.Provider value={auth}><MemoryRouter><DocumentsPage /></MemoryRouter></AuthContext.Provider>);
  return list;
}

const fileNames = () => within(screen.getByRole("table", { name: "Documents" }))
  .getAllByRole("link").filter((link) => link.getAttribute("href")?.startsWith("/documents/"))
  .map((link) => link.textContent);

it("lists each file as a row, newest first, with its type, readiness and owner in words", async () => {
  const list = renderPage();

  expect(await screen.findByRole("link", { name: "contract.docx" })).toHaveAttribute("href", "/documents/doc-2");
  expect(fileNames()).toEqual(["contract.docx", "notes.md", "brief.pdf"]);
  expect(list).toHaveBeenCalledWith(
    { q: undefined, filter: "all", owner: undefined, sort: "added_desc", limit: 50, offset: 0 },
    { signal: expect.any(AbortSignal) },
  );
  expect(screen.getAllByText(/Word document/).length).toBeGreaterThan(0);
  expect(screen.queryByText(/application\//)).toBeNull();
  expect(screen.getAllByText("Could not be read").length).toBeGreaterThan(0);
  // The owner's title comes with each file, so no requirement is fetched one by one.
  expect(screen.getAllByRole("link", { name: "High-speed business bundles" })[0]).toHaveAttribute("href", "/requirements/requirement-1/capture");
  expect(screen.getAllByRole("link", { name: /Invoice discount display/ })[0]).toHaveAttribute("href", "/requirements/new?draft=draft-1");
});

it("asks the API for the files that need a decision, and searches by name", async () => {
  const list = renderPage();
  await screen.findByRole("link", { name: "contract.docx" });

  await userEvent.click(screen.getByRole("button", { name: /Blocks analysis/ }));
  await waitFor(() => expect(fileNames()).toEqual(["contract.docx"]));
  expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ filter: "attention" }), expect.anything());

  expect(screen.getByText("Showing 1 of 3")).toBeVisible();
  // One name for the state, on the pill and on the row; it is not also "left out".
  expect(screen.getAllByText("Blocks analysis").length).toBeGreaterThan(1);
  expect(screen.queryByText("Not usable")).toBeNull();
  expect(screen.queryByRole("button", { name: /Left out 2/ })).toBeNull();

  await userEvent.click(screen.getByRole("button", { name: /^All/ }));
  const search = screen.getByRole("searchbox", { name: "Search files and requirements" });
  await userEvent.type(search, "notes");
  await waitFor(() => expect(fileNames()).toEqual(["notes.md"]));
  expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ q: "notes" }), expect.anything());

  // A requirement's name finds its files.
  await userEvent.clear(search);
  await userEvent.type(search, "high-speed");
  await waitFor(() => expect(fileNames()).toEqual(["contract.docx", "brief.pdf"]));

  await userEvent.clear(search);
  await userEvent.type(search, "nothing like it");
  expect(await screen.findByText(/No files match/)).toBeVisible();
});

it("sorts by name from the column header, exposing the direction", async () => {
  const list = renderPage();
  await screen.findByRole("link", { name: "contract.docx" });

  await userEvent.click(screen.getByRole("button", { name: "File" }));
  // The file blocking analysis stays pinned first; the rest sort by name.
  await waitFor(() => expect(fileNames()).toEqual(["contract.docx", "brief.pdf", "notes.md"]));
  expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ sort: "name_asc" }), expect.anything());
  expect(screen.getByRole("columnheader", { name: "File" })).toHaveAttribute("aria-sort", "ascending");
});

it("says how to start when there are no documents", async () => {
  serve([]);
  renderWithClient(<MemoryRouter><DocumentsPage /></MemoryRouter>);

  expect(await screen.findByRole("heading", { name: "No documents yet" })).toBeVisible();
  expect(screen.getByRole("link", { name: "New requirement" })).toHaveAttribute("href", "/requirements/new");
});

it("filters to one requirement's files", async () => {
  const list = renderPage();
  await screen.findAllByRole("link", { name: "High-speed business bundles" });

  await userEvent.selectOptions(screen.getByRole("combobox", { name: "Attached to" }), "draft-1");
  await waitFor(() => expect(fileNames()).toEqual(["notes.md"]));
  expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ owner: "draft-1" }), expect.anything());
});

it("tells apart two requirements with the same title in the filter", async () => {
  serve([
    file("a", "one.pdf", { requirement_id: "11111111-aaaa", owner: { kind: "requirement", id: "11111111-aaaa", title: "Same name" } }),
    file("b", "two.pdf", { requirement_id: "22222222-bbbb", owner: { kind: "requirement", id: "22222222-bbbb", title: "Same name" } }),
  ]);
  renderWithClient(<MemoryRouter><DocumentsPage /></MemoryRouter>);

  const select = await screen.findByRole("combobox", { name: "Attached to" });
  expect(within(select).getByRole("option", { name: "Same name · 11111111" })).toBeInTheDocument();
  expect(within(select).getByRole("option", { name: "Same name · 22222222" })).toBeInTheDocument();
});

it("loads the next page of files on request", async () => {
  const many = Array.from({ length: 52 }, (_, index) =>
    file(`doc-${index}`, `file-${String(index).padStart(2, "0")}.pdf`, {}, {
      created_at: `2026-09-01T12:${String(index).padStart(2, "0")}:00Z`,
    }));
  const list = renderPage([], many);
  await screen.findByRole("link", { name: "file-51.pdf" });
  expect(fileNames()).toHaveLength(50);

  await userEvent.click(screen.getByRole("button", { name: "Load more" }));

  await waitFor(() => expect(fileNames()).toHaveLength(52));
  expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 50 }), expect.anything());
  expect(screen.queryByRole("button", { name: "Load more" })).toBeNull();
});

it("opens the knowledge portal for its admins, and only for them", async () => {
  renderPage(["knowledge_admin"]);
  expect(await screen.findByRole("link", { name: "Open knowledge portal" })).toHaveAttribute("href", "/knowledge/");
});

it("keeps the shared library out of a member's documents", async () => {
  renderPage();
  await screen.findByRole("link", { name: "contract.docx" });
  expect(screen.queryByRole("link", { name: "Open knowledge portal" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /library/i })).not.toBeInTheDocument();
});
