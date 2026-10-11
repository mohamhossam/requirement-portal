import type { ActivityListParams, DocumentListParams, RequirementListParams } from "../api/client";

let actorNamespace = "anonymous";

export function configureQueryActor(actorId: string | null) {
  actorNamespace = actorId?.trim() || "anonymous";
}

const scoped = (...parts: readonly unknown[]) => ["actor", actorNamespace, ...parts] as const;

export const queryKeys = {
  scope: (...parts: readonly unknown[]) => scoped(...parts),
  requirementLists: () => scoped("requirements"),
  requirementList: (params: RequirementListParams = {}) => scoped("requirements", params),
  requirement: (id: string) => scoped("requirement", id),
  requirementDrafts: () => scoped("requirement-drafts"),
  requirementDraft: (id: string) => scoped("requirement-draft", id),
  documents: () => scoped("documents"),
  documentList: (params: DocumentListParams = {}) => scoped("documents", params),
  document: (id: string) => scoped("document", id),
  requirementDocuments: (id: string) => scoped("requirement-documents", id),
  draftDocuments: (id: string) => scoped("draft-documents", id),
  analysis: (id: string) => scoped("analysis", id),
  analysisRounds: (id: string) => scoped("analysis-rounds", id),
  knowledgeReview: (id: string) => scoped("knowledge-review", id),
  priorArt: (id: string) => scoped("prior-art", id),
  answerSuggestions: (id: string, questionId: string) => scoped("answer-suggestions", id, questionId),
  assignments: (id: string) => scoped("assignments", id),
  epic: (id: string) => scoped("epic", id),
  features: (id: string) => scoped("features", id),
  revisions: (id: string) => scoped("revisions", id),
  publication: (id: string, revision: number) => scoped("publication", id, revision),
  publicationStatus: (id: string) => scoped("publication-status", id),
  stories: (id: string, featureId: string) => scoped("stories", id, featureId),
  storyQuality: (id: string, featureId: string) => scoped("story-quality", id, featureId),
  storyProposals: (id: string, featureId: string) => scoped("story-proposals", id, featureId),
  breakdownReview: (id: string) => scoped("breakdown-review", id),
  approvalWorkflow: (id: string) => scoped("approval-workflow", id),
  aiJobs: (id: string) => scoped("ai-jobs", id),
  notifications: () => scoped("notifications"),
  notificationPreference: () => scoped("notification-preference"),
  activity: (params: ActivityListParams = {}) => scoped("activity", params),
  reports: (weeks: number) => scoped("operational-report", weeks),
  savedViews: () => scoped("saved-views"),
};
