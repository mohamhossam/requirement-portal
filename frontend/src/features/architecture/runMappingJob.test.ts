import { afterEach, describe, expect, it, vi } from "vitest";

import { api, type ArchitectureMappingJob } from "../../api/client";
import { runArchitectureMapping } from "./runMappingJob";

const job = (status: ArchitectureMappingJob["status"], extra: Partial<ArchitectureMappingJob> = {}): ArchitectureMappingJob => ({
  id: "job-1",
  kind: "mapping",
  subject_id: "req-1",
  fingerprint: "fingerprint",
  actor_id: "fake-owner",
  status,
  attempts: 1,
  ...extra,
});
const noPause = () => Promise.resolve();

describe("runArchitectureMapping", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns at once when the job finished inside the starting request", async () => {
    vi.spyOn(api, "startArchitectureMappingJob").mockResolvedValue(job("succeeded"));
    const poll = vi.spyOn(api, "getArchitectureMappingJob");

    await expect(runArchitectureMapping("req-1", noPause)).resolves.toMatchObject({ status: "succeeded" });
    expect(poll).not.toHaveBeenCalled();
  });

  it("waits for a queued job until it succeeds", async () => {
    vi.spyOn(api, "startArchitectureMappingJob").mockResolvedValue(job("queued"));
    const poll = vi.spyOn(api, "getArchitectureMappingJob")
      .mockResolvedValueOnce(job("running"))
      .mockResolvedValueOnce(job("succeeded"));

    await expect(runArchitectureMapping("req-1", noPause)).resolves.toMatchObject({ status: "succeeded" });
    expect(poll).toHaveBeenCalledTimes(2);
    expect(poll).toHaveBeenCalledWith("req-1", "job-1");
  });

  it("fails with the job's reason when it does not finish", async () => {
    vi.spyOn(api, "startArchitectureMappingJob").mockResolvedValue(job("queued"));
    vi.spyOn(api, "getArchitectureMappingJob").mockResolvedValue(
      job("failed", { error_category: "attempts_exhausted" }),
    );

    await expect(runArchitectureMapping("req-1", noPause)).rejects.toThrow(
      "Architecture mapping did not finish (attempts_exhausted). Try again.",
    );
  });

  it("says so when the job was cancelled", async () => {
    vi.spyOn(api, "startArchitectureMappingJob").mockResolvedValue(job("cancelled"));

    await expect(runArchitectureMapping("req-1", noPause)).rejects.toThrow("Architecture mapping was cancelled.");
  });
});
