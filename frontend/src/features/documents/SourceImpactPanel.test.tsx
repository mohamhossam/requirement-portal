import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import { api, type DependencyImpact } from "../../api/client";
import { queryKeys } from "../../app/queryKeys";
import { SourceImpactPanel } from "./SourceImpactPanel";

afterEach(() => vi.restoreAllMocks());
const item: DependencyImpact = {
  dependency: {
    id: "dep-1", requirement_id: "req-1", requirement_title: "Coverage orders",
    target_kind: "clarification", target_id: "q-1", statement: "Check coverage",
    content_fingerprint: "content", active: true, current: true, status: "recorded",
    analysis_id: "a-1", round_number: 2,
    lineage: { via: [], citation: {
      document_id: "doc-1", title: "Coverage policy", version_id: "v-1", version_number: 1,
      revision_id: "r-1", publication_id: "pub-1", approval_fingerprint: "a".repeat(64),
      block_id: "b-1", location: "Line 1", excerpt: "Check coverage", start_offset: 0,
      end_offset: 14, lineage_hash: "b".repeat(64),
    } },
  },
  publication_current: false, publication_state: "4:withdrawn", needs_review: true, decisions: [],
};

function mount(canDecide: boolean) {
  const cache = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={cache}><MemoryRouter>
    <SourceImpactPanel requirementId="req-1" canDecide={canDecide} />
  </MemoryRouter></QueryClientProvider>);
  return cache;
}

it("requires a rationale and refreshes the analysis gate after owner reconciliation", async () => {
  vi.spyOn(api, "sourceImpact").mockResolvedValue({ items: [item], next_offset: null });
  const save = vi.spyOn(api, "decideSourceImpact").mockResolvedValue(item);
  const cache = mount(true);
  cache.setQueryData(queryKeys.analysis("req-1"), { stale_reference_proposal_ids: ["dep-1"] });
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Review source impact" }));
  const button = await screen.findByRole("button", { name: "Record impact decision" });
  expect(button).toBeDisabled();
  await user.selectOptions(screen.getByRole("combobox", { name: "Impact decision" }), "retain_historical");
  await user.type(screen.getByLabelText("Reason for impact decision"), "Retain this rollout's reviewed policy");
  await user.click(button);
  expect(await screen.findByRole("status")).toHaveTextContent("Impact decision recorded.");
  expect(save).toHaveBeenCalledWith(item, "retain_historical", "Retain this rollout's reviewed policy");
  expect(cache.getQueryState(queryKeys.analysis("req-1"))?.isInvalidated).toBe(true);
});

it("keeps reviewer access read-only and does not claim unreviewed history was reconciled", async () => {
  vi.spyOn(api, "sourceImpact").mockResolvedValue({ items: [item], next_offset: null });
  const user = userEvent.setup();
  mount(false);
  await user.click(screen.getByRole("button", { name: "Review source impact" }));
  expect(await screen.findByText(/The Requirement owner can record/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Record impact decision" })).not.toBeInTheDocument();
  expect(screen.queryByText("Historical evidence — review recorded")).not.toBeInTheDocument();
});
