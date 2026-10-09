import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type AiJob } from "../../api/client";
import { renderWithJobs } from "../../test/renderWithClient";
import { AiJobStatusPanel } from "./AiJobStatusPanel";

const activeJob: AiJob = {
  id: "job-1",
  version: 2,
  requirement_id: "req-1",
  operation: "analyse_requirement",
  status: "running",
  created_by: { id: "actor-1", display_name: "Owner", email: null },
  created_at: "2026-09-03T12:00:00Z",
  updated_at: "2026-09-03T12:00:00Z",
  started_at: "2026-09-03T12:00:00Z",
  completed_at: null,
  cancel_requested_at: null,
  attempt_count: 1,
  retry_of_job_id: null,
  failure: null,
  result_resources: [],
  origin: "user",
  phase: "analyzing_evidence",
  completed_units: 2,
  total_units: 5,
  current_section_label: "BUC2",
};

const failedJob: AiJob = {
  ...activeJob,
  id: "job-failed-1",
  operation: "resolve_clarification_questions",
  status: "failed",
  updated_at: "2026-09-03T12:01:00Z",
  completed_at: "2026-09-03T12:01:00Z",
  item_count: 1,
  failure: {
    code: "provider_failure",
    message: "Local LLM returned no usable analysis after one completeness retry.",
    retryable: true,
    correlation_id: "test-correlation-id",
  },
};

describe("AiJobStatusPanel", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows durable progress and lets the user request cancellation", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([activeJob]);
    const cancel = vi.spyOn(api, "cancelAiJob").mockResolvedValue({
      ...activeJob,
      status: "cancellation_requested",
    });

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Analyzing evidence")).toBeVisible();
    expect(screen.getByText("Current section: BUC2")).toBeVisible();
    expect(screen.getByRole("progressbar", { name: "Analysis progress" })).toHaveAttribute("value", "2");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(cancel).toHaveBeenCalledWith("req-1", "job-1", activeJob.version);
  });

  it.each([
    ["preparing", "Preparing generation context"], ["generating", "Generating draft"],
    ["checking", "Checking draft"], ["refining", "Refining draft"], ["saving", "Saving checked draft"],
  ])("shows generation phase %s", async (phase, label) => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([{ ...activeJob, operation: "generate_stories", phase }]);
    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);
    expect(await screen.findByText(label)).toBeVisible();
    expect(screen.getByRole("progressbar", { name: "Generation progress" })).toBeVisible();
  });

  it("distinguishes queued work from running analysis", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([
      {
        ...activeJob,
        status: "queued",
        started_at: null,
        attempt_count: 0,
        phase: null,
        completed_units: 0,
        total_units: null,
        current_section_label: null,
      },
    ]);

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Analysing requirement queued")).toBeVisible();
    expect(screen.getByText(/User-requested work is processed before automatic/)).toBeVisible();
  });

  it("says when a job that met an outage will try again", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([
      {
        ...activeJob,
        status: "queued",
        phase: "waiting_to_retry",
        completed_units: 0,
        total_units: null,
        current_section_label: null,
        next_attempt_at: "2026-09-03T12:05:00Z",
      },
    ]);

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Analysing requirement will try again")).toBeVisible();
    expect(screen.getByText(/was unavailable\. It tries again at/)).toBeVisible();
  });

  it("shows the durable batch size for clarification resolution", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([
      {
        ...activeJob,
        operation: "resolve_clarification_questions",
        item_count: 3,
      },
    ]);

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Resolving 3 questions")).toBeVisible();
  });

  it("shows only the newest failure for an operation", async () => {
    const latestFailure = {
      ...failedJob,
      id: "job-failed-2",
      created_at: "2026-09-03T12:02:00Z",
    };
    vi.spyOn(api, "listAiJobs").mockResolvedValue([failedJob, latestFailure]);
    const retry = vi.spyOn(api, "retryAiJob").mockResolvedValue({
      ...latestFailure,
      id: "job-retry",
      status: "queued",
      retry_of_job_id: latestFailure.id,
      failure: null,
      completed_at: null,
    });

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findAllByText("Resolving 1 question failed")).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledWith("req-1", "job-failed-2", latestFailure.version);
  });

  it("clears prior failures after a newer main-button action succeeds", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([
      activeJob,
      {
        ...failedJob,
        id: "job-succeeded",
        status: "succeeded",
        created_at: "2026-09-03T12:03:00Z",
        retry_of_job_id: null,
        failure: null,
      },
      {
        ...failedJob,
        id: "job-failed-2",
        created_at: "2026-09-03T12:02:00Z",
      },
      failedJob,
    ]);

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Analyzing evidence")).toBeVisible();
    expect(screen.queryByText("Resolving 1 question failed")).not.toBeInTheDocument();
  });

  it("hides a failure while a newer action for that operation is active", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([
      failedJob,
      {
        ...activeJob,
        id: "job-active-resolution",
        operation: "resolve_clarification_questions",
        created_at: "2026-09-03T12:02:00Z",
        item_count: 1,
      },
    ]);

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Resolving 1 question")).toBeVisible();
    expect(screen.queryByText("Resolving 1 question failed")).not.toBeInTheDocument();
  });

  it("keeps a failure actionable when a newer action was cancelled", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([
      {
        ...failedJob,
        id: "job-cancelled",
        status: "cancelled",
        created_at: "2026-09-03T12:02:00Z",
        failure: null,
      },
      failedJob,
    ]);

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Resolving 1 question failed")).toBeVisible();
    expect(screen.getByRole("button", { name: "Retry" })).toBeVisible();
  });

  it("shows a cancelled automatic knowledge screen as manual retry", async () => {
    const cancelled = {
      ...activeJob,
      id: "knowledge-cancelled",
      operation: "screen_requirement_knowledge" as const,
      status: "cancelled" as const,
      origin: "automatic" as const,
      completed_at: "2026-09-03T12:02:00Z",
      cancel_requested_at: "2026-09-03T12:02:00Z",
    };
    vi.spyOn(api, "listAiJobs").mockResolvedValue([cancelled]);
    const retry = vi.spyOn(api, "retryAiJob").mockResolvedValue({
      ...cancelled,
      id: "knowledge-retry",
      status: "queued",
      origin: "user",
      completed_at: null,
      retry_of_job_id: cancelled.id,
    });

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Screening requirement knowledge stopped")).toBeVisible();
    expect(screen.getByText(/remains stopped until a team member retries/)).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledWith("req-1", cancelled.id, cancelled.version);
  });

  it("keeps current failures for different operations visible", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([
      {
        ...failedJob,
        id: "job-epic-failed",
        operation: "generate_epic",
        created_at: "2026-09-03T12:02:00Z",
        item_count: null,
      },
      failedJob,
    ]);

    renderWithJobs(<AiJobStatusPanel requirementId="req-1" />);

    expect(await screen.findByText("Generating Epic failed")).toBeVisible();
    expect(screen.getByText("Resolving 1 question failed")).toBeVisible();
    expect(screen.getAllByRole("button", { name: "Retry" })).toHaveLength(2);
  });
  it("keeps the operation visible while showing its phase in focused progress", async () => {
    vi.spyOn(api, "listAiJobs").mockResolvedValue([{ ...activeJob, operation: "generate_stories", phase: "checking" }]);
    renderWithJobs(<AiJobStatusPanel requirementId="req-1" focused />);
    expect(await screen.findByText("Generating Stories")).toBeVisible();
    expect(screen.getByText("Checking draft · Work continues in the background.")).toBeVisible();
  });

});
