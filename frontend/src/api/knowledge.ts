/**
 * Read-only views of the knowledge a Requirement relies on (ADR-0099).
 *
 * The library and the architecture catalogue are curated in the knowledge
 * portal. This app only shows what is published: the exact passage a
 * Requirement cites, the evidence behind an architecture impact, and which
 * catalogue version new mappings use.
 */
import { apiRequest } from "./client";
import type { components } from "./schema";

type Schemas = components["schemas"];
export type ActiveRelease = Schemas["ActiveRelease"];
export type ArchitectureEvidence = Schemas["ArchitectureEvidence"];
export type CitedPassage = Schemas["CitedPassage"];

/** Which exact published passage a citation names. */
export interface PassageCitation {
  document_id: string;
  publication_id: string;
  version_id: string;
  revision_id: string;
  block_id: string;
}

/**
 * Where knowledge administrators curate the library and the catalogues, or null when this
 * deployment has no knowledge portal (ADR-0104). `VITE_KNOWLEDGE_PORTAL_URL` names it; unset,
 * it is the platform path `/knowledge/`, and set empty, every link to it is hidden.
 */
export function knowledgePortalUrl(configured: string | undefined): string | null {
  if (configured === undefined) return "/knowledge/";
  const url = configured.trim();
  return url === "" ? null : url;
}

export const KNOWLEDGE_PORTAL_URL = knowledgePortalUrl(import.meta.env.VITE_KNOWLEDGE_PORTAL_URL);
/** The role that opens the knowledge portal. */
export const KNOWLEDGE_ADMIN_ROLE = "knowledge_admin";

export const knowledgeApi = {
  activeRelease: () => apiRequest<ActiveRelease | null>("/architecture/active-release"),
  evidence: (releaseId: string, chunkId: string) =>
    apiRequest<ArchitectureEvidence>(
      `/architecture-evidence/${encodeURIComponent(releaseId)}/${encodeURIComponent(chunkId)}`,
    ),
  passage: (citation: PassageCitation) =>
    apiRequest<CitedPassage>(`/references/passage?${new URLSearchParams({ ...citation })}`),
};

/** The in-app link to a cited passage's read-only view. */
export function passageHref(citation: PassageCitation): string {
  return `/references/passage?${new URLSearchParams({
    document: citation.document_id,
    publication: citation.publication_id,
    version: citation.version_id,
    revision: citation.revision_id,
    passage: citation.block_id,
  })}`;
}

/** The in-app link to the evidence behind an architecture impact. */
export function evidenceHref(releaseId: string, chunkId: string): string {
  return `/architecture-evidence/${encodeURIComponent(releaseId)}/${encodeURIComponent(chunkId)}`;
}
