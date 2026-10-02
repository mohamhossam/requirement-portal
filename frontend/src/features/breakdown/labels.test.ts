import { describe, expect, it } from "vitest";

import type { Approval } from "../../api/client";
import { backlogVerdict, needsApproval, signature } from "./labels";

const approval: Approval = {
  id: "approval-1",
  decision: "approved",
  rationale: null,
  recorded_at: "2026-09-26T09:00:00Z",
  recorded_by: { id: "owner", display_name: "Amina Owner", email: null },
  subject_fingerprint: "fp",
  target: { kind: "feature", item_id: "feature-1" },
};

describe("backlog verdicts", () => {
  it("puts staleness before everything, including an approval", () => {
    const item = { status: "approved" as const, stale: { reason: "epic_changed" }, current_approval: approval };
    expect(backlogVerdict(item, "feature")).toEqual({ label: "Out of date", tone: "warning" });
    expect(signature(item)).toBeNull();
    expect(needsApproval(item)).toBe(true);
  });

  it("says who signed an approved item, and when", () => {
    const item = { status: "approved" as const, current_approval: approval, approval_history: [approval] };
    expect(backlogVerdict(item, "epic")).toEqual({ label: "Approved", tone: "success" });
    expect(signature(item)).toMatch(/^Approved by Amina Owner · /);
    expect(needsApproval(item)).toBe(false);
  });

  it("tells a lapsed approval from one never given", () => {
    const lapsed = { status: "edited" as const, current_approval: null, approval_history: [approval] };
    const fresh = { status: "generated" as const, current_approval: null, approval_history: [] };
    expect(backlogVerdict(lapsed, "feature").label).toBe("Needs approving again");
    expect(backlogVerdict(fresh, "feature").label).toBe("Needs approval");
  });

  it("does not ask for a Story's approval here, where it cannot be given", () => {
    const story = { status: "generated" as const, current_approval: null, approval_history: [] };
    expect(backlogVerdict(story, "story")).toEqual({ label: "Not yet approved", tone: "neutral" });
  });
});
