import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { api } from "../../api/client";
import { useLazyKnowledgeScreening } from "./useLazyKnowledgeScreening";

function Harness({ fingerprint }: { fingerprint: string }) {
  useLazyKnowledgeScreening({
    requirementId: "requirement-1",
    fingerprint,
    enabled: true,
  });
  return null;
}

describe("useLazyKnowledgeScreening", () => {
  it("ensures once for a fingerprint across React rerenders", async () => {
    const ensure = vi.spyOn(api, "ensureKnowledgeScreen").mockResolvedValue({
      outcome: "scheduled",
      job_id: "job-1",
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <QueryClientProvider client={client}>
        <Harness fingerprint="fingerprint-1" />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(ensure).toHaveBeenCalledTimes(1));
    view.rerender(
      <QueryClientProvider client={client}>
        <Harness fingerprint="fingerprint-1" />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(ensure).toHaveBeenCalledTimes(1));
  });

  it("ensures a changed evidence fingerprint independently", async () => {
    const ensure = vi.spyOn(api, "ensureKnowledgeScreen").mockResolvedValue({
      outcome: "already_scheduled",
      job_id: "job-1",
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = render(
      <QueryClientProvider client={client}>
        <Harness fingerprint="fingerprint-1" />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(ensure).toHaveBeenCalledTimes(1));

    view.rerender(
      <QueryClientProvider client={client}>
        <Harness fingerprint="fingerprint-2" />
      </QueryClientProvider>,
    );

    await waitFor(() => expect(ensure).toHaveBeenCalledTimes(2));
  });
});
