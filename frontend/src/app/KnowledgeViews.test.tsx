import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../api/errors";
import { knowledgeApi, type CitedPassage } from "../api/knowledge";
import { AuthContext, type AuthState } from "../auth/authContext";
import { ArchitectureEvidencePage } from "./ArchitectureEvidencePage";
import { LegacyEvidenceLink, LegacyLibraryLink } from "./legacyKnowledgeLinks";
import { ReferencePassagePage } from "./ReferencePassagePage";

afterEach(() => vi.restoreAllMocks());

const passage: CitedPassage = {
  document_id: "doc-1", publication_id: "pub-1", version_id: "v-1", revision_id: "r-1", block_id: "b-1",
  title: "Coverage policy", version_number: 3, section_path: ["Eligibility", "Fibre"], label: "Paragraph 2",
  text: "Coverage is confirmed before an order is accepted.",
};
const citationQuery = "document=doc-1&publication=pub-1&version=v-1&revision=r-1&passage=b-1";

function signedIn(roles: string[]) {
  return { actor: { id: "a-1", display_name: "Amina", email: null, roles } } as unknown as AuthState;
}

/** Where a redirect landed, so a test can read it. */
function Landed() {
  const { pathname, search } = useLocation();
  return <output aria-label="Landed at">{pathname + search}</output>;
}

function mount(path: string, routes: ReactNode, roles: string[] = []) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <AuthContext.Provider value={signedIn(roles)}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            {routes}
            <Route path="*" element={<Landed />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </AuthContext.Provider>,
  );
}

const passageRoute = <Route path="/references/passage" element={<ReferencePassagePage />} />;
const evidenceRoute = <Route path="/architecture-evidence/:releaseId/:chunkId" element={<ArchitectureEvidencePage />} />;

describe("ReferencePassagePage", () => {
  it("shows the exact published passage a link cites", async () => {
    const read = vi.spyOn(knowledgeApi, "passage").mockResolvedValue(passage);
    mount(`/references/passage?${citationQuery}`, passageRoute);

    const card = await screen.findByRole("region", { name: "Cited published passage" });
    expect(card).toHaveTextContent("Published version 3 · Eligibility / Fibre · Paragraph 2");
    expect(card).toHaveTextContent("Coverage is confirmed before an order is accepted.");
    expect(screen.getByRole("heading", { level: 1, name: "Coverage policy" })).toBeVisible();
    expect(read).toHaveBeenCalledWith({
      document_id: "doc-1", publication_id: "pub-1", version_id: "v-1", revision_id: "r-1", block_id: "b-1",
    });
  });

  it("says so, without asking, when the link does not name a whole citation", () => {
    const read = vi.spyOn(knowledgeApi, "passage");
    mount("/references/passage?document=doc-1&publication=pub-1", passageRoute);

    expect(screen.getByText(/does not name a complete citation/)).toBeVisible();
    expect(read).not.toHaveBeenCalled();
  });

  it("explains a withdrawn or replaced publication instead of showing old text", async () => {
    vi.spyOn(knowledgeApi, "passage").mockRejectedValue(
      new ApiError(404, "This publication is no longer live.", "knowledge_view_unavailable"),
    );
    mount(`/references/passage?${citationQuery}`, passageRoute);

    expect(await screen.findByText("We couldn’t show this passage")).toBeVisible();
    expect(screen.queryByRole("region", { name: "Cited published passage" })).not.toBeInTheDocument();
  });

  it("does not offer the knowledge portal to anyone else", async () => {
    vi.spyOn(knowledgeApi, "passage").mockResolvedValue(passage);
    mount(`/references/passage?${citationQuery}`, passageRoute);
    await screen.findByRole("region", { name: "Cited published passage" });
    expect(screen.queryByRole("link", { name: "Knowledge portal" })).not.toBeInTheDocument();
  });

  it("links knowledge admins to the portal", async () => {
    vi.spyOn(knowledgeApi, "passage").mockResolvedValue(passage);
    mount(`/references/passage?${citationQuery}`, passageRoute, ["knowledge_admin"]);
    expect(await screen.findByRole("link", { name: "Knowledge portal" })).toHaveAttribute("href", "/knowledge/");
  });
});

describe("ArchitectureEvidencePage", () => {
  it("shows the catalogue passage a mapping cited, from the version it used", async () => {
    const read = vi.spyOn(knowledgeApi, "evidence").mockResolvedValue({
      id: "chunk-1", source_label: "BSCS overview", location: "Section 2", text: "BSCS rates usage.",
    });
    mount("/architecture-evidence/rel-2/chunk-1", evidenceRoute);

    const card = await screen.findByRole("region", { name: "Cited passage" });
    expect(card).toHaveTextContent("BSCS overview · Section 2 · version rel-2");
    expect(card).toHaveTextContent("BSCS rates usage.");
    expect(read).toHaveBeenCalledWith("rel-2", "chunk-1");
    expect(screen.queryByRole("link", { name: "Knowledge portal" })).not.toBeInTheDocument();
  });
});

describe("links saved before the move", () => {
  const legacy = (
    <>
      <Route path="/documents/library/:libraryId" element={<LegacyLibraryLink />} />
      <Route path="/architecture-knowledge/releases/:releaseId/evidence/:chunkId" element={<LegacyEvidenceLink />} />
    </>
  );

  it("open an old citation link in the read-only passage view", () => {
    mount("/documents/library/doc-1?publication=pub-1&version=v-1&revision=r-1&passage=b-1", legacy);
    const landed = new URL(screen.getByRole("status", { name: "Landed at" }).textContent!, "http://x");
    expect(landed.pathname).toBe("/references/passage");
    expect(Object.fromEntries(landed.searchParams)).toEqual({
      document: "doc-1", publication: "pub-1", version: "v-1", revision: "r-1", passage: "b-1",
    });
  });

  it("send an old library page without a citation to Documents", () => {
    mount("/documents/library/doc-1", legacy);
    expect(screen.getByRole("status", { name: "Landed at" })).toHaveTextContent(/^\/documents$/);
  });

  it("open an old evidence link in the read-only evidence view", () => {
    mount("/architecture-knowledge/releases/rel 2/evidence/chunk-1", legacy);
    expect(screen.getByRole("status", { name: "Landed at" }))
      .toHaveTextContent(/^\/architecture-evidence\/rel%202\/chunk-1$/);
  });
});
