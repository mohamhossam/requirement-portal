/**
 * Where a Requirement is in its journey, and what it needs next.
 *
 * SIX steps, not five. `docs/ux-plan.md` §3.2 records the inconsistency this
 * fixes: the journey declared five steps while `/review` and `/revisions` were
 * real screens the progress model did not contain, reachable only from buttons in
 * the Backlog page header — and `stagePath.ts` sends a requirement whose stage is
 * `features` or `stories` to `/review`, so clicking a worklist row could land a
 * person on a screen the stepper said did not exist. §4 calls promoting Review to
 * step 6 "the single highest-leverage IA change", because it makes the Product
 * Owner's screen a first-class destination. Done here.
 *
 * `/revisions` stays out on purpose. §4 puts History among the things that are
 * *always available* — a panel, not a step — because it is not a stage a
 * requirement passes through.
 *
 * The step names are §4's: Source, Clarify, Knowledge, Confirm, Backlog, Review &
 * approve. "Capture", "Analyse" and "Breakdown" are gone — method words for
 * screens a business owner has to read.
 *
 * `nextAction` is a UI affordance derived from what the workspace has already
 * loaded. It is NOT the backend's NextAction: that lives on the worklist read
 * model, which the workspace does not fetch. Do not treat this as authoritative
 * for anything but telling the person on screen what to do next.
 */

export type JourneyStepKey =
  | "source"
  | "clarify"
  | "knowledge"
  | "confirm"
  | "backlog"
  | "review";

export type JourneyStatus = "complete" | "current" | "blocked" | "pending";

export type JourneyState = {
  /** The source has enough in it to analyse. */
  eligible: boolean;
  hasAnalysis: boolean;
  /** Questions that must be answered before the analysis can be confirmed. */
  blockingCount: number;
  knowledgeReady: boolean;
  humanConfirmed: boolean;
  /** Closed as a duplicate: everything downstream of the source is unavailable. */
  isDuplicate: boolean;
};

export type JourneyStep = {
  key: JourneyStepKey;
  label: string;
  path: string;
  status: JourneyStatus;
};

const STEPS: { key: JourneyStepKey; label: string; segment: string }[] = [
  { key: "source", label: "Source", segment: "capture" },
  { key: "clarify", label: "Clarify", segment: "clarify" },
  { key: "knowledge", label: "Knowledge", segment: "knowledge" },
  { key: "confirm", label: "Confirm", segment: "confirm" },
  { key: "backlog", label: "Backlog", segment: "breakdown" },
  { key: "review", label: "Review & approve", segment: "review" },
];

/**
 * The furthest step that still needs something from a person.
 *
 * It stops at `backlog`. Whether the generated backlog has been approved is not
 * in `JourneyState` — it lives in the review projection, which the shell does not
 * fetch — so claiming Review as the current step would be a guess. Review is
 * reachable and unblocked once the analysis is confirmed, which is the honest
 * statement of what is known here.
 */
function currentKey(state: JourneyState): JourneyStepKey {
  if (!state.eligible) return "source";
  if (!state.hasAnalysis || state.blockingCount > 0) return "clarify";
  if (!state.knowledgeReady) return "knowledge";
  if (!state.humanConfirmed) return "confirm";
  return "backlog";
}

/**
 * A step is blocked when reaching it cannot help yet: the analysis cannot be
 * confirmed before the knowledge screen clears, and neither the backlog nor its
 * review exists before confirmation. Blocked steps stay navigable — each
 * destination explains itself — but they should not read as available.
 */
function isBlocked(key: JourneyStepKey, state: JourneyState): boolean {
  if (state.isDuplicate) return key !== "source";
  if (key === "confirm") return !state.knowledgeReady;
  if (key === "backlog" || key === "review") return !state.humanConfirmed;
  return false;
}

export function journey(requirementId: string, state: JourneyState): JourneyStep[] {
  const current = currentKey(state);
  const currentIndex = STEPS.findIndex((step) => step.key === current);
  return STEPS.map((step, index) => ({
    key: step.key,
    label: step.label,
    path: `/requirements/${requirementId}/${step.segment}`,
    status:
      index < currentIndex ? "complete"
      : index === currentIndex ? "current"
      : isBlocked(step.key, state) ? "blocked"
      : "pending",
  }));
}

export function currentStep(steps: JourneyStep[]): JourneyStep | undefined {
  return steps.find((step) => step.status === "current");
}

const plural = (count: number, one: string, many: string) =>
  `${count} ${count === 1 ? one : many}`;

/** What the person should do next, in their words, or null when nothing is owed. */
export function nextAction(
  state: JourneyState,
  steps: JourneyStep[],
): { label: string; to: string } | null {
  const step = currentStep(steps);
  if (!step) return null;
  if (state.isDuplicate) return null;

  const label = {
    source: "Add a business need or attach a ready file",
    clarify: state.hasAnalysis
      ? `Answer ${plural(state.blockingCount, "blocking question", "blocking questions")}`
      : "Analyse the requirement",
    knowledge: "Review the knowledge findings",
    confirm: "Confirm the analysis",
    backlog: "Review the generated backlog",
    review: "Review the backlog for approval",
  }[step.key];

  return { label, to: step.path };
}
