import { cx } from "./cx";
import { FOCUS_RING_INVERSE, HOVER_GROUND, TRANSITION } from "./recipes";

/**
 * The button recipe, apart from the components that wear it — in its own module
 * so Button.tsx exports only components and keeps fast refresh.
 */
export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "text" | "text-danger";
export type ButtonSize = "md" | "sm" | "icon";

const VARIANT: Record<ButtonVariant, string> = {
  /* Filled, so the ring inverts and insets (§4.6). */
  primary: cx(
    "border-accent bg-accent text-on-accent hover:border-accent-strong hover:bg-accent-strong",
    FOCUS_RING_INVERSE,
  ),
  /* Transparent ground, and the border is the only thing identifying it —
     which is why it is `--line-strong` and not `--line`. */
  secondary: cx("border-line-strong bg-transparent text-ink", HOVER_GROUND),
  /* No border until hover. */
  ghost: cx("border-transparent bg-transparent text-ink hover:border-line-strong", HOVER_GROUND),
  /* Destructive confirmation only. Never the default action in a dialog. */
  danger: cx(
    "border-danger bg-danger text-on-accent hover:[background-color:color-mix(in_srgb,var(--ink)_14%,var(--danger))]",
    FOCUS_RING_INVERSE,
  ),
  /* The inline text button — Cancel, Retry, Mark read, Clear all. Underlined,
     because colour alone does not identify a control. */
  text: "border-transparent bg-transparent text-accent underline underline-offset-2 hover:text-accent-strong hover:decoration-2",
  /* The same inline shape for a small destructive act — Delete a saved view.
     Red and underlined: the underline, not the colour, is what says control. */
  "text-danger": "border-transparent bg-transparent text-danger underline underline-offset-2 hover:decoration-2",
};

/**
 * Heights are floors, not targets (§6). `text` takes the 24×24 floor from WCAG
 * 2.2 2.5.8 rather than the 36px control height: it sits in a line of prose, so
 * a 36px box would pad the paragraph open. That floor is the redesign's fix for
 * the verified `.text-button` failure in `ux-plan.md` §3.11, and it is enforced
 * here so that no screen has to remember it.
 */
const SIZE: Record<ButtonSize, string> = {
  md: "min-h-9 px-4 py-2 text-body",
  sm: "min-h-8 px-3 py-1.5 text-meta",
  icon: "min-h-8 min-w-8 p-0 text-body",
};

const TEXT_SIZE = "min-h-6 min-w-6 px-1 text-body";

const BASE =
  "inline-flex cursor-pointer items-center justify-center gap-2 rounded-sm border border-solid" +
  " font-semibold no-underline";

export function recipe(variant: ButtonVariant, size: ButtonSize, className?: string): string {
  return cx(
    BASE,
    TRANSITION,
    variant === "text" || variant === "text-danger" ? TEXT_SIZE : SIZE[size],
    VARIANT[variant],
    // `aria-disabled` is the gated-but-visible case; `:disabled` is the real
    // one. They look the same and mean different things — see `blockedReason`.
    "disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken disabled:text-ink-faint",
    // Hover is pinned too, so a blocked control never lights up as if it would act.
    "aria-disabled:cursor-not-allowed aria-disabled:border-line aria-disabled:bg-surface-sunken aria-disabled:text-ink-faint",
    "aria-disabled:hover:border-line aria-disabled:hover:bg-surface-sunken aria-disabled:hover:text-ink-faint",
    className,
  );
}

/**
 * The recipe on its own, for the few controls that cannot be a `<button>` or a
 * `<Link>`: a `<label>` that opens a hidden file input, a plain `<a>` to a blob
 * URL. Same classes, so they cannot drift from the primitive. Anything that can
 * be a `Button` or a `ButtonLink` should be one instead.
 */
export function buttonClass(
  variant: ButtonVariant = "secondary",
  size: ButtonSize = "md",
  className?: string,
): string {
  return recipe(variant, size, className);
}
