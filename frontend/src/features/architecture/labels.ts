import type { components } from "../../api/schema";

type RelationshipKind = components["schemas"]["RelationshipKind"];

/** A responsibility's role as words: "PRIMARY_ORCHESTRATOR" reads "Primary orchestrator". */
export const roleLabel = (role: string) => {
  const words = role.replaceAll("_", " ").toLowerCase().trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

/** Dependency kinds as direction-neutral nouns, for lists read from either end. */
const RELATIONSHIP_KIND_NOUN: Record<RelationshipKind, string> = {
  calls_api: "API call",
  publishes_events_to: "Events",
  transfers_data_to: "Data transfer",
  orchestrates: "Orchestration",
  unspecified: "",
};

/** A kind worth showing beside a dependency; nothing when no source says how. */
export const kindNote = (kind: RelationshipKind | null | undefined) =>
  kind ? RELATIONSHIP_KIND_NOUN[kind] || null : null;
