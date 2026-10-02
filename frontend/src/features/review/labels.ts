import type {
  Approval,
  ApprovalTargetKind,
  BreakdownReview,
  ReviewFlag,
} from "../../api/client";
import type { BadgeTone } from "../../components/ui";

/**
 * Every enum the Review & approve screen renders, in the words a business
 * owner reads.
 *
 * `docs/ux-plan.md` §3.7 found `.replaceAll("_", " ")` on this screen at three
 * sites — the approval lifecycle, the effective status and each Story's state —
 * and the flag filters rendering the literal strings `all`, `blocking`,
 * `warning` and `resolved`. Severity, flag status, dependency evidence and an
 * approval's target kind reached the page unmapped too. §4: "One label map, in
 * the presentation layer, for every enum the API returns."
 *
 * The same shape as `features/analysis/labels.ts`, and kept beside the screen
 * for the same reason: nothing outside `features/review` renders these.
 */

type BreakdownStatus = BreakdownReview["status"];
type DependencyEvidenceKind = BreakdownReview["dependencies"][number]["evidence_kind"];

/** The four stages the backlog passes through, in order. */
export const LIFECYCLE: readonly BreakdownStatus[] = [
  "generated",
  "under_review",
  "needs_revision",
  "approved",
];

export const BREAKDOWN_STATUS_LABEL: Record<BreakdownStatus, string> = {
  generated: "Not yet submitted",
  under_review: "Under review",
  needs_revision: "Needs revision",
  approved: "Approved",
};

/**
 * Status is two channels, never colour alone (design-system §4.5): the badge
 * primitive adds the glyph. "Not yet submitted" is neutral rather than a
 * warning — nothing is wrong with a backlog nobody has submitted yet.
 */
export const BREAKDOWN_STATUS_TONE: Record<BreakdownStatus, BadgeTone> = {
  generated: "neutral",
  under_review: "warning",
  needs_revision: "danger",
  approved: "success",
};

export const SEVERITY_LABEL: Record<ReviewFlag["severity"], string> = {
  blocking: "Blocks approval",
  warning: "Worth resolving",
};

export const CATEGORY_LABEL: Record<ReviewFlag["category"], string> = {
  open_question: "Open question",
  assumption: "Assumption",
  ambiguity: "Ambiguity",
  dependency: "Dependency",
  architecture: "Architecture",
  quality: "Story quality",
  staleness: "Out of date",
};

/**
 * "Potential" is the analysis inferring a dependency from the requirement's
 * text; "catalogued" is one the architecture catalogue already records. The
 * API's words are accurate and mean nothing to a reader.
 */
export const EVIDENCE_KIND_LABEL: Record<DependencyEvidenceKind, string> = {
  potential: "Inferred",
  catalogued: "In the catalogue",
};

export const EVIDENCE_KIND_TONE: Record<DependencyEvidenceKind, BadgeTone> = {
  potential: "warning",
  catalogued: "neutral",
};

export const TARGET_KIND_LABEL: Record<ApprovalTargetKind, string> = {
  breakdown: "Whole backlog",
  epic: "Epic",
  feature: "Feature",
  story: "Story",
  flag: "Concern",
};

export const DECISION_LABEL: Record<Approval["decision"], string> = {
  approved: "approved",
  rejected: "rejected",
};

/** The flag filter, as the person reads it. */
export type FlagFilter = "all" | "blocking" | "warning" | "resolved";

export const FILTER_LABEL: Record<FlagFilter, string> = {
  all: "All",
  blocking: "Blocks approval",
  warning: "Worth resolving",
  resolved: "Resolved",
};

/** A risk is not a flag: its severity says how bad, not what it gates. */
export const RISK_SEVERITY_LABEL: Record<ReviewFlag["severity"], string> = {
  blocking: "Serious",
  warning: "Moderate",
};

/**
 * One timestamp format for the screen. `toLocaleString()` with no options picks
 * its own, which is how the decision log and the approval history came to
 * write the same kind of moment two ways (the reason `ProvenanceDetails` has
 * the same formatter).
 */
const TIMESTAMP = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export function when(iso: string): string {
  return TIMESTAMP.format(new Date(iso));
}
