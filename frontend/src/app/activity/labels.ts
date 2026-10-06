import {
  BookOpen,
  CircleAlert,
  CircleCheck,
  FileText,
  MessageCircleQuestion,
  Sparkles,
  Stamp,
  UserRound,
  type LucideIcon,
} from "lucide-react";

import type { ActivityAction, ActivityCategory, ActivityEvent } from "../../api/client";

type AuditSource = ActivityEvent["sources"][number];

/**
 * The activity vocabulary, in business words (docs/ux-plan.md §3.7).
 *
 * Categories and actions are grouped here the way the audit projection emits
 * them (infrastructure/persistence/activity_projection.py), so the "What
 * happened" filter can offer each action under the category it belongs to.
 * AI job outcomes are listed under AI generation; a failed knowledge screen is
 * the same action, filed by the projection under Knowledge.
 */
export const categoryLabels: Record<ActivityCategory, string> = {
  requirement: "Requirement",
  clarification: "Clarification",
  access: "Ownership and access",
  generation: "AI generation",
  governance: "Review and approval",
  knowledge: "Knowledge",
};

/** "Any … activity", written out: lower-casing the label made "Any ai generation". */
export const anyCategoryLabels: Record<ActivityCategory, string> = {
  requirement: "Any change to a requirement",
  clarification: "Any clarification activity",
  access: "Any ownership or access change",
  generation: "Any AI generation activity",
  governance: "Any review or approval activity",
  knowledge: "Any knowledge activity",
};

/**
 * Work Requirement AI does itself. When one of these carries no person, it is
 * the product's own work, and says so, rather than reading as a gap in the trail.
 */
export const automaticActions = new Set<ActivityAction>([
  "analysis_generated",
  "ai_succeeded",
  "ai_failed",
  "ai_cancelled",
  "knowledge_screened",
]);

export const categoryIcons: Record<ActivityCategory, LucideIcon> = {
  requirement: FileText,
  clarification: MessageCircleQuestion,
  access: UserRound,
  generation: Sparkles,
  governance: Stamp,
  knowledge: BookOpen,
};

export const actionLabels: Record<ActivityAction, string> = {
  requirement_created: "Requirement created",
  requirement_updated: "Requirement updated",
  analysis_generated: "Analysis generated",
  analysis_confirmed: "Analysis confirmed",
  intent_proposal_decided: "Intent proposal decided",
  question_asked: "Question opened",
  question_assigned: "Question assigned",
  question_classified: "Question reclassified",
  question_resolved: "Question resolved",
  question_superseded: "Question replaced",
  owner_claimed: "Ownership claimed",
  owner_transferred: "Ownership transferred",
  reviewer_assigned: "Reviewer added",
  reviewer_removed: "Reviewer removed",
  ai_succeeded: "AI work finished",
  ai_failed: "AI work failed",
  ai_cancelled: "AI work cancelled",
  artifact_approved: "Backlog item approved",
  story_rejected: "Story rejected",
  review_flag_resolved: "Review flag resolved",
  review_commented: "Review comment added",
  breakdown_submitted: "Backlog submitted for review",
  breakdown_needs_revision: "Backlog sent back for revision",
  breakdown_approved: "Backlog approved",
  knowledge_screened: "Knowledge screened",
  requirement_marked_distinct: "Possible duplicate marked distinct",
  requirement_marked_duplicate: "Requirement closed as duplicate",
  conflict_resolution_proposed: "Conflict resolution proposed",
  conflict_resolution_accepted: "Conflict resolution accepted",
  conflict_resolved: "Conflict resolved",
  finding_source_retired: "Finding closed: source retired",
};

/** Filter order: the daily loop first, housekeeping last. */
export const actionsByCategory: Array<{ category: ActivityCategory; actions: ActivityAction[] }> = [
  {
    category: "clarification",
    actions: [
      "analysis_generated",
      "question_asked",
      "question_assigned",
      "question_classified",
      "question_resolved",
      "question_superseded",
    ],
  },
  {
    category: "governance",
    actions: [
      "analysis_confirmed",
      "intent_proposal_decided",
      "artifact_approved",
      "story_rejected",
      "breakdown_submitted",
      "breakdown_needs_revision",
      "breakdown_approved",
      "review_commented",
      "review_flag_resolved",
    ],
  },
  { category: "requirement", actions: ["requirement_created", "requirement_updated"] },
  { category: "generation", actions: ["ai_succeeded", "ai_failed", "ai_cancelled"] },
  {
    category: "knowledge",
    actions: [
      "knowledge_screened",
      "requirement_marked_distinct",
      "requirement_marked_duplicate",
      "conflict_resolution_proposed",
      "conflict_resolution_accepted",
      "conflict_resolved",
      "finding_source_retired",
    ],
  },
  { category: "access", actions: ["owner_claimed", "owner_transferred", "reviewer_assigned", "reviewer_removed"] },
];

/**
 * The few outcomes that carry a status (DESIGN.md, Reserved Vocabulary): an
 * approval is green, a failure red, a send-back amber. Everything else is a
 * record, not a state, and stays neutral. Each ships a glyph beside the words.
 */
export const actionTone: Partial<Record<ActivityAction, { tone: "success" | "warning" | "danger"; icon: LucideIcon }>> = {
  analysis_confirmed: { tone: "success", icon: CircleCheck },
  artifact_approved: { tone: "success", icon: CircleCheck },
  breakdown_approved: { tone: "success", icon: CircleCheck },
  breakdown_needs_revision: { tone: "warning", icon: CircleAlert },
  story_rejected: { tone: "warning", icon: CircleAlert },
  ai_failed: { tone: "danger", icon: CircleAlert },
};

const sourceLabels: Record<AuditSource["kind"], string> = {
  requirement_revision: "Requirement version",
  breakdown_revision: "Backlog revision",
  analysis_round: "Analysis round",
  clarification_question: "Question",
  intent_proposal: "Intent proposal",
  access_change: "Access change",
  ai_job: "AI job",
  approval: "Approval record",
  review_comment: "Review comment",
  review_decision: "Review decision",
  review_flag: "Review flag",
  knowledge_finding: "Knowledge finding",
};

/**
 * The record an event was read from, in words, plus the short reference an
 * auditor can quote. A revision id is `<requirement>:<n>`, so it reads as
 * "Requirement version 3"; everything else is an opaque id, shown as its first
 * eight characters in mono, the way the worklist shows requirement IDs.
 */
export function sourceView(source: AuditSource) {
  const label = sourceLabels[source.kind];
  const version = /:(\d+)$/.exec(source.source_id)?.[1];
  if (version && (source.kind === "requirement_revision" || source.kind === "breakdown_revision")) {
    return { label: `${label} ${version}`, reference: null };
  }
  return { label, reference: source.source_id.replace(/-/g, "").slice(0, 8) };
}

/** "Today", "Yesterday", or the weekday and date, in the reader's own time. */
export function dayLabel(date: Date, now = new Date()) {
  const startOf = (value: Date) => new Date(value.getFullYear(), value.getMonth(), value.getDate()).getTime();
  const days = Math.round((startOf(now) - startOf(date)) / 86_400_000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  return date.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: date.getFullYear() === now.getFullYear() ? undefined : "numeric",
  });
}

export const dayKey = (date: Date) => `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;

/** A UTC day boundary (`2026-09-21T00:00:00Z`), as the date a person picked. */
export const utcDate = (iso: string) => iso.slice(0, 10);

/**
 * "21 Sep" for a UTC date — the year only when it is not this one — without
 * letting the reader's own zone move it a day.
 */
export function utcDayLabel(iso: string) {
  const date = new Date(iso);
  const thisYear = date.getUTCFullYear() === new Date().getUTCFullYear();
  return date.toLocaleDateString(undefined, { timeZone: "UTC", day: "numeric", month: "short", year: thisYear ? undefined : "numeric" });
}

/** Before is the first day left out, so it has to come after From. */
export function dateRangeError({ start, end }: { start: string; end: string }) {
  return start && end && end <= start ? "Before is not included, so pick a day after From." : undefined;
}

/** "GMT+3" — the zone the times on this page are shown in. */
export function localZoneName(date = new Date()) {
  return new Intl.DateTimeFormat(undefined, { timeZoneName: "short" }).formatToParts(date).find((part) => part.type === "timeZoneName")?.value ?? "local time";
}
