import type { AiJob } from "../api/client";

export const jobFixture: AiJob = {
  id: "job-1", version: 1, requirement_id: "req-1", operation: "analyse_requirement", status: "queued",
  created_by: { id: "actor-1", display_name: "Owner", email: null },
  created_at: "2026-09-18T12:00:00Z", updated_at: "2026-09-18T12:00:00Z",
  started_at: null, completed_at: null, cancel_requested_at: null, attempt_count: 0,
  retry_of_job_id: null, failure: null, result_resources: [], origin: "user",
  phase: null, completed_units: 0, total_units: null, current_section_label: null,
};
