import type { KnowledgeFinding, KnowledgeReview } from "../../api/client";
import type { BadgeTone } from "../../components/ui";
import { evidenceFieldLabel } from "../analysis/labels";

/**
 * The Knowledge screen's vocabulary, in business language.
 *
 * The baseline critique for Phase 5 found the screen printing its data record:
 * "open", "resolution pending" and "action required" through
 * `.replaceAll("_", " ")`, evidence fields as `business need`, and the linked
 * requirement as an eight-character hash. Everything the screen says about a
 * finding comes from here, and a unit test asserts no raw value reaches the page.
 */

export const REVIEW_HEADING: Record<KnowledgeReview["status"], string> = {
  required: "Not checked yet",
  stale: "Check out of date",
  action_required: "Decisions needed",
  ready: "Knowledge review clear",
};

export const REVIEW_DESCRIPTION: Record<KnowledgeReview["status"], string> = {
  required: "This version of the requirement has not been checked against other requirements yet.",
  stale: "The requirement changed after it was last checked against other requirements.",
  action_required:
    "Each overlap below needs an owner’s decision before the analysis can be confirmed. You can decide them while Clarify is still in progress.",
  ready: "Nothing in this version repeats or conflicts with another requirement. Confirmation is not waiting on this step.",
};

export const RUNNING_HEADING = "Screening in progress";
export const RUNNING_DESCRIPTION =
  "This requirement is being checked against other requirements. You can keep working on Clarify meanwhile.";

export const KIND_LABEL: Record<KnowledgeFinding["kind"], string> = {
  possible_duplicate: "Possible duplicate of",
  possible_contradiction: "Possible contradiction with",
};

/** Where a quoted passage came from: the requirement's own fields, which Clarify never quotes. */
const FIELD_LABEL: Record<string, string> = {
  title: "Title",
  business_need: "Business need",
  desired_outcome: "Desired outcome",
  customer_context: "Customer context",
  channel: "Channel",
  system: "System",
  business_rule: "Business rule",
  constraint: "Constraint",
  known_fact: "Known fact",
  conflict_resolution: "Agreed resolution",
};

const PREFIX_LABEL: Record<string, string> = {
  clarification: "Clarification answer",
  intent: "Intent decision",
  proposal: "Reference decision",
};

/**
 * `clarification:open_question` and `proposal:<uuid>` carry a prefix that says
 * what kind of passage it is; the part after the colon is either another enum
 * or an identifier, and neither belongs on the page.
 */
export function fieldLabel(field: string): string {
  if (FIELD_LABEL[field]) return FIELD_LABEL[field];
  const prefix = field.split(":")[0] ?? "";
  if (PREFIX_LABEL[prefix]) return PREFIX_LABEL[prefix];
  // Clarify's map already humanises the analysis's own field names.
  return field.trim() ? evidenceFieldLabel(field.replaceAll(":", " ")) : "Requirement text";
}

export const DECISION_LABEL: Record<string, string> = {
  distinct: "Marked as distinct",
  duplicate: "Closed as a duplicate",
  resolution_proposed: "Resolution proposed",
  resolution_accepted: "Resolution accepted",
};

export function decisionLabel(kind: string): string {
  return DECISION_LABEL[kind] ?? "Decision recorded";
}

export type FindingVerdict = { label: string; tone: BadgeTone };

/**
 * What a finding needs from the person looking at it.
 *
 * A pending resolution used to sit on Approved Green while nobody had accepted
 * it. "Waiting" is neutral; "needs you" is amber; only a settled finding is
 * green.
 */
export function findingVerdict(
  finding: KnowledgeFinding,
  { canDecide, actorId }: { canDecide: boolean; actorId: string | null },
): FindingVerdict {
  switch (finding.status) {
    case "open":
      // Amber is for what the viewer owes. Someone who cannot decide is waiting too.
      return canDecide
        ? { label: "Needs your decision", tone: "warning" }
        : { label: "Waiting for an owner’s decision", tone: "neutral" };
    case "resolution_pending":
      if (actorId && finding.resolution_approvals.includes(actorId)) {
        return { label: "Waiting for the other owner", tone: "neutral" };
      }
      return { label: canDecide ? "Needs your acceptance" : "Waiting for the owners", tone: canDecide ? "warning" : "neutral" };
    case "distinct":
      return { label: "Marked as distinct", tone: "success" };
    case "duplicate":
      return { label: "Closed as a duplicate", tone: "neutral" };
    case "resolved":
      return { label: "Resolved", tone: "success" };
  }
}

/** Whether this finding is waiting on the person looking at it. */
export function owedBy(finding: KnowledgeFinding, { canDecide, actorId }: { canDecide: boolean; actorId: string | null }) {
  if (!canDecide) return false;
  if (finding.status === "open") return true;
  return finding.status === "resolution_pending" && !(actorId && finding.resolution_approvals.includes(actorId));
}

export function approvalsLine(count: number): string {
  if (count === 0) return "No owner has accepted it yet.";
  return count === 1 ? "Accepted by 1 owner." : `Accepted by ${count} owners.`;
}

/** The other requirement in a finding, named by its own title where the evidence carries it. */
export function linkedRequirement(finding: KnowledgeFinding, requirementId: string) {
  const id = finding.subject_requirement_id === requirementId
    ? finding.related_requirement_id
    : finding.subject_requirement_id;
  const title = finding.evidence.find((item) => item.requirement_id === id && item.field === "title")?.excerpt.trim();
  return { id, title: title || null, name: title || `requirement ${id.slice(0, 8)}` };
}
