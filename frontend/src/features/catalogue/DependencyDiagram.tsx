import { useId } from "react";

import type { KnowledgeRelease, Relationship, System } from "../../api/knowledge";
import { kindNote } from "./labels";

const MAX_PER_SIDE = 8;
const ROW = 40;
const NODE_W = 136;
const NODE_H = 28;
const WIDTH = 480;
const CENTRE_X = (WIDTH - NODE_W) / 2;
const RIGHT_X = WIDTH - NODE_W - 8;

const short = (name: string) => (name.length > 19 ? `${name.slice(0, 18)}…` : name);

function Node({ x, y, name, note, strong = false }: {
  x: number; y: number; name: string; note?: string | null; strong?: boolean;
}) {
  return (
    <g>
      <title>{note ? `${name} (${note})` : name}</title>
      <rect x={x} y={y} width={NODE_W} height={NODE_H} rx={6}
        fill="var(--surface)" stroke={strong ? "var(--accent)" : "var(--line-strong)"} strokeWidth={strong ? 2 : 1} />
      <text x={x + NODE_W / 2} y={y + NODE_H / 2} textAnchor="middle" dominantBaseline="central"
        fill="var(--ink)" fontSize={12} fontWeight={strong ? 600 : 400}>
        {short(name)}
      </text>
    </g>
  );
}

/**
 * One system's neighbours: what it uses on the right, what uses it on the left.
 * The same facts are listed in text beside it, so the picture is a summary for
 * sighted readers and says so in its label.
 */
export function DependencyDiagram({ system, release }: { system: System; release: KnowledgeRelease }) {
  const markerId = useId();
  const names = new Map(release.systems.map((item) => [item.id, item.name]));
  type End = { name: string; note: string | null };
  const end = (id: string, item: Relationship): End =>
    ({ name: names.get(id) ?? id, note: kindNote(item.kind) });
  const uses = release.relationships.filter((item) => item.source_system_id === system.id)
    .map((item) => end(item.target_system_id, item));
  const usedBy = release.relationships.filter((item) => item.target_system_id === system.id)
    .map((item) => end(item.source_system_id, item));
  if (uses.length === 0 && usedBy.length === 0) return null;

  const side = (items: End[]): End[] => {
    const shown = items.slice(0, MAX_PER_SIDE);
    return items.length > MAX_PER_SIDE
      ? [...shown, { name: `+${items.length - MAX_PER_SIDE} more`, note: null }]
      : shown;
  };
  const left = side(usedBy);
  const right = side(uses);
  const rows = Math.max(left.length, right.length, 1);
  const height = rows * ROW + 8;
  const centreY = height / 2 - NODE_H / 2;
  const top = (count: number, index: number) => (height - count * ROW) / 2 + index * ROW + (ROW - NODE_H) / 2;
  const label = `${system.name} depends on ${uses.length} ${uses.length === 1 ? "system" : "systems"} and is used by ${usedBy.length}.`;

  return (
    <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={label}
      className="hidden h-auto w-full max-w-[480px] sm:block">
      <defs>
        <marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--ink-muted)" />
        </marker>
      </defs>
      {left.map(({ name, note }, index) => {
        const y = top(left.length, index);
        return (
          <g key={`in-${index}`}>
            <line x1={8 + NODE_W} y1={y + NODE_H / 2} x2={CENTRE_X - 2} y2={centreY + NODE_H / 2}
              stroke="var(--ink-muted)" strokeWidth={1} markerEnd={`url(#${markerId})`} />
            <Node x={8} y={y} name={name} note={note} />
          </g>
        );
      })}
      {right.map(({ name, note }, index) => {
        const y = top(right.length, index);
        return (
          <g key={`out-${index}`}>
            <line x1={CENTRE_X + NODE_W} y1={centreY + NODE_H / 2} x2={RIGHT_X - 2} y2={y + NODE_H / 2}
              stroke="var(--ink-muted)" strokeWidth={1} markerEnd={`url(#${markerId})`} />
            <Node x={RIGHT_X} y={y} name={name} note={note} />
          </g>
        );
      })}
      <Node x={CENTRE_X} y={centreY} name={system.name} strong />
    </svg>
  );
}
