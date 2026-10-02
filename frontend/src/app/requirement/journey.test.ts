import { describe, expect, it } from "vitest";

import { currentStep, journey, nextAction, type JourneyState } from "./journey";

const base: JourneyState = {
  eligible: true,
  hasAnalysis: false,
  blockingCount: 0,
  knowledgeReady: false,
  humanConfirmed: false,
  isDuplicate: false,
};

const state = (overrides: Partial<JourneyState> = {}): JourneyState => ({ ...base, ...overrides });
const steps = (overrides?: Partial<JourneyState>) => journey("req-1", state(overrides));
const statuses = (overrides?: Partial<JourneyState>) =>
  Object.fromEntries(steps(overrides).map((step) => [step.key, step.status]));
const current = (overrides?: Partial<JourneyState>) => currentStep(steps(overrides))?.key;

describe("journey shape", () => {
  it("has one route per step, and no two steps share a destination", () => {
    const paths = steps().map((step) => step.path);
    expect(paths).toEqual([
      "/requirements/req-1/capture",
      "/requirements/req-1/clarify",
      "/requirements/req-1/knowledge",
      "/requirements/req-1/confirm",
      "/requirements/req-1/breakdown",
      // Step six. docs/ux-plan.md §3.2: Review was a real screen the progress
      // model did not contain, reachable only from a button in a page header.
      "/requirements/req-1/review",
    ]);
    expect(new Set(paths).size).toBe(paths.length);
  });

  it("has exactly one current step, whatever the state", () => {
    for (const overrides of [
      {}, { eligible: false }, { hasAnalysis: true }, { hasAnalysis: true, blockingCount: 3 },
      { hasAnalysis: true, knowledgeReady: true }, { hasAnalysis: true, knowledgeReady: true, humanConfirmed: true },
      { isDuplicate: true },
    ]) {
      expect(steps(overrides).filter((step) => step.status === "current")).toHaveLength(1);
    }
  });
});

describe("where the requirement is", () => {
  it("waits at the source until it is worth analysing", () => {
    expect(current({ eligible: false })).toBe("source");
    expect(statuses({ eligible: false }).clarify).toBe("pending");
  });

  it("moves to clarify once there is something to analyse", () => {
    expect(current()).toBe("clarify");
    expect(statuses().source).toBe("complete");
  });

  it("stays on clarify while questions block, since analysing is the same screen", () => {
    expect(current({ hasAnalysis: true, blockingCount: 2 })).toBe("clarify");
  });

  it("moves through knowledge, confirmation and the backlog in turn", () => {
    expect(current({ hasAnalysis: true })).toBe("knowledge");
    expect(current({ hasAnalysis: true, knowledgeReady: true })).toBe("confirm");
    expect(current({ hasAnalysis: true, knowledgeReady: true, humanConfirmed: true })).toBe("backlog");
  });

  it("marks everything behind the current step complete", () => {
    expect(statuses({ hasAnalysis: true, knowledgeReady: true, humanConfirmed: true })).toEqual({
      source: "complete", clarify: "complete", knowledge: "complete", confirm: "complete",
      backlog: "current",
      // Pending, not current: whether the generated backlog has been approved
      // lives in the review projection, which the workspace does not fetch, so
      // claiming Review as the current step would be a guess.
      review: "pending",
    });
  });
});

describe("steps that cannot help yet", () => {
  it("blocks confirmation until the knowledge screen clears", () => {
    expect(statuses({ hasAnalysis: true, blockingCount: 1 }).confirm).toBe("blocked");
  });

  it("blocks the backlog and its review until the analysis is confirmed", () => {
    expect(statuses({ hasAnalysis: true, blockingCount: 1 }).backlog).toBe("blocked");
    expect(statuses({ hasAnalysis: true, blockingCount: 1 }).review).toBe("blocked");
    expect(statuses({ hasAnalysis: true, knowledgeReady: true }).backlog).toBe("blocked");
    expect(statuses({ hasAnalysis: true, knowledgeReady: true }).review).toBe("blocked");
  });

  it("stops blocking once the precondition is met", () => {
    expect(statuses({ hasAnalysis: true, knowledgeReady: true }).confirm).toBe("current");
    expect(statuses({ hasAnalysis: true, knowledgeReady: true, humanConfirmed: true }).backlog).toBe("current");
    expect(statuses({ hasAnalysis: true, knowledgeReady: true, humanConfirmed: true }).review).toBe("pending");
  });

  it("blocks everything downstream of the source for a duplicate", () => {
    expect(statuses({ isDuplicate: true })).toEqual({
      source: "complete", clarify: "current", knowledge: "blocked", confirm: "blocked",
      backlog: "blocked", review: "blocked",
    });
  });
});

describe("what to do next", () => {
  it("names the work the current step is waiting on", () => {
    expect(nextAction(state({ eligible: false }), steps({ eligible: false })))
      .toMatchObject({ label: "Add a business need or attach a ready file", to: "/requirements/req-1/capture" });
    expect(nextAction(state(), steps()))
      .toMatchObject({ label: "Analyse the requirement", to: "/requirements/req-1/clarify" });
    expect(nextAction(state({ hasAnalysis: true }), steps({ hasAnalysis: true })))
      .toMatchObject({ label: "Review the knowledge findings" });
    expect(nextAction(state({ hasAnalysis: true, knowledgeReady: true }), steps({ hasAnalysis: true, knowledgeReady: true })))
      .toMatchObject({ label: "Confirm the analysis" });
  });

  it("counts the questions, and gets the singular right", () => {
    const one = { hasAnalysis: true, blockingCount: 1 };
    const many = { hasAnalysis: true, blockingCount: 4 };
    expect(nextAction(state(one), steps(one))?.label).toBe("Answer 1 blocking question");
    expect(nextAction(state(many), steps(many))?.label).toBe("Answer 4 blocking questions");
  });

  it("asks for nothing on a requirement closed as a duplicate", () => {
    expect(nextAction(state({ isDuplicate: true }), steps({ isDuplicate: true }))).toBeNull();
  });
});
