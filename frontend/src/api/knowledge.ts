import { api, apiDownload, apiRequest, apiRequestNoContent } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Capability = {
  id: string; name: string; triggers: string[];
  /** The capability domain it is placed in (ADR-0089); null or absent while unplaced. */
  domain_id?: string | null;
  /** The component of its system that delivers it (ADR-0092); null or absent while unplaced. */
  component_id?: string | null;
};
/** A business area capabilities belong to; parent_id nests one inside another. */
export type CapabilityDomain = Schemas["CapabilityDomainSchema"];
/** A named part of a system, such as a module or service; it groups the system's capabilities. */
export type Component = Schemas["SystemComponentSchema"];
/** Where systems sit in the landscape, such as Customer › Assisted (ADR-0094); a separate tree. */
export type LandscapeDomain = Schemas["LandscapeDomainSchema"];
/** A commercial offering, its order types and components, and the systems behind them (ADR-0095). */
export type ProductOffering = Schemas["ProductOfferingSchema"];
export type OfferingComponent = Schemas["OfferingComponentSchema"];
export type OrderType = Schemas["OrderTypeSchema"];
export type ComponentResponsibility = Schemas["ComponentResponsibilitySchema"];
export type OfferingPoint = Schemas["OfferingPointSchema"];
/** The activities that fulfil an offering's order type, with the flow derived from them (ADR-0096). */
export type Journey = Schemas["JourneySchema"];
export type Activity = Schemas["ActivitySchema"];
export type FlowRule = Schemas["FlowRuleSchema"];
export type FlowRuleKind = Schemas["FlowRuleKind"];
export type ActivityIntegration = Schemas["ActivityIntegrationSchema"];
export type JourneyEdge = Schemas["JourneyEdgeResponse"];
/** How sure the source document says it is of a fact. */
export type SourceConfidence = Schemas["SourceConfidence"];
export type System = {
  id: string; name: string; name_ar: string | null; aliases: string[];
  capabilities: Capability[]; constraints: string[];
  /** Absent from releases recorded before components existed. */
  components?: Component[];
  /** What the system is for; null or absent while nobody has said (ADR-0094). */
  description?: string | null;
  /** The landscape domain or sub-domain it sits in; null or absent while unplaced. */
  landscape_domain_id?: string | null;
};
/** How the source depends on the target (ADR-0088); "unspecified" when no source says. */
export type RelationshipKind = Schemas["RelationshipKind"];
export type Relationship = {
  source_system_id: string; target_system_id: string; description: string; kind: RelationshipKind;
};
export type KnowledgeDocument = {
  id: string; title: string; filename: string; mime_type: string; language: string; checksum: string;
  uploaded_by: string; uploaded_at: string;
};
export type KnowledgeRelease = {
  id: string; revision: number; status: "draft" | "published";
  built_revision: number | null; published_at: string | null; published_by: string | null;
  index_profile: string | null; index_hash: string | null;
  /** What people call this version, and who started it; null on unnamed older records. */
  name?: string | null; created_by?: string | null;
  systems: System[]; relationships: Relationship[];
  documents: KnowledgeDocument[];
  capability_domains?: CapabilityDomain[];
  landscape_domains?: LandscapeDomain[];
  products?: ProductOffering[];
  journeys?: Journey[];
};
export type ArchitectureJob = {
  id: string; kind: "index" | "mapping" | "extraction"; subject_id: string; fingerprint: string;
  actor_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  attempts: number; error_category: string | null;
};
export type Evidence = {
  id: string; source_label: string; location: string; text: string;
  document_version_id: string | null;
};
export type KnowledgeAuditEvent = {
  release_id: string; actor_id: string; action: string; revision: number;
  rationale: string | null; created_at: string;
};
export type ImpactPreview = {
  release_id: string; system_ids: string[]; citation_ids: string[];
  uncertainty: string | null; evidence: Evidence[];
};
export type CatalogueDiff = Schemas["CatalogueDiffResponse"];
export type CatalogueChange = Schemas["CatalogueChangeResponse"];
export type CatalogueFileFormat = "xlsx" | "yaml" | "json";
export type Suggestion = Schemas["CatalogueSuggestionResponse"];
export type SuggestionContent = Schemas["CandidateContentSchema"];
export type SuggestionsOverview = Schemas["CatalogueSuggestionsResponse"];
export type ExtractionRun = Schemas["ExtractionRunResponse"];
export type DocumentExtraction = Schemas["DocumentExtractionResponse"];
export type SampleRequirements = Schemas["SampleRequirementsResponse"];
export type SampleRequirement = Schemas["SampleRequirementSchema"];
export type ImpactComparison = Schemas["ImpactComparisonResponse"];
export type MappingImpact = Schemas["MappingImpactResponse"];
export type DocumentPassage = Schemas["DocumentPassageResponse"];

export const knowledgeRoot = "/architecture-knowledge";

export const knowledgeRequest = apiRequest;

const release = (id: string) => `${knowledgeRoot}/releases/${encodeURIComponent(id)}`;

const fileForm = (file: File, revision?: number) => {
  const body = new FormData();
  body.append("file", file);
  if (revision !== undefined) body.append("expected_revision", String(revision));
  return body;
};

export const knowledgeApi = {
  documents: () => knowledgeRequest<KnowledgeDocument[]>(`${knowledgeRoot}/documents`),
  me: api.getCurrentActor,
  releases: () => knowledgeRequest<KnowledgeRelease[]>(`${knowledgeRoot}/releases`),
  active: () => knowledgeRequest<KnowledgeRelease>(`${knowledgeRoot}/releases/active`),
  get: (id: string) => knowledgeRequest<KnowledgeRelease>(release(id)),
  audit: (id: string) => knowledgeRequest<KnowledgeAuditEvent[]>(`${release(id)}/audit`),
  createDraft: (name: string) => knowledgeRequest<KnowledgeRelease>(
    `${knowledgeRoot}/releases`, { method: "POST", body: JSON.stringify({ name }) },
  ),
  rename: (draft: KnowledgeRelease, name: string) => knowledgeRequest<KnowledgeRelease>(
    `${release(draft.id)}/name`,
    { method: "PUT", body: JSON.stringify({ expected_revision: draft.revision, name }) },
  ),
  discard: (draft: KnowledgeRelease) => apiRequestNoContent(
    release(draft.id), { method: "DELETE", body: JSON.stringify({ expected_revision: draft.revision }) },
  ),
  /** How much of the backlog is mapped, and how much uses an older version; counts only. */
  mappingImpact: () => knowledgeRequest<MappingImpact>(`${knowledgeRoot}/mapping-impact`),
  save: (draft: KnowledgeRelease) => knowledgeRequest<KnowledgeRelease>(
    release(draft.id),
    { method: "PUT", body: JSON.stringify({ expected_revision: draft.revision,
      systems: draft.systems, relationships: draft.relationships,
      // Left out when unknown, so the draft keeps the domains it has.
      ...(draft.capability_domains ? { capability_domains: draft.capability_domains } : {}),
      ...(draft.landscape_domains ? { landscape_domains: draft.landscape_domains } : {}),
      ...(draft.products ? { products: draft.products } : {}),
      ...(draft.journeys ? { journeys: draft.journeys } : {}) }) },
  ),
  upload: (draft: KnowledgeRelease, file: File, title: string, language: string) => {
    const body = fileForm(file, draft.revision);
    body.append("title", title);
    body.append("language", language);
    return knowledgeRequest<KnowledgeRelease>(`${release(draft.id)}/documents`, { method: "POST", body });
  },
  build: (draft: KnowledgeRelease) => knowledgeRequest<ArchitectureJob>(
    `${release(draft.id)}/build`,
    { method: "POST", body: JSON.stringify({ expected_revision: draft.revision }) },
  ),
  /** The latest evidence-index build for a release, or null before the first one. */
  buildStatus: (id: string) => knowledgeRequest<ArchitectureJob | null>(`${release(id)}/build`),
  publish: ({ release: draft, rationale }: { release: KnowledgeRelease; rationale: string }) =>
    knowledgeRequest<KnowledgeRelease>(`${release(draft.id)}/publish`,
      { method: "POST", body: JSON.stringify({ expected_revision: draft.revision, rationale }) }),
  activate: (published: KnowledgeRelease, rationale: string) => knowledgeRequest<KnowledgeRelease>(
    `${release(published.id)}/activate`,
    { method: "POST", body: JSON.stringify({ rationale }) },
  ),
  changes: (id: string) => knowledgeRequest<CatalogueDiff>(`${release(id)}/changes`),
  previewFile: (draft: KnowledgeRelease, file: File) => knowledgeRequest<CatalogueDiff>(
    `${release(draft.id)}/catalogue-file/preview`, { method: "POST", body: fileForm(file) },
  ),
  importFile: (draft: KnowledgeRelease, file: File) => knowledgeRequest<KnowledgeRelease>(
    `${release(draft.id)}/catalogue-file`, { method: "POST", body: fileForm(file, draft.revision) },
  ),
  exportFile: (id: string, format: CatalogueFileFormat) =>
    apiDownload(`${release(id)}/catalogue-file?format=${format}`, `${id}.${format}`),
  template: () => apiDownload(`${knowledgeRoot}/catalogue-template.xlsx`, "catalogue-template.xlsx"),
  selectDocuments: (draft: KnowledgeRelease, versionIds: string[]) => knowledgeRequest<KnowledgeRelease>(
    `${release(draft.id)}/documents`,
    { method: "PUT", body: JSON.stringify({ expected_revision: draft.revision,
      version_ids: versionIds }) },
  ),
  extract: (draft: KnowledgeRelease, versionId: string) => knowledgeRequest<ArchitectureJob>(
    `${release(draft.id)}/documents/${encodeURIComponent(versionId)}/extractions`, { method: "POST" },
  ),
  extractions: (id: string) => knowledgeRequest<DocumentExtraction[]>(`${release(id)}/extractions`),
  suggestions: (id: string) => knowledgeRequest<SuggestionsOverview>(`${release(id)}/suggestions`),
  decide: (draft: KnowledgeRelease, suggestionId: string, accept: boolean, content?: SuggestionContent) =>
    knowledgeRequest<KnowledgeRelease>(
      `${release(draft.id)}/suggestions/${encodeURIComponent(suggestionId)}/decision`,
      { method: "POST", body: JSON.stringify({ expected_revision: draft.revision, accept,
        content: content ?? null }) },
    ),
  rejectSuggestions: (draft: KnowledgeRelease, ids: string[]) =>
    knowledgeRequest<Schemas["RejectSuggestionsResponse"]>(
      `${release(draft.id)}/suggestions/rejection`,
      { method: "POST", body: JSON.stringify({ expected_revision: draft.revision, suggestion_ids: ids }) },
    ),
  passage: (releaseId: string, versionId: string, location: string) => knowledgeRequest<DocumentPassage>(
    `${release(releaseId)}/documents/${encodeURIComponent(versionId)}/passage?location=${encodeURIComponent(location)}`,
  ),
  acceptAll: (draft: KnowledgeRelease) => knowledgeRequest<Schemas["AcceptAllResponse"]>(
    `${release(draft.id)}/suggestions/acceptance`,
    { method: "POST", body: JSON.stringify({ expected_revision: draft.revision }) },
  ),
  preview: (target: KnowledgeRelease, query: string) => knowledgeRequest<Evidence[]>(
    `${release(target.id)}/preview`,
    { method: "POST", body: JSON.stringify({ query }) },
  ),
  previewImpact: (target: KnowledgeRelease, query: string) => knowledgeRequest<ImpactPreview>(
    `${release(target.id)}/preview-impact`,
    { method: "POST", body: JSON.stringify({ query }) },
  ),
  samples: () => knowledgeRequest<SampleRequirements>(`${knowledgeRoot}/sample-requirements`),
  saveSamples: (revision: number, items: SampleRequirement[]) => knowledgeRequest<SampleRequirements>(
    `${knowledgeRoot}/sample-requirements`,
    { method: "PUT", body: JSON.stringify({ expected_revision: revision, items }) },
  ),
  /** One requirement mapped by the version in use and by this built version. */
  compareImpact: (releaseId: string, query: string) => knowledgeRequest<ImpactComparison>(
    `${release(releaseId)}/compare-impact`,
    { method: "POST", body: JSON.stringify({ query }) },
  ),
  job: (id: string) => knowledgeRequest<ArchitectureJob>(`/jobs/${id}`),
  retryJob: (id: string) => knowledgeRequest<ArchitectureJob>(`/jobs/${id}/retry`,
    { method: "POST" }),
  cancelJob: (id: string) => knowledgeRequest<ArchitectureJob>(`/jobs/${id}/cancel`,
    { method: "POST" }),
  map: (requirementId: string) => knowledgeRequest<ArchitectureJob>(
    `/requirements/${encodeURIComponent(requirementId)}/architecture-mapping/jobs`,
    { method: "POST" },
  ),
};
