import { TriangleAlert } from "lucide-react";
import type { ElementType, HTMLAttributes, ReactNode } from "react";

import { Skeleton } from "../Skeleton";
import { cx } from "./cx";
import { HOVER_GROUND_SOFT, TRANSITION } from "./recipes";

/**
 * Card and panel (§11). One primitive, because the difference between the two
 * was only ever padding.
 *
 * `--radius-md`, `--surface`, 1px `--line`, `--elev-0`, 24px. The elevation is
 * the part worth saying out loud: **anything in the document flow is flat**
 * (§8). A hairline and a half-step of surface tone do all the separating, and
 * shadow is reserved for layers that genuinely float — dropdowns, drawers,
 * modals, the toast stack. A page of drop-shadowed cards has no way left to
 * show which one is actually on top.
 */
export type CardTone = "default" | "accent" | "success" | "warning" | "danger";

/**
 * A status tone adds the 3px left edge *and* the wash, never the wash alone:
 * measured ground separation between a wash and its surface is 1.17:1 in light
 * and 1.07:1 in dark (§4.5), so the tint groups at a glance and carries nothing
 * on its own. The edge is the second channel.
 */
const TONE: Record<CardTone, string> = {
  default: "border-line",
  accent: "border-line border-l-accent border-l-[3px] bg-accent-wash",
  success: "border-line border-l-success border-l-[3px] bg-success-wash",
  // `--warning-edge` is non-text only — a left edge is exactly what it is for.
  warning: "border-line border-l-[3px] border-l-[var(--warning-edge)] bg-warning-wash",
  danger: "border-line border-l-danger border-l-[3px] bg-danger-wash",
};

export type CardProps = HTMLAttributes<HTMLElement> & {
  tone?: CardTone;
  /** Inset in a panel that already has a `--surface` ground. */
  inset?: boolean;
  /**
   * The card is a target — hover tone, pointer cursor, and the one shadow a
   * card may carry, `--elev-1`, on hover only. Put the real `<a>` or
   * `<button>` inside it; this is presentation.
   */
  interactive?: boolean;
  /** Replaces the body with a panel skeleton that reserves the same space. */
  loading?: boolean;
  loadingLabel?: string;
  /** Replaces the body with the message, announced assertively. */
  error?: ReactNode;
  /** `section` by default; `article` or `li` where the document says so. */
  as?: ElementType;
  /**
   * 24px by default. A padding class passed in `className` does not win: the
   * utilities are emitted in scale order, so `.p-6` lands after `.p-4` and a
   * caller's `p-4` was silently ignored on every card that passed one. This is
   * the supported way to ask for less.
   *
   * `compact` is 16px, `snug` 20px, `fluid` 16px below `sm` and 24px above it —
   * for cards that hold prose, where 24px of padding either side of a 390px
   * column leaves the prose too little room.
   */
  padding?: "default" | "compact" | "snug" | "fluid";
};

const PADDING = { default: "p-6", compact: "p-4", snug: "p-5", fluid: "p-4 sm:p-6" } as const;

export function Card({
  tone = "default",
  inset = false,
  interactive = false,
  loading = false,
  loadingLabel = "Loading…",
  error,
  as: Element = "section",
  padding = "default",
  className,
  children,
  ...rest
}: CardProps) {
  return (
    <Element
      {...rest}
      aria-busy={loading || undefined}
      className={cx(
        "rounded-md border border-solid",
        PADDING[padding],
        inset ? "bg-surface-sunken" : tone === "default" && "bg-surface",
        TONE[tone],
        interactive &&
          cx(
            "cursor-pointer hover:border-line-strong hover:shadow-elev-1",
            // The same response to the keyboard as to the pointer. The real
            // control is the `<a>` inside, so the card itself is never focused
            // and a hover-only rule leaves a person tabbing through a list of
            // cards with a ring around a link and no indication of which card
            // it belongs to.
            "focus-within:border-line-strong focus-within:shadow-elev-1",
            "focus-within:[background-color:color-mix(in_srgb,var(--accent)_6%,var(--surface))]",
            HOVER_GROUND_SOFT,
          ),
        TRANSITION,
        className,
      )}
    >
      {loading ? (
        <Skeleton label={loadingLabel} variant="panel" />
      ) : error ? (
        <p className="text-danger text-body m-0 flex items-start gap-2 font-semibold" role="alert">
          <TriangleAlert aria-hidden="true" className="mt-0.5 shrink-0" size={16} />
          {error}
        </p>
      ) : (
        children
      )}
    </Element>
  );
}

/**
 * The card heading row. `title` renders at Title type; the heading level is the
 * caller's to set, because only the screen knows where it sits in the outline
 * and a primitive that always emits `<h3>` is how documents end up skipping
 * from `<h1>` to `<h3>` (§13, item 12).
 */
export function CardHeader({
  title,
  headingLevel: Heading = "h3",
  eyebrow,
  description,
  actions,
  className,
}: {
  title: ReactNode;
  headingLevel?: "h2" | "h3" | "h4";
  /** A small label above the title — a register, never a status. */
  eyebrow?: ReactNode;
  description?: ReactNode;
  /** Controls, right-aligned. They wrap under the title below `sm`. */
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cx("mb-4 flex flex-wrap items-start justify-between gap-3", className)}>
      <div className="grid min-w-0 gap-1">
        {eyebrow && <p className="text-label text-ink-muted m-0">{eyebrow}</p>}
        <Heading className="text-title text-ink m-0">{title}</Heading>
        {description && (
          <p className="text-ink-muted text-meta m-0 max-w-[var(--measure-interface)]">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function CardBody({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div {...rest} className={cx("text-body text-ink-soft grid gap-4", className)}>
      {children}
    </div>
  );
}

/**
 * Actions, separated by a hairline rather than by a tone change: a footer on a
 * different ground reads as a second panel stuck to the bottom of the first.
 */
export function CardFooter({ className, children, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={cx(
        "mt-4 flex flex-wrap items-center gap-2 pt-4 [border-top:1px_solid_var(--line)]",
        className,
      )}
    >
      {children}
    </div>
  );
}
