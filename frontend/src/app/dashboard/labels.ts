import { Check, Copy, FilePen, History, PencilLine, RefreshCw, Send, TriangleAlert, type LucideIcon } from "lucide-react";

import type { RequirementWorklistItem, WorkflowStatus } from "../../api/client";
import type { BadgeTone } from "../../components/ui/Badge";

/**
 * Wording shared by the worklist, the attention strip and the filters, which
 * each show the same states and must not describe them differently.
 */
export const statusLabels: Record<WorkflowStatus, string> = {
  draft: "Draft",
  needs_answers: "Needs answers",
  reanalysing: "Re-analysing",
  ready_for_review: "Ready for review",
  approved: "Approved",
  needs_revision: "Needs revision",
  stale: "Stale",
  knowledge_review: "Knowledge review",
  duplicate: "Duplicate",
};

/**
 * The badge each status wears (docs/design-system.md §4.5): amber for anything
 * waiting on a person's judgement, green only for approved, neutral for states
 * that are in hand. Each carries its own glyph as the second channel, so "Ready
 * for review" is not mistaken for approved and "Stale" is not a generic warning.
 */
export const statusBadge: Record<WorkflowStatus, { tone: BadgeTone; icon: LucideIcon }> = {
  draft: { tone: "neutral", icon: FilePen },
  needs_answers: { tone: "warning", icon: TriangleAlert },
  reanalysing: { tone: "neutral", icon: RefreshCw },
  ready_for_review: { tone: "neutral", icon: Send },
  approved: { tone: "success", icon: Check },
  needs_revision: { tone: "warning", icon: PencilLine },
  stale: { tone: "warning", icon: History },
  knowledge_review: { tone: "warning", icon: TriangleAlert },
  duplicate: { tone: "neutral", icon: Copy },
};

export const jobLabels: Record<NonNullable<RequirementWorklistItem["active_ai_operation"]>, string> = {
  analyse_requirement: "Analysis queued",
  clarify_requirement_analysis: "Analysis refinement running",
  resolve_clarification_question: "Question resolution running",
  resolve_clarification_questions: "Question resolution running",
  generate_epic: "Epic generation running",
  generate_features: "Feature generation running",
  generate_stories: "Story generation running",
  regenerate_story: "Story regeneration running",
  regenerate_story_set: "Story-set regeneration running",
  propose_story_change: "Story proposal running",
  evaluate_feature_quality: "Quality evaluation running",
  generate_breakdown_review: "Review generation running",
  resolve_review_open_question: "Review resolution running",
  screen_requirement_knowledge: "Knowledge screening running",
  suggest_clarification_answers: "Answer suggestions running",
};

/**
 * Where the requirement has got to, in the journey's own words.
 *
 * The worklist rendered `current_stage` raw, so the Progress column read
 * "capture", "epic", "stories" — lowercase API enum values on the screen a
 * business owner opens first (docs/ux-plan.md §3.7, PRODUCT.md Principle 3).
 * The six journey steps are the vocabulary; the three backlog sub-stages say
 * which level of the backlog is in progress.
 */
export const stageLabels: Record<RequirementWorklistItem["current_stage"], string> = {
  capture: "Source",
  clarify: "Clarify",
  knowledge: "Knowledge",
  confirm: "Confirm",
  epic: "Backlog — Epic",
  features: "Backlog — Features",
  stories: "Backlog — Stories",
  review: "Review & approve",
  complete: "Complete",
};

export const nextActionLabels: Record<RequirementWorklistItem["next_action"], string> = {
  analyse: "Analyse requirement",
  answer_questions: "Answer open questions",
  confirm_analysis: "Confirm analysis",
  generate_epic: "Generate Epic",
  review_epic: "Review Epic",
  generate_features: "Generate Features",
  review_features: "Review Features",
  generate_stories: "Generate Stories",
  review_stories: "Review Stories",
  submit_for_review: "Submit for review",
  revise_backlog: "Revise backlog",
  approve_breakdown: "Grant final approval",
  reconcile_stale: "Review stale content",
  open: "Open requirement",
  review_knowledge: "Review knowledge findings",
};

/** Filter order: what a reviewer is most likely to be looking for, first. */
export const counterStatuses: WorkflowStatus[] = [
  "needs_answers",
  "reanalysing",
  "ready_for_review",
  "needs_revision",
  "stale",
  "knowledge_review",
  "draft",
  "approved",
  "duplicate",
];

export function updatedLabel(raw: string) {
  const value = new Date(raw);
  const seconds = Math.round((Date.now() - value.getTime()) / 1000);
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (seconds < 60) return formatter.format(-seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return formatter.format(-minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (hours < 24) return formatter.format(-hours, "hour");
  const days = Math.round(hours / 24);
  if (days < 30) return formatter.format(-days, "day");
  return value.toLocaleDateString();
}

export function actorLabel(item: RequirementWorklistItem) {
  if (item.last_activity?.actor?.display_name) return item.last_activity.actor.display_name;
  return item.last_activity ? "Actor unavailable" : "System";
}
