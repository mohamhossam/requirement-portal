import { ArrowLeft, ArrowRight, Search } from "lucide-react";
import { useId, useRef, useState, type KeyboardEvent, type ReactNode, type RefObject } from "react";

import type { CatalogueDiff, KnowledgeRelease, RelationshipKind, System } from "../../api/knowledge";
import type { Organisation } from "../../api/organisation";
import { SEARCH_FRAME, SEARCH_INPUT } from "../../app/dashboard/controls";
import { Badge, cx } from "../../components/ui";
import { FOCUS_RING, HOVER_GROUND_SOFT, TRANSITION } from "../../components/ui/recipes";
import { ownershipOf } from "../organisation/ownership";
import { DependencyDiagram } from "./DependencyDiagram";
import {
  CHANGE_LABEL, FIELD_LABEL, ITEM_LABEL, changesFor, domainLabel, kindNote, linkChanges, systemMarks,
} from "./labels";

const otherNames = (system: System) => [system.name_ar, ...system.aliases].filter(Boolean).join(" · ");

/** Below `md` the dossier sits under the list, out of sight of the row that opened it. */
const stacked = () => typeof window !== "undefined" && window.matchMedia?.("(max-width: 899.98px)").matches;

function Block({ title, count, children }: { title: string; count?: ReactNode; children: ReactNode }) {
  return (
    <section className="grid content-start gap-2" aria-label={title}>
      <h4 className="text-label text-ink-muted m-0">
        {title}
        {count !== undefined && <span className="tabular-nums font-normal"> ({count})</span>}
      </h4>
      {children}
    </section>
  );
}

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

const COMPONENT_ROW = "grid gap-x-6 gap-y-2 py-3 first:pt-0 last:pb-0 @xl:grid-cols-[minmax(9rem,13rem)_minmax(0,1fr)]";

/** Capabilities, each with its domain and the phrases that find it on one line beneath. */
function Capabilities({ items, release }: { items: System["capabilities"]; release: KnowledgeRelease }) {
  return (
    <ul className="m-0 grid list-none gap-2 p-0">
      {items.map((capability) => (
        <li key={capability.id} className="grid gap-0.5">
          <span className="text-body text-ink">{capability.name}</span>
          <span className="text-meta text-ink-muted">
            <span>Domain: {domainLabel(release.capability_domains ?? [], capability.domain_id) ?? "not placed yet"}</span>
            {" · "}
            <span dir="auto">Found by: {capability.triggers.join(", ")}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

type Neighbour = {
  id: string; name: string; description: string; known: boolean; removed?: boolean; kind?: RelationshipKind;
};

function Neighbours({ links, direction, onOpen }: {
  links: Neighbour[];
  direction: "out" | "in";
  onOpen: (id: string) => void;
}) {
  if (links.length === 0) {
    return <p className="text-meta text-ink-muted m-0">{direction === "out" ? "Depends on no other system." : "No system depends on it."}</p>;
  }
  const Arrow = direction === "out" ? ArrowRight : ArrowLeft;
  return (
    <ul className="m-0 grid list-none gap-1 p-0">
      {links.map((link) => (
        <li key={`${link.id}-${link.description}`} className="flex min-w-0 items-start gap-2">
          <Arrow className="text-ink-muted mt-1 shrink-0" size={14} aria-hidden="true" />
          <span className={cx("text-body min-w-0 break-words", link.removed ? "text-ink-muted" : "text-ink-soft")}>
            {link.known && !link.removed ? (
              <button type="button" onClick={() => onOpen(link.id)}
                className={cx("text-body text-accent inline min-h-6 cursor-pointer border-0 bg-transparent p-0 font-semibold underline underline-offset-2",
                  FOCUS_RING)}>
                {link.name}
              </button>
            ) : <span className={cx("font-semibold", link.removed ? "line-through" : "text-ink")}>{link.name}</span>}
            {kindNote(link.kind) && <span className="text-meta text-ink-muted"> ({kindNote(link.kind)})</span>}
            {link.description && <> — {link.description}</>}
            {link.removed && <> <Badge tone="danger">Removed</Badge></>}
          </span>
        </li>
      ))}
    </ul>
  );
}

function SystemDossier({ system, release, nameOf, organisation, diff, removed: gone = false, headingRef, onOpen }: {
  system: System;
  /** This version removes the system; it is shown as it stands in the version in use. */
  removed?: boolean;
  release: KnowledgeRelease;
  nameOf: (id: string) => string;
  organisation: Organisation | undefined;
  diff: CatalogueDiff | undefined;
  headingRef: RefObject<HTMLHeadingElement | null>;
  onOpen: (id: string) => void;
}) {
  const titleId = useId();
  const present = new Set(release.systems.map((item) => item.id));
  const link = (id: string, description: string, removed = false, kind?: RelationshipKind): Neighbour =>
    ({ id, description, name: nameOf(id), known: present.has(id), removed, kind });
  const { removed } = linkChanges(diff);
  const uses = [
    ...release.relationships.filter((item) => item.source_system_id === system.id)
      .map((item) => link(item.target_system_id, item.description, false, item.kind)),
    ...removed.filter((item) => item.source === system.id).map((item) => link(item.target, item.description, true)),
  ];
  const usedBy = [
    ...release.relationships.filter((item) => item.target_system_id === system.id)
      .map((item) => link(item.source_system_id, item.description, false, item.kind)),
    ...removed.filter((item) => item.target === system.id).map((item) => link(item.source, item.description, true)),
  ];
  const current = [...uses, ...usedBy].filter((item) => !item.removed).length;
  const dropped = uses.length + usedBy.length - current;
  const owners = organisation ? ownershipOf(system.id, organisation) : null;
  const ownerLines = owners
    ? [
        ...owners.squads.map((squad) => `Squad: ${squad.name}`),
        ...owners.valueStreams.map((stream) => `Value stream: ${stream.name}`),
        ...owners.products.map((product) => `Product: ${product.name}`),
      ]
    : [];
  const changes = changesFor(diff, system.id);
  const aka = otherNames(system);
  const place = domainLabel(release.landscape_domains ?? [], system.landscape_domain_id);
  const parts = system.components ?? [];
  const placed = new Set(parts.map((part) => part.id));
  const loose = system.capabilities.filter((item) => !item.component_id || !placed.has(item.component_id));

  return (
    <article aria-labelledby={titleId}
      className="bg-surface border-line grid min-w-0 content-start gap-6 rounded-md border border-solid p-6">
      <header className="grid gap-1">
        <h3 className="text-headline text-ink m-0 break-words" id={titleId} ref={headingRef} tabIndex={-1}>{system.name}</h3>
        <p className="text-meta text-ink-muted m-0 flex flex-wrap gap-x-2">
          <span className="font-mono">{system.id}</span>
          {aka && <span dir="auto">· {aka}</span>}
        </p>
        {(place || system.description) && (
          <div className="mt-1 grid gap-0.5">
            {system.description && <p className="text-body text-ink-soft m-0 max-w-[68ch]" dir="auto">{system.description}</p>}
            <p className="text-meta text-ink-muted m-0">Landscape: {place ?? "not placed yet"}</p>
          </div>
        )}
        {gone && (
          <p className="bg-danger-wash text-ink-soft text-meta m-0 mt-2 flex items-center gap-2 rounded-sm border-0 border-l-[3px] border-solid border-l-[var(--danger)] px-3 py-2">
            <Badge tone="danger">Removed</Badge>
            This version removes it. Shown as it is in the version in use, with the dependencies that go with it.
          </p>
        )}
      </header>

      {changes.length > 0 && (
        <Block title="Changed in this version" count={changes.length}>
          <ul className="m-0 grid list-none gap-1 p-0">
            {changes.map((change) => (
              <li key={`${change.item}-${change.change}-${change.key}`} className="grid grid-cols-[auto_minmax(0,1fr)] items-baseline gap-x-2">
                <Badge tone={CHANGE_LABEL[change.change].tone}>{CHANGE_LABEL[change.change].label}</Badge>
                <span className="text-body text-ink break-words" dir="auto">
                  <span className="text-meta text-ink-muted">{ITEM_LABEL[change.item]} · </span>
                  {change.label}
                  {change.fields.length > 0 && (
                    <span className="text-meta text-ink-muted">
                      {" "}({change.fields.map((field) => FIELD_LABEL[field] ?? field).join(", ")})
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Block>
      )}

      <Block title="Dependencies" count={dropped > 0 ? `${current} now · ${dropped} removed` : current}>
        <DependencyDiagram system={system} release={release} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid content-start gap-1">
            <p className="text-meta text-ink-muted m-0">Depends on</p>
            <Neighbours links={uses} direction="out" onOpen={onOpen} />
          </div>
          <div className="grid content-start gap-1">
            <p className="text-meta text-ink-muted m-0">Used by</p>
            <Neighbours links={usedBy} direction="in" onOpen={onOpen} />
          </div>
        </div>
      </Block>

      <Block title="What it does" count={parts.length > 0
        ? `${plural(system.capabilities.length, "capability", "capabilities")} in `
          + plural(parts.length, "component", "components")
        : system.capabilities.length}>
        {system.capabilities.length === 0 && parts.length === 0 ? (
          <p className="text-meta text-ink-muted m-0">No capabilities recorded.</p>
        ) : parts.length === 0 ? (
          <Capabilities items={system.capabilities} release={release} />
        ) : (
          // A component per row: what it is on the left, what it delivers on the right, once
          // the dossier is wide enough to hold both at a readable measure.
          <ul className="@container m-0 grid list-none p-0 [&>li+li]:[border-top:1px_solid_var(--line)]">
            {parts.map((part) => {
              const delivers = system.capabilities.filter((item) => item.component_id === part.id);
              const facts = [part.technology, part.aliases.length ? `also called ${part.aliases.join(", ")}` : null]
                .filter(Boolean).join(" · ");
              return (
                <li key={part.id} className={COMPONENT_ROW}>
                  <div className="grid content-start gap-0.5">
                    <h5 className="text-title text-ink m-0 break-words" dir="auto">{part.name}</h5>
                    {part.name_ar && <p className="text-meta text-ink-muted m-0" dir="auto">{part.name_ar}</p>}
                    {facts && <p className="text-meta text-ink-muted m-0" dir="auto">{facts}</p>}
                    {part.description && <p className="text-meta text-ink-soft m-0" dir="auto">{part.description}</p>}
                  </div>
                  {delivers.length > 0
                    ? <Capabilities items={delivers} release={release} />
                    : <p className="text-meta text-ink-muted m-0">No capabilities placed here yet.</p>}
                </li>
              );
            })}
            {loose.length > 0 && (
              <li className={COMPONENT_ROW}>
                <div className="grid content-start gap-0.5">
                  <h5 className="text-title text-ink-soft m-0">Not in a component</h5>
                  <p className="text-meta text-ink-muted m-0">Not placed in a part of {system.name} yet.</p>
                </div>
                <Capabilities items={loose} release={release} />
              </li>
            )}
          </ul>
        )}
      </Block>

      <div className="grid gap-6 sm:grid-cols-2">
        <Block title="Owned by">
          {!owners ? (
            <p className="text-meta text-ink-muted m-0">Ownership is loading.</p>
          ) : ownerLines.length > 0 ? (
            <ul className="text-body text-ink-soft m-0 grid list-none gap-1 p-0">
              {ownerLines.map((line) => <li key={line}>{line}</li>)}
            </ul>
          ) : (
            <p className="text-meta text-ink-muted m-0">No squad owns this system yet.</p>
          )}
        </Block>
        {system.constraints.length > 0 && (
          <Block title="Known constraints" count={system.constraints.length}>
            <ul className="text-body text-ink-soft m-0 grid gap-1 pl-5">
              {system.constraints.map((item) => <li key={item} dir="auto">{item}</li>)}
            </ul>
          </Block>
        )}
      </div>
    </article>
  );
}

/**
 * The systems of one catalogue version: a searchable index beside the dossier of
 * the one selected — what it does, what it depends on, what depends on it and
 * who owns it. Read-only, for readers and maintainers alike. Given the diff of a
 * version in progress, what it touches comes first, marked, and removed systems
 * and dependencies keep the names they have in the version in use.
 *
 * The index is one tab stop: arrow keys, Home and End move through it.
 */
export function CatalogueBrowser({ release, baseline, organisation, heading, diff, selected, onSelect }: {
  release: KnowledgeRelease;
  /** The version in use, for the names of what a version in progress removes. */
  baseline?: KnowledgeRelease;
  organisation: Organisation | undefined;
  heading: string;
  diff?: CatalogueDiff;
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  const [search, setSearch] = useState("");
  const countId = useId();
  const headingId = useId();
  const list = useRef<HTMLUListElement>(null);
  const dossierHeading = useRef<HTMLHeadingElement>(null);
  const names = new Map([...(baseline?.systems ?? []), ...release.systems].map((item) => [item.id, item.name]));
  const nameOf = (id: string) => names.get(id) ?? id;
  const needle = search.trim().toLowerCase();
  const marks = systemMarks(diff);
  const degree = (id: string) => release.relationships
    .filter((item) => item.source_system_id === id || item.target_system_id === id).length;
  const sorted = [...release.systems].sort((a, b) => a.name.localeCompare(b.name));
  const systems = sorted.filter((system) => !needle || [system.id, system.name, system.name_ar ?? "", ...system.aliases]
    .some((value) => value.toLowerCase().includes(needle)));
  const changed = systems.filter((system) => marks.has(system.id));
  const unchanged = systems.filter((system) => !marks.has(system.id));
  const removed = (diff?.changes ?? []).filter((change) => change.item === "system" && change.change === "removed");
  // A removed system opens as it stands in the version in use, so "what goes with it?" has an answer.
  const removedSystems = removed.map((change) => baseline?.systems.find((system) => system.id === change.key))
    .filter((system): system is System => Boolean(system));
  const showRemoved = removed.length > 0 && !needle;
  // Open on what the version changes, or else on the best-connected system, never on an empty record by accident.
  const fallback = changed[0] ?? [...systems].sort((a, b) => degree(b.id) - degree(a.id))[0] ?? sorted[0];
  const current = release.systems.find((system) => system.id === selected)
    ?? removedSystems.find((system) => system.id === selected) ?? fallback;
  const currentRemoved = removedSystems.some((system) => system.id === current?.id);
  const ordered = [...(showRemoved ? removedSystems : []), ...changed, ...unchanged];

  const open = (id: string, focus: boolean) => {
    onSelect(id);
    if (!focus) return;
    requestAnimationFrame(() => {
      dossierHeading.current?.focus({ preventScroll: true });
      dossierHeading.current?.scrollIntoView?.({ block: "start" });
    });
  };
  const move = (event: KeyboardEvent<HTMLUListElement>) => {
    const keys = ["ArrowDown", "ArrowUp", "Home", "End"];
    if (!keys.includes(event.key) || ordered.length === 0) return;
    event.preventDefault();
    const at = ordered.findIndex((system) => system.id === current?.id);
    const next = event.key === "Home" ? 0 : event.key === "End" ? ordered.length - 1
      : Math.min(ordered.length - 1, Math.max(0, at + (event.key === "ArrowDown" ? 1 : -1)));
    const target = ordered[next];
    if (!target) return;
    onSelect(target.id);
    requestAnimationFrame(() => list.current?.querySelector<HTMLButtonElement>(`[data-system="${CSS.escape(target.id)}"]`)?.focus());
  };

  const row = (system: System, gone = false) => {
    const active = system.id === current?.id;
    const mark = gone ? "removed" : marks.get(system.id);
    return (
      <li key={system.id}>
        <button type="button" data-system={system.id} aria-current={active || undefined} tabIndex={active ? 0 : -1}
          onClick={() => open(system.id, stacked())}
          className={cx(
            "grid w-full min-h-10 cursor-pointer gap-0.5 rounded-sm border-0 px-3 py-1.5 text-left",
            active ? "bg-surface-sunken [box-shadow:inset_0_0_0_1px_var(--line-strong)]" : cx("bg-transparent", HOVER_GROUND_SOFT),
            FOCUS_RING,
            TRANSITION,
          )}>
          <span className="flex min-w-0 items-center justify-between gap-2">
            <span className={cx("text-body min-w-0 truncate", gone ? "text-ink-muted line-through" : "text-ink",
              active && "font-semibold")}>{system.name}</span>
            {mark && <Badge tone={CHANGE_LABEL[mark].tone}>{CHANGE_LABEL[mark].label}</Badge>}
          </span>
          {!gone && otherNames(system) && (
            <span className="text-meta text-ink-muted min-w-0 truncate" dir="auto">{otherNames(system)}</span>
          )}
        </button>
      </li>
    );
  };
  const groupLabel = (text: string) => (
    <li role="presentation" className="text-label text-ink-muted px-3 pt-2 pb-1">{text}</li>
  );

  return (
    <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] items-start gap-6 md:grid-cols-[minmax(13rem,15rem)_minmax(0,1fr)]">
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] content-start gap-3 md:sticky md:top-[calc(var(--header-height)+var(--space-6))]">
        <div className="grid gap-0.5">
          <h2 className="text-title text-ink m-0" id={headingId}>{heading}</h2>
          <p className="text-meta text-ink-muted m-0 tabular-nums" id={countId} aria-live="polite">
            {systems.length === release.systems.length
              ? `${systems.length} systems`
              : `${systems.length} of ${release.systems.length} systems`}
          </p>
        </div>
        <label className={cx(SEARCH_FRAME, "w-full max-w-none min-w-0")}>
          <Search className="text-ink-muted shrink-0" size={16} aria-hidden="true" />
          <span className="sr-only">Search the catalogue</span>
          <input className={SEARCH_INPUT} type="search" value={search} aria-describedby={countId}
            placeholder="Name, ID or other name" onChange={(event) => setSearch(event.target.value)} />
        </label>
        {systems.length === 0 && !showRemoved ? (
          <p className="text-body text-ink-muted m-0">No system matches this search.</p>
        ) : (
          <ul ref={list} aria-label="Systems in this version" onKeyDown={move}
            className={cx("border-line bg-surface m-0 grid list-none overflow-y-auto overscroll-contain rounded-md border border-solid p-1",
              "max-h-80 md:max-h-[calc(100dvh-var(--header-height)-15rem)]")}>
            {(changed.length > 0 || showRemoved) && groupLabel(`Changed in this version (${changed.length + (showRemoved ? removed.length : 0)})`)}
            {showRemoved && removedSystems.map((system) => row(system, true))}
            {/* Removed with no record in the version in use: named, but there is nothing to open. */}
            {showRemoved && removed.filter((change) => !removedSystems.some((system) => system.id === change.key)).map((change) => (
              <li key={`removed-${change.key}`} className="flex min-h-10 items-center justify-between gap-2 px-3 py-1.5">
                <span className="text-body text-ink-muted min-w-0 truncate line-through">{names.get(change.key) ?? change.label}</span>
                <Badge tone="danger">Removed</Badge>
              </li>
            ))}
            {changed.map((system) => row(system))}
            {(changed.length > 0 || showRemoved) && unchanged.length > 0 && groupLabel("Other systems")}
            {unchanged.map((system) => row(system))}
          </ul>
        )}
      </div>
      {current ? (
        <SystemDossier key={current.id} system={current} release={currentRemoved && baseline ? baseline : release}
          nameOf={nameOf} organisation={organisation} diff={currentRemoved ? undefined : diff} removed={currentRemoved}
          headingRef={dossierHeading} onOpen={(id) => { setSearch(""); open(id, true); }} />
      ) : (
        <p className="text-body text-ink-muted m-0">This version has no systems yet.</p>
      )}
    </div>
  );
}
