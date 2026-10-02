import { LoaderCircle } from "lucide-react";
import { Link, type LinkProps } from "react-router-dom";
import { forwardRef, useId, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cx } from "./cx";
import { recipe, type ButtonSize, type ButtonVariant } from "./buttonClass";

export type { ButtonSize, ButtonVariant } from "./buttonClass";

/**
 * The one button in the app (docs/design-system.md §11).
 *
 * `--radius-sm`, 36px minimum, 8/16px padding, label type in sentence case and
 * written as the act — "Save and analyse", not "Save". Hover
 * changes the ground colour and nothing else: the old `.button` lifted itself
 * by a pixel and cast a shadow on hover, which moves layout and breaks both the
 * no-lift rule (§8) and the hover-shifts-nothing rule (§9).
 *
 * Deliberately not styled through the `.button` class. Six stylesheets
 * redeclare it — `.breakdown-shell .button` alone makes it 44px, red and
 * uppercase — so a primitive wearing that class would render differently
 * depending on which subtree it landed in.
 */

type SharedProps = {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Leading glyph. Decorative — the label carries the meaning. */
  icon?: ReactNode;
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  SharedProps & {
    /**
     * The action is running. Disables for the duration and says what is
     * running, per §11 — a disabled control with an unchanged label tells a
     * person nothing about why it stopped responding.
     */
    loading?: boolean;
    /** What to say while `loading`. Defaults to the label, unchanged. */
    loadingLabel?: string;
    /**
     * Why this action cannot be taken yet, in the person's own words.
     *
     * §11: "a gated primary action stays visible and explains why rather than
     * disappearing". So this does *not* set `disabled` — the control keeps its
     * place in the tab order, announces itself as unavailable through
     * `aria-disabled`, and renders the reason underneath where a screen reader
     * reaches it through `aria-describedby`. Clicks are swallowed.
     */
    blockedReason?: string;
    /**
     * The same gate, when the reason is already on screen beside the button —
     * the id of the element that says it. The button is `aria-disabled`,
     * swallows clicks and is described by that element; nothing is rendered
     * under it, so the reason is not said twice.
     */
    blockedBy?: string;
  };

/**
 * `forwardRef` because dialogs focus their confirm button on open, and a
 * `useRef` pointed at this has to reach the real element.
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    icon,
    loading = false,
    loadingLabel,
    blockedReason,
    blockedBy,
    className,
    children,
    disabled,
    onClick,
    type = "button",
    ...rest
  },
  ref,
) {
  const blocked = Boolean(blockedReason || blockedBy);
  // Generated, not derived from `rest.id`: almost nothing passes an id, so the
  // old template collapsed to the literal `blocked--reason` on every gated
  // button, and two of them on a page made `aria-describedby` ambiguous.
  const generated = useId();
  const reasonId = blockedReason ? `${generated}-reason` : undefined;

  const button = (
    <button
      {...rest}
      ref={ref}
      type={type}
      className={recipe(variant, size, className)}
      disabled={disabled || loading}
      aria-disabled={blocked || undefined}
      aria-busy={loading || undefined}
      // Deduplicated: a caller that already points at the element gating it
      // would otherwise have the reason read twice.
      aria-describedby={[...new Set(cx(rest["aria-describedby"], reasonId, blockedBy).split(" ").filter(Boolean))].join(" ") || undefined}
      onClick={(event) => {
        // A gated action is not `disabled`, so the click has to be stopped here.
        if (blocked) {
          event.preventDefault();
          return;
        }
        onClick?.(event);
      }}
    >
      {loading ? (
        <LoaderCircle
          className="animate-spin motion-reduce:animate-none"
          size={16}
          aria-hidden="true"
        />
      ) : (
        icon
      )}
      {/* The label change is the part that survives reduced motion: with the
          spin frozen, "Analysing…" is the only thing left saying it is running. */}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );

  if (!blockedReason) return button;

  return (
    <span className="inline-grid justify-items-start gap-1">
      {button}
      <span className="text-ink-muted text-meta" id={reasonId}>
        {blockedReason}
      </span>
    </span>
  );
});

export type ButtonLinkProps = LinkProps & SharedProps;

/**
 * A link wearing the button's clothes, for the ~40 places that navigate rather
 * than act. Same recipe, so the two cannot drift; still an `<a>`, so it keeps
 * middle-click, "open in new tab" and the status bar.
 *
 * No `loading` and no `disabled`: a link that cannot be followed is not a link.
 * Where an action is unavailable, use `Button` with `blockedReason`.
 */
export function ButtonLink({
  variant = "secondary",
  size = "md",
  icon,
  className,
  children,
  ...rest
}: ButtonLinkProps) {
  return (
    <Link {...rest} className={recipe(variant, size, className)}>
      {icon}
      {children}
    </Link>
  );
}
