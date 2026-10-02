import { FilePlus2 } from "lucide-react";
import type { ReactNode } from "react";

/**
 * Nothing here yet, and what to do about it.
 *
 * docs/design-system.md §11: one row — a soft-tinted rounded icon tile, a
 * Title-size heading, and one `--ink-muted` line saying what would be here and
 * how to start. Dashed 1px `--line`, `--radius-md`. Never a large illustration,
 * never a centred hero.
 *
 * Styled in utilities rather than through `.empty-state`, which four stylesheets
 * redeclare — two of them with hardcoded hex — and which override each other by
 * source order. Below `sm` the row becomes a stack and the action goes full
 * width, because a 44px target beside a two-line heading on a 375px screen
 * leaves neither room.
 *
 * `headingLevel` is the caller's: this renders inside a panel on one screen and
 * directly under the page title on another, and a component that always emits
 * `<h3>` is how a document ends up skipping from `<h1>` to `<h3>`.
 */
export function EmptyState({
  title,
  message,
  action,
  icon,
  headingLevel: Heading = "h3",
}: {
  title: string;
  message: string;
  action?: ReactNode;
  /** A drawn glyph. Decorative — the heading carries the meaning. */
  icon?: ReactNode;
  headingLevel?: "h2" | "h3" | "h4";
}) {
  return (
    <div
      /* `minmax(0, 1fr)` and `min-w-0` below, not `1fr` and nothing: an `auto`
         or `1fr` track floors at its content's min-width, so a long message or a
         gated action with a reason under it sizes the track past the panel and
         pushes the page sideways. */
      className="empty-state border-line grid items-center gap-4 rounded-md border border-dashed p-5 sm:grid-cols-[auto_minmax(0,1fr)_auto]"
      data-state="empty"
    >
      {/* A drawn glyph, not a typed "+". The plus sign rendered at whatever the
          icon font resolved to, sat on the text baseline rather than centred,
          and changed shape between platforms. */}
      <span
        className="bg-accent-wash text-accent grid size-10 shrink-0 place-items-center rounded-md"
        aria-hidden="true"
      >
        {icon ?? <FilePlus2 aria-hidden="true" size={20} />}
      </span>
      <div className="grid min-w-0 gap-1">
        <Heading className="text-title text-ink m-0">{title}</Heading>
        <p className="text-ink-muted text-body m-0 max-w-[80ch]">{message}</p>
      </div>
      {action ? (
        <div className="grid min-w-0 justify-items-stretch sm:justify-items-end">{action}</div>
      ) : null}
    </div>
  );
}
