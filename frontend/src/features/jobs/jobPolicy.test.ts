import { describe, expect, it } from "vitest";

import type { AiJob } from "../../api/client";
import { activeRunKey, jobPollInterval, jobToast } from "./jobPolicy";

const NOW = Date.parse("2026-09-18T12:00:00Z");
const agedBy = (ms: number) => new Date(NOW - ms).toISOString();

function job(overrides: Partial<AiJob> = {}): AiJob {
  return {
    id: "job-1",
    requirement_id: "req-1",
    operation: "analyse_requirement",
    status: "running",
    origin: "user",
    version: 1,
    attempt_count: 1,
    completed_units: 0,
    total_units: null,
    item_count: null,
    phase: null,
    current_section_label: null,
    failure: null,
    result_resources: [],
    retry_of_job_id: null,
    cancel_requested_at: null,
    started_at: agedBy(0),
    completed_at: null,
    created_at: agedBy(0),
    updated_at: agedBy(0),
    created_by: { id: "actor-1", display_name: "Owner", email: "owner@example.com" },
    ...overrides,
  } as unknown as AiJob;
}

describe("job poll interval", () => {
  it("looks briskly at work it has only just started watching", () => {
    expect(jobPollInterval(0)).toBe(1_000);
    expect(jobPollInterval(9_999)).toBe(1_000);
  });

  it("eases off the longer the run goes on", () => {
    expect(jobPollInterval(10_000)).toBe(2_000);
    expect(jobPollInterval(59_999)).toBe(2_000);
    expect(jobPollInterval(60_000)).toBe(5_000);
    expect(jobPollInterval(10 * 60_000)).toBe(5_000);
  });

  it("costs far fewer requests than the flat one-second poll it replaces", () => {
    const TEN_MINUTES = 10 * 60_000;
    let elapsed = 0;
    let requests = 0;
    while (elapsed < TEN_MINUTES) {
      elapsed += jobPollInterval(elapsed);
      requests += 1;
    }
    expect(requests).toBeLessThan(150);
    expect(TEN_MINUTES / 1_000).toBe(600);
  });
});

describe("active run key", () => {
  it("is empty when nothing is in flight, which stops the poll", () => {
    expect(activeRunKey([])).toBe("");
    expect(activeRunKey(undefined)).toBe("");
    expect(activeRunKey([job({ status: "succeeded" })])).toBe("");
  });

  it("is stable while the same work continues, so pacing is not reset", () => {
    const jobs = [job({ id: "b" }), job({ id: "a" })];
    expect(activeRunKey(jobs)).toBe("a,b");
    expect(activeRunKey([job({ id: "a" }), job({ id: "b" })])).toBe("a,b");
  });

  it("changes when work is added or finishes, so pacing restarts", () => {
    expect(activeRunKey([job({ id: "a" })])).not.toBe(
      activeRunKey([job({ id: "a" }), job({ id: "b" })]),
    );
  });

  it("counts queued and cancelling work as still in flight", () => {
    expect(activeRunKey([job({ id: "a", status: "queued" })])).toBe("a");
    expect(activeRunKey([job({ id: "a", status: "cancellation_requested" })])).toBe("a");
  });
});

describe("job completion notices", () => {
  it("announces work the person asked for", () => {
    const notice = jobToast(job({ status: "succeeded", operation: "generate_epic" }));
    expect(notice).toMatchObject({ tone: "success", title: "Epic generation finished" });
  });

  it("links to the result when the job produced one", () => {
    const notice = jobToast(job({
      status: "succeeded",
      operation: "generate_features",
      result_resources: [{ kind: "features", path: "/requirements/req-1/breakdown" }],
    } as Partial<AiJob>));
    expect(notice).toMatchObject({ to: "/requirements/req-1/breakdown", linkLabel: "Open result" });
  });

  it("stays quiet about background screening that simply worked", () => {
    expect(jobToast(job({
      status: "succeeded", origin: "automatic", operation: "screen_requirement_knowledge",
    }))).toBeNull();
  });

  it("reports failures even when nobody asked for the work", () => {
    const notice = jobToast(job({
      status: "failed",
      origin: "automatic",
      operation: "screen_requirement_knowledge",
      failure: { code: "provider_error", message: "The model timed out.", retryable: true, correlation_id: "abc" },
    } as Partial<AiJob>));
    expect(notice).toMatchObject({ tone: "error", title: "Knowledge screening failed", message: "The model timed out." });
  });

  it("says nothing when the person cancelled the work themselves", () => {
    expect(jobToast(job({ status: "cancelled" }))).toBeNull();
  });

  it("keeps repeats of one operation collapsed onto a single notice", () => {
    const first = jobToast(job({ status: "failed", operation: "generate_epic" }));
    const second = jobToast(job({ id: "job-2", status: "succeeded", operation: "generate_epic" }));
    expect(first?.key).toBe(second?.key);
  });
});
