import { useId } from "react";

import type { Journey } from "../../api/knowledge";
import { byNumber } from "./labels";

const W = 184;
const H = 56;
const GAP_X = 28;
const GAP_Y = 44;
const PAD = 16;
// Room on the left for arrows that loop back up the flow.
const LOOP = 36;

const isMain = (track: string | null | undefined) => !track || track.toUpperCase() === "MAIN";
const clip = (text: string, length: number) => (text.length > length ? `${text.slice(0, length - 1)}…` : text);

/**
 * The journey's flow drawn as it runs (ADR-0096): each activity a box, side
 * tracks dashed, decisions and loops labelled, parallel tracks side by side
 * until they rejoin. The flow comes from the server, derived from the
 * activities and rules; this only lays it out. The activities table beside it
 * says the same in words, so the drawing is one image with a summary.
 */
export function JourneyFlow({ journey, names }: { journey: Journey; names: Map<string, string> }) {
  const markerId = useId();
  const titleId = useId();
  const activities = [...(journey.activities ?? [])].sort((a, b) => byNumber(a.number, b.number));
  const edges = journey.edges ?? [];
  if (activities.length === 0) return null;
  const position = new Map(activities.map((item, index) => [item.number, index]));
  const forward = edges.filter((edge) =>
    (position.get(edge.from_activity) ?? 0) < (position.get(edge.to_activity) ?? 0));
  // Each activity one row below the furthest activity that leads into it.
  const rank = new Map<string, number>();
  let deepest = -1;
  for (const item of activities) {
    const into = forward.filter((edge) => edge.to_activity === item.number)
      .map((edge) => rank.get(edge.from_activity))
      .filter((value): value is number => value !== undefined);
    const own = into.length > 0 ? Math.max(...into) + 1 : deepest + 1;
    rank.set(item.number, own);
    deepest = Math.max(deepest, own);
  }
  const rows = new Map<number, typeof activities>();
  for (const item of activities) {
    const row = rank.get(item.number) ?? 0;
    rows.set(row, [...(rows.get(row) ?? []), item]);
  }
  for (const [row, items] of rows) {
    rows.set(row, [...items].sort((a, b) => Number(isMain(b.track)) - Number(isMain(a.track))
      || byNumber(a.number, b.number)));
  }
  const widest = Math.max(...[...rows.values()].map((items) => items.length));
  const width = LOOP + PAD * 2 + widest * W + (widest - 1) * GAP_X;
  const height = PAD * 2 + (deepest + 1) * H + deepest * GAP_Y;
  const box = new Map<string, { x: number; y: number }>();
  for (const [row, items] of rows) {
    const span = items.length * W + (items.length - 1) * GAP_X;
    const start = LOOP + PAD + (widest * W + (widest - 1) * GAP_X - span) / 2;
    items.forEach((item, index) => box.set(item.number, { x: start + index * (W + GAP_X), y: PAD + row * (H + GAP_Y) }));
  }

  const summary = `${journey.name}: ${activities.length} activities and ${edges.length} arrows, drawn from the first activity down. The activities table lists the same steps in words.`;
  return (
    <div className="border-line bg-surface-sunken overflow-x-auto rounded-md border border-solid" tabIndex={0}
      role="region" aria-label={`Flow of ${journey.name}`}>
      <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="img" aria-labelledby={titleId}
        className="block max-w-none">
        <title id={titleId}>{summary}</title>
        <defs>
          <marker id={markerId} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--ink-muted)" />
          </marker>
        </defs>
        {edges.map((edge) => {
          const from = box.get(edge.from_activity);
          const to = box.get(edge.to_activity);
          if (!from || !to) return null;
          const back = (position.get(edge.from_activity) ?? 0) >= (position.get(edge.to_activity) ?? 0);
          let path: string;
          let labelAt: { x: number; y: number };
          if (back) {
            // Out of the left side, up the margin, into the left side of where it loops to.
            const sx = from.x;
            const sy = from.y + H / 2;
            const tx = to.x;
            const ty = to.y + H / 2;
            path = `M ${sx} ${sy} C ${PAD} ${sy}, ${PAD} ${ty}, ${tx} ${ty}`;
            labelAt = { x: PAD + LOOP / 2 + 6, y: (sy + ty) / 2 };
          } else {
            const sx = from.x + W / 2;
            const sy = from.y + H;
            const tx = to.x + W / 2;
            const ty = to.y;
            const middle = (sy + ty) / 2;
            path = `M ${sx} ${sy} C ${sx} ${middle}, ${tx} ${middle}, ${tx} ${ty}`;
            labelAt = { x: (sx + tx) / 2, y: middle };
          }
          const label = edge.label && edge.kind !== "rejoin" ? clip(edge.label, 22) : null;
          return (
            <g key={`${edge.from_activity}-${edge.to_activity}`}>
              <path d={path} fill="none" stroke="var(--ink-muted)" strokeWidth={1.25}
                strokeDasharray={edge.kind === "loop" ? "5 4" : undefined} markerEnd={`url(#${markerId})`} />
              {label && (
                <g>
                  <rect x={labelAt.x - label.length * 3.4 - 6} y={labelAt.y - 9} width={label.length * 6.8 + 12} height={18}
                    rx={4} fill="var(--surface)" stroke="var(--line)" />
                  <text x={labelAt.x} y={labelAt.y + 4} textAnchor="middle" fontSize={11} fill="var(--ink-soft)">{label}</text>
                </g>
              )}
            </g>
          );
        })}
        {activities.map((item) => {
          const at = box.get(item.number);
          if (!at) return null;
          const system = item.performing_system_id ? names.get(item.performing_system_id) ?? item.performing_system_id : "";
          return (
            <g key={item.number}>
              <title>{`${item.number}. ${item.name}${system ? ` — ${system}` : ""}${isMain(item.track) ? "" : ` (${item.track} track)`}`}</title>
              <rect x={at.x} y={at.y} width={W} height={H} rx={6} fill="var(--surface)"
                stroke={isMain(item.track) ? "var(--line-strong)" : "var(--ink-faint)"}
                strokeDasharray={isMain(item.track) ? undefined : "4 3"} />
              <text x={at.x + 10} y={at.y + 22} fontSize={12} fontWeight={600} fill="var(--ink)">
                {clip(`${item.number}. ${item.name}`, 26)}
              </text>
              <text x={at.x + 10} y={at.y + 41} fontSize={11} fill="var(--ink-muted)">
                {clip([system, isMain(item.track) ? null : item.track].filter(Boolean).join(" · "), 28)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
