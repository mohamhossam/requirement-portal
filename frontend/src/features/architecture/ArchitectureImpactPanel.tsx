import { useId } from "react";
import { Boxes, Layers, Network, Package, Route, TriangleAlert, Waypoints } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import type { ArchitectureImpact } from "../../api/client";

type SystemReference = ArchitectureImpact["systems"][number];
import { KNOWLEDGE_PORTAL_URL, evidenceHref, knowledgeApi } from "../../api/knowledge";
import { useIsKnowledgeAdmin } from "../../auth/useIsKnowledgeAdmin";
import { kindNote, roleLabel } from "./labels";
import { Badge, cx } from "../../components/ui";

/**
 * Which systems a Feature or Story touches, and on what evidence.
 *
 * Phase 4 moved this off the last of the retired styling it wore — an 11px
 * uppercase tracked label under the 12px floor, 5px and 8px radii, a
 * `toLocaleString()` timestamp in a second format beside the card's own — and
 * into business language: "Declared, not catalogued" is "Not in the
 * catalogue", "Squad" names the squads, value stream and products that own the system, "Legacy deterministic catalogue mapping" is
 * "Matched from the architecture catalogue". The query is unchanged.
 */
const TIMESTAMP = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

const LABEL = "text-label text-ink-muted m-0";

const names = (items: { name: string }[]) => (items.length ? items.map((item) => item.name).join(", ") : null);
const LINK = "text-ink-soft hover:text-ink inline-flex min-h-6 items-center underline underline-offset-2";

export function ArchitectureImpactPanel({
  impact,
  compact = false,
}: {
  impact: ArchitectureImpact | null;
  compact?: boolean;
}) {
  const active = useQuery({ queryKey: ["knowledge", "active"], queryFn: ({ signal }) => knowledgeApi.activeRelease({ signal }),
    enabled: Boolean(impact) });
  if (!impact) {
    return (
      <section className="text-body text-ink-muted flex items-center gap-2" aria-label="Architecture impact">
        <Boxes size={16} aria-hidden="true" className="shrink-0" />
        <span>Architecture not mapped</span>
      </section>
    );
  }

  const systemNames = new Map(impact.systems.map((system) => [system.id, system.name]));
  const nameOf = (id: string) => systemNames.get(id) ?? id;
  const outdated = active.data && active.data.id !== impact.knowledge_version;
  // The business areas of the capabilities mapping matched: the top of each one's domain
  // (ADR-0089). Only matched capabilities are listed, so the label says so.
  const areas = [...new Set(impact.systems.flatMap((system) =>
    system.capabilities.map((capability) => capability.domain_path?.[0]).filter((area): area is string => Boolean(area))))];
  return (
    <section className="grid gap-4" aria-label="Architecture impact" data-compact={compact || undefined}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-0.5">
          <p className="text-meta text-ink-muted m-0">
            {impact.evidence_classification === "ai_inference"
              ? "Suggested by AI from cited evidence"
              : "Matched from the architecture catalogue"}
            {" · mapped "}
            <time className="tabular-nums" dateTime={impact.mapped_at}>{TIMESTAMP.format(new Date(impact.mapped_at))}</time>
          </p>
          {/* Traceability, kept but quiet: the catalogue release and model
              that produced this mapping. */}
          <p className="text-meta text-ink-muted m-0">
            Catalogue{" "}
            {active.data?.id === impact.knowledge_version && active.data.name
              ? active.data.name
              : <span className="font-mono">{impact.knowledge_version}</span>}
            {impact.model ? ` · ${impact.model}` : ""}
          </p>
          {areas.length > 0 && (
            <p className="text-meta text-ink-muted m-0">Matched business areas: <span className="text-ink-soft">{areas.join(", ")}</span></p>
          )}
        </div>
        {impact.cross_system && !compact && <Badge tone="warning">Crosses systems</Badge>}
      </header>

      {outdated && (
        <p className="text-body text-ink-soft m-0 flex items-start gap-2" role="status">
          <TriangleAlert aria-hidden="true" className="text-warning mt-0.5 shrink-0" size={16} />
          This mapping uses an older release of the architecture catalogue. Refresh it to check against the current one.
        </p>
      )}
      {impact.uncertainty && (
        <p className="text-body text-ink-soft m-0 flex items-start gap-2">
          <TriangleAlert aria-hidden="true" className="text-warning mt-0.5 shrink-0" size={16} />
          <span><strong className="text-ink">Not certain:</strong> {impact.uncertainty}</span>
        </p>
      )}

      {impact.systems.length === 0 ? (
        (impact.suggested_domains ?? []).length > 0
          ? <SuggestedDomains impact={impact} />
          : <p className="text-body text-ink-muted m-0">No likely systems identified.</p>
      ) : (
        <ul className={cx("m-0 grid list-none gap-3 p-0", compact ? "[grid-template-columns:repeat(auto-fit,minmax(11rem,1fr))]" : "[grid-template-columns:repeat(auto-fit,minmax(13rem,1fr))]")}>
          {impact.systems.map((system) => (
            <li key={system.id} className="border-line bg-surface-sunken grid content-start gap-2 rounded-md border border-solid p-3">
              <div className="flex flex-wrap items-center gap-2">
                <strong className="text-body text-ink font-semibold">{system.name}</strong>
                {!system.catalogued && <Badge tone="warning">Not in the catalogue</Badge>}
              </div>
              <dl className="text-meta m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-0.5">
                <dt className="text-ink-muted">Squads</dt>
                <dd className="text-ink-soft m-0">{names(system.squads) ?? "not assigned"}</dd>
                {system.value_streams.length > 0 && <>
                  <dt className="text-ink-muted">Value stream</dt>
                  <dd className="text-ink-soft m-0">{names(system.value_streams)}</dd>
                </>}
                {system.products.length > 0 && <>
                  <dt className="text-ink-muted">Products</dt>
                  <dd className="text-ink-soft m-0">{names(system.products)}</dd>
                </>}
              </dl>
              {system.capabilities.length > 0 && (
                <ul aria-label={`Matched capabilities for ${system.name}`} className="m-0 flex list-none flex-wrap gap-1.5 p-0">
                  {system.capabilities.map((capability) => (
                    <li key={capability.id} className="text-meta text-ink-soft bg-surface rounded-sm px-2 py-0.5">
                      {capability.domain_path?.length
                        ? <span className="text-ink-muted whitespace-nowrap">{capability.domain_path.join(" › ")}: </span>
                        : null}
                      {capability.name}
                      {capability.component_name && (
                        <span className="text-ink-muted"> · {capability.component_name}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {system.constraints.length > 0 && (
                <ul aria-label={`Constraints for ${system.name}`} className="text-meta text-ink-soft m-0 grid gap-1 pl-4">
                  {system.constraints.map((constraint) => <li key={constraint}>{constraint}</li>)}
                </ul>
              )}
              {(impact.citations ?? []).filter((item) => item.system_id === system.id).map((citation, index) => (
                <blockquote key={`${citation.chunk_id}-${index}`} dir="auto" className="border-line m-0 grid gap-1 border-0 border-l-2 border-solid pl-3">
                  <p className="text-document font-document text-ink-soft m-0">{citation.quote}</p>
                  <Link className={cx("text-meta", LINK)} to={evidenceHref(impact.knowledge_version, citation.chunk_id)}>
                    View supporting evidence
                  </Link>
                </blockquote>
              ))}
            </li>
          ))}
        </ul>
      )}

      {impact.dependencies.length > 0 && (
        <div className="grid gap-1.5">
          <p className={cx(LABEL, "inline-flex items-center gap-1.5")}><Network size={14} aria-hidden="true" /> Dependencies between systems</p>
          <ul className="text-body text-ink-soft m-0 grid gap-1 pl-5">
            {impact.dependencies.map((dependency) => (
              <li key={`${dependency.source_system_id}-${dependency.target_system_id}-${dependency.description}`}>
                <strong className="text-ink">{nameOf(dependency.source_system_id)}</strong>
                {" → "}
                <strong className="text-ink">{nameOf(dependency.target_system_id)}</strong>
                {`: ${dependency.description}`}
                {kindNote(dependency.kind) && <span className="text-meta text-ink-muted"> ({kindNote(dependency.kind)})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}

      <ProductContexts impact={impact} compact={compact} />
      <JourneySteps impact={impact} compact={compact} />
      <ConnectedSystems impact={impact} compact={compact} />
      {impact.citation_ids.length > 0 && (
        <div className="grid gap-1.5">
          <p className={LABEL}>Source evidence</p>
          <ul className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0">
            {impact.citation_ids.map((id, index) => (
              <li key={id}>
                <Link className={cx("text-meta", LINK)} to={evidenceHref(impact.knowledge_version, id)}>
                  Evidence {index + 1}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

type ConnectedRow = {
  system: SystemReference; relation: string; description: string; kind: string | null;
};

/**
 * Systems one catalogued relationship away from the mapped ones (ADR-0087).
 * They are not mapped: the reviewer checks whether the change reaches them.
 * Grouped under the mapped system they connect to, because a hub (six
 * neighbours through one system) is the finding; direction is said in words.
 */
function ConnectedSystems({ impact, compact }: { impact: ArchitectureImpact; compact: boolean }) {
  const labelId = useId();
  const connected = impact.adjacent_systems ?? [];
  if (connected.length === 0) return null;

  const byId = new Map(connected.map((system) => [system.id, system]));
  const groups = impact.systems
    .map((mapped) => {
      const rows: ConnectedRow[] = [];
      for (const item of impact.adjacent_dependencies ?? []) {
        const uses = item.source_system_id === mapped.id;
        if (!uses && item.target_system_id !== mapped.id) continue;
        const system = byId.get(uses ? item.target_system_id : item.source_system_id);
        if (!system) continue;
        rows.push({
          system,
          relation: uses ? `Used by ${mapped.name}` : `Uses ${mapped.name}`,
          description: item.description,
          kind: kindNote(item.kind),
        });
      }
      rows.sort((a, b) => a.system.name.localeCompare(b.system.name));
      return { mapped, rows };
    })
    .filter((group) => group.rows.length > 0);
  const anySquads = connected.some((system) => system.squads.length > 0);
  const more = impact.adjacent_omitted;

  return (
    <div className="grid gap-2" role="group" aria-labelledby={labelId}>
      <p id={labelId} className={cx(LABEL, "inline-flex items-center gap-1.5")}>
        <Route size={14} aria-hidden="true" /> Connected systems to check
      </p>
      {compact ? (
        <p className="text-body text-ink-soft m-0">
          <span className="text-ink-muted">Not mapped: </span>
          {connected.map((system) => system.name).join("; ")}
          {more > 0 && `; and ${more} more`}
        </p>
      ) : (
        <>
          <p className="text-meta text-ink-muted m-0 max-w-[80ch]">
            Not part of this mapping. The catalogue links each one to a mapped system, so this change may reach it.
          </p>
          {groups.map(({ mapped, rows }) => (
            <div key={mapped.id} className="grid gap-1.5">
              <p className="text-meta text-ink-muted m-0">
                Linked to {mapped.name} ({rows.length === 1 ? "1 system" : `${rows.length} systems`})
              </p>
              <ul role="list" className="m-0 grid max-w-[80ch] list-none gap-2 p-0">
                {rows.map(({ system, relation, description, kind }) => (
                  <li key={`${system.id}-${relation}-${description}`} className="text-body grid gap-0.5">
                    <p className="m-0 flex flex-wrap items-baseline gap-x-2">
                      <span className="text-ink">{system.name}</span>
                      {system.capabilities.length > 0 && (
                        <span className="text-meta text-ink-muted">{names(system.capabilities)}</span>
                      )}
                    </p>
                    <p className="text-ink-soft m-0">
                      {relation}: {description}
                      {kind && <span className="text-meta text-ink-muted"> ({kind})</span>}
                    </p>
                    {anySquads && (
                      <p className="text-meta text-ink-muted m-0">
                        Squads: {names(system.squads) ?? "not assigned"}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
          {!anySquads && (
            <p className="text-meta text-ink-muted m-0">The squad catalogue assigns no squads to these systems.</p>
          )}
          {more > 0 && (
            <p className="text-meta text-ink-muted m-0">
              {more === 1 ? "1 more connected system is" : `${more} more connected systems are`} in the{" "}
              <CatalogueName />.
            </p>
          )}
        </>
      )}
    </div>
  );
}

type Activity = NonNullable<NonNullable<ArchitectureImpact["journey_steps"]>[number]["after"]>[number];

const activity = (item: Activity) => `${item.number}. ${item.name}${item.system_name ? ` (${item.system_name})` : ""}`;

/**
 * The product offerings the item names, and the systems the catalogue makes
 * responsible for what it named (ADR-0097). Advice for the reviewer, never a
 * mapping: set apart from the mapped-system cards, under its own label.
 */
function ProductContexts({ impact, compact }: { impact: ArchitectureImpact; compact: boolean }) {
  const labelId = useId();
  const contexts = impact.product_contexts ?? [];
  if (contexts.length === 0) return null;
  return (
    <div className="grid gap-2" role="group" aria-labelledby={labelId}>
      <p id={labelId} className={cx(LABEL, "inline-flex items-center gap-1.5")}>
        <Package size={14} aria-hidden="true" /> Product offering named
      </p>
      {!compact && (
        <p className="text-meta text-ink-muted m-0 max-w-[80ch]">
          A note, not a mapping: the systems the catalogue makes responsible for what this item names.
        </p>
      )}
      <ul role="list" className="m-0 grid max-w-[80ch] list-none gap-3 p-0">
        {contexts.map((context) => {
          const title = [context.product_name, context.order_type].filter(Boolean).join(" › ");
          const duties = context.responsibilities ?? [];
          const parts = [...new Set(duties.map((duty) => duty.component_name))];
          return (
            <li key={context.product_id} className="text-body text-ink-soft grid gap-1">
              <span className="text-ink">{title}</span>
              {compact ? (
                <span className="text-meta">
                  {duties.length ? [...new Set(duties.map((duty) => duty.system_name))].join(", ") : "No systems named yet"}
                </span>
              ) : (
                <>
                  <span className="text-meta text-ink-muted">
                    Words in common: {context.matched_terms.map((term) => `“${term}”`).join(", ")}
                  </span>
                  {duties.length === 0 ? (
                    <span className="text-meta text-ink-muted">The catalogue names no systems for it yet.</span>
                  ) : (
                    <dl className="text-meta m-0 grid gap-1">
                      {parts.map((part) => (
                        <div key={part} className="grid gap-0.5">
                          <dt className="text-ink">{part}</dt>
                          {duties.filter((duty) => duty.component_name === part).map((duty) => (
                            <dd key={`${duty.system_id}-${duty.role}`} className="m-0 pl-3">
                              <span className="text-ink">{duty.system_name}</span>
                              <span className="text-ink-muted"> · {roleLabel(duty.role)}</span>
                              {duty.description && <>: {duty.description}</>}
                            </dd>
                          ))}
                        </div>
                      ))}
                    </dl>
                  )}
                </>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Where each mapped system acts in the catalogue's journeys, and the activities
 * that hand over to and from it (ADR-0097): the systems to check either side of
 * the change. Advice, never a mapping.
 */
function JourneySteps({ impact, compact }: { impact: ArchitectureImpact; compact: boolean }) {
  const labelId = useId();
  const steps = impact.journey_steps ?? [];
  if (steps.length === 0) return null;
  const groups = impact.systems
    .map((system) => ({ system, steps: steps.filter((step) => step.system_id === system.id) }))
    .filter((group) => group.steps.length > 0);
  return (
    <div className="grid gap-2" role="group" aria-labelledby={labelId}>
      <p id={labelId} className={cx(LABEL, "inline-flex items-center gap-1.5")}>
        <Waypoints size={14} aria-hidden="true" /> Journey steps to check
      </p>
      {compact ? (
        <p className="text-body text-ink-soft m-0">
          {groups.map(({ system, steps: own }) =>
            `${system.name}: ${own.map((step) => `${step.number}. ${step.name}`).join(", ")}`).join("; ")}
        </p>
      ) : (
        <>
          <p className="text-meta text-ink-muted m-0 max-w-[80ch]">
            Where the mapped systems act in the catalogue&rsquo;s journeys, and the activities just before and after.
          </p>
          {groups.map(({ system, steps: own }) => (
            <div key={system.id} className="grid gap-1.5">
              <p className="text-meta text-ink-muted m-0">{system.name}</p>
              <ul role="list" className="m-0 grid max-w-[80ch] list-none gap-2 p-0">
                {own.map((step) => (
                  <li key={`${step.journey_id}-${step.number}`} className="text-body grid gap-0.5">
                    <p className="m-0 flex flex-wrap items-baseline gap-x-2">
                      <span className="text-ink">{step.number}. {step.name}</span>
                      <span className="text-meta text-ink-muted">
                        {step.performs ? "Performs" : "Supports"} · {step.fulfils?.length ? step.fulfils.join(" › ") : step.journey_name}
                      </span>
                    </p>
                    {(step.before ?? []).length > 0 && (
                      <p className="text-meta text-ink-soft m-0">After {(step.before ?? []).map(activity).join("; ")}</p>
                    )}
                    {(step.after ?? []).length > 0 && (
                      <p className="text-meta text-ink-soft m-0">Then {(step.after ?? []).map(activity).join("; ")}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

/**
 * When nothing was mapped, the capability domains whose catalogue wording the
 * item shares (ADR-0089): a lead for the reviewer, never a mapping. It is set
 * as plain text, apart from the mapped-system cards it must not be mistaken for.
 */
function SuggestedDomains({ impact }: { impact: ArchitectureImpact }) {
  const labelId = useId();
  const suggestions = impact.suggested_domains ?? [];
  return (
    <div className="grid gap-2" role="group" aria-labelledby={labelId}>
      <p className="text-body text-ink-muted m-0">No system mapped.</p>
      <p id={labelId} className={cx(LABEL, "inline-flex items-center gap-1.5")}>
        <Layers size={14} aria-hidden="true" /> Closest business areas
      </p>
      <p className="text-meta text-ink-muted m-0 max-w-[68ch]">
        A suggestion, not a mapping: the wording shares these words with the catalogue. Check whether their
        systems are affected. Naming a system on the requirement, or adding these words to the{" "}
        <CatalogueName />, lets mapping find it.
      </p>
      <ul role="list" className="m-0 grid list-none gap-2 p-0">
        {suggestions.map((item) => (
          <li key={item.domain_id} className="text-body text-ink-soft grid gap-0.5">
            <span>{item.path.join(" › ")}</span>
            <span className="text-meta text-ink-muted">
              Its systems, not mapped: {item.system_names?.length ? item.system_names.join(", ") : "none placed yet"}
            </span>
            <span className="text-meta text-ink-muted">
              Words in common: {item.matched_terms.map((term) => `“${term}”`).join(", ")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * "architecture catalogue", linked to the knowledge portal for the people who
 * curate it there (ADR-0099); plain words for everyone else.
 */
function CatalogueName() {
  const admin = useIsKnowledgeAdmin();
  return admin && KNOWLEDGE_PORTAL_URL !== null
    ? <a className={LINK} href={KNOWLEDGE_PORTAL_URL}>architecture catalogue</a>
    : <>architecture catalogue</>;
}
