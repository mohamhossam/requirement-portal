import { Minus, Plus } from "lucide-react";
import { useId, useState } from "react";

import type { CatalogueDiff, KnowledgeRelease } from "../../api/knowledge";
import { Badge, Button, Checkbox, cx } from "../../components/ui";
import { FOCUS_RING, TRANSITION } from "../../components/ui/recipes";
import { linkChanges, linkKey } from "./labels";

type Link = { source: string; target: string; description: string; change?: "added" | "removed" };

/** Row and column bands under the pointer or focus: an accent tint too faint to read as the accent. */
const BAND = "[background-color:color-mix(in_srgb,var(--accent)_7%,var(--surface))]";

function Mark({ links }: { links: Link[] }) {
  const change = links.find((link) => link.change)?.change;
  if (change === "added") return <Plus size={14} strokeWidth={3} className="text-success" aria-hidden="true" />;
  if (change === "removed") return <Minus size={14} strokeWidth={3} className="text-danger" aria-hidden="true" />;
  return <span aria-hidden="true" className="bg-ink block size-2.5 rounded-full" />;
}

/**
 * The whole landscape at once, as a design structure matrix: every system on
 * both axes and a mark where the row's system depends on the column's. Hover or
 * focus crosshairs a pair; selecting a mark reads the dependency out in words.
 * In a version in progress, added and removed dependencies carry a plus or a
 * minus as well as their colour, and the legend and the selected line say so.
 */
export function DependencyMatrix({ release, baseline, diff, onOpenSystem }: {
  release: KnowledgeRelease;
  /** The version in use, for the names of what a version in progress removes. */
  baseline?: KnowledgeRelease;
  diff?: CatalogueDiff;
  onOpenSystem: (id: string) => void;
}) {
  const titleId = useId();
  const [showAll, setShowAll] = useState(false);
  const [hover, setHover] = useState<{ row: string; col: string } | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  const names = new Map([...(baseline?.systems ?? []), ...release.systems].map((system) => [system.id, system.name]));
  const present = new Set(release.systems.map((system) => system.id));
  const nameOf = (id: string) => names.get(id) ?? id;
  const { added, removed } = linkChanges(diff);
  const cells = new Map<string, Link[]>();
  const put = (link: Link) => {
    const key = `${link.source}->${link.target}`;
    cells.set(key, [...(cells.get(key) ?? []), link]);
  };
  for (const item of release.relationships) {
    put({ source: item.source_system_id, target: item.target_system_id, description: item.description,
      change: added.has(linkKey(item.source_system_id, item.target_system_id, item.description)) ? "added" : undefined });
  }
  for (const item of removed) put({ ...item, change: "removed" });

  const linked = new Set([...cells.values()].flat().flatMap((link) => [link.source, link.target]));
  const live = new Set(release.relationships.flatMap((item) => [item.source_system_id, item.target_system_id]));
  const isolated = release.systems.filter((system) => !linked.has(system.id)).length;
  const axis = [...new Set([...(showAll ? release.systems.map((system) => system.id) : []), ...linked])]
    .sort((a, b) => nameOf(a).localeCompare(nameOf(b)));
  const selected = picked ? cells.get(picked) : undefined;
  const count = release.relationships.length;
  const changed = added.size + removed.length;

  const band = (row: string, col: string) => hover !== null && (hover.row === row || hover.col === col);

  return (
    <section aria-labelledby={titleId} className="grid min-w-0 gap-4">
      <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
        <div className="grid gap-0.5">
          <h2 className="text-title text-ink m-0" id={titleId}>Dependencies</h2>
          <p className="text-meta text-ink-muted m-0 flex flex-wrap items-center gap-x-3 gap-y-1 tabular-nums">
            <span>{count} {count === 1 ? "dependency" : "dependencies"} between {live.size} systems · rows depend on the columns marked</span>
            {changed > 0 && added.size > 0 && (
              <span className="inline-flex items-center gap-1"><Plus size={14} strokeWidth={3} className="text-success" aria-hidden="true" />Added in this version ({added.size})</span>
            )}
            {changed > 0 && removed.length > 0 && (
              <span className="inline-flex items-center gap-1"><Minus size={14} strokeWidth={3} className="text-danger" aria-hidden="true" />Removed in this version ({removed.length})</span>
            )}
          </p>
        </div>
        {isolated > 0 && (
          <Checkbox label={`Show systems with no dependencies (${isolated})`} checked={showAll}
            onChange={(event) => setShowAll(event.target.checked)} />
        )}
      </header>

      {/* A fixed line for the selected dependency, so choosing one never moves the grid. */}
      <div className="bg-surface-sunken border-line flex min-h-14 flex-wrap items-center justify-between gap-3 rounded-md border border-solid px-4 py-2"
        role="status" aria-live="polite">
        {selected ? (
          <>
            <div className="grid min-w-0 gap-0.5">
              {selected.map((link) => (
                <p key={link.description} className="text-body text-ink m-0 flex flex-wrap items-center gap-2">
                  <span><strong>{nameOf(link.source)}</strong> depends on <strong>{nameOf(link.target)}</strong>
                    {link.description && <span className="text-ink-soft"> — {link.description}</span>}</span>
                  {link.change === "added" && <Badge tone="success">Added</Badge>}
                  {link.change === "removed" && <Badge tone="danger">Removed</Badge>}
                </p>
              ))}
            </div>
            <div className="flex flex-wrap gap-1">
              {[selected[0]!.source, selected[0]!.target].filter((id) => present.has(id)).map((id) => (
                <Button key={id} size="sm" variant="ghost" onClick={() => onOpenSystem(id)}>Open {nameOf(id)}</Button>
              ))}
            </div>
          </>
        ) : (
          <p className="text-meta text-ink-muted m-0">Select a mark to read that dependency.</p>
        )}
      </div>

      {axis.length === 0 ? (
        <p className="text-body text-ink-muted m-0">No dependencies are recorded in this version.</p>
      ) : (
        <div className="border-line bg-surface max-h-[calc(100dvh-var(--header-height)-14rem)] min-h-64 overflow-auto overscroll-contain rounded-md border border-solid [scroll-padding-left:12rem] [scroll-padding-top:9rem]"
          onMouseLeave={() => setHover(null)}>
          <table className="border-separate [border-spacing:0]">
            <caption className="sr-only">Dependencies: each row's system depends on the systems marked in its columns</caption>
            <thead>
              <tr>
                <td className="bg-surface border-line sticky top-0 left-0 z-[var(--z-sticky)] border-0 border-r border-b border-solid" />
                {axis.map((col) => (
                  <th key={col} scope="col" title={nameOf(col)}
                    className={cx("bg-surface border-line sticky top-0 z-[var(--z-base)] border-0 border-b border-solid px-0 pt-2 pb-2 align-bottom font-normal",
                      hover?.col === col && BAND)}>
                    <span className={cx("text-meta mx-auto block max-h-32 w-8 truncate text-left [writing-mode:vertical-rl] rotate-180",
                      hover?.col === col ? "text-ink font-semibold" : "text-ink-muted", !present.has(col) && "line-through")}>
                      {nameOf(col)}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {axis.map((row) => (
                <tr key={row}>
                  <th scope="row"
                    className={cx("bg-surface border-line sticky left-0 z-[var(--z-base)] border-0 border-r border-solid px-1 py-0 text-left font-normal",
                      hover?.row === row && BAND)}>
                    {present.has(row) ? (
                      <button type="button" onClick={() => onOpenSystem(row)} title={`Open ${nameOf(row)} in the systems list`}
                        className={cx("text-meta block max-w-44 min-h-8 w-full cursor-pointer truncate rounded-xs border-0 bg-transparent px-2 text-left",
                          "focus-visible:relative focus-visible:z-[var(--z-sticky)]",
                          hover?.row === row ? "text-ink font-semibold" : "text-ink-soft", "hover:underline", FOCUS_RING)}>
                        {nameOf(row)}
                      </button>
                    ) : (
                      // A system this version removes: named, struck through, and not openable.
                      <span className="text-meta text-ink-muted flex min-h-8 max-w-44 items-center truncate px-2 line-through">
                        {nameOf(row)}
                      </span>
                    )}
                  </th>
                  {axis.map((col) => {
                    const key = `${row}->${col}`;
                    const links = cells.get(key);
                    const focus = () => setHover({ row, col });
                    return (
                      <td key={col} onMouseEnter={focus}
                        className={cx("border-line size-8 border-0 border-r border-b border-dotted p-0 text-center",
                          row === col ? "[background-color:color-mix(in_srgb,var(--line)_40%,var(--surface))]" : band(row, col) && BAND)}>
                        {links && (
                          <button type="button" onFocus={focus} onClick={() => setPicked(picked === key ? null : key)}
                            aria-pressed={picked === key}
                            aria-label={links.map((link) => `${nameOf(row)} depends on ${nameOf(col)}${link.change ? `, ${link.change} in this version` : ""}`).join("; ")}
                            className={cx("grid size-8 cursor-pointer place-items-center rounded-xs border-0 bg-transparent p-0",
                              picked === key && "[box-shadow:inset_0_0_0_2px_var(--ink)]", "focus-visible:relative focus-visible:z-[var(--z-sticky)]",
                              FOCUS_RING, TRANSITION)}>
                            <Mark links={links} />
                          </button>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
