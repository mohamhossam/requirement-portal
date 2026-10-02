import { useQueries, useQuery } from "@tanstack/react-query";

import { api, type DocumentSummary } from "../../api/client";
import { queryKeys } from "../../app/queryKeys";

export type DocumentOwner = {
  kind: "requirement" | "draft";
  /** The requirement's or draft's id. */
  id: string;
  /** The requirement's or draft's title, or null while it loads or when it cannot be read. */
  title: string | null;
  to: string;
};

/**
 * What each file is attached to, by name.
 *
 * A document only carries its requirement's or draft's id, and the catalogue
 * printed nothing about it at all, so a list of six files named "notes.md"
 * could not be told apart. This reads the titles through the same queries and
 * cache keys the workspace and the worklist already use — a requirement opened
 * a moment ago costs nothing — and one request per distinct requirement.
 *
 * A title is a label, not a gate: while it loads, or when it cannot be read (a
 * private draft that belongs to someone else), the link still works and says
 * "Requirement" or "Draft".
 */
export function useDocumentOwners(documents: DocumentSummary[] | undefined) {
  const requirementIds = [...new Set(
    (documents ?? []).flatMap((document) => document.requirement_id ? [document.requirement_id] : []),
  )];
  const requirements = useQueries({
    queries: requirementIds.map((id) => ({
      queryKey: queryKeys.requirement(id),
      queryFn: () => api.getRequirement(id),
    })),
  });
  const hasDrafts = Boolean(documents?.some((document) => document.draft_id));
  const drafts = useQuery({
    queryKey: queryKeys.requirementDrafts(),
    queryFn: () => api.listRequirementDrafts(),
    enabled: hasDrafts,
  });

  const titles = new Map<string, string>();
  requirementIds.forEach((id, index) => {
    const title = requirements[index]?.data?.title;
    if (title) titles.set(id, title);
  });
  drafts.data?.forEach((draft) => { if (draft.title) titles.set(draft.id, draft.title); });

  return (document: DocumentSummary): DocumentOwner | null => {
    if (document.requirement_id) {
      return {
        kind: "requirement",
        id: document.requirement_id,
        title: titles.get(document.requirement_id) ?? null,
        // The Source step, where a requirement's files are attached and managed.
        to: `/requirements/${document.requirement_id}/capture`,
      };
    }
    if (document.draft_id) {
      return {
        kind: "draft",
        id: document.draft_id,
        title: titles.get(document.draft_id) ?? null,
        to: `/requirements/new?draft=${encodeURIComponent(document.draft_id)}`,
      };
    }
    return null;
  };
}
