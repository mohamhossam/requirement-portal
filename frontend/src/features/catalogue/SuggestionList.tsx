import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, Link2, PencilLine, Sparkles, Table2, X } from "lucide-react";
import { useState } from "react";

import { errorMessage } from "../../api/errors";
import {
  knowledgeApi,
  type KnowledgeRelease,
  type ProductOffering,
  type Suggestion,
  type SuggestionContent,
} from "../../api/knowledge";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import { ErrorNotice } from "../../components/ErrorNotice";
import { AsyncState, asyncStatus } from "../../components/states";
import { Badge, Button, Pill } from "../../components/ui";
import { catalogueKeys } from "./keys";
import {
  MATCH_LABEL, POSSIBLE_MATCH_LABEL, STATUS_LABEL, SUGGESTION_KIND, TABLE_READER, domainLabel, kindNote,
} from "./labels";
import { PassageDialog } from "./PassageDialog";
import { SuggestionEditor } from "./SuggestionEditor";

// In the order they are accepted: a domain before the systems placed in it.
const KINDS: SuggestionContent["kind"][] = [
  "landscape_domain", "system", "placement", "component", "capability", "constraint", "relationship", "product",
  "journey",
];
const ONE_KIND: Record<SuggestionContent["kind"], string> = {
  system: "system", component: "component", capability: "capability", constraint: "constraint",
  relationship: "dependency", landscape_domain: "landscape domain", placement: "placement",
  product: "product offering", journey: "journey",
};
type Filter = "proposed" | "accepted" | "rejected" | "all";
const FILTERS: { key: Filter; label: string }[] = [
  { key: "proposed", label: "Waiting for review" },
  { key: "accepted", label: "Accepted" },
  { key: "rejected", label: "Rejected" },
];

/** A component's name, keyed `system/component`, from the draft or from a suggestion still waiting. */
type ComponentNames = Map<string, string>;

function describe(item: Suggestion, names: Map<string, string>, components: ComponentNames,
  domains: Map<string, string>, offerings: Map<string, ProductOffering>) {
  const { content } = item;
  // The server names draft systems by any of their names; a system still only suggested is
  // named from its suggestion.
  const system = item.system_name ?? names.get(content.system_id) ?? content.system_id;
  switch (content.kind) {
    case "system": {
      const facts = [content.aliases.length ? `Also called ${content.aliases.join(", ")}` : null, content.description]
        .filter(Boolean).join(" · ");
      return { title: content.name, detail: facts || null };
    }
    case "landscape_domain": {
      const parent = content.parent_domain_id ? domains.get(content.parent_domain_id) ?? content.parent_domain_id : null;
      const where = parent ? `A sub-domain of ${parent}` : "A landscape domain";
      return { title: content.name, detail: content.description ? `${where} · ${content.description}` : where };
    }
    case "product": {
      const offering = content.product;
      const parts = offering?.components ?? [];
      const duties = parts.reduce((count, part) => count + (part.responsibilities ?? []).length, 0);
      const counts = [
        plural((offering?.order_types ?? []).length, "order type", "order types"),
        plural(parts.length, "component", "components"),
        plural(duties, "system responsibility", "system responsibilities"),
      ].join(" · ");
      return { title: `Product offering: ${content.name}`, detail: counts };
    }
    case "journey": {
      const journey = content.journey;
      const offering = offerings.get(journey?.product_id ?? "");
      const order = offering?.order_types.find((type) => type.code === journey?.order_type_code)?.name
        ?? journey?.order_type_code;
      const fulfils = journey?.product_id
        ? `For ${[offering?.name ?? journey.product_id, order].filter(Boolean).join(" › ")}` : null;
      const counts = [
        plural((journey?.activities ?? []).length, "activity", "activities"),
        plural((journey?.flow_rules ?? []).length, "flow rule", "flow rules"),
        plural((journey?.integrations ?? []).length, "integration", "integrations"),
      ].join(" · ");
      return { title: `Journey: ${content.name}`, detail: fulfils ? `${fulfils} · ${counts}` : counts };
    }
    case "placement": {
      const place = domains.get(content.landscape_domain_id ?? "") ?? content.landscape_domain_id;
      return { title: `Place ${system} in ${place}`, detail: "Where the system sits in the landscape" };
    }
    case "component": {
      const facts = [content.technology, content.description].filter(Boolean).join(" · ");
      return { title: `${content.name} — ${system}`, detail: facts || `A part of ${system}` };
    }
    case "capability": {
      const ref = content.component_id;
      const part = ref ? components.get(`${content.system_id}/${ref}`) ?? ref : null;
      const phrases = `Matching phrases: ${content.triggers.join(", ")}`;
      return { title: `${content.name} — ${system}`, detail: part ? `${phrases} · Delivered by ${part}` : phrases };
    }
    case "constraint":
      return { title: content.text, detail: `Constraint on ${system}` };
    default: {
      const target = item.target_system_name ?? names.get(content.target_system_id ?? "")
        ?? content.target_system_id;
      const how = kindNote(content.relationship_kind);
      return { title: `${system} → ${target}`, detail: how ? `${how} · ${content.text}` : content.text };
    }
  }
}

type PossibleMatch = Suggestion["possible_matches"][number];

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

// A space never appears in a system id, so this key cannot meet one.
const LANDSCAPE_GROUP = " landscape-domains";
const OFFERING_GROUP = " product-offerings";
const JOURNEY_GROUP = " journeys";
const groupKey = (item: Suggestion) =>
  item.content.kind === "landscape_domain" ? LANDSCAPE_GROUP
    : item.content.kind === "product" ? OFFERING_GROUP
      : item.content.kind === "journey" ? JOURNEY_GROUP : item.content.system_id;

/** The suggestion pointed at the existing system instead of the name the document used. */
function linked(content: SuggestionContent, match: PossibleMatch): SuggestionContent {
  return match.role === "target"
    ? { ...content, target_system_id: match.system_id }
    : { ...content, system_id: match.system_id };
}

/** Never accepted in bulk: the server leaves these for a one-by-one decision too. */
function oneByOne(item: Suggestion) {
  return item.basis === "inferred" || item.possible_matches.length > 0;
}

/** What the maintainer needs to recognise an existing system: its other names and what it does. */
function profile(system: KnowledgeRelease["systems"][number] | undefined) {
  if (!system) return null;
  const parts = [
    system.aliases.length ? `Also called ${system.aliases.slice(0, 3).join(", ")}` : "",
    system.capabilities.slice(0, 2).map((capability) => capability.name).join(", "),
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

/** Possible matches, one group per name the document used. */
function byName(matches: PossibleMatch[]) {
  const groups = new Map<string, PossibleMatch[]>();
  for (const match of matches) {
    const key = `${match.role}:${match.written_as}`;
    groups.set(key, [...(groups.get(key) ?? []), match]);
  }
  return [...groups.values()];
}

/**
 * What the AI found, waiting for a person. The evidence comes before the
 * decision on every row (design-system §14, "approval above evidence").
 */
export function SuggestionList({ draft, onChanged }: { draft: KnowledgeRelease; onChanged: () => void }) {
  const [filter, setFilter] = useState<Filter>("proposed");
  const [editing, setEditing] = useState<Suggestion | null>(null);
  const [groupBy, setGroupBy] = useState<"kind" | "system">("kind");
  const [rejecting, setRejecting] = useState<{ title: string; ids: string[] } | null>(null);
  const [reading, setReading] = useState<{ item: Suggestion; location: string; quote: string } | null>(null);
  const [notice, setNotice] = useState("");
  const [acceptingAll, setAcceptingAll] = useState(false);
  const overview = useQuery({
    queryKey: catalogueKeys.suggestions(draft.id),
    queryFn: () => knowledgeApi.suggestions(draft.id),
  });
  const decide = useMutation({
    // `done` is the notice to show afterwards when the generic one would not say what happened.
    mutationFn: ({ item, accept, content }: {
      item: Suggestion; accept: boolean; content?: SuggestionContent; done?: string;
    }) => knowledgeApi.decide(draft, item.id, accept, content),
    onSuccess: (_, { accept, done }) => {
      setEditing(null);
      setNotice(done ?? (accept ? "Added to this version." : "Suggestion rejected."));
      onChanged();
    },
  });
  const acceptAll = useMutation({
    mutationFn: () => knowledgeApi.acceptAll(draft),
    onSuccess: ({ remaining }) => {
      setNotice(remaining
        ? `Accepted what could be added. ${remaining} still wait for a decision one by one: inferred dependencies, `
          + "names that may already exist, and items whose system, component or offering isn’t in this version yet."
        : "Every waiting suggestion was added to this version.");
      onChanged();
    },
  });

  const rejectMany = useMutation({
    mutationFn: (ids: string[]) => knowledgeApi.rejectSuggestions(draft, ids),
    onSuccess: ({ rejected }) => {
      setNotice(rejected === 1 ? "1 suggestion rejected." : `${rejected} suggestions rejected.`);
      onChanged();
    },
  });

  const suggestions = overview.data?.suggestions ?? [];
  // Draft systems come last so their names win over a suggestion that was added to one of them.
  const names = new Map([
    ...suggestions.filter((item) => item.content.kind === "system")
      .map((item) => [item.content.system_id, item.content.name] as const),
    ...draft.systems.map((system) => [system.id, system.name] as const),
  ]);
  const components: ComponentNames = new Map([
    ...suggestions.filter((item) => item.content.kind === "component")
      .map((item) => [`${item.content.system_id}/${item.content.component_id}`, item.content.name] as const),
    ...draft.systems.flatMap((system) => (system.components ?? [])
      .map((component) => [`${system.id}/${component.id}`, component.name] as const)),
  ]);
  // Landscape domains by path, "Customer › Assisted", from the draft and from suggestions still waiting.
  const suggestedDomains = suggestions.filter((item) => item.content.kind === "landscape_domain")
    .map((item) => ({ id: item.content.landscape_domain_id ?? item.content.system_id, name: item.content.name,
      name_ar: null, parent_id: item.content.parent_domain_id ?? null, description: null }));
  const allDomains = [...suggestedDomains.filter((item) =>
    !(draft.landscape_domains ?? []).some((known) => known.id === item.id)), ...(draft.landscape_domains ?? [])];
  const domains = new Map(allDomains.map((item) => [item.id, domainLabel(allDomains, item.id) ?? item.name]));
  // Offerings a journey may name: the draft's, and those still only suggested.
  const offeringList: ProductOffering[] = [
    ...(draft.products ?? []),
    ...suggestions.flatMap((item) => (item.status === "proposed" && item.content.product
      && !(draft.products ?? []).some((known) => known.id === item.content.product?.id) ? [item.content.product] : [])),
  ];
  const offerings = new Map(offeringList.map((item) => [item.id, item]));
  const documents = new Map(draft.documents.map((document) => [document.id, document.title]));
  const images = new Set(draft.documents.filter((item) => item.mime_type.startsWith("image/")).map((item) => item.id));
  const counts = {
    proposed: suggestions.filter((item) => item.status === "proposed").length,
    accepted: suggestions.filter((item) => item.status === "accepted").length,
    rejected: suggestions.filter((item) => item.status === "rejected").length,
  };
  const waiting = suggestions.filter((item) => item.status === "proposed");
  const bulk = waiting.filter((item) => !oneByOne(item));
  const held = waiting.length - bulk.length;
  const systems = new Map(draft.systems.map((system) => [system.id, system]));
  const shown = suggestions.filter((item) => filter === "all" || item.status === filter);
  const warnings = [...new Set((overview.data?.runs ?? []).flatMap((run) => run.warnings))];
  const failure = decide.error ?? acceptAll.error ?? rejectMany.error;
  const groups = groupBy === "kind"
    ? KINDS.map((kind) => ({ key: kind, title: SUGGESTION_KIND[kind],
      items: shown.filter((item) => item.content.kind === kind) }))
    // A landscape domain belongs to no system, so domains share one group of their own.
    : [...new Set(shown.map(groupKey))]
      .map((key) => ({ key, title: key === LANDSCAPE_GROUP ? SUGGESTION_KIND.landscape_domain
        : key === OFFERING_GROUP ? SUGGESTION_KIND.product
          : key === JOURNEY_GROUP ? SUGGESTION_KIND.journey : names.get(key) ?? key,
        items: shown.filter((item) => groupKey(item) === key) }))
      .sort((a, b) => a.title.localeCompare(b.title));

  return (
    <section className="grid min-w-0 gap-4" aria-labelledby="suggestions-title">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="grid gap-1">
          <h3 className="text-title text-ink m-0" id="suggestions-title">AI suggestions</h3>
          <p className="text-meta text-ink-muted m-0">Check each suggestion against its source passage before accepting it.</p>
          {held > 0 && (
            <p className="text-meta text-ink-muted m-0">
              {held === 1 ? "1 needs" : `${held} need`} a decision one by one: inferred dependencies and names
              that may already exist are never accepted in bulk.
            </p>
          )}
        </div>
        {bulk.length > 0 && (
          <Button icon={<Check size={16} aria-hidden="true" />} loading={acceptAll.isPending}
            loadingLabel="Accepting…" onClick={() => setAcceptingAll(true)}>
            Accept all {bulk.length} waiting
          </Button>
        )}
      </header>
      {failure && <ErrorNotice message={errorMessage(failure)} />}
      {notice && <p className="text-meta text-ink-soft m-0" role="status">{notice}</p>}
      {warnings.length > 0 && (
        <ul className="text-meta text-ink-soft m-0 grid gap-1 pl-5" aria-label="Notes from reading the documents">
          {warnings.map((warning) => <li key={warning}>{warning}</li>)}
        </ul>
      )}
      <AsyncState
        status={asyncStatus(overview, suggestions.length === 0)}
        loading={{ label: "Loading suggestions", variant: "row", bars: 3 }}
        error={{ title: "We couldn’t load the suggestions", message: errorMessage(overview.error) }}
        onRetry={() => void overview.refetch()}
        headingLevel="h4"
        empty={{
          title: "No suggestions yet",
          message: "Add a document above and the AI’s suggestions appear here once it has read it.",
          icon: <Sparkles size={18} aria-hidden="true" />,
        }}
      >
        <div className="flex flex-wrap gap-2" role="group" aria-label="Show suggestions">
          {FILTERS.filter(({ key }) => counts[key as keyof typeof counts] > 0 || filter === key).map(({ key, label }) => (
            <Pill key={key} active={filter === key} count={counts[key as keyof typeof counts]} onClick={() => setFilter(key)}>
              {label}
            </Pill>
          ))}
          <Pill active={filter === "all"} count={suggestions.length} onClick={() => setFilter("all")}>All</Pill>
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Group suggestions by">
          <span className="text-meta text-ink-muted">Group by</span>
          <Pill active={groupBy === "kind"} onClick={() => setGroupBy("kind")}>Kind</Pill>
          <Pill active={groupBy === "system"} onClick={() => setGroupBy("system")}>System</Pill>
        </div>
        {shown.length === 0 && <p className="text-body text-ink-muted m-0">Nothing here with this filter.</p>}
        {groups.map(({ key, title, items: group }) => {
          if (group.length === 0) return null;
          const waiting = group.filter((item) => item.status === "proposed");
          return (
            <section key={key} className="grid gap-2" aria-label={title}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-label text-ink-muted m-0">{title} ({group.length})</h4>
                {waiting.length > 1 && (
                  <Button size="sm" variant="ghost" icon={<X size={14} aria-hidden="true" />}
                    disabled={decide.isPending || acceptAll.isPending} loading={rejectMany.isPending
                      && rejectMany.variables?.every((id) => waiting.some((item) => item.id === id))}
                    loadingLabel="Rejecting…"
                    onClick={() => setRejecting({ title, ids: waiting.map((item) => item.id) })}
                    aria-label={`Reject all ${waiting.length} waiting in ${title}`}>
                    Reject all {waiting.length} waiting
                  </Button>
                )}
              </div>
              <ul className="border-line m-0 grid list-none rounded-md border border-solid p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
                {group.map((item) => {
                  const text = describe(item, names, components, domains, offerings);
                  const matching = item.status === "proposed" && item.possible_matches.length > 0;
                  const match = MATCH_LABEL[item.match];
                  const state = STATUS_LABEL[item.status];
                  const pending = decide.isPending && decide.variables.item.id === item.id;
                  const naming = matching && item.content.kind === "system";
                  return (
                    <li key={item.id} className="grid gap-2 px-4 py-3">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="grid min-w-0 gap-0.5">
                          <strong className="text-body text-ink break-words" dir="auto">{text.title}</strong>
                          {text.detail && <span className="text-meta text-ink-soft break-words" dir="auto">{text.detail}</span>}
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {item.model === TABLE_READER && (
                            <Badge icon={<Table2 aria-hidden={true} className="shrink-0" size={12} />}>Read from table</Badge>
                          )}
                          {item.basis === "inferred" && (
                            <Badge icon={<Sparkles aria-hidden={true} className="shrink-0" size={12} />}>Inferred</Badge>
                          )}
                          {matching && <Badge tone={POSSIBLE_MATCH_LABEL.tone}>{POSSIBLE_MATCH_LABEL.label}</Badge>}
                          {item.status === "proposed"
                            // A possible match never hides that the suggestion is still blocked.
                            ? (!matching || item.match !== "new") && <Badge tone={match.tone}>{match.label}</Badge>
                            : <Badge tone={state.tone}>{item.edited ? `${state.label} with edits` : state.label}</Badge>}
                        </div>
                      </div>
                      {item.citations.map((citation) => (
                        <blockquote key={`${citation.location}-${citation.quote}`} dir="auto"
                          className="border-line m-0 grid gap-0.5 border-0 border-l-2 border-solid pl-3">
                          <p className="text-document font-document text-ink-soft m-0">“{citation.quote}”</p>
                          <span className="text-meta text-ink-muted flex flex-wrap items-center gap-x-2">
                            <span>{documents.get(item.document_version_id) ?? "Source document"} · {citation.location}</span>
                            {!images.has(item.document_version_id) && documents.has(item.document_version_id) && (
                              <Button size="sm" variant="ghost"
                                onClick={() => setReading({ item, location: citation.location, quote: citation.quote })}
                                aria-label={`Show ${citation.location} in ${documents.get(item.document_version_id)}`}>
                                Show in document
                              </Button>
                            )}
                          </span>
                        </blockquote>
                      ))}
                      {item.basis === "inferred" && item.rationale && (
                        <p className="text-meta text-ink-soft m-0 max-w-[75ch] break-words" dir="auto">
                          <span className="text-ink font-semibold">Inferred, not stated.</span> {item.rationale}
                        </p>
                      )}
                      {matching && byName(item.possible_matches).map((options) => {
                        const [first] = options;
                        if (!first) return null;
                        const keep = `Keep as a new system: “${first.written_as}”`;
                        return (
                          <div key={`${first.role}:${first.written_as}`} role="group"
                            aria-label={`Possible existing systems for “${first.written_as}”`}
                            className="bg-surface-sunken grid gap-3 rounded-md px-3 py-3">
                            <p className="text-meta text-ink-soft m-0 max-w-[75ch]" dir="auto">
                              “{first.written_as}” may already be in the catalogue under another name. Is it one
                              of these?
                            </p>
                            <ul className="m-0 grid list-none gap-3 p-0">
                              {options.map((option) => {
                                const target = linked(item.content, option);
                                const label = naming ? `Add to ${option.system_name}` : `Use ${option.system_name}`;
                                const known = profile(systems.get(option.system_id));
                                return (
                                  <li key={option.system_id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 max-sm:grid-cols-1 max-sm:justify-items-start">
                                    <div className="grid min-w-0 gap-0.5" dir="auto">
                                      <span className="text-meta text-ink-soft break-words">
                                        <strong className="text-ink">{option.system_name}</strong> — {option.reason}
                                      </span>
                                      {known && <span className="text-meta text-ink-muted break-words">{known}</span>}
                                    </div>
                                    <Button size="sm" icon={<Link2 size={14} aria-hidden="true" />}
                                      disabled={decide.isPending || acceptAll.isPending}
                                      loading={pending && decide.variables.content !== undefined
                                        && decide.variables.content.system_id === target.system_id
                                        && decide.variables.content.target_system_id === target.target_system_id}
                                      loadingLabel="Linking…"
                                      onClick={() => decide.mutate({
                                        item, accept: true, content: target,
                                        done: naming
                                          ? `“${first.written_as}” added to ${option.system_name} as another name.`
                                          : `Added to this version, using ${option.system_name} for “${first.written_as}”.`,
                                      })}
                                      aria-label={naming
                                        ? `${label}: “${first.written_as}” as another name`
                                        : `${label} for “${first.written_as}” in ${text.title}`}>
                                      {label}
                                    </Button>
                                  </li>
                                );
                              })}
                              {naming && (
                                <li className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-2 max-sm:grid-cols-1 max-sm:justify-items-start">
                                  <span className="text-meta text-ink-soft">None of these.</span>
                                  <Button size="sm" icon={<Check size={14} aria-hidden="true" />}
                                    disabled={decide.isPending || acceptAll.isPending}
                                    loading={pending && decide.variables.accept && decide.variables.content === undefined}
                                    loadingLabel="Accepting…"
                                    onClick={() => decide.mutate({ item, accept: true })}
                                    aria-label={keep}>
                                    Keep as a new system
                                  </Button>
                                </li>
                              )}
                            </ul>
                          </div>
                        );
                      })}
                      {item.status === "proposed" && (
                        <div className="flex flex-wrap gap-2">
                          {!naming && (
                            <Button size="sm" variant={matching ? "ghost" : undefined}
                              icon={<Check size={14} aria-hidden="true" />}
                              disabled={decide.isPending || acceptAll.isPending}
                              loading={pending && decide.variables.accept && decide.variables.content === undefined}
                              loadingLabel="Accepting…"
                              onClick={() => decide.mutate({ item, accept: true })}
                              aria-label={matching ? `Accept as written: ${text.title}` : `Accept ${text.title}`}>
                              {matching ? "Accept as written" : "Accept"}
                            </Button>
                          )}
                          <Button size="sm" variant="ghost" icon={<PencilLine size={14} aria-hidden="true" />}
                            disabled={decide.isPending} onClick={() => setEditing(item)}
                            aria-label={`Edit and accept ${text.title}`}>
                            Edit and accept
                          </Button>
                          <Button size="sm" variant="ghost" icon={<X size={14} aria-hidden="true" />}
                            disabled={decide.isPending || acceptAll.isPending}
                            loading={pending && !decide.variables.accept} loadingLabel="Rejecting…"
                            onClick={() => decide.mutate({ item, accept: false })}
                            aria-label={`Reject ${text.title}`}>
                            Reject
                          </Button>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </section>
          );
        })}
      </AsyncState>
      {acceptingAll && (
        <ConfirmDialog
          title={bulk.length === 1 ? "Accept the 1 waiting suggestion?" : `Accept all ${bulk.length} waiting suggestions?`}
          message={`Added to this version without checking each one against its source passage: ${KINDS
            .map((kind) => [kind, bulk.filter((item) => item.content.kind === kind).length] as const)
            .filter(([, count]) => count > 0)
            .map(([kind, count]) => `${count} ${count === 1 ? ONE_KIND[kind] : SUGGESTION_KIND[kind].toLowerCase()}`)
            .join(", ")}.${held > 0
            ? ` ${held} inferred or possibly existing ${held === 1 ? "item stays" : "items stay"} for you to decide`
              + " one by one."
            : ""}`}
          confirmLabel="Accept all"
          onCancel={() => setAcceptingAll(false)}
          onConfirm={() => { setAcceptingAll(false); acceptAll.mutate(); }}
        />
      )}
      {rejecting && (
        <ConfirmDialog
          title={`Reject ${rejecting.ids.length} suggestions for ${rejecting.title}?`}
          message="They are marked rejected and nothing is added to this version. Reading the document again can suggest them again."
          confirmLabel="Reject all"
          onCancel={() => setRejecting(null)}
          onConfirm={() => { const ids = rejecting.ids; setRejecting(null); rejectMany.mutate(ids); }}
        />
      )}
      {reading && (
        <PassageDialog
          releaseId={draft.id}
          versionId={reading.item.document_version_id}
          documentTitle={documents.get(reading.item.document_version_id) ?? "Source document"}
          location={reading.location}
          quote={reading.quote}
          onClose={() => setReading(null)}
        />
      )}
      {editing && (
        <SuggestionEditor
          suggestion={editing}
          systems={[...names].map(([id, name]) => ({ id, name, components: systems.get(id)?.components ?? [] }))}
          domains={[...domains].map(([id, label]) => ({ id, label }))}
          offerings={offeringList}
          saving={decide.isPending}
          error={decide.error ? errorMessage(decide.error) : null}
          onCancel={() => { setEditing(null); decide.reset(); }}
          onSave={(content) => decide.mutate({ item: editing, accept: true, content })}
        />
      )}
    </section>
  );
}
