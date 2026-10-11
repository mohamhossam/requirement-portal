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

/** Why a decided product impact names a system (ADR-0115); an unknown role reads as written. */
const SYSTEM_ROLE: Record<string, string> = {
  primary: "Primary system",
  channel: "Serves the channel",
  named: "Named in the requirement",
  supporting: "Supporting",
  owner: "Owns the data",
  consumer: "Uses the data",
};

export const systemRoleLabel = (role: string) => SYSTEM_ROLE[role] ?? roleLabel(role);

/** What the requirement does to a system, from its decided product impact. */
const CHANGE_TYPE: Record<string, string> = {
  new: "New system",
  modify: "Changed",
  configure: "Configured only",
  retire: "Retired",
  consume_only: "Used as it is",
};

export const changeTypeLabel = (changeType: string) => CHANGE_TYPE[changeType] ?? roleLabel(changeType);
