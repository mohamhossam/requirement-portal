import type { components } from "./schema";
import { ABORTED_REQUEST, ApiError, normalizeErrorDetail, REQUEST_TIMEOUT } from "./errors";

export type Requirement = components["schemas"]["RequirementResponse"];
export type RequirementDraft = components["schemas"]["RequirementDraftResponse"];
export type RequirementDraftList = components["schemas"]["RequirementDraftListResponse"];
export type RequirementDraftListParams = {
  /** The drafts nobody owns, which a person may claim, instead of their own. */
  unowned?: boolean;
  q?: string;
  sort?: components["schemas"]["DraftSort"];
  offset?: number;
  limit?: number;
};
export type RequirementImpact = components["schemas"]["RequirementImpactResponse"];
export type RequirementList = components["schemas"]["RequirementListResponse"];
export type RequirementWorklistItem = components["schemas"]["RequirementWorklistItemResponse"];
export type WorkflowStatus = components["schemas"]["WorkflowStatus"];
export type WorklistSort = components["schemas"]["WorklistSort"];
export type RequirementAnalysis = components["schemas"]["RequirementAnalysisResponse"];
export type Epic = components["schemas"]["EpicResponse"];
export type Feature = components["schemas"]["FeatureResponse"];
export type FeatureSet = components["schemas"]["FeatureSetResponse"];
export type GenerationStatus = components["schemas"]["GenerationStatus"];
export type Staleness = components["schemas"]["StalenessResponse"];
export type DeliveryDrop = components["schemas"]["DeliveryDrop"];
export type SplittingPattern = components["schemas"]["SplittingPattern"];
export type ClarificationKind = components["schemas"]["ClarificationKind"];
export type ClarificationSeverity = components["schemas"]["ClarificationSeverity"];
export type ClarificationQuestion = components["schemas"]["ClarificationQuestionResponse"];
export type AnalysisRound = components["schemas"]["AnalysisRoundResponse"];
export type IntentProposal = components["schemas"]["IntentProposalResponse"];
export type IntentProposalStatus = components["schemas"]["IntentProposalStatus"];
export type RevisionHistory = components["schemas"]["RevisionHistoryResponse"];
export type BreakdownComparison = components["schemas"]["BreakdownComparisonResponse"];
export type PublicationPreview = components["schemas"]["PublicationPreviewResponse"];
export type PublicationReport = components["schemas"]["PublicationReportResponse"];
export type PublicationStatus = components["schemas"]["PublicationStatusResponse"];
export type Story = components["schemas"]["StoryResponse"];
export type StorySet = components["schemas"]["StorySetResponse"];
export type AcceptanceCriterion = components["schemas"]["AcceptanceCriterionPayload"];
export type StoryChangeOperation = components["schemas"]["StoryChangeOperation"];
export type StoryProposal = components["schemas"]["StoryChangeProposalResponse"];
export type DocumentSummary = components["schemas"]["DocumentSummaryResponse"];
export type DocumentDetail = components["schemas"]["DocumentDetailResponse"];
/** A document with the Requirement or draft it is attached to, as the list and its page show it. */
export type DocumentListItem = components["schemas"]["DocumentListItemResponse"];
export type DocumentList = components["schemas"]["DocumentListResponse"];
export type DocumentOwnerSummary = components["schemas"]["DocumentOwnerResponse"];
export type OwnedDocumentDetail = components["schemas"]["OwnedDocumentDetailResponse"];
export type DocumentListParams = {
  q?: string;
  filter?: components["schemas"]["DocumentFilter"];
  /** A requirement's or draft's id. */
  owner?: string;
  sort?: components["schemas"]["DocumentSort"];
  offset?: number;
  limit?: number;
};
export type DocumentContent = components["schemas"]["DocumentContentResponse"];
export type StoryQuality = components["schemas"]["StoryQualityResponse"];
export type FeatureStoryQualitySnapshot =
  components["schemas"]["FeatureStoryQualitySnapshotResponse"];
export type ArchitectureImpact = components["schemas"]["ArchitectureImpactResponse"];
export type ArchitectureMappingJob = components["schemas"]["ArchitectureJobResponse"];
export type BreakdownReview = components["schemas"]["BreakdownReviewResponse"];
export type ReviewFlag = components["schemas"]["ReviewFlagResponse"];
export type ApprovalWorkflow = components["schemas"]["ApprovalWorkflowResponse"];
export type Approval = components["schemas"]["ApprovalResponse"];
export type ApprovalTargetKind = components["schemas"]["ApprovalTargetKind"];
export type Actor = components["schemas"]["ActorResponse"];
export type IdentityConfig = components["schemas"]["IdentityConfigResponse"];
export type RequirementAccess = components["schemas"]["RequirementAccessResponse"];
export type AiJob = components["schemas"]["AiJobResponse"];
export type AiJobOperation = components["schemas"]["AiJobOperation"];
export type Notification = components["schemas"]["NotificationResponse"];
export type NotificationPreference = components["schemas"]["NotificationPreferenceResponse"];
export type ActivityEvent = components["schemas"]["ActivityEventResponse"];
export type ActivityList = components["schemas"]["ActivityListResponse"];
export type ActivityAction = components["schemas"]["ActivityAction"];
export type ActivityCategory = components["schemas"]["ActivityCategory"];
export type OperationalReport = components["schemas"]["OperationalReportResponse"];
export type SavedRequirementView = components["schemas"]["SavedViewResponse"];
export type SavedViewCriteria = components["schemas"]["SavedViewCriteriaRequest"];
export type KnowledgeReview = components["schemas"]["KnowledgeReviewResponse"];
/** Similar past requirements from the historic corpus: reference only (ADR-0102). */
export type PriorArt = components["schemas"]["PriorArtResponse"];
export type PriorArtMatch = components["schemas"]["PriorArtMatchResponse"];
export type PriorArtPassage = components["schemas"]["PriorArtPassageResponse"];
export type KnowledgeScreenEnsure = components["schemas"]["KnowledgeScreenEnsureResponse"];
export type KnowledgeFinding = components["schemas"]["KnowledgeFindingResponse"];
export type KnowledgeFindingDecision = components["schemas"]["KnowledgeFindingDecisionRequest"];
export type AnswerSuggestionSet = components["schemas"]["AnswerSuggestionSetResponse"];
export type ExportFormat = "json" | "xlsx";
export type AiJobStartInput =
  | (components["schemas"]["AnalyseRequirementJobRequest"] & { context_token: string })
  | components["schemas"]["ClarifyAnalysisJobRequest"]
  | components["schemas"]["ResolveQuestionJobRequest"]
  | components["schemas"]["ResolveQuestionsJobRequest"]
  | (components["schemas"]["GenerateEpicJobRequest"] & { context_token: string })
  | (components["schemas"]["GenerateFeaturesJobRequest"] & { context_token: string })
  | (components["schemas"]["GenerateStoriesJobRequest"] & { context_token: string })
  | (components["schemas"]["RegenerateStoryJobRequest"] & { context_token: string })
  | (components["schemas"]["RegenerateStorySetJobRequest"] & { context_token: string })
  | components["schemas"]["ProposeStoryChangeJobRequest"]
  | components["schemas"]["EvaluateFeatureQualityJobRequest"]
  | components["schemas"]["GenerateBreakdownReviewJobRequest"]
  | components["schemas"]["ResolveReviewOpenQuestionJobRequest"]
  | components["schemas"]["ScreenRequirementKnowledgeJobRequest"]
  | components["schemas"]["SuggestClarificationAnswersJobRequest"];

export type RequirementInput = {
  title: string;
  description: string;
  desired_outcome?: string | null;
  customer_context?: string | null;
  channels?: string[];
  systems?: string[];
  business_rules?: string[];
  constraints?: string[];
  expected_version?: number;
  impact_acknowledged?: boolean;
};
export type RequirementDraftInput = {
  title: string;
  description: string;
  desired_outcome: string;
  customer_context: string;
  channels: string[];
  systems: string[];
  business_rules: string[];
  constraints: string[];
};
export type ClarificationAnswerInput = {
  kind: ClarificationKind;
  subject: string;
  answer: string;
};
export type ClarificationResolutionInput =
  components["schemas"]["ClarificationResolutionRequest"];
export type EpicInput = {
  name: string;
  outcome: string;
  business_case: string;
  source_reconciled?: boolean;
};
export type StoryInput = {
  role: string;
  action: string;
  value: string;
  acceptance_criteria: AcceptanceCriterion[];
  source_reconciled?: boolean;
};
export type FeatureInput = {
  name: string;
  outcome: string;
  delivery_drop: DeliveryDrop;
  splitting_pattern: SplittingPattern;
  splitting_rationale: string;
  source_reconciled?: boolean;
};

export type RequirementListParams = {
  q?: string;
  workflowStatus?: WorkflowStatus[];
  sort?: WorklistSort;
  offset?: number;
  limit?: number;
  ownerId?: string;
  assignedToMe?: boolean;
};

export type ActivityListParams = {
  requirementId?: string;
  categories?: ActivityCategory[];
  actions?: ActivityAction[];
  actorId?: string;
  occurredFrom?: string;
  occurredBefore?: string;
  offset?: number;
  limit?: number;
};

/** Where the API is: `VITE_API_BASE`, else this origin's `/api`. */
export const baseUrl = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");
let authorizationHeaders: () => Record<string, string> = () => ({});
let authenticationFailure: (() => void) | null = null;
let credentialSession = new AbortController();

/**
 * A new identity: every request still in flight belongs to the old one, so it is
 * aborted and its answer discarded, even when the answer has already arrived.
 */
export function configureAuthenticationHeaders(headers: () => Record<string, string>) {
  credentialSession.abort();
  credentialSession = new AbortController();
  authorizationHeaders = headers;
}

/**
 * The same identity with a renewed token. Requests in flight carry the old token,
 * which was valid when they left, so they are left to finish.
 */
export function replaceAuthenticationHeaders(headers: () => Record<string, string>) {
  authorizationHeaders = headers;
}

/** A query's `signal`: TanStack Query aborts it when nobody needs the answer any more. */
export type RequestOptions = { signal?: AbortSignal };

/** How long a request may take, body included, before the client gives up on it. */
const JSON_TIMEOUT_MS = 30_000;
/** Uploads and downloads carry whole files. */
const TRANSFER_TIMEOUT_MS = 120_000;
/** How long a downloaded file's object URL outlives the click that started it. */
export const DOWNLOAD_URL_LIFETIME_MS = 40_000;

/**
 * A signal that aborts when any of these does. `AbortSignal.any` where the browser
 * has it; Safari before 17.4 does not, so there the signals are joined by hand.
 */
function anySignal(signals: AbortSignal[]): AbortSignal {
  if (typeof AbortSignal.any === "function") return AbortSignal.any(signals);
  const joined = new AbortController();
  for (const signal of signals) {
    if (signal.aborted) {
      joined.abort(signal.reason);
      break;
    }
    signal.addEventListener("abort", () => joined.abort(signal.reason), { once: true });
  }
  return joined.signal;
}

/** The signals one request runs under, so a failure can say which one ended it. */
type Transfer = { session: AbortSignal; timeout: AbortSignal; caller?: AbortSignal };

/**
 * A request the client gave up on. All are status 0, because any may have reached
 * the server:
 * - the identity changed, or the caller stopped waiting (a cancelled query): both
 *   carry `ABORTED_REQUEST`, which nobody needs to be told about;
 * - the server took longer than the timeout: `REQUEST_TIMEOUT`;
 * - the network failed.
 */
function transportError(error: unknown, transfer: Transfer): ApiError {
  if (transfer.session.aborted) {
    return new ApiError(0, "The request was cancelled because the signed-in identity changed.", ABORTED_REQUEST);
  }
  if (transfer.caller?.aborted) {
    return new ApiError(0, "The request was cancelled.", ABORTED_REQUEST);
  }
  if (transfer.timeout.aborted) {
    return new ApiError(0, "The server took too long to answer. Please try again.", REQUEST_TIMEOUT);
  }
  return new ApiError(0, error instanceof Error ? error.message : "The API is unavailable.");
}

/** Read a response body, refusing it if the identity changed while it arrived. */
async function sessionBody<T>(transfer: Transfer, read: () => Promise<T>): Promise<T> {
  let body: T;
  try {
    body = await read();
  } catch (error) {
    throw transportError(error, transfer);
  }
  if (transfer.session.aborted) throw transportError(null, transfer);
  return body;
}

async function sessionFetch(
  url: string,
  init: RequestInit | undefined,
  timeoutMs: number,
): Promise<{ response: Response; transfer: Transfer }> {
  const transfer: Transfer = {
    session: credentialSession.signal,
    timeout: AbortSignal.timeout(timeoutMs),
    caller: init?.signal ?? undefined,
  };
  const signal = anySignal(
    [transfer.session, transfer.timeout, transfer.caller].filter(
      (item): item is AbortSignal => item !== undefined,
    ),
  );
  try {
    const response = await fetch(url, { ...init, signal });
    if (transfer.session.aborted) throw transportError(null, transfer);
    return { response, transfer };
  } catch (error) {
    throw error instanceof ApiError ? error : transportError(error, transfer);
  }
}

export function configureUnauthorizedHandler(onUnauthorized: (() => void) | null) {
  authenticationFailure = onUnauthorized;
}

export function configureAuthentication(
  headers: () => Record<string, string>,
  onUnauthorized?: () => void,
) {
  configureAuthenticationHeaders(headers);
  if (onUnauthorized !== undefined) configureUnauthorizedHandler(onUnauthorized);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const { response, transfer } = await sessionFetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...authorizationHeaders(),
      ...init?.headers,
    },
  }, isFormData ? TRANSFER_TIMEOUT_MS : JSON_TIMEOUT_MS);
  if (!response.ok) {
    if (response.status === 401) authenticationFailure?.();
    const payload: unknown = await response.json().catch(() => null);
    throw responseError(response.status, payload);
  }
  return sessionBody(transfer, () => response.json() as Promise<T>);
}

export const apiRequest = request;
export const apiRequestNoContent = requestNoContent;
export const apiDownload = (path: string, fallbackFilename: string) => download(path, fallbackFilename);

async function optional<T>(path: string, options?: RequestOptions): Promise<T | null> {
  try {
    return await request<T>(path, options);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

async function requestNoContent(path: string, init?: RequestInit): Promise<void> {
  const { response } = await sessionFetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authorizationHeaders(),
      ...init?.headers,
    },
  }, JSON_TIMEOUT_MS);
  if (!response.ok) {
    if (response.status === 401) authenticationFailure?.();
    const payload: unknown = await response.json().catch(() => null);
    throw responseError(response.status, payload);
  }
}

const requirementPath = (requirementId: string) =>
  `/requirements/${encodeURIComponent(requirementId)}`;

const storiesPath = (requirementId: string, featureId: string) =>
  `${requirementPath(requirementId)}/features/${encodeURIComponent(featureId)}/stories`;

const documentForm = (file: File, expectedVersion?: number, includeInAnalysis = false) => {
  const body = new FormData();
  body.append("file", file);
  body.append("include_in_analysis", String(includeInAnalysis));
  if (expectedVersion !== undefined) body.append("expected_version", String(expectedVersion));
  return body;
};

function responseError(status: number, payload: unknown): ApiError {
  const value = typeof payload === "object" && payload !== null
    ? payload as Record<string, unknown>
    : {};
  return new ApiError(
    status,
    normalizeErrorDetail(payload, `Request failed with status ${status}.`),
    typeof value.code === "string" ? value.code : undefined,
    typeof value.correlation_id === "string" ? value.correlation_id : undefined,
  );
}

function requirementListPath(params: RequirementListParams = {}) {
  const query = new URLSearchParams();
  if (params.q?.trim()) query.set("q", params.q.trim());
  params.workflowStatus?.forEach((status) => query.append("workflow_status", status));
  if (params.sort) query.set("sort", params.sort);
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.ownerId) query.set("owner_id", params.ownerId);
  if (params.assignedToMe) query.set("assigned_to_me", "true");
  const encoded = query.toString();
  return `/requirements${encoded ? `?${encoded}` : ""}`;
}

async function download(path: string, fallbackFilename: string): Promise<void> {
  const { response, transfer } = await sessionFetch(`${baseUrl}${path}`, {
    headers: authorizationHeaders(),
  }, TRANSFER_TIMEOUT_MS);
  if (!response.ok) {
    if (response.status === 401) authenticationFailure?.();
    const payload: unknown = await response.json().catch(() => null);
    throw responseError(response.status, payload);
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="([^"]+)"/i)?.[1] ?? fallbackFilename;
  const body = await sessionBody(transfer, () => response.blob());
  const objectUrl = URL.createObjectURL(body);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  // Firefox and Safari start the download after `click()` returns; revoked at once,
  // the file can arrive empty or not at all.
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), DOWNLOAD_URL_LIFETIME_MS);
}

function documentListPath(params: DocumentListParams = {}) {
  const query = new URLSearchParams();
  if (params.q?.trim()) query.set("q", params.q.trim());
  if (params.filter) query.set("filter", params.filter);
  if (params.owner) query.set("owner", params.owner);
  if (params.sort) query.set("sort", params.sort);
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  const encoded = query.toString();
  return `/documents${encoded ? `?${encoded}` : ""}`;
}

function draftListPath(params: RequirementDraftListParams = {}) {
  const query = new URLSearchParams();
  if (params.unowned) query.set("unowned", "true");
  if (params.q?.trim()) query.set("q", params.q.trim());
  if (params.sort) query.set("sort", params.sort);
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  const encoded = query.toString();
  return `/requirements/drafts${encoded ? `?${encoded}` : ""}`;
}

function activityListPath(params: ActivityListParams = {}) {
  const query = new URLSearchParams();
  if (params.requirementId) query.set("requirement_id", params.requirementId);
  params.categories?.forEach((category) => query.append("category", category));
  params.actions?.forEach((action) => query.append("action", action));
  if (params.actorId) query.set("actor_id", params.actorId);
  if (params.occurredFrom) query.set("occurred_from", params.occurredFrom);
  if (params.occurredBefore) query.set("occurred_before", params.occurredBefore);
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  const encoded = query.toString();
  return `/activity${encoded ? `?${encoded}` : ""}`;
}

async function requestBlob(path: string, options?: RequestOptions): Promise<Blob> {
  const { response, transfer } = await sessionFetch(
    `${baseUrl}${path}`,
    { ...options, headers: authorizationHeaders() },
    TRANSFER_TIMEOUT_MS,
  );
  if (!response.ok) {
    if (response.status === 401) authenticationFailure?.();
    const payload: unknown = await response.json().catch(() => null);
    throw responseError(response.status, payload);
  }
  return sessionBody(transfer, () => response.blob());
}

export const api = {
  getRequirementIndex: (id: string, options?: RequestOptions) => request<components["schemas"]["RequirementIndexStatus"]>(`/requirements/${encodeURIComponent(id)}/knowledge-index`, options),
  retryRequirementIndex: (id: string) => request<components["schemas"]["RequirementIndexStatus"]>(`/requirements/${encodeURIComponent(id)}/knowledge-index/retry`, { method: "POST" }),
  listAttachmentIngestions: (sourceId: string, draft: boolean, options?: RequestOptions) =>
    request<components["schemas"]["AttachmentIngestionView"][]>(`/${draft ? "requirement-drafts" : "requirements"}/${encodeURIComponent(sourceId)}/document-ingestions`, options),
  submitAttachment: (sourceId: string, draft: boolean, file: File, key: string, include: boolean, replacement?: DocumentSummary) => {
    const body = documentForm(file, replacement?.version, include);
    body.append("idempotency_key", key);
    if (replacement) body.append("document_id", replacement.id);
    return request<components["schemas"]["AttachmentIngestionView"]>(`/${draft ? "requirement-drafts" : "requirements"}/${encodeURIComponent(sourceId)}/document-ingestions`, { method: "POST", body });
  },
  controlAttachment: (sourceId: string, draft: boolean, id: string, version: number, action: "retry" | "cancellation" | "exclusion") =>
    request<components["schemas"]["AttachmentIngestionView"]>(`/${draft ? "requirement-drafts" : "requirements"}/${encodeURIComponent(sourceId)}/document-ingestions/${encodeURIComponent(id)}/${action}`, {
      method: "POST", body: JSON.stringify({ expected_version: version }),
    }),
  sourceImpact: ({ requirementId, offset, activeOnly, query }: { requirementId: string; offset: number; activeOnly: boolean; query: string }, options?: RequestOptions) =>
    request<components["schemas"]["DependencyImpactPage"]>(`/requirements/${encodeURIComponent(requirementId)}/source-impact?offset=${offset}&limit=20&active_only=${activeOnly}&query=${encodeURIComponent(query)}`, options),
  decideSourceImpact: (requirementId: string, item: DependencyImpact, decision: "retain_historical" | "revise_content", reason: string) =>
    request<DependencyImpact>(`/requirements/${encodeURIComponent(requirementId)}/source-impact/${encodeURIComponent(item.dependency.id)}/decisions`, { method: "POST", body: JSON.stringify({ publication_state: item.publication_state, expected_version: item.decisions.length, decision, reason }) }),
  searchUnifiedKnowledge: (query: string) => request<components["schemas"]["UnifiedSearchHit"][]>("/knowledge/search/unified", {
    method: "POST", body: JSON.stringify({ query }),
  }),
  listActivity: (params: ActivityListParams = {}, options?: RequestOptions) =>
    request<ActivityList>(activityListPath(params), options),
  getOperationalReport: (weeks: 4 | 12 | 26 = 12, options?: RequestOptions) =>
    request<OperationalReport>(`/reports/operational?weeks=${weeks}`, options),
  listSavedViews: (options?: RequestOptions) => request<SavedRequirementView[]>("/saved-views", options),
  createSavedView: (name: string, criteria: SavedViewCriteria) =>
    request<SavedRequirementView>("/saved-views", {
      method: "POST",
      body: JSON.stringify({ name, criteria }),
    }),
  updateSavedView: (
    id: string,
    name: string,
    criteria: SavedViewCriteria,
    expectedVersion: number,
  ) =>
    request<SavedRequirementView>(`/saved-views/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({ name, criteria, expected_version: expectedVersion }),
    }),
  deleteSavedView: (id: string, expectedVersion: number) =>
    requestNoContent(
      `/saved-views/${encodeURIComponent(id)}?expected_version=${expectedVersion}`,
      { method: "DELETE" },
    ),
  startAiJob: (id: string, input: AiJobStartInput, idempotencyKey: string = crypto.randomUUID()) =>
    request<AiJob>(`${requirementPath(id)}/ai-jobs`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify(input),
    }),
  listAiJobs: (id: string, activeOnly = false, options?: RequestOptions) =>
    request<AiJob[]>(`${requirementPath(id)}/ai-jobs?active_only=${activeOnly}`, options),
  getAiJob: (id: string, jobId: string) =>
    request<AiJob>(`${requirementPath(id)}/ai-jobs/${encodeURIComponent(jobId)}`),
  cancelAiJob: (id: string, jobId: string, expectedVersion: number) =>
    request<AiJob>(
      `${requirementPath(id)}/ai-jobs/${encodeURIComponent(jobId)}/cancellation`,
      { method: "POST", body: JSON.stringify({ expected_version: expectedVersion }) },
    ),
  retryAiJob: (
    id: string,
    jobId: string,
    expectedVersion: number,
    idempotencyKey: string = crypto.randomUUID(),
  ) =>
    request<AiJob>(`${requirementPath(id)}/ai-jobs/${encodeURIComponent(jobId)}/retry`, {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body: JSON.stringify({ expected_version: expectedVersion }),
    }),
  listNotifications: (unreadOnly = false, options?: RequestOptions) =>
    request<Notification[]>(`/notifications?unread_only=${unreadOnly}`, options),
  markNotificationRead: (notificationId: string) =>
    request<Notification>(`/notifications/${encodeURIComponent(notificationId)}/read`, {
      method: "POST",
    }),
  getNotificationPreference: (options?: RequestOptions) =>
    request<NotificationPreference>("/notifications/preferences/current", options),
  setNotificationPreference: (browserEnabled: boolean) =>
    request<NotificationPreference>("/notifications/preferences/current", {
      method: "PUT",
      body: JSON.stringify({ browser_enabled: browserEnabled }),
    }),
  getIdentityConfig: () => request<IdentityConfig>("/identity/config"),
  getCurrentActor: () => request<Actor>("/identity/me"),
  searchActors: (query = "", limit = 20, options?: RequestOptions) =>
    request<Actor[]>(`/identity/actors?q=${encodeURIComponent(query)}&limit=${limit}`, options),
  getAssignments: (id: string, options?: RequestOptions) =>
    request<RequirementAccess>(`${requirementPath(id)}/assignments`, options),
  getPriorArt: (id: string, options?: RequestOptions) =>
    request<PriorArt>(`${requirementPath(id)}/prior-art`, options),
  getKnowledgeReview: (id: string, options?: RequestOptions) =>
    request<KnowledgeReview>(`${requirementPath(id)}/knowledge-review`, options),
  ensureKnowledgeScreen: (id: string) =>
    request<KnowledgeScreenEnsure>(`${requirementPath(id)}/knowledge-screen/ensure`, {
      method: "POST",
    }),
  decideKnowledgeFinding: (
    id: string,
    findingId: string,
    input: KnowledgeFindingDecision,
  ) =>
    request<KnowledgeFinding>(
      `${requirementPath(id)}/knowledge-findings/${encodeURIComponent(findingId)}/decisions`,
      { method: "POST", body: JSON.stringify(input) },
    ),
  claimRequirementOwnership: (id: string, expectedVersion: number) =>
    request<RequirementAccess>(`${requirementPath(id)}/ownership/claim`, {
      method: "POST", body: JSON.stringify({ expected_version: expectedVersion })
    }),
  transferRequirementOwnership: (id: string, actorId: string, expectedVersion: number) =>
    request<RequirementAccess>(`${requirementPath(id)}/ownership`, {
      method: "PUT",
      body: JSON.stringify({ actor_id: actorId, expected_version: expectedVersion }),
    }),
  assignReviewer: (id: string, actorId: string, expectedVersion: number) =>
    request<RequirementAccess>(
      `${requirementPath(id)}/reviewers/${encodeURIComponent(actorId)}`,
      { method: "PUT", body: JSON.stringify({ expected_version: expectedVersion }) },
    ),
  removeReviewer: (id: string, actorId: string, expectedVersion: number) =>
    request<RequirementAccess>(
      `${requirementPath(id)}/reviewers/${encodeURIComponent(actorId)}`,
      { method: "DELETE", body: JSON.stringify({ expected_version: expectedVersion }) },
    ),
  claimDraftOwnership: (id: string) =>
    request<components["schemas"]["AssignmentResponse"]>(
      `/requirements/drafts/${encodeURIComponent(id)}/ownership/claim`,
      { method: "POST" },
    ),
  listDocuments: (params: DocumentListParams = {}, options?: RequestOptions) =>
    request<DocumentList>(documentListPath(params), options),
  getDocument: (id: string, options?: RequestOptions) =>
    request<OwnedDocumentDetail>(`/documents/${encodeURIComponent(id)}`, options),
  getDocumentContent: (id: string) =>
    request<DocumentContent>(`/documents/${encodeURIComponent(id)}/content`),
  getDocumentPdf: (id: string, options?: RequestOptions) =>
    requestBlob(`/documents/${encodeURIComponent(id)}/pdf`, options),
  getDocumentAsset: (documentId: string, versionId: string, assetId: string, options?: RequestOptions) =>
    requestBlob(
      `/documents/${encodeURIComponent(documentId)}/versions/` +
      `${encodeURIComponent(versionId)}/assets/${encodeURIComponent(assetId)}`, options),
  listRequirementDocuments: (id: string, options?: RequestOptions) =>
    request<DocumentSummary[]>(`${requirementPath(id)}/attachments`, options),
  uploadRequirementDocument: (id: string, file: File, includeInAnalysis = false) =>
    request<DocumentDetail>(`${requirementPath(id)}/attachments`, {
      method: "POST",
      body: documentForm(file, undefined, includeInAnalysis),
    }),
  uploadRequirementDocumentVersion: (
    requirementId: string, documentId: string, file: File, expectedVersion: number, includeInAnalysis = false
  ) =>
    request<DocumentDetail>(
      `${requirementPath(requirementId)}/attachments/${encodeURIComponent(documentId)}/versions`,
      { method: "POST", body: documentForm(file, expectedVersion, includeInAnalysis) },
    ),
  listDraftDocuments: (id: string, options?: RequestOptions) =>
    request<DocumentSummary[]>(`/requirement-drafts/${encodeURIComponent(id)}/attachments`, options),
  uploadDraftDocument: (id: string, file: File, includeInAnalysis = false) =>
    request<DocumentDetail>(`/requirement-drafts/${encodeURIComponent(id)}/attachments`, {
      method: "POST",
      body: documentForm(file, undefined, includeInAnalysis),
    }),
  uploadDraftDocumentVersion: (
    draftId: string, documentId: string, file: File, expectedVersion: number, includeInAnalysis = false
  ) =>
    request<DocumentDetail>(
      `/requirement-drafts/${encodeURIComponent(draftId)}/attachments/${encodeURIComponent(documentId)}/versions`,
      { method: "POST", body: documentForm(file, expectedVersion, includeInAnalysis) },
    ),
  setDocumentInclusion: (
    requirementId: string, documentId: string, included: boolean, expectedVersion: number
  ) =>
    request<DocumentDetail>(
      `${requirementPath(requirementId)}/attachments/${encodeURIComponent(documentId)}/analysis-inclusion`,
      { method: "PUT", body: JSON.stringify({ included, expected_version: expectedVersion }) },
    ),
  removeDocument: (requirementId: string, documentId: string, expectedVersion: number) =>
    requestNoContent(
      `${requirementPath(requirementId)}/attachments/${encodeURIComponent(documentId)}` +
        `?expected_version=${expectedVersion}`,
      { method: "DELETE" },
    ),
  setDraftDocumentInclusion: (draftId: string, documentId: string, included: boolean, expectedVersion: number) =>
    request<DocumentDetail>(`/requirement-drafts/${encodeURIComponent(draftId)}/attachments/${encodeURIComponent(documentId)}/analysis-inclusion`,
      { method: "PUT", body: JSON.stringify({ included, expected_version: expectedVersion }) }),
  removeDraftDocument: (draftId: string, documentId: string, expectedVersion: number) =>
    requestNoContent(`/requirement-drafts/${encodeURIComponent(draftId)}/attachments/${encodeURIComponent(documentId)}?expected_version=${expectedVersion}`, { method: "DELETE" }),
  createRequirement: (input: RequirementInput) =>
    request<Requirement>("/requirements", { method: "POST", body: JSON.stringify(input) }),
  listRequirements: (params: RequirementListParams = {}, options?: RequestOptions) =>
    request<RequirementList>(requirementListPath(params), options),
  getRequirement: (id: string, options?: RequestOptions) => request<Requirement>(requirementPath(id), options),
  createRequirementDraft: (input: RequirementDraftInput) =>
    request<RequirementDraft>("/requirements/drafts", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  listRequirementDrafts: (params: RequirementDraftListParams = {}, options?: RequestOptions) =>
    request<RequirementDraftList>(draftListPath(params), options),
  getRequirementDraft: (id: string, options?: RequestOptions) =>
    request<RequirementDraft>(`/requirements/drafts/${encodeURIComponent(id)}`, options),
  saveRequirementDraft: (id: string, input: RequirementDraftInput, expectedVersion: number) =>
    request<RequirementDraft>(`/requirements/drafts/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify({ ...input, expected_version: expectedVersion }),
    }),
  promoteRequirementDraft: (id: string, expectedVersion: number) =>
    request<Requirement>(`/requirements/drafts/${encodeURIComponent(id)}/promote`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion }),
    }),
  previewRequirementImpact: (id: string, input: RequirementInput) =>
    request<RequirementImpact>(`${requirementPath(id)}/impact-preview`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  updateRequirement: (id: string, input: RequirementInput) =>
    request<Requirement>(requirementPath(id), { method: "PUT", body: JSON.stringify(input) }),
  getAnalysis: (id: string, options?: RequestOptions) => optional<RequirementAnalysis>(`${requirementPath(id)}/analysis`, options),
  getAnswerSuggestions: (id: string, questionId: string, options?: RequestOptions) =>
    optional<AnswerSuggestionSet>(
      `${requirementPath(id)}/analysis/questions/${encodeURIComponent(questionId)}/answer-suggestions`, options),
  setHiddenWorksheetInclusion: (
    requirementId: string,
    documentId: string,
    worksheetNames: string[],
    expectedVersion: number,
  ) => request<DocumentDetail>(
    `${requirementPath(requirementId)}/attachments/${encodeURIComponent(documentId)}` +
      "/hidden-worksheets",
    { method: "PUT", body: JSON.stringify({ worksheet_names: worksheetNames, expected_version: expectedVersion }) },
  ),
  listAnalysisRounds: (id: string, options?: RequestOptions) =>
    request<AnalysisRound[]>(`${requirementPath(id)}/analysis/rounds`, options),
  askClarificationQuestion: (
    id: string,
    input: components["schemas"]["AskClarificationQuestionRequest"],
  ) =>
    request<ClarificationQuestion>(`${requirementPath(id)}/analysis/questions`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  classifyClarificationQuestion: (
    id: string,
    questionId: string,
    input: components["schemas"]["ClassifyClarificationQuestionRequest"],
  ) =>
    request<ClarificationQuestion>(
      `${requirementPath(id)}/analysis/questions/${encodeURIComponent(questionId)}`,
      { method: "PATCH", body: JSON.stringify(input) },
    ),
  assignClarificationQuestion: (
    id: string,
    questionId: string,
    assigneeId: string | null,
    expectedVersion: number,
  ) =>
    request<ClarificationQuestion>(
      `${requirementPath(id)}/analysis/questions/${encodeURIComponent(questionId)}/assignment`,
      {
        method: "PUT",
        body: JSON.stringify({ assignee_id: assigneeId, expected_version: expectedVersion }),
      },
    ),
  saveClarificationDraft: (
    id: string,
    questionId: string,
    answer: string,
    expectedVersion: number,
  ) =>
    request<ClarificationQuestion>(
      `${requirementPath(id)}/analysis/questions/${encodeURIComponent(questionId)}/draft`,
      { method: "PUT", body: JSON.stringify({ answer, expected_version: expectedVersion }) },
    ),
  confirmAnalysis: (id: string, expectedVersion: number) =>
    request<RequirementAnalysis>(`${requirementPath(id)}/analysis/confirmation`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion }),
    }),
  decideIntentProposal: (
    id: string,
    proposalId: string,
    input: components["schemas"]["DecideIntentProposalRequest"],
  ) =>
    request<RequirementAnalysis>(
      `${requirementPath(id)}/analysis/proposals/${encodeURIComponent(proposalId)}`,
      { method: "PATCH", body: JSON.stringify(input) },
    ),
  getEpic: (id: string, options?: RequestOptions) => optional<Epic>(`${requirementPath(id)}/epic`, options),
  editEpic: (id: string, input: EpicInput & { expected_version: number }) =>
    request<Epic>(`${requirementPath(id)}/epic`, {
      method: "PUT",
      body: JSON.stringify(input),
    }),
  approveEpic: (id: string, expectedVersion: number, expected: string, rationale?: string) =>
    request<Epic>(`${requirementPath(id)}/epic/approval`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion, expected_content_fingerprint: expected, rationale }),
    }),
  getFeatures: (id: string, options?: RequestOptions) => optional<FeatureSet>(`${requirementPath(id)}/features`, options),
  editFeature: (
    requirementId: string, featureId: string, input: FeatureInput & { expected_version: number }
  ) =>
    request<Feature>(
      `${requirementPath(requirementId)}/features/${encodeURIComponent(featureId)}`,
      { method: "PUT", body: JSON.stringify(input) },
    ),
  approveFeature: (
    requirementId: string,
    featureId: string,
    expectedVersion: number,
    expected: string,
    rationale?: string,
  ) =>
    request<Feature>(
      `${requirementPath(requirementId)}/features/${encodeURIComponent(featureId)}/approval`,
      {
        method: "POST",
        body: JSON.stringify({ expected_version: expectedVersion, expected_content_fingerprint: expected, rationale }),
      },
    ),
  getRevisionHistory: (id: string, options?: RequestOptions) =>
    request<RevisionHistory>(`${requirementPath(id)}/revisions`, options),
  compareBreakdownRevisions: (id: string, fromRevision: number, toRevision: number) =>
    request<BreakdownComparison>(
      `${requirementPath(id)}/revisions/compare?from_revision=${fromRevision}&to_revision=${toRevision}`,
    ),
  exportBreakdownRevision: (id: string, revision: number, format: ExportFormat) =>
    download(
      `${requirementPath(id)}/revisions/${revision}/export?format=${format}`,
      `requirement-${id}-breakdown-v${revision}.${format}`,
    ),
  getPublicationPreview: (id: string, revision: number, options?: RequestOptions) =>
    request<PublicationPreview>(`${requirementPath(id)}/revisions/${revision}/publication`, options),
  publishBreakdownRevision: (id: string, revision: number, approvalFingerprint: string) =>
    request<PublicationReport>(`${requirementPath(id)}/revisions/${revision}/publication`, {
      method: "POST",
      body: JSON.stringify({ approval_fingerprint: approvalFingerprint }),
    }),
  getPublicationStatus: (id: string, options?: RequestOptions) =>
    request<PublicationStatus>(`${requirementPath(id)}/publication`, options),
  retryPublication: (id: string) =>
    request<PublicationReport>(`${requirementPath(id)}/publication/retry`, { method: "POST" }),
  getStories: (id: string, featureId: string, options?: RequestOptions) =>
    optional<StorySet>(storiesPath(id, featureId), options),
  getFeatureStoryQualityAssessment: (id: string, featureId: string, options?: RequestOptions) =>
    optional<FeatureStoryQualitySnapshot>(`${storiesPath(id, featureId)}/quality-assessment`, options),
  startArchitectureMappingJob: (id: string) =>
    request<ArchitectureMappingJob>(`${requirementPath(id)}/architecture-mapping/jobs`, {
      method: "POST",
    }),
  getArchitectureMappingJob: (id: string, jobId: string) =>
    request<ArchitectureMappingJob>(
      `${requirementPath(id)}/architecture-mapping/jobs/${encodeURIComponent(jobId)}`,
    ),
  getBreakdownReview: (id: string, options?: RequestOptions) =>
    optional<BreakdownReview>(`${requirementPath(id)}/breakdown-review`, options),
  getApprovalWorkflow: (id: string, options?: RequestOptions) =>
    optional<ApprovalWorkflow>(`${requirementPath(id)}/approval-workflow`, options),
  submitForReview: (id: string, expectedFingerprint: string, expectedVersion: number) =>
    request<ApprovalWorkflow>(`${requirementPath(id)}/review-submission`, {
      method: "POST",
      body: JSON.stringify({
        expected_fingerprint: expectedFingerprint,
        expected_version: expectedVersion,
      }),
    }),
  approveBreakdown: (
    id: string, expectedFingerprint: string, expectedVersion: number, rationale?: string
  ) =>
    request<ApprovalWorkflow>(`${requirementPath(id)}/breakdown-approval`, {
      method: "POST",
      body: JSON.stringify({
        expected_fingerprint: expectedFingerprint,
        expected_version: expectedVersion,
        rationale,
      }),
    }),
  addReviewComment: (
    id: string,
    targetKind: ApprovalTargetKind,
    targetId: string,
    body: string,
    expectedVersion: number,
  ) =>
    request<ApprovalWorkflow>(`${requirementPath(id)}/breakdown-review/comments`, {
      method: "POST",
      body: JSON.stringify({
        target_kind: targetKind,
        target_id: targetId,
        body,
        expected_version: expectedVersion,
      }),
    }),
  recordReviewDecision: (
    id: string,
    input: {
      decision: string;
      rationale: string;
      expected_fingerprint: string;
      expected_version: number;
      target_flag_id?: string;
    },
  ) =>
    request<BreakdownReview>(`${requirementPath(id)}/breakdown-review/decisions`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
  resolveReviewFlag: (
    id: string,
    flagId: string,
    input: {
      decision: string;
      rationale: string;
      expected_fingerprint: string;
      expected_version: number;
    },
  ) =>
    request<BreakdownReview>(
      `${requirementPath(id)}/breakdown-review/flags/${encodeURIComponent(flagId)}/resolution`,
      { method: "POST", body: JSON.stringify(input) },
    ),
  editStory: (
    id: string, featureId: string, storyId: string,
    input: StoryInput & { expected_version: number }
  ) =>
    request<Story>(`${storiesPath(id, featureId)}/${encodeURIComponent(storyId)}`, {
      method: "PUT",
      body: JSON.stringify(input),
    }),
  listStoryProposals: (id: string, featureId: string, options?: RequestOptions) =>
    request<StoryProposal[]>(`${storiesPath(id, featureId)}/change-proposals`, options),
  applyStoryProposal: (
    id: string,
    featureId: string,
    proposalId: string,
    expectedVersion: number,
    expectedSetVersion: number,
  ) =>
    request<StorySet>(
      `${storiesPath(id, featureId)}/change-proposals/${encodeURIComponent(proposalId)}/application`,
      { method: "POST", body: JSON.stringify({ expected_version: expectedVersion, expected_set_version: expectedSetVersion }) },
    ),
  splitStory: (
    id: string,
    featureId: string,
    storyId: string,
    replacements: StoryInput[],
    expectedSetVersion: number,
  ) =>
    request<StorySet>(
      `${storiesPath(id, featureId)}/${encodeURIComponent(storyId)}/split`,
      { method: "POST", body: JSON.stringify({ replacements, expected_set_version: expectedSetVersion }) },
    ),
  mergeStories: (
    id: string,
    featureId: string,
    storyIds: string[],
    replacement: StoryInput,
    expectedSetVersion: number,
  ) =>
    request<StorySet>(`${storiesPath(id, featureId)}/merge`, {
      method: "POST",
      body: JSON.stringify({ story_ids: storyIds, replacement, expected_set_version: expectedSetVersion }),
    }),
  approveStory: (
    id: string,
    featureId: string,
    storyId: string,
    expectedVersion: number,
    expected: string,
    rationale?: string,
  ) =>
    request<Story>(`${storiesPath(id, featureId)}/${encodeURIComponent(storyId)}/approval`, {
      method: "POST",
      body: JSON.stringify({ expected_version: expectedVersion, expected_content_fingerprint: expected, rationale }),
    }),
  rejectStory: (
    id: string,
    featureId: string,
    storyId: string,
    expectedFingerprint: string,
    expectedVersion: number,
    expectedReviewVersion: number,
    reason: string,
  ) =>
    request<Story>(`${storiesPath(id, featureId)}/${encodeURIComponent(storyId)}/rejection`, {
      method: "POST",
      body: JSON.stringify({
        expected_fingerprint: expectedFingerprint,
        expected_version: expectedVersion,
        expected_review_version: expectedReviewVersion,
        reason,
      }),
    }),
  discardStoryProposal: (
    id: string,
    featureId: string,
    proposalId: string,
    expectedVersion: number,
    expectedSetVersion: number,
  ) =>
    requestNoContent(
      `${storiesPath(id, featureId)}/change-proposals/${encodeURIComponent(proposalId)}`,
      { method: "DELETE", body: JSON.stringify({ expected_version: expectedVersion, expected_set_version: expectedSetVersion }) },
    ),
};

export type DependencyImpact = components["schemas"]["DependencyImpact"];
