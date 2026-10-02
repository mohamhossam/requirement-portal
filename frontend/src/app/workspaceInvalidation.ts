import type { QueryClient } from "@tanstack/react-query";
import type { AiJob } from "../api/client";
import { queryKeys } from "./queryKeys";

export type WorkspaceChange =
  | "question" | "analysis" | "source" | "epic" | "features" | "stories"
  | "story-quality" | "story-proposals" | "answer-suggestions" | "knowledge"
  | "review" | "architecture" | "epic-approval" | "feature-approval";

export function workspaceChangeKeys(id: string, change: WorkspaceChange, featureId?: string) {
  const featureKey = (kind: string) => queryKeys.scope(kind, id, ...(featureId ? [featureId] : []));
  const governance = [queryKeys.breakdownReview(id), queryKeys.approvalWorkflow(id), queryKeys.revisions(id), queryKeys.requirementLists()];
  const stories = [featureKey("stories"), featureKey("story-quality"), featureKey("story-proposals")];
  const downstream = [queryKeys.epic(id), queryKeys.features(id), ...stories, ...governance];
  switch (change) {
    case "question": return [queryKeys.analysis(id), queryKeys.analysisRounds(id), queryKeys.revisions(id), queryKeys.requirementLists()];
    case "analysis":
    case "source": return [queryKeys.requirement(id), queryKeys.analysis(id), queryKeys.analysisRounds(id), queryKeys.knowledgeReview(id), queryKeys.scope("answer-suggestions", id), ...downstream];
    case "epic": return [queryKeys.epic(id), queryKeys.features(id), ...stories, ...governance];
    case "features": return [queryKeys.features(id), ...stories, ...governance];
    case "epic-approval": return [queryKeys.epic(id), ...governance];
    case "feature-approval": return [queryKeys.features(id), ...governance];
    case "stories": return [...stories, ...governance];
    case "story-quality": return [featureKey("story-quality"), queryKeys.breakdownReview(id), queryKeys.approvalWorkflow(id)];
    case "story-proposals": return [featureKey("story-proposals")];
    case "answer-suggestions": return [queryKeys.scope("answer-suggestions", id)];
    case "knowledge": return [queryKeys.knowledgeReview(id), queryKeys.requirement(id), queryKeys.requirementLists()];
    case "review": return governance;
    case "architecture": return [queryKeys.features(id), ...stories, ...governance];
  }
}

export function invalidateWorkspace(client: QueryClient, id: string, change: WorkspaceChange, featureId?: string) {
  return invalidateWorkspaceKeys(client, workspaceChangeKeys(id, change, featureId));
}

export function invalidateWorkspaceKeys(client: QueryClient, keys: ReadonlyArray<readonly unknown[]>) {
  const unique = [...new Map(keys.map((key) => [JSON.stringify(key), key])).values()];
  return Promise.all(unique.map(async (queryKey) => {
    // A first load has no data, so invalidation would join its in-flight read and
    // keep an answer from before the change; cancel it so the refetch is fresh.
    await client.cancelQueries({ queryKey });
    return client.invalidateQueries({ queryKey, refetchType: "active" });
  }));
}

const jobChanges: Record<AiJob["operation"], WorkspaceChange> = {
  analyse_requirement: "analysis", clarify_requirement_analysis: "analysis",
  resolve_clarification_question: "analysis", resolve_clarification_questions: "analysis",
  generate_epic: "epic", generate_features: "features", generate_stories: "stories",
  regenerate_story: "stories", regenerate_story_set: "stories",
  propose_story_change: "story-proposals", evaluate_feature_quality: "story-quality",
  generate_breakdown_review: "review", resolve_review_open_question: "analysis",
  screen_requirement_knowledge: "knowledge", suggest_clarification_answers: "answer-suggestions",
};

export function jobCompletionKeys(job: AiJob) {
  if (job.status !== "succeeded") return [];
  const match = job.result_resources?.map((item) => item.path.match(/\/breakdown\/features\/([^/]+)/)).find(Boolean);
  const featureId = match?.[1] ? decodeURIComponent(match[1]) : undefined;
  return workspaceChangeKeys(job.requirement_id, jobChanges[job.operation], featureId);
}
