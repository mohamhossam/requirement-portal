import type { BadgeTone } from "../../components/ui";
import type {
  ArchitectureJob, CapabilityDomain, CatalogueChange, CatalogueDiff, KnowledgeRelease, RelationshipKind,
  FlowRuleKind, SourceConfidence, Suggestion,
} from "../../api/knowledge";

/** One label map for every catalogue enum the API returns (design-system §11). */
export const ITEM_LABEL: Record<CatalogueChange["item"], string> = {
  system: "System",
  component: "Component",
  capability: "Capability",
  relationship: "Dependency",
  document: "Source document",
  domain: "Capability domain",
  landscape_domain: "Landscape domain",
  product: "Product offering",
  journey: "Journey",
};

export const CHANGE_LABEL: Record<CatalogueChange["change"], { label: string; tone: BadgeTone }> = {
  added: { label: "Added", tone: "success" },
  changed: { label: "Changed", tone: "neutral" },
  removed: { label: "Removed", tone: "danger" },
};

export const FIELD_LABEL: Record<string, string> = {
  name: "name",
  name_ar: "Arabic name",
  aliases: "other names",
  constraints: "constraints",
  triggers: "matching phrases",
  kind: "how it depends",
  domain: "domain",
  parent: "parent domain",
  description: "description",
  component: "component",
  technology: "technology",
  landscape_domain: "landscape domain",
  code: "code",
  family: "family",
  version: "version",
  lifecycle: "lifecycle",
  proposition: "proposition",
  rules: "rules",
  confidence: "confidence",
  source: "source",
  order_types: "order types",
  components: "components",
  responsibilities: "responsibilities",
  values: "customer value",
  audiences: "who it is for",
  product_id: "product offering",
  order_type_code: "order type",
  activities: "activities",
  flow_rules: "flow rules",
  integrations: "integrations",
};

/** Activities in number order: "75" before "100". */
export function byNumber(a: string, b: string) {
  const na = Number.parseFloat(a);
  const nb = Number.parseFloat(b);
  if (!Number.isNaN(na) && !Number.isNaN(nb) && na !== nb) return na - nb;
  return a.localeCompare(b);
}

/** How a flow rule leaves its activity. */
export const RULE_LABEL: Record<FlowRuleKind, string> = {
  decision: "Decision",
  loop: "Loop back",
  parallel: "Parallel track",
};
export const RULE_KINDS: FlowRuleKind[] = ["decision", "loop", "parallel"];

/** How sure the source is of a fact; always shown as words, never by colour alone. */
export const CONFIDENCE_LABEL: Record<SourceConfidence, { label: string; tone: BadgeTone }> = {
  confirmed: { label: "Confirmed", tone: "success" },
  inferred: { label: "Inferred", tone: "warning" },
  gap: { label: "Known gap", tone: "danger" },
};
export const CONFIDENCES: SourceConfidence[] = ["confirmed", "inferred", "gap"];

/** A responsibility's role as words: "PRIMARY_ORCHESTRATOR" reads "Primary orchestrator". */
export const roleLabel = (role: string) => {
  const words = role.replaceAll("_", " ").toLowerCase().trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
};

/** A stable key from a name: "Order capture" → "order-capture". */
export const slug = (value: string, fallback = "item") =>
  value.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || fallback;

/** A domain and the domains above it, from the top of the tree down; empty when unplaced. */
export function domainPath(domains: CapabilityDomain[], id: string | null | undefined): CapabilityDomain[] {
  const byId = new Map(domains.map((item) => [item.id, item]));
  const path: CapabilityDomain[] = [];
  for (let current = byId.get(id ?? ""); current && !path.includes(current);
    current = byId.get(current.parent_id ?? "")) {
    path.unshift(current);
  }
  return path;
}

/** Domains in reading order: each followed by the ones inside it, with its depth. */
export function domainTree(domains: CapabilityDomain[]): { domain: CapabilityDomain; depth: number }[] {
  const children = (parent: string | null) => domains
    .filter((item) => (item.parent_id ?? null) === parent)
    .sort((a, b) => a.name.localeCompare(b.name));
  const walk = (parent: string | null, depth: number): { domain: CapabilityDomain; depth: number }[] =>
    children(parent).flatMap((domain) => [{ domain, depth }, ...walk(domain.id, depth + 1)]);
  return walk(null, 0);
}

/** "Order capture › Quoting", or null when unplaced. */
export const domainLabel = (domains: CapabilityDomain[], id: string | null | undefined) =>
  domainPath(domains, id).map((item) => item.name).join(" › ") || null;

/**
 * How the source depends on the target, read after "A → B". "Not stated" is the
 * honest default: a kind is recorded only when a source says how.
 */
export const RELATIONSHIP_KIND_LABEL: Record<RelationshipKind, string> = {
  calls_api: "Calls its API",
  publishes_events_to: "Sends it events",
  transfers_data_to: "Sends it data",
  orchestrates: "Orchestrates it",
  unspecified: "Not stated",
};

/** The choices in a picker, with "Not stated" first as the default. */
export const RELATIONSHIP_KINDS: RelationshipKind[] = [
  "unspecified", "calls_api", "publishes_events_to", "transfers_data_to", "orchestrates",
];

/** The same kinds as direction-neutral nouns, for lists read from either end. */
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

export const SUGGESTION_KIND: Record<Suggestion["content"]["kind"], string> = {
  system: "Systems",
  component: "Components",
  capability: "Capabilities",
  constraint: "Constraints",
  relationship: "Dependencies",
  landscape_domain: "Landscape domains",
  placement: "Placements in the landscape",
  product: "Product offerings",
  journey: "Journeys",
};

export const MATCH_LABEL: Record<Suggestion["match"], { label: string; tone: BadgeTone }> = {
  new: { label: "New", tone: "neutral" },
  updates_existing: { label: "Adds to an existing item", tone: "neutral" },
  already_present: { label: "Already in this version", tone: "neutral" },
  needs_system: { label: "Needs its system first", tone: "warning" },
  needs_component: { label: "Needs its component first", tone: "warning" },
  needs_domain: { label: "Needs its domain first", tone: "warning" },
  needs_offering: { label: "Needs its product offering first", tone: "warning" },
};

/** The `model` of a suggestion read straight from a table's cells, not by the AI model (ADR-0093). */
export const TABLE_READER = "catalogue-table-reader";

/** Shown instead of the match label while a name may be an existing system under another name. */
export const POSSIBLE_MATCH_LABEL: { label: string; tone: BadgeTone } = { label: "May already exist", tone: "warning" };

export const STATUS_LABEL: Record<Suggestion["status"], { label: string; tone: BadgeTone }> = {
  proposed: { label: "Waiting for review", tone: "warning" },
  accepted: { label: "Accepted", tone: "success" },
  rejected: { label: "Rejected", tone: "neutral" },
};

export const JOB_LABEL: Record<ArchitectureJob["status"], { label: string; tone: BadgeTone }> = {
  queued: { label: "Waiting to start", tone: "neutral" },
  running: { label: "Running", tone: "accent" },
  succeeded: { label: "Finished", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export const LANGUAGE_LABEL: Record<string, string> = {
  en: "English",
  ar: "Arabic",
  mixed: "English and Arabic",
};

export const AUDIT_LABEL: Record<string, string> = {
  create_draft: "Started a new version",
  edit_draft: "Edited the version",
  upload_document: "Added a source document",
  select_documents: "Changed the source documents",
  build_index: "Built the evidence index",
  accept_suggestion: "Accepted an AI suggestion",
  publish: "Published",
  activate: "Made active again",
  rename: "Renamed the version",
  discard_draft: "Discarded the version",
};

export const TIMESTAMP = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export const formatTime = (value: string | null | undefined) =>
  value ? TIMESTAMP.format(new Date(value)) : "—";

const JOB_ERROR: Record<string, string> = {
  catalogue_extraction: "no part of the document could be read by the AI model",
  catalogue_extraction_unusable:
    "the AI model's answers could not be used, even when asked twice; retry, or try a stronger model",
  catalogue_extraction_uncited:
    "the AI model answered, but none of its suggestions quoted the document so they could be checked; retry, or try a stronger model",
  model_invalid_output: "the AI model returned an empty, refused or cut-off answer; retry, or try a stronger model",
  model_timeout: "the AI model took too long to answer; retry, or check the model's performance",
  model_rate_limit: "the AI provider's rate limit was reached; wait a minute, then retry",
  model_unavailable: "the AI provider is unavailable right now; retry later",
  model_authentication: "the AI provider rejected its credentials; check the API key in the backend configuration",
  model_configuration: "the AI provider rejected the configured model or its settings; check the backend configuration",
  model_payment: "the AI provider needs credits or a higher spending limit on the API key",
  catalogue_extraction_unsupported:
    "the configured model cannot read this file (an image without vision support, or a context window too small; raise LOCAL_LLM_CONTEXT_WINDOW_TOKENS)",
  attempts_exhausted: "it was tried three times without finishing; check that the worker container is running",
  architecture_knowledge_conflict: "the document left the version, or the version changed, while it was being read",
  model_transport: "the AI model could not be reached",
  document_extraction: "the file could not be read",
};

export const jobError = (code: string | null) =>
  code ? JOB_ERROR[code] ?? "something went wrong on the server" : null;

/** "2 added · 1 changed": how many items each kind of change touches. */
export function changeSummary(diff: CatalogueDiff): string {
  return (["added", "changed", "removed"] as const)
    .map((kind) => [kind, diff.changes.filter((item) => item.change === kind).length] as const)
    .filter(([, count]) => count > 0)
    .map(([kind, count]) => `${count} ${CHANGE_LABEL[kind].label.toLowerCase()}`)
    .join(" · ");
}

/** A version as people know it: its name, or its id for unnamed older records. */
export function versionName(release: Pick<KnowledgeRelease, "id" | "name">): string {
  return release.name ?? release.id;
}

type Kind = CatalogueChange["change"];

/** "bcrm->billing:bills orders" → the pair it links; the key format is the server's diff key. */
const linkOf = (key: string) => {
  const [pair = ""] = key.split(":");
  const [source = "", target = ""] = pair.split("->");
  return { source, target };
};

/**
 * How a version in progress touches each system: added or removed outright, or
 * changed through its own fields, a component, a capability or a dependency. For marks in the
 * browser; the full list stays in the Review changes step.
 */
export function systemMarks(diff: CatalogueDiff | undefined): Map<string, Kind> {
  const marks = new Map<string, Kind>();
  const touch = (id: string) => {
    if (id && !marks.has(id)) marks.set(id, "changed");
  };
  for (const change of diff?.changes ?? []) {
    if (change.item === "system") marks.set(change.key, change.change);
  }
  for (const change of diff?.changes ?? []) {
    if (change.item === "capability" || change.item === "component") touch(change.key.split("/")[0] ?? "");
    if (change.item === "relationship") {
      const { source, target } = linkOf(change.key);
      touch(source);
      touch(target);
    }
  }
  return marks;
}

export type LinkChange = { source: string; target: string; description: string; key: string };

/** Dependencies a version in progress adds and removes, keyed as the server keys them. */
export function linkChanges(diff: CatalogueDiff | undefined) {
  const added = new Set<string>();
  const removed: LinkChange[] = [];
  for (const change of diff?.changes ?? []) {
    if (change.item !== "relationship") continue;
    if (change.change === "added") added.add(change.key);
    if (change.change === "removed") {
      const colon = change.label.indexOf(": ");
      removed.push({ ...linkOf(change.key), key: change.key,
        description: colon >= 0 ? change.label.slice(colon + 2) : "" });
    }
  }
  return { added, removed };
}

/** The server's key for a dependency, to match it against the diff. */
export const linkKey = (source: string, target: string, description: string) =>
  `${source}->${target}:${description.toLocaleLowerCase()}`;

/** The changes that name one system, for its dossier. */
export function changesFor(diff: CatalogueDiff | undefined, systemId: string): CatalogueChange[] {
  return (diff?.changes ?? []).filter((change) => {
    if (change.item === "system") return change.key === systemId;
    if (change.item === "capability" || change.item === "component") return change.key.split("/")[0] === systemId;
    if (change.item === "relationship") {
      const { source, target } = linkOf(change.key);
      return source === systemId || target === systemId;
    }
    return false;
  });
}

/** The systems a change is about: its own key, a capability's system, or a dependency's two ends. */
export function systemOf(change: CatalogueChange): string[] {
  if (change.item === "system") return [change.key];
  if (change.item === "capability" || change.item === "component") return [change.key.split("/")[0] ?? ""];
  if (change.item === "relationship") {
    const { source, target } = linkOf(change.key);
    return [source, target];
  }
  return [];
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/**
 * What a version in progress does, in one line of the reader's words:
 * "Removes CWOM · 6 dependencies removed · touches 5 other systems".
 */
export function changeStory(diff: CatalogueDiff | undefined): string {
  const changes = diff?.changes ?? [];
  const of = (item: CatalogueChange["item"], kind: Kind) =>
    changes.filter((change) => change.item === item && change.change === kind);
  const names = (items: CatalogueChange[]) => items.map((change) => change.label).join(", ");
  const added = of("system", "added");
  const removed = of("system", "removed");
  const edited = of("system", "changed");
  const links = {
    added: of("relationship", "added").length,
    removed: of("relationship", "removed").length,
    changed: of("relationship", "changed").length,
  };
  const capabilities = changes.filter((change) => change.item === "capability").length;
  const components = changes.filter((change) => change.item === "component").length;
  const documents = changes.filter((change) => change.item === "document").length;
  const domains = changes.filter((change) => change.item === "domain" || change.item === "landscape_domain").length;
  const offerings = changes.filter((change) => change.item === "product").length;
  const journeys = changes.filter((change) => change.item === "journey").length;
  const direct = new Set([...added, ...removed, ...edited].map((change) => change.key));
  const touched = [...systemMarks(diff).keys()].filter((id) => !direct.has(id)).length;
  return [
    removed.length > 0 && `Removes ${names(removed)}`,
    added.length > 0 && `Adds ${names(added)}`,
    edited.length > 0 && `Edits ${names(edited)}`,
    links.added > 0 && `${plural(links.added, "dependency", "dependencies")} added`,
    links.removed > 0 && `${plural(links.removed, "dependency", "dependencies")} removed`,
    links.changed > 0 && `${plural(links.changed, "dependency", "dependencies")} changed`,
    components > 0 && plural(components, "component change", "component changes"),
    capabilities > 0 && plural(capabilities, "capability change", "capability changes"),
    documents > 0 && plural(documents, "source document change", "source document changes"),
    domains > 0 && plural(domains, "domain change", "domain changes"),
    offerings > 0 && plural(offerings, "product offering change", "product offering changes"),
    journeys > 0 && plural(journeys, "journey change", "journey changes"),
    touched > 0 && `touches ${plural(touched, "other system", "other systems")}`,
  ].filter(Boolean).join(" · ");
}
