import { TriangleAlert } from "lucide-react";

import type { CapabilityDomain, CatalogueDiff, KnowledgeRelease } from "../../api/knowledge";
import { Badge, cx } from "../../components/ui";
import { FOCUS_RING } from "../../components/ui/recipes";
import { CHANGE_LABEL } from "./labels";

type Held = { capability: string; systemId: string; systemName: string };

const HEADINGS = ["h3", "h4", "h5"] as const;
const SYSTEM_LINK = cx(
  "text-body text-ink-soft hover:text-ink inline min-h-6 cursor-pointer border-0 bg-transparent p-0 text-left underline underline-offset-2",
  FOCUS_RING,
);

/**
 * The Domains view: where the systems sit in the landscape (ADR-0094), then
 * what they do by business area (ADR-0089). Two trees, read separately.
 */
export function DomainTree({ release, diff, onOpenSystem }: {
  release: KnowledgeRelease;
  diff?: CatalogueDiff;
  onOpenSystem: (id: string) => void;
}) {
  return (
    <div className="grid gap-8">
      <LandscapeTree release={release} diff={diff} onOpenSystem={onOpenSystem} />
      <CapabilityTree release={release} diff={diff} onOpenSystem={onOpenSystem} />
    </div>
  );
}

/**
 * Where the systems sit (ADR-0094): each landscape domain with the systems
 * placed in it and what each is for, sub-domains nested inside, then the
 * systems nobody has placed yet. A system opens its dossier.
 */
function LandscapeTree({ release, diff, onOpenSystem }: {
  release: KnowledgeRelease;
  diff?: CatalogueDiff;
  onOpenSystem: (id: string) => void;
}) {
  const domains = release.landscape_domains ?? [];
  const placed = new Map<string, KnowledgeRelease["systems"]>();
  for (const system of release.systems) {
    const key = system.landscape_domain_id ?? "";
    placed.set(key, [...(placed.get(key) ?? []), system]);
  }
  const changed = new Map((diff?.changes ?? [])
    .filter((change) => change.item === "landscape_domain" && change.change !== "removed")
    .map((change) => [change.key, change.change]));
  const childrenOf = (parent: string | null) => domains
    .filter((item) => (item.parent_id ?? null) === parent)
    .sort((a, b) => a.name.localeCompare(b.name));
  const count = (domain: CapabilityDomain): number =>
    (placed.get(domain.id) ?? []).length + childrenOf(domain.id).reduce((total, child) => total + count(child), 0);

  const rows = (systems: KnowledgeRelease["systems"]) => (
    <ul role="list" className="m-0 grid list-none gap-1 p-0">
      {[...systems].sort((a, b) => a.name.localeCompare(b.name)).map((system) => (
        <li key={system.id} className="grid gap-0.5">
          <span>
            <button type="button" className={SYSTEM_LINK} onClick={() => onOpenSystem(system.id)}>
              {system.name}
            </button>
          </span>
          {system.description && (
            <span className="text-meta text-ink-muted max-w-[68ch] break-words" dir="auto">{system.description}</span>
          )}
        </li>
      ))}
    </ul>
  );

  const node = (domain: CapabilityDomain, depth: number) => {
    const Heading = HEADINGS[Math.min(depth, 2)] ?? "h5";
    const own = placed.get(domain.id) ?? [];
    const children = childrenOf(domain.id);
    const total = count(domain);
    const change = changed.get(domain.id);
    return (
      <li key={domain.id} className={cx("grid content-start gap-2", depth === 0
        ? "bg-surface border-line rounded-md border border-solid p-4"
        : "border-line border-0 border-l border-solid pl-4")}>
        <div className="grid gap-0.5">
          <Heading className="text-body text-ink m-0 flex flex-wrap items-center gap-x-2 font-semibold">
            {domain.name}
            {domain.name_ar && <span className="text-meta text-ink-muted font-normal" dir="auto">{domain.name_ar}</span>}
            {change && <Badge tone={CHANGE_LABEL[change].tone}>{CHANGE_LABEL[change].label}</Badge>}
          </Heading>
          <p className="text-meta text-ink-muted m-0">
            {total === 0 ? "No systems placed here yet." : `${total} ${total === 1 ? "system" : "systems"}`}
          </p>
          {domain.description && <p className="text-meta text-ink-muted m-0 max-w-[68ch]" dir="auto">{domain.description}</p>}
        </div>
        {own.length > 0 && rows(own)}
        {children.length > 0 && (
          <ul role="list" className="m-0 grid list-none gap-3 p-0">
            {children.map((child) => node(child, depth + 1))}
          </ul>
        )}
      </li>
    );
  };

  if (domains.length === 0) {
    return (
      <section aria-labelledby="landscape-tree-title" className="bg-surface border-line grid gap-2 rounded-md border border-solid p-6">
        <h2 id="landscape-tree-title" className="text-headline text-ink m-0">Landscape domains</h2>
        <p className="text-body text-ink-muted m-0 max-w-[68ch]">
          This version has no landscape domains yet. A maintainer adds them under Add content, Edit manually.
        </p>
      </section>
    );
  }
  const unplaced = placed.get("") ?? [];
  return (
    <section aria-labelledby="landscape-tree-title" className="grid gap-4">
      <header className="grid gap-1">
        <h2 id="landscape-tree-title" className="text-headline text-ink m-0">Landscape domains ({domains.length})</h2>
        <p className="text-meta text-ink-muted m-0">Where the systems sit in the architecture landscape.</p>
      </header>
      <ul role="list" className="m-0 grid list-none items-start gap-4 p-0 lg:grid-cols-2">
        {childrenOf(null).map((domain) => node(domain, 0))}
      </ul>
      {unplaced.length > 0 && (
        <section aria-labelledby="landscape-tree-unplaced"
          className="bg-warning-wash grid gap-2 rounded-md border-0 border-l-[3px] border-solid border-l-[var(--warning-edge)] p-4">
          <h3 id="landscape-tree-unplaced" className="text-body text-ink m-0 flex items-center gap-2 font-semibold">
            <TriangleAlert size={16} aria-hidden="true" className="text-warning shrink-0" />
            Not placed in the landscape yet ({unplaced.length})
          </h3>
          {rows(unplaced)}
        </section>
      )}
    </section>
  );
}

/**
 * The landscape read by business area (ADR-0089): each capability domain with
 * the capabilities placed in it and the systems that provide them, nested as
 * the tree is, then the capabilities nobody has placed yet. A version in
 * progress marks the domains it adds or changes. A system opens its dossier.
 */
function CapabilityTree({ release, diff, onOpenSystem }: {
  release: KnowledgeRelease;
  diff?: CatalogueDiff;
  onOpenSystem: (id: string) => void;
}) {
  const domains = release.capability_domains ?? [];
  const held = new Map<string, Held[]>();
  for (const system of release.systems) {
    for (const capability of system.capabilities) {
      const key = capability.domain_id ?? "";
      held.set(key, [...(held.get(key) ?? []),
        { capability: capability.name, systemId: system.id, systemName: system.name }]);
    }
  }
  const changed = new Map((diff?.changes ?? [])
    .filter((change) => change.item === "domain" && change.change !== "removed")
    .map((change) => [change.key, change.change]));
  const unplaced = held.get("") ?? [];
  const childrenOf = (parent: string | null) => domains
    .filter((item) => (item.parent_id ?? null) === parent)
    .sort((a, b) => a.name.localeCompare(b.name));
  /** Everything placed in a domain or in the domains inside it. */
  const within = (domain: CapabilityDomain): Held[] =>
    [...(held.get(domain.id) ?? []), ...childrenOf(domain.id).flatMap(within)];

  const rows = (items: Held[]) => (
    <ul role="list" className="m-0 grid list-none gap-1 p-0">
      {[...items].sort((a, b) => a.capability.localeCompare(b.capability)).map((item) => (
        <li key={`${item.systemId}-${item.capability}`}
          className="grid grid-cols-[minmax(0,1fr)_minmax(0,10rem)] items-baseline gap-x-3">
          <span className="text-body text-ink-soft min-w-0 break-words">{item.capability}</span>
          <span className="min-w-0 text-right">
            <button type="button" className={SYSTEM_LINK} onClick={() => onOpenSystem(item.systemId)}>
              {item.systemName}
            </button>
          </span>
        </li>
      ))}
    </ul>
  );

  const node = (domain: CapabilityDomain, depth: number) => {
    const Heading = HEADINGS[Math.min(depth, 2)] ?? "h5";
    const own = held.get(domain.id) ?? [];
    const children = childrenOf(domain.id);
    const all = within(domain);
    const systems = new Set(all.map((item) => item.systemId)).size;
    const change = changed.get(domain.id);
    return (
      <li key={domain.id} className={cx("grid content-start gap-2", depth === 0
        ? "bg-surface border-line rounded-md border border-solid p-4"
        : "border-line border-0 border-l border-solid pl-4")}>
        <div className="grid gap-0.5">
          <Heading className="text-body text-ink m-0 flex flex-wrap items-center gap-x-2 font-semibold">
            {domain.name}
            {domain.name_ar && <span className="text-meta text-ink-muted font-normal" dir="auto">{domain.name_ar}</span>}
            {change && <Badge tone={CHANGE_LABEL[change].tone}>{CHANGE_LABEL[change].label}</Badge>}
          </Heading>
          <p className="text-meta text-ink-muted m-0">
            {all.length === 0
              ? "No capabilities placed here yet."
              : `${all.length} ${all.length === 1 ? "capability" : "capabilities"} · ${systems} ${systems === 1 ? "system" : "systems"}`}
          </p>
          {domain.description && <p className="text-meta text-ink-muted m-0 max-w-[68ch]" dir="auto">{domain.description}</p>}
        </div>
        {own.length > 0 && rows(own)}
        {children.length > 0 && (
          <ul role="list" className="m-0 grid list-none gap-3 p-0">
            {children.map((child) => node(child, depth + 1))}
          </ul>
        )}
      </li>
    );
  };

  if (domains.length === 0) {
    return (
      <section aria-labelledby="domain-tree-title" className="bg-surface border-line grid gap-2 rounded-md border border-solid p-6">
        <h2 id="domain-tree-title" className="text-headline text-ink m-0">Capability domains</h2>
        <p className="text-body text-ink-muted m-0 max-w-[68ch]">
          This version has no capability domains yet. A maintainer adds them under Add content, Edit manually.
        </p>
      </section>
    );
  }

  return (
    <section aria-labelledby="domain-tree-title" className="grid gap-4">
      <header className="grid gap-1">
        <h2 id="domain-tree-title" className="text-headline text-ink m-0">Capability domains ({domains.length})</h2>
        <p className="text-meta text-ink-muted m-0">What the systems do, grouped by business area.</p>
      </header>
      <ul role="list" className="m-0 grid list-none items-start gap-4 p-0 lg:grid-cols-2">
        {childrenOf(null).map((domain) => node(domain, 0))}
      </ul>
      {unplaced.length > 0 && (
        <section aria-labelledby="domain-tree-unplaced"
          className="bg-warning-wash grid gap-2 rounded-md border-0 border-l-[3px] border-solid border-l-[var(--warning-edge)] p-4">
          <h3 id="domain-tree-unplaced" className="text-body text-ink m-0 flex items-center gap-2 font-semibold">
            <TriangleAlert size={16} aria-hidden="true" className="text-warning shrink-0" />
            Not placed in a domain yet ({unplaced.length})
          </h3>
          {rows(unplaced)}
        </section>
      )}
    </section>
  );
}
