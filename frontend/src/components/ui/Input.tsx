import { LoaderCircle } from "lucide-react";
import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";

import { cx } from "./cx";
import { describedBy } from "./describedBy";
import { FieldShell } from "./Field";
import { CONTROL_BASE } from "./recipes";

type FieldProps = {
  /** Sentence case, and the thing being asked for — not the format. */
  label: ReactNode;
  /**
   * A worked example, standing guidance or a format note. Persistent, because
   * help that vanishes on focus is help nobody can re-read (WCAG 2.2 3.2.6).
   */
  hint?: ReactNode;
  /**
   * What went wrong, in plain words. Sets `aria-invalid`, turns the border
   * `--danger` and renders the message below the field.
   */
  error?: ReactNode;
  /**
   * Something asynchronous is happening *to this field* — a uniqueness check,
   * a lookup. Shows the ring, sets `aria-busy` and announces `loadingLabel`.
   *
   * It does not disable: a person mid-sentence should not lose their field
   * because a background check started. `Select` and `Checkbox` do disable,
   * because there is nothing to choose from until the work finishes.
   */
  loading?: boolean;
  loadingLabel?: string;
  /** Wrapper class. The control's own class goes on `className`. */
  fieldClassName?: string;
};

/** The spinner, its live region, and the padding that keeps text off it. */
function Busy({ label }: { label?: string }) {
  return (
    <span className="pointer-events-none absolute inset-y-0 right-3 grid place-items-center">
      <LoaderCircle
        aria-hidden="true"
        className="text-ink-muted animate-spin motion-reduce:animate-none"
        size={16}
      />
      <span className="sr-only" role="status">
        {label ?? "Checking…"}
      </span>
    </span>
  );
}

export type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> &
  FieldProps & { id?: string };

/**
 * A labelled single-line field (§11): `--surface` ground, 1px `--line-strong`,
 * `--radius-sm`, 36px.
 *
 * Placeholders are worked examples — "Example: High-speed business bundles" —
 * and never a label in disguise; `FieldShell` renders the real one above.
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, loading, loadingLabel, required, className, fieldClassName, id, ...rest },
  ref,
) {
  const generated = useId();
  const fieldId = id ?? generated;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;

  return (
    <FieldShell
      className={fieldClassName}
      error={error}
      errorId={errorId}
      hint={hint}
      hintId={hintId}
      id={fieldId}
      label={label}
      required={required}
    >
      <span className="relative block">
        <input
          {...rest}
          ref={ref}
          aria-busy={loading || undefined}
          aria-describedby={describedBy(hint, hintId, error, errorId, rest["aria-describedby"])}
          aria-invalid={error ? true : undefined}
          className={cx(CONTROL_BASE, loading && "pr-9", className)}
          id={fieldId}
          required={required}
        />
        {loading && <Busy label={loadingLabel} />}
      </span>
    </FieldShell>
  );
});

export type TextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> &
  FieldProps & { id?: string };

/**
 * The same field, taller. Prose typed here becomes the requirement, so the
 * measure is capped at `--measure-interface` rather than running the full
 * width of a 1360px column (§5).
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  {
    label,
    hint,
    error,
    loading,
    loadingLabel,
    required,
    className,
    fieldClassName,
    id,
    rows = 5,
    ...rest
  },
  ref,
) {
  const generated = useId();
  const fieldId = id ?? generated;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;

  return (
    <FieldShell
      className={fieldClassName}
      error={error}
      errorId={errorId}
      hint={hint}
      hintId={hintId}
      id={fieldId}
      label={label}
      required={required}
    >
      <span className="relative block">
        <textarea
          {...rest}
          ref={ref}
          aria-busy={loading || undefined}
          aria-describedby={describedBy(hint, hintId, error, errorId, rest["aria-describedby"])}
          aria-invalid={error ? true : undefined}
          className={cx(CONTROL_BASE, "max-w-[var(--measure-interface)] resize-y leading-[1.5]", className)}
          id={fieldId}
          required={required}
          rows={rows}
        />
        {loading && <Busy label={loadingLabel} />}
      </span>
    </FieldShell>
  );
});
