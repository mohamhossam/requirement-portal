/**
 * The fragments every primitive in this folder shares.
 *
 * They live here, in one file, for the same reason the Toaster and the Skeleton
 * carry their own styling rather than adding to the stylesheets: `.button` is
 * declared in six of the thirteen CSS files and they override each other by
 * source order, so a seventh declaration would have to be read against all of
 * them. Nothing in this folder emits a legacy class name, which is what keeps
 * `.breakdown-shell .button` — uppercase, square, red — off these primitives.
 *
 * Everything below resolves to a token. No hex, no duration and no radius that
 * is not on a ladder in `docs/design-system.md`.
 */

/**
 * Colour, border and background move; position and size never do (§9). 120ms is
 * `--motion-fast`, the hover/focus step. `motion-reduce` is belt and braces —
 * base.css already flattens every duration — but it keeps the intent legible at
 * the call site.
 */
export const TRANSITION =
  "transition-colors duration-[var(--motion-fast)] ease-out motion-reduce:transition-none";

/**
 * The focus ring, for elements base.css does not already reach. base.css sets
 * `3px solid var(--focus)` at `2px` offset on button, a, input, textarea,
 * select and summary; anything else — a label acting as a control, a custom
 * composite — asks for it here.
 */
export const FOCUS_RING =
  "focus-visible:[outline:3px_solid_var(--focus)] focus-visible:[outline-offset:2px]";

/**
 * The ring on an accent-filled or danger-filled surface (§4.6). Two changes,
 * and both are required: the colour inverts, because an accent ring on an
 * accent fill measures about 1:1, and the offset goes negative so the inverted
 * ring lands *on* the fill. At the global +2px it would sit on the page ground
 * instead, where `--focus-inverse` is near-white in the light theme and
 * therefore invisible — which is the measurement §4.6 quotes, 7.90:1 against
 * the fill, not against the canvas.
 */
export const FOCUS_RING_INVERSE =
  "focus-visible:[outline-color:var(--focus-inverse)] focus-visible:[outline-offset:-3px]";

/**
 * Hover ground for anything that is not already filled — secondary and ghost
 * buttons, table rows, interactive cards, tabs, pills.
 *
 * Mixed from `--accent` rather than set to `--surface-sunken`, and that is the
 * whole point: the accent inverts with the theme, so the mix darkens a white
 * surface in light and lightens a slate one in dark. `--surface-sunken` is
 * *darker* than `--surface` in both themes, so reusing it here would break the
 * dark-mode rule that hover goes lighter (§4.3 rule 3) and read as disabled.
 *
 * Underscores are Tailwind's escape for spaces inside an arbitrary value.
 */
export const HOVER_GROUND =
  "hover:[background-color:color-mix(in_srgb,var(--accent)_10%,var(--surface))]";

/** The same idea at half strength, for a surface a person sweeps across — rows. */
export const HOVER_GROUND_SOFT =
  "hover:[background-color:color-mix(in_srgb,var(--accent)_6%,var(--surface))]";

/**
 * Disabled, for a control that stays in the layout. `--ink-faint` on
 * `--surface-sunken` is the system's one forbidden pair at 4.43:1 (tokens.css)
 * — which is exactly right here and nowhere else: disabled text is explicitly
 * exempt from 1.4.3, and reading as unavailable is the entire job.
 *
 * A gated *primary* action never uses this. It stays enabled and explains
 * itself, per §11 — see `Button`'s `blockedReason`.
 */
export const DISABLED_CONTROL =
  "disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken" +
  " disabled:text-ink-faint disabled:shadow-none";

/**
 * The shared shape of an input, a select and a textarea (§11): `--surface`
 * ground, 1px `--line-strong` because the border is the only thing identifying
 * the control, `--radius-sm`, 36px.
 *
 * The invalid state doubles the border with an inset shadow rather than
 * switching to `border-2`. A width change moves every pixel inside the field by
 * one, which is a layout shift on the exact frame a person is being told they
 * got something wrong.
 */
export const CONTROL_BASE =
  "min-h-9 w-full rounded-sm border border-solid border-line-strong bg-surface px-3 py-2" +
  " text-body text-ink placeholder:text-ink-muted" +
  " hover:border-ink-muted focus-visible:border-accent" +
  " aria-invalid:border-danger aria-invalid:[box-shadow:inset_0_0_0_1px_var(--danger)]" +
  ` ${DISABLED_CONTROL} ${TRANSITION}`;

/** Sizes are floors, not targets (§6). Nothing here goes under 24×24. */
export const TARGET_MIN = "min-h-6 min-w-6";
