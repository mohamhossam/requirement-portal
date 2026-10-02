import { useEffect, useRef, useState, type RefObject } from "react";

import { cx } from "../../components/ui/cx";
import { utcDayLabel } from "../activity/labels";

export type ThroughputSeries = {
  key: string;
  label: string;
  values: Array<{ weekStart: string; value: number }>;
};

const HEIGHT = 64;
/** Where the top of the scale sits; a column at the maximum reaches it. */
const TOP = 4;
const GAP = 2;
const BAR_MAX = 24;

/**
 * One small column chart per measure, sharing the week axis (docs/ux-plan.md §5,
 * Phase 8: "give the weekly time series a visualization alongside the table").
 *
 * Small multiples rather than five lines on one plot: the measures differ in
 * scale by an order of magnitude, one axis would flatten the small ones, and
 * each gets its own y-range instead — printed beside it, 0 and the maximum, so
 * the separate scales are never mistaken for one. Every multiple is a single
 * series, so the heading names it and there is no legend and no categorical
 * hue — the bars are ink, because green, amber and red are statuses here and
 * indigo is the next action (DESIGN.md, Reserved Vocabulary). This week is still
 * counting, so it is drawn open rather than filled: a shape, which reads the
 * same in both themes, where a lighter or darker shade would invert in Slate.
 *
 * Hover names a week and its count in the readout line; the table below the
 * chart carries every value and its evidence link for keyboard and screen
 * readers, so the picture is described once and not walked bar by bar.
 */
export function ThroughputChart({ series, weeks }: { series: ThroughputSeries[]; weeks: number }) {
  return (
    <ul className="m-0 grid list-none gap-4 p-0 md:grid-cols-3 lg:grid-cols-5" aria-label={`Weekly counts, last ${weeks} weeks`}>
      {series.map((item) => (
        <li key={item.key}>
          <Multiple series={item} weeks={weeks} />
        </li>
      ))}
    </ul>
  );
}

function Multiple({ series, weeks }: { series: ThroughputSeries; weeks: number }) {
  const [hover, setHover] = useState<number | null>(null);
  const total = series.values.reduce((sum, entry) => sum + entry.value, 0);
  const max = Math.max(1, ...series.values.map((entry) => entry.value));
  const peak = series.values.reduce<(typeof series.values)[number] | undefined>(
    (best, entry) => (!best || entry.value > best.value ? entry : best),
    undefined,
  );
  const svgRef = useRef<SVGSVGElement>(null);
  const width = useWidth(svgRef);
  const slot = width / Math.max(1, series.values.length);
  const bar = Math.max(2, Math.min(BAR_MAX, slot - GAP));
  const hovered = hover === null ? null : series.values[hover];
  const described = `${series.label}: ${total} in ${weeks} weeks${
    total > 0 && peak ? `, most in the week of ${utcDayLabel(peak.weekStart)} (${peak.value})` : ""
  }.`;

  const first = series.values[0];
  const last = series.values.at(-1);

  return (
    <figure className="m-0 grid gap-2">
      <figcaption className="grid gap-0.5">
        <span className="text-label text-ink">{series.label}</span>
        <span aria-hidden="true" className="text-meta text-ink-muted min-h-[1.2rem] tabular-nums">
          {hovered ? (
            <>
              <strong className="text-ink font-semibold">{hovered.value}</strong> in the week of{" "}
              {utcDayLabel(hovered.weekStart)}
              {hover === series.values.length - 1 && " (in progress)"}
            </>
          ) : (
            <>
              <strong className="text-ink font-semibold">{total}</strong> in {weeks} weeks
            </>
          )}
        </span>
      </figcaption>
      {/* The scale is printed, because each multiple has its own: without it a
          column of 5 and a column of 17 are the same height and say so. */}
      <div aria-hidden="true" className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2">
        <span className="text-meta text-ink-muted flex h-16 flex-col justify-between text-right leading-none tabular-nums">
          <span>{max}</span>
          <span>0</span>
        </span>
        <svg
          className="block h-16 w-full overflow-visible"
          onPointerLeave={() => setHover(null)}
          ref={svgRef}
        >
          <line stroke="var(--line)" strokeWidth={1} x1={0} x2={width} y1={TOP + 0.5} y2={TOP + 0.5} />
          <line stroke="var(--line-strong)" strokeWidth={1} x1={0} x2={width} y1={HEIGHT - 0.5} y2={HEIGHT - 0.5} />
          {series.values.map((entry, index) => {
            const height = entry.value === 0 ? 0 : Math.max(2, (entry.value / max) * (HEIGHT - TOP));
            const latest = index === series.values.length - 1;
            const x = index * slot + (slot - bar) / 2;
            const radius = Math.min(4, bar / 2, height);
            return (
              <g key={entry.weekStart} onPointerEnter={() => setHover(index)}>
                {/* The hit area is the whole slot, taller than any bar. */}
                <rect fill="transparent" height={HEIGHT} width={slot} x={index * slot} y={0} />
                {height > 0 &&
                  (latest ? (
                    // This week, still counting: drawn open, so it reads as
                    // unfinished by shape and not by a shade of grey.
                    <path
                      className={cx("fill-surface", hover === index ? "stroke-ink" : "stroke-ink-muted")}
                      d={roundedTop(x + 0.75, HEIGHT - height + 0.75, bar - 1.5, height - 0.75, Math.max(0, radius - 0.75))}
                      strokeWidth={1.5}
                    />
                  ) : (
                    <path
                      className={hover === index ? "fill-ink" : "fill-ink-muted"}
                      d={roundedTop(x, HEIGHT - height, bar, height, radius)}
                    />
                  ))}
              </g>
            );
          })}
        </svg>
        <span />
        <span className="text-meta text-ink-muted mt-1 flex justify-between gap-2 tabular-nums">
          <span>{first ? utcDayLabel(first.weekStart) : ""}</span>
          <span>{last ? "This week" : ""}</span>
        </span>
      </div>
      <p className="sr-only">{described}</p>
    </figure>
  );
}

/** The drawn width in CSS pixels, so a 4px corner stays 4px at every size. */
function useWidth(ref: RefObject<SVGSVGElement | null>) {
  const [width, setWidth] = useState(240);
  useEffect(() => {
    const element = ref.current;
    // Older engines and the test DOM have no observer; the default width stands.
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry?.contentRect.width || 240));
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return width;
}

/** A column with a rounded data end and a square foot on the baseline. */
function roundedTop(x: number, y: number, width: number, height: number, radius: number) {
  const bottom = y + height;
  return [
    `M${x},${bottom}`,
    `V${y + radius}`,
    `Q${x},${y} ${x + radius},${y}`,
    `H${x + width - radius}`,
    `Q${x + width},${y} ${x + width},${y + radius}`,
    `V${bottom}`,
    "Z",
  ].join(" ");
}
