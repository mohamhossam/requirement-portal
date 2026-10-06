import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PriorArt } from "../../api/client";
import { PriorArtPanel } from "./PriorArtPanel";
import { PRIOR_ART_DESCRIPTION, REFERENCE_ONLY, priorArtShown } from "./labels";

const current: PriorArt = {
  status: "current",
  input_key: "abc:3",
  label: "historic",
  trust: "reference",
  checked_at: "2026-10-07T09:00:00Z",
  provenance: { generated_at: "2026-10-07T09:00:00Z", model: "judge-model", prompt_version: "prior-art-v1" },
  matches: [
    {
      historic_requirement_id: "h1",
      title: "BRD-2025-014 XGPON bundles",
      publication: 2,
      verdict: "similar_past_requirement",
      rationale: "It delivered XGPON bundle ordering for small offices.",
      passages: [
        {
          source_kind: "historic_brd",
          excerpt: "Business customers order XGPON fibre bundles through BCRM.",
          brd_filename: "BRD-2025-014.docx",
          label: "Paragraph 2",
          section_path: ["Scope"],
          lineage: [],
        },
        {
          source_kind: "historic_backlog",
          excerpt: "User Story #48216 As a sales agent, I choose an XGPON bundle",
          brd_filename: null,
          label: null,
          section_path: [],
          lineage: [
            { id: 48213, type: "epic", title: "XGPON fibre bundles", state: "Closed", url: "https://dev.azure.com/x/48213" },
            { id: 48216, type: "user_story", title: "Choose a bundle", state: "Closed", url: null },
          ],
        },
      ],
    },
  ],
};

describe("PriorArtPanel", () => {
  it("shows each match as historic reference, with its rationale and what it was delivered as", () => {
    render(<PriorArtPanel priorArt={current} />);
    expect(screen.getByRole("heading", { level: 2, name: "Similar past requirements" })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(REFERENCE_ONLY))).toBeInTheDocument();
    const card = screen.getByRole("article", { name: "BRD-2025-014 XGPON bundles" });
    expect(within(card).getByText("Historic")).toBeInTheDocument();
    expect(within(card).getByText("Generated")).toBeInTheDocument();
    expect(within(card).getByText(/delivered XGPON bundle ordering/)).toBeInTheDocument();
    expect(within(card).getByText(/BRD-2025-014.docx · Paragraph 2/)).toBeInTheDocument();
    const ado = within(card).getByRole("link", { name: /#48213\s+\(opens Azure DevOps\)/ });
    expect(ado).toHaveAttribute("href", "https://dev.azure.com/x/48213");
    expect(ado).toHaveAttribute("target", "_blank");
    expect(ado).toHaveAttribute("rel", "noopener noreferrer");
    // A work item without a web address is shown, never linked.
    expect(within(card).queryByRole("link", { name: /#48216/ })).toBeNull();
    expect(within(card).getByText("Epic")).toBeInTheDocument();
    expect(within(card).getByText("User Story")).toBeInTheDocument();
    expect(screen.getByText("How similar past requirements were found")).toBeInTheDocument();
  });

  it("says when nothing is similar, and stays away when it is off or has nothing to compare", () => {
    const { rerender, container } = render(<PriorArtPanel priorArt={{ ...current, matches: [] }} />);
    expect(screen.getByText("No delivered requirement looks like this one.")).toBeInTheDocument();
    rerender(<PriorArtPanel priorArt={{ ...current, status: "disabled", matches: [] }} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<PriorArtPanel priorArt={{ ...current, status: "no_historic_knowledge", matches: [] }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("announces a check in progress, and keeps an older answer readable while it is out of date", () => {
    const { rerender } = render(<PriorArtPanel priorArt={{ ...current, status: "waiting", matches: [] }} />);
    expect(screen.getByRole("status")).toHaveTextContent(PRIOR_ART_DESCRIPTION.waiting!);
    rerender(<PriorArtPanel priorArt={{ ...current, status: "out_of_date" }} />);
    expect(screen.getByText(new RegExp(PRIOR_ART_DESCRIPTION.out_of_date!))).toBeInTheDocument();
    expect(screen.getByRole("article", { name: "BRD-2025-014 XGPON bundles" })).toBeInTheDocument();
  });

  it("never prints a raw status, kind or type", () => {
    for (const status of ["not_checked", "checking", "waiting", "current", "out_of_date", "failed"] as const) {
      const { container, unmount } = render(<PriorArtPanel priorArt={{ ...current, status }} />);
      expect(container.textContent).not.toMatch(/historic_brd|historic_backlog|user_story|similar_past_requirement|_/);
      unmount();
    }
    expect(priorArtShown("current")).toBe(true);
  });
});
