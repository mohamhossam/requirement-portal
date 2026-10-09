import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "./queryKeys";
import { contextTokenKeys, invalidateWorkspace, workspaceChangeKeys } from "./workspaceInvalidation";

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

describe("contextTokenKeys", () => {
  it("names the reads each start's context token came from", () => {
    expect(contextTokenKeys("req-1", { operation: "analyse_requirement", context_token: "", force: false }))
      .toEqual(workspaceChangeKeys("req-1", "analysis"));
    expect(contextTokenKeys("req-1", { operation: "generate_epic", context_token: "", force: false }))
      .toEqual(workspaceChangeKeys("req-1", "analysis"));
    expect(contextTokenKeys("req-1", { operation: "generate_features", context_token: "", force: false }))
      .toEqual(workspaceChangeKeys("req-1", "epic"));
    const stories = contextTokenKeys("req-1", { operation: "regenerate_story_set", feature_id: "feature-2", context_token: "", force: false });
    expect(stories).toEqual(workspaceChangeKeys("req-1", "features", "feature-2"));
    expect(stories).toContainEqual(queryKeys.stories("req-1", "feature-2"));
    expect(contextTokenKeys("req-1", { operation: "generate_breakdown_review" })).toEqual([]);
  });
});
