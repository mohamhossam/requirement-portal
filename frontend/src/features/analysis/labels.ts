import type {
  ClarificationKind,
  ClarificationSeverity,
  IntentProposal,
  IntentProposalStatus,
} from "../../api/client";

/**
 * Every enum this screen renders, in the words a business owner reads.
 *
 * `docs/ux-plan.md` §3.7 counted `.replaceAll("_", " ")` at six call sites and
 * called it a direct breach of `PRODUCT.md` Principle 3 — "a business owner
 * should never need the method". Five of them were on this screen: a question's
 * status, a proposal's status, a reconciliation action, a suggestion's evidence
 * field, and a round's raw severity. §4 sets the rule: "One label map, in the
 * presentation layer, for every enum the API returns."
 *
 * The same shape as `src/components/statusLabels.ts`, which does this job for
 * generation status. Kept beside the screen that owns these enums rather than
 * merged into it: nothing outside `features/analysis` renders any of them.
 */

export const INTENT_KIND_LABEL: Record<IntentProposal["kind"], string> = {
  desired_outcome: "Desired outcome",
  business_rule: "Business rule",
  constraint: "Constraint",
};

export const KIND_LABEL: Record<ClarificationKind, string> = {
  assumption: "Assumption",
  open_question: "Open question",
  ambiguity: "Ambiguity",
  potential_dependency: "Potential dependency",
};

/**
 * Severity is the analysis's own judgement of how much this matters, so it is
 * named as consequence rather than as a scale: "Low" alone tells a reader
 * nothing about what happens if they skip it.
 */
export const SEVERITY_LABEL: Record<ClarificationSeverity, string> = {
  low: "Minor",
  medium: "Significant",
  high: "Critical",
};

/**
 * `superseded` is the one that mattered most: a question retired by a later
 * round used to read as the literal word, which tells a business owner nothing
 * about why it stopped being their problem.
 */
export const QUESTION_STATUS_LABEL: Record<string, string> = {
  open: "Not started",
  in_progress: "Draft saved",
  resolved: "Answered",
  superseded: "Replaced by a later round",
};

export const PROPOSAL_STATUS_LABEL: Record<IntentProposalStatus, string> = {
  pending: "Awaiting your decision",
  accepted: "Accepted",
  edited: "Accepted with edits",
  rejected: "Rejected",
};

/**
 * What one round did to a question that already existed. `replaced` is the
 * outlier: the API's word describes the record, "Revised" describes what
 * happened to the question a person asked.
 */
export const CHANGE_ACTION_LABEL: Record<string, string> = {
  retained: "Kept",
  retired: "Retired",
  replaced: "Revised",
  created: "New",
};

export const SUGGESTION_SOURCE_LABEL = {
  current_analysis: "This analysis, unconfirmed",
  trusted_knowledge: "Trusted knowledge",
  combined: "Multiple evidence sources",
  published_reference: "Published reference · applicability unconfirmed",
} as const;

/**
 * A knowledge-evidence `field` is a free string on the wire, not an enum, so
 * this humanises rather than maps: `known_fact` becomes "Known fact". The
 * known names are spelled out above it because "Ai summary" is not a word.
 */
const EVIDENCE_FIELD_LABEL: Record<string, string> = {
  known_fact: "Known fact",
  business_rule: "Business rule",
  constraint: "Constraint",
  open_question: "Open question",
  ambiguity: "Ambiguity",
  assumption: "Assumption",
  potential_dependency: "Potential dependency",
  intent_proposal: "Intent proposal",
  requirement_text: "Requirement text",
  title: "Title",
};

export function evidenceFieldLabel(field: string): string {
  const known = EVIDENCE_FIELD_LABEL[field];
  if (known) return known;
  const words = field.replaceAll("_", " ").trim();
  return words ? words.charAt(0).toUpperCase() + words.slice(1) : field;
}

/** A label map's fallback is the raw value — visible, so it gets reported. */
export function questionStatusLabel(status: string): string {
  return QUESTION_STATUS_LABEL[status] ?? status;
}

export function changeActionLabel(action: string): string {
  return CHANGE_ACTION_LABEL[action] ?? action;
}
