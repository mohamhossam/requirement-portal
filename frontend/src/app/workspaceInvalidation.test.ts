import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "./queryKeys";
import { invalidateWorkspace } from "./workspaceInvalidation";

describe("invalidateWorkspace", () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  afterEach(() => client.clear());

  it("reads again when a first load is still in flight", async () => {
    // The analysis job finishes between the first read being answered and it
    // arriving: that answer predates the change and must not be kept.
    const answers: Array<(value: string | null) => void> = [];
    const observer = new QueryObserver<string | null>(client, {
      queryKey: queryKeys.analysis("req-1"),
      queryFn: () => new Promise<string | null>((resolve) => answers.push(resolve)),
    });
    const unsubscribe = observer.subscribe(() => undefined);
    expect(answers).toHaveLength(1);

    const refreshed = invalidateWorkspace(client, "req-1", "analysis");
    answers[0]?.(null);
    await vi.waitFor(() => expect(answers).toHaveLength(2));
    answers[1]?.("drafted");
    await refreshed;

    expect(observer.getCurrentResult().data).toBe("drafted");
    unsubscribe();
  });
});
