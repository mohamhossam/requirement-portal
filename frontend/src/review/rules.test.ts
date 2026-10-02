import { describe, expect, it } from "vitest";

import {
  analysisFixture,
  approvedFeatureFixture,
  epicFixture,
  featureSetFixture,
  storyFixture,
} from "../test/fixtures";
import {
  canApprove,
  canDecompose,
  canGenerateEpic,
  canGenerateStories,
  regenerationLoss,
  storyRegenerationLoss,
} from "./rules";

describe("review rules", () => {
  it("requires analysis before Epic generation", () => {
    expect(canGenerateEpic(null)).toEqual({
      ok: false,
      reason: "Analyse the current requirement before generating an Epic.",
    });
    expect(canGenerateEpic(analysisFixture)).toEqual({
      ok: false,
      reason: "Confirm the analysis before generating an Epic.",
    });
    expect(canGenerateEpic({ ...analysisFixture, human_confirmed: true })).toEqual({ ok: true });
  });

  it("requires analysis and a current approved Epic before decomposition", () => {
    expect(canDecompose(null, epicFixture).ok).toBe(false);
    expect(canDecompose(analysisFixture, epicFixture)).toEqual({
      ok: false,
      reason: "Approve the Epic first.",
    });
    expect(canDecompose(analysisFixture, { ...epicFixture, status: "approved" })).toEqual({
      ok: true,
    });
  });

  it("blocks approval when an item is stale", () => {
    const stale = {
      ...epicFixture,
      stale: { reason: "requirement_changed" as const, since: "2026-01-01T13:00:00Z" },
    };
    expect(canApprove(stale)).toEqual({
      ok: false,
      reason: "Reconcile this item because its source requirement changed.",
    });
  });

  it("blocks repeat approval until the approved version changes", () => {
    expect(canApprove({ ...epicFixture, status: "approved" })).toEqual({
      ok: false,
      reason: "This version is already approved. Regenerate or edit it before approving again.",
    });
  });

  it("describes human review and downstream impact before regeneration", () => {
    const approved = { ...epicFixture, status: "approved" as const };
    expect(regenerationLoss(approved, featureSetFixture)).toContain("mark 2 Features out of date");
    expect(regenerationLoss(epicFixture, featureSetFixture)).toBeNull();
  });

  it("only offers Story generation on an approved, current Feature", () => {
    expect(canGenerateStories(approvedFeatureFixture)).toEqual({ ok: true });
    expect(canGenerateStories({ ...approvedFeatureFixture, status: "generated" })).toEqual({
      ok: false,
      reason: "Approve the Feature before generating its Stories.",
    });
    expect(
      canGenerateStories({
        ...approvedFeatureFixture,
        stale: { reason: "requirement_changed", since: "2026-01-01T13:00:00Z" },
      }),
    ).toEqual({
      ok: false,
      reason:
        "Reconcile the stale Feature because its source requirement changed before changing Stories.",
    });
  });

  it("warns before regenerating over human-owned Story content", () => {
    expect(storyRegenerationLoss(storyFixture)).toBeNull();
    expect(storyRegenerationLoss({ ...storyFixture, status: "edited" })).toContain(
      "acceptance criteria",
    );
    expect(storyRegenerationLoss({ ...storyFixture, status: "approved" })).toContain("approved");
  });
});
