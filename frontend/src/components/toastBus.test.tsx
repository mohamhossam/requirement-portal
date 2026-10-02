import { MutationCache, QueryClient, QueryClientProvider, useMutation } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ApiError } from "../api/errors";
import { mutationErrorToast } from "../app/mutationErrors";
import { Toaster } from "./Toaster";
import { publishToast } from "./toastBus";

/** The wiring main.tsx installs, rebuilt here so the whole path is exercised. */
function clientWithNotices() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    mutationCache: new MutationCache({
      onError: (error, _variables, _context, mutation) => {
        const notice = mutationErrorToast(error, mutation.options.meta);
        if (notice) publishToast(notice);
      },
    }),
  });
}

function Failing({ error, meta }: { error: unknown; meta?: Record<string, unknown> }) {
  const mutation = useMutation({
    mutationFn: async () => { throw error; },
    meta,
  });
  return <button type="button" onClick={() => mutation.mutate()}>Do it</button>;
}

function mount(node: React.ReactNode) {
  return render(
    <QueryClientProvider client={clientWithNotices()}>
      <MemoryRouter><Toaster>{node}</Toaster></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("mutation failures reaching the toast layer", () => {
  it("surfaces a failure raised anywhere in the tree", async () => {
    mount(<Failing error={new ApiError(500, "Upstream exploded.")} meta={{ action: "Approving the Epic" }} />);
    await userEvent.click(screen.getByRole("button", { name: "Do it" }));
    expect(await screen.findByText("Approving the Epic failed")).toBeInTheDocument();
    expect(screen.getByText("Upstream exploded.")).toBeInTheDocument();
  });

  it("leaves a version conflict to the editor's own reconciliation", async () => {
    mount(<Failing error={new ApiError(409, "Stale version.")} meta={{ action: "Saving the Epic" }} />);
    await userEvent.click(screen.getByRole("button", { name: "Do it" }));
    expect(screen.queryByText(/failed/)).not.toBeInTheDocument();
  });

  it("respects a mutation that reports its own outcome", async () => {
    mount(<Failing error={new ApiError(500, "Nope.")} meta={{ toastOnError: false }} />);
    await userEvent.click(screen.getByRole("button", { name: "Do it" }));
    expect(screen.queryByText(/could not be completed/)).not.toBeInTheDocument();
  });

  it("publishes nothing once the Toaster has gone", async () => {
    const { unmount } = mount(<Failing error={new ApiError(500, "Late.")} />);
    unmount();
    // The bus disconnects on unmount, so this must not throw.
    expect(() => publishToast({ tone: "error", title: "Orphaned" })).not.toThrow();
  });
});
