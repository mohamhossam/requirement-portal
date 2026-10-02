/**
 * The one way this app says "not here yet".
 *
 * Loading had grown two idioms: shimmer blocks written out by hand at nine
 * sites, and a bare "Loading …" paragraph at twelve more. The hand-written ones
 * carried an aria-label on a plain div, which has no role for the label to
 * belong to, so assistive technology announced nothing at all. This announces
 * through role="status" and keeps the shimmer decorative.
 *
 * Variants describe the shape of what is coming, so the page does not jump when
 * it arrives:
 *
 *   page    the whole workspace opening
 *   panel   a section within a page (the default)
 *   row     list rows, sized to the worklist
 *   inline  a slot inside a line of text or a list item
 *
 * Styled in utilities rather than in a stylesheet: the shapes only ever meant
 * anything here, and the app's CSS files override each other by source order,
 * so anything added there has to be read against the fourteen files around it.
 */
export type SkeletonVariant = "page" | "panel" | "row" | "inline";

const DEFAULT_BARS: Record<SkeletonVariant, number> = {
  page: 3,
  panel: 3,
  row: 5,
  inline: 1,
};

/**
 * Each variant carries its own display, gap and background rather than
 * overriding a shared base: utilities that set the same property are ordered by
 * Tailwind, not by the order they appear in the class attribute, so `grid` and
 * `inline-grid` together would resolve to whichever Tailwind emits last.
 */
const SHAPE: Record<SkeletonVariant, { frame: string; bar: string }> = {
  page: { frame: "grid gap-px bg-line w-[min(40rem,80vw)]", bar: "h-16" },
  panel: { frame: "grid gap-px bg-line", bar: "h-16" },
  row: { frame: "grid gap-px bg-line", bar: "h-24" },
  inline: {
    frame: "inline-grid gap-0 bg-transparent w-[min(14rem,100%)] align-middle",
    bar: "h-[1em] rounded-[3px]",
  },
};

export function Skeleton({
  label,
  variant = "panel",
  bars,
}: {
  /** What is loading, announced once. Written as a sentence, not a heading. */
  label: string;
  variant?: SkeletonVariant;
  bars?: number;
}) {
  const count = bars ?? DEFAULT_BARS[variant];
  const shape = SHAPE[variant];
  return (
    // Both are needed, and they do different jobs: the live region announces
    // its CONTENT when it appears, which is what the hidden text is for, while
    // role="status" takes no name from that content, so the region is nameless
    // without aria-label.
    <div className={shape.frame} role="status" aria-label={label} data-variant={variant}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: count }, (_, index) => (
        <span
          className={`bg-surface-sunken animate-skeleton-pulse ${shape.bar}`}
          key={index}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}
