import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { RequirementIndexNotice } from "./RequirementIndexNotice";

afterEach(() => vi.restoreAllMocks());

function show() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <RequirementIndexNotice requirementId="req-1" />
  </QueryClientProvider>);
}

it("explains background indexing and keeps completed batches visible", async () => {
  vi.spyOn(api, "getRequirementIndex").mockResolvedValue({ state: "indexing", completed_chunks: 16, total_chunks: 25, retryable: false });
  show();
  expect(await screen.findByText("16 of 25 sections prepared.")).toBeVisible();
  expect(screen.getByRole("status")).toHaveTextContent("start when it is ready");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("retries failed indexing without resubmitting source content", async () => {
  vi.spyOn(api, "getRequirementIndex").mockResolvedValue({ state: "failed", completed_chunks: 16, total_chunks: 25, retryable: true });
  const retry = vi.spyOn(api, "retryRequirementIndex").mockResolvedValue({ state: "indexing", completed_chunks: 16, total_chunks: 25, retryable: false });
  show();
  await userEvent.click(await screen.findByRole("button", { name: "Retry knowledge preparation" }));
  expect(retry).toHaveBeenCalledWith("req-1");
});

it("explains an incompatible model without offering a misleading retry", async () => {
  vi.spyOn(api, "getRequirementIndex").mockResolvedValue({ state: "rebuild_required", completed_chunks: 0, total_chunks: 0, retryable: false });
  show();
  expect(await screen.findByRole("status")).toHaveTextContent("an administrator has to rebuild");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});
