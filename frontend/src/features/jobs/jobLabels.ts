import type { AiJob } from "../../api/client";

/** Human wording for each AI operation, shared by the status panel and toasts. */
export const operationLabels: Record<string, string> = {
  analyse_requirement: "Analysing requirement",
  clarify_requirement_analysis: "Refining analysis",
  resolve_clarification_question: "Resolving question",
  resolve_clarification_questions: "Resolving questions",
  generate_epic: "Generating Epic",
  generate_features: "Generating Features",
  generate_stories: "Generating Stories",
  regenerate_story: "Regenerating Story",
  regenerate_story_set: "Regenerating Stories",
  propose_story_change: "Preparing Story proposal",
  evaluate_feature_quality: "Evaluating Story quality",
  generate_breakdown_review: "Generating breakdown review",
  resolve_review_open_question: "Resolving review question",
  screen_requirement_knowledge: "Screening requirement knowledge",
  suggest_clarification_answers: "Finding grounded answer suggestions",
  screen_prior_art: "Looking for similar past requirements",
};

/** What finished, in words, without the progressive tense. */
export const completionLabels: Record<string, string> = {
  analyse_requirement: "Analysis",
  clarify_requirement_analysis: "Analysis refinement",
  resolve_clarification_question: "Question resolution",
  resolve_clarification_questions: "Question resolution",
  generate_epic: "Epic generation",
  generate_features: "Feature generation",
  generate_stories: "Story generation",
  regenerate_story: "Story regeneration",
  regenerate_story_set: "Story regeneration",
  propose_story_change: "Story proposal",
  evaluate_feature_quality: "Story quality evaluation",
  generate_breakdown_review: "Breakdown review",
  resolve_review_open_question: "Review resolution",
  screen_requirement_knowledge: "Knowledge screening",
  suggest_clarification_answers: "Answer suggestions",
  screen_prior_art: "Similar past requirements check",
};

export const operationLabel = (operation: string) => operationLabels[operation] ?? operation;
export const completionLabel = (operation: string) => completionLabels[operation] ?? operation;

/** "1m 20s" — how long a job has been going, for the waiting person. */
export function elapsedLabel(job: AiJob, now = Date.now()): string | null {
  const from = job.started_at ?? job.created_at;
  const seconds = Math.floor((now - Date.parse(from)) / 1000);
  if (!Number.isFinite(seconds) || seconds < 5) return null;
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ${seconds % 60}s`;
}
