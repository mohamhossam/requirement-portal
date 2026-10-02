import { Check, CircleAlert, CircleDot, Info, TriangleAlert } from "lucide-react";
import type { ComponentType, HTMLAttributes, ReactNode } from "react";

import { cx } from "./cx";
import { HOVER_GROUND, TRANSITION } from "./recipes";

/**
 * Badge and filter pill (§11).
 *
 * The rule this primitive exists to enforce is §4.5: **status is never colour
 * alone**. Every tone below ships a glyph, and it cannot be turned off — a
 * badge whose only difference from its neighbour is hue is unreadable to a
 * third of the people looking at it and invisible in a printout.
 */
export type BadgeTone = "neutral" | "accent" | "success" | "warning" | "danger";

const TONE: Record<BadgeTone, { className: string; icon: ComponentType<{ size?: number; className?: string; "aria-hidden"?: boolean }> }> = {
  /* A register, not a status — system names, catalogued evidence, IDs. */
  neutral: { className: "bg-surface-sunken text-ink-muted", icon: CircleDot },
  accent: { className: "bg-accent-wash text-accent", icon: Info },
  success: { className: "bg-success-wash text-success", icon: Check },
  warning: { className: "bg-warning-wash text-warning", icon: TriangleAlert },
  danger: { className: "bg-danger-wash text-danger", icon: CircleAlert },
};

export function Badge({
  tone = "neutral",
  icon,
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLSpanElement> & {
  tone?: BadgeTone;
  /** Overrides the tone glyph. It cannot be removed, only replaced. */
  icon?: ReactNode;
  children: ReactNode;
}) {
  const Glyph = TONE[tone].icon;
  return (
    // `--radius-sm`, no border, 12px/600 on a status wash. 12px is the floor
    // for every piece of text in this product, badges included (§5).
    <span
      {...rest}
      className={cx(
        "text-label inline-flex max-w-full items-center gap-1 rounded-sm px-2 py-1",
        TONE[tone].className,
        className,
      )}
    >
      {icon ?? <Glyph aria-hidden={true} className="shrink-0" size={12} />}
      <span className="truncate">{children}</span>
    </span>
  );
}

/**
 * A filter pill. `--radius-full`, `--surface` with `--line-strong`, filled with
 * `--accent` when it is on.
 *
 * A toggle, so it carries `aria-pressed` — without it a screen reader reads
 * "Blocking, button" whether the filter is applied or not, and the fill is the
 * only thing saying which. Only statuses with a non-zero count should render
 * one at all (§11).
 */
export function Pill({
  active = false,
  count,
  disabled = false,
  onClick,
  className,
  children,
}: {
  active?: boolean;
  count?: number;
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <button
      aria-pressed={active}
      className={cx(
        "text-meta inline-flex min-h-8 cursor-pointer items-center gap-2 rounded-full",
        "border border-solid px-3 py-1 font-semibold",
        active
          ? cx(
              "border-accent bg-accent text-on-accent",
              // Filled, so the ring inverts and insets (§4.6).
              "focus-visible:[outline-color:var(--focus-inverse)] focus-visible:[outline-offset:-3px]",
            )
          : cx("border-line-strong bg-surface text-ink", !disabled && HOVER_GROUND),
        "disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken disabled:text-ink-faint",
        TRANSITION,
        className,
      )}
      disabled={disabled}
      onClick={onClick}
      type="button"
    >
      {children}
      {count !== undefined && (
        <span
          className={cx(
            "tabular-nums",
            active ? "text-on-accent" : "text-ink-muted",
          )}
        >
          {count}
        </span>
      )}
    </button>
  );
}
