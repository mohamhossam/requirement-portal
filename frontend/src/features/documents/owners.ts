import type { DocumentOwnerSummary } from "../../api/client";

export type DocumentOwner = DocumentOwnerSummary & {
  /** Where the requirement's or draft's files are attached and managed. */
  to: string;
};

/**
 * What a file is attached to, by name, and where to open it.
 *
 * The API returns each document's requirement or draft with its title, so a list of six
 * files named "notes.md" can be told apart without a request per requirement. A title is
 * a label, not a gate: when the requirement or draft is gone, the link still works and
 * says "Requirement" or "Draft".
 */
export function ownerLink(owner: DocumentOwnerSummary): DocumentOwner {
  return {
    ...owner,
    to: owner.kind === "requirement"
      // The Source step, where a requirement's files are attached and managed.
      ? `/requirements/${owner.id}/capture`
      : `/requirements/new?draft=${encodeURIComponent(owner.id)}`,
  };
}
