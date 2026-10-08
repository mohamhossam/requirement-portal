import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type AiJob, type AiJobStartInput } from "../../api/client";
import { ApiError } from "../../api/errors";
import { configureQueryActor, queryKeys } from "../../app/queryKeys";
import { jobCompletionKeys } from "../../app/workspaceInvalidation";
import { jobFixture } from "../../test/jobFixture";
import { approvedFeatureFixture } from "../../test/fixtures";
import { StoryList } from "../stories/StoryList";
import { observeJobs, registerStartedJob } from "./jobObservation";
import { RequirementJobsProvider } from "./RequirementJobsProvider";
import { useRequirementJobs } from "./useRequirementJobs";

function Consumer() {
  const jobs = useRequirementJobs("req-1");
  return <button onClick={() => void jobs.startJob({ operation: "generate_epic", context_token: "context", force: false })}>Start</button>;
}

function Starter({ input, idempotencyKey }: { input: AiJobStartInput; idempotencyKey?: string }) {
  const jobs = useRequirementJobs("req-1");
  const [failure, setFailure] = useState("");
  const start = () => {
    setFailure("");
    jobs.startJob(input, idempotencyKey).catch((error: Error) => setFailure(error.message));
  };
  return <><button onClick={start}>Start</button><p role="status">{failure}</p></>;
}

function Reads({ readEpic, readSuggestions }: { readEpic: () => Promise<null>; readSuggestions: () => Promise<null> }) {
  useQuery({ queryKey: queryKeys.epic("req-1"), queryFn: readEpic });
  useQuery({ queryKey: queryKeys.answerSuggestions("req-1", "question-1"), queryFn: readSuggestions });
  return null;
}

function RequirementRead({ read }: { read: () => Promise<null> }) {
  useQuery({ queryKey: queryKeys.requirement("req-1"), queryFn: read });
  return null;
}

function HiddenEpic({ read }: { read: () => Promise<null> }) {
  useQuery({ queryKey: queryKeys.epic("req-1"), queryFn: read, enabled: false });
  return null;
}

function mount(children: React.ReactNode, client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 10_000 } } })) {
  const tree = <QueryClientProvider client={client}><RequirementJobsProvider requirementId="req-1">{children}</RequirementJobsProvider></QueryClientProvider>;
  return { client, tree, ...render(tree) };
}

describe("shared requirement jobs", () => {
  afterEach(() => { vi.restoreAllMocks(); configureQueryActor(null); });

  it("loads historical jobs without refreshing artifact queries", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([{ ...jobFixture, status: "succeeded" }]);
    const readEpic = vi.fn(async () => null), readSuggestions = vi.fn(async () => null);
    const { client } = mount(<><Consumer /><Consumer /><Reads readEpic={readEpic} readSuggestions={readSuggestions} /></>);
    await waitFor(() => expect(client.getQueryData(queryKeys.aiJobs("req-1"))).toBeDefined());
    expect(api.listAiJobs).toHaveBeenCalledTimes(1);
    expect(readEpic).toHaveBeenCalledTimes(1);
    expect(readSuggestions).toHaveBeenCalledTimes(1);
  });

  it("shares one polling owner across multiple Story lists and stops after completion", async () => {
    let result: AiJob[] = [{ ...jobFixture, status: "running", operation: "suggest_clarification_answers" }];
    const list = vi.spyOn(api, "listAiJobs").mockImplementation(async () => result);
    vi.spyOn(api, "getStories").mockResolvedValue(null);
    vi.spyOn(api, "listStoryProposals").mockResolvedValue([]);
    const readEpic = vi.fn(async () => null), readSuggestions = vi.fn(async () => null);
    mount(<><StoryList requirementId="req-1" feature={approvedFeatureFixture} canManage /><StoryList requirementId="req-1" feature={{ ...approvedFeatureFixture, id: "feature-2" }} canManage /><Reads readEpic={readEpic} readSuggestions={readSuggestions} /></>);
    await waitFor(() => expect(list).toHaveBeenCalledTimes(1));
    result = result.map((job) => ({ ...job, status: "succeeded" }));
    await waitFor(() => expect(readSuggestions).toHaveBeenCalledTimes(2), { timeout: 2_000 });
    expect(list).toHaveBeenCalledTimes(2);
    expect(readEpic).toHaveBeenCalledTimes(1);
    await new Promise((resolve) => setTimeout(resolve, 1_100));
    expect(list).toHaveBeenCalledTimes(2);
  });

  it("registers a fast completion and refreshes its artifact exactly once", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    vi.spyOn(api, "startAiJob").mockResolvedValue({ ...jobFixture, operation: "generate_epic", status: "succeeded" });
    const readEpic = vi.fn(async () => null), readSuggestions = vi.fn(async () => null);
    mount(<><Consumer /><Reads readEpic={readEpic} readSuggestions={readSuggestions} /></>);
    await waitFor(() => expect(api.listAiJobs).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByText("Start"));
    await waitFor(() => expect(readEpic).toHaveBeenCalledTimes(2));
    expect(readSuggestions).toHaveBeenCalledTimes(1);
  });

  it.each(["failed", "cancelled"] as const)("does not refresh artifacts after a %s transition", async (status) => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([{ ...jobFixture, status: "running" }]);
    const readEpic = vi.fn(async () => null), readSuggestions = vi.fn(async () => null);
    const { client } = mount(<Reads readEpic={readEpic} readSuggestions={readSuggestions} />);
    await waitFor(() => expect(client.getQueryData(queryKeys.aiJobs("req-1"))).toBeDefined());
    vi.mocked(api.listAiJobs).mockResolvedValue([{ ...jobFixture, status }]);
    await client.invalidateQueries({ queryKey: queryKeys.aiJobs("req-1") });
    expect(readEpic).toHaveBeenCalledTimes(1);
    expect(readSuggestions).toHaveBeenCalledTimes(1);
  });

  it("preserves active observations while the workspace is unmounted", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([{ ...jobFixture, status: "running", operation: "generate_epic" }]);
    const readEpic = vi.fn(async () => null), readSuggestions = vi.fn(async () => null);
    const mounted = mount(<Reads readEpic={readEpic} readSuggestions={readSuggestions} />);
    await waitFor(() => expect(mounted.client.getQueryData(queryKeys.aiJobs("req-1"))).toBeDefined());
    mounted.unmount();
    vi.mocked(api.listAiJobs).mockResolvedValue([{ ...jobFixture, status: "succeeded", operation: "generate_epic" }]);
    render(mounted.tree);
    await waitFor(() => expect(readEpic).toHaveBeenCalledTimes(2));
    expect(api.listAiJobs).toHaveBeenCalledTimes(2);
  });

  it("isolates actor and requirement observations, including jobs finishing between polls", () => {
    const client = new QueryClient();
    configureQueryActor("actor-a");
    expect(observeJobs(client, "req-1", [])).toEqual([]);
    expect(observeJobs(client, "req-1", [{ ...jobFixture, status: "succeeded" }])).toHaveLength(1);
    expect(observeJobs(client, "req-1", [{ ...jobFixture, status: "succeeded" }])).toEqual([]);
    expect(observeJobs(client, "req-2", [{ ...jobFixture, status: "succeeded" }])).toEqual([]);
    configureQueryActor("actor-b");
    expect(observeJobs(client, "req-1", [{ ...jobFixture, status: "succeeded" }])).toEqual([]);
    registerStartedJob(client, "req-1", { ...jobFixture, id: "retry", status: "succeeded" });
    expect(observeJobs(client, "req-1", [{ ...jobFixture, id: "retry", status: "succeeded" }])).toHaveLength(1);
  });

  it("targets only the Feature identified by a Story job result", () => {
    const keys = jobCompletionKeys({ ...jobFixture, operation: "generate_stories", status: "succeeded", result_resources: [{ kind: "stories", path: "/requirements/req-1/breakdown/features/feature-2" }] });
    expect(keys).toContainEqual(queryKeys.stories("req-1", "feature-2"));
    expect(keys).not.toContainEqual(queryKeys.stories("req-1", "feature-1"));
    expect(keys).not.toContainEqual(queryKeys.epic("req-1"));
  });

  it("marks hidden backlog caches stale without fetching them", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([{ ...jobFixture, status: "running" }]);
    const read = vi.fn(async () => null);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(queryKeys.epic("req-1"), null);
    mount(<HiddenEpic read={read} />, client);
    await waitFor(() => expect(client.getQueryData(queryKeys.aiJobs("req-1"))).toBeDefined());
    vi.mocked(api.listAiJobs).mockResolvedValue([{ ...jobFixture, status: "succeeded" }]);
    await client.invalidateQueries({ queryKey: queryKeys.aiJobs("req-1") });
    expect(client.getQueryState(queryKeys.epic("req-1"))?.isInvalidated).toBe(true);
    expect(read).not.toHaveBeenCalled();
  });

  it("distinguishes an intake completion from historical jobs on the first status read", () => {
    const client = new QueryClient();
    const newJob = { ...jobFixture, status: "succeeded" as const };
    registerStartedJob(client, "req-1", newJob);
    const history = { ...newJob, id: "old-job" };
    expect(observeJobs(client, "req-1", [history, newJob])).toEqual([newJob]);
    expect(observeJobs(client, "req-1", [{ ...newJob, status: "running" }])).toEqual([]);
    expect(observeJobs(client, "req-1", [newJob])).toEqual([]);
  });

  it("refreshes a blank context token instead of sending a request that can only be refused", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    const start = vi.spyOn(api, "startAiJob");
    const readRequirement = vi.fn(async () => null);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    mount(<><Starter input={{ operation: "analyse_requirement", context_token: " ", force: false }} /><RequirementRead read={readRequirement} /></>, client);
    await waitFor(() => expect(readRequirement).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByText("Start"));
    expect(await screen.findByText("This page was out of date and has been refreshed. Try again.")).toBeVisible();
    expect(start).not.toHaveBeenCalled();
    await waitFor(() => expect(readRequirement).toHaveBeenCalledTimes(2));
  });

  it("refreshes what the token was read from when the server says it changed", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    vi.spyOn(api, "startAiJob").mockRejectedValue(new ApiError(409, "The Epic changed.", "stale_generation_context"));
    const readEpic = vi.fn(async () => null), readSuggestions = vi.fn(async () => null);
    mount(<><Starter input={{ operation: "generate_features", context_token: "epic-context", force: false }} /><Reads readEpic={readEpic} readSuggestions={readSuggestions} /></>);
    await waitFor(() => expect(readEpic).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByText("Start"));
    expect(await screen.findByText("The Epic changed.")).toBeVisible();
    await waitFor(() => expect(readEpic).toHaveBeenCalledTimes(2));
    expect(readSuggestions).toHaveBeenCalledTimes(1);
  });

  it("reuses the key only while the last start's outcome is unknown", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    const start = vi.spyOn(api, "startAiJob")
      .mockRejectedValueOnce(new ApiError(0, "Network down"))
      .mockRejectedValueOnce(new ApiError(503, "Unavailable"))
      .mockResolvedValueOnce(jobFixture)
      .mockRejectedValueOnce(new ApiError(422, "Invalid"))
      .mockResolvedValueOnce(jobFixture);
    mount(<Starter input={{ operation: "generate_epic", context_token: "context", force: false }} />);
    for (const message of ["Network down", "Unavailable", "", "Invalid", ""]) {
      await userEvent.click(screen.getByText("Start"));
      await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(message));
    }
    await waitFor(() => expect(start).toHaveBeenCalledTimes(5));
    const keys = start.mock.calls.map((call) => call[2]);
    // Lost and failed responses replay the first key; a success or a refusal starts afresh.
    expect(keys[1]).toBe(keys[0]);
    expect(keys[2]).toBe(keys[0]);
    expect(keys[3]).not.toBe(keys[0]);
    expect(keys[4]).not.toBe(keys[3]);
  });

  it("sends an explicit Idempotency-Key unchanged", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([]);
    const start = vi.spyOn(api, "startAiJob").mockResolvedValue(jobFixture);
    mount(<Starter input={{ operation: "generate_epic", context_token: "context", force: false }} idempotencyKey="caller-key" />);
    await userEvent.click(screen.getByText("Start"));
    await waitFor(() => expect(start).toHaveBeenCalledWith("req-1", expect.objectContaining({ operation: "generate_epic" }), "caller-key"));
  });
});
