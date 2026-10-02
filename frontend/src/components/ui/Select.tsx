import { ChevronDown, LoaderCircle } from "lucide-react";
import { forwardRef, useId, type ReactNode, type SelectHTMLAttributes } from "react";

import { cx } from "./cx";
import { describedBy } from "./describedBy";
import { FieldShell } from "./Field";
import { CONTROL_BASE } from "./recipes";

export type SelectProps = Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> & {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  /**
   * The options are still being fetched. Disables — unlike `Input`, where the
   * person is mid-sentence, there is genuinely nothing to choose from yet —
   * sets `aria-busy`, and announces `loadingLabel`.
   */
  loading?: boolean;
  loadingLabel?: string;
  id?: string;
  fieldClassName?: string;
  children: ReactNode;
};

/**
 * A labelled select (§11), sharing the field recipe with `Input` so the two
 * line up at 36px in a row.
 *
 * Still a native `<select>`. The platform control brings keyboard behaviour,
 * type-ahead, the mobile wheel and the screen-reader announcement for free, and
 * every listbox rebuilt in React to match a design loses at least one of them.
 * The only thing replaced is the vendor arrow, which does not follow the theme:
 * `appearance-none` and a `lucide` chevron, `aria-hidden` and
 * `pointer-events-none` so it is a picture on top of the real control, not a
 * second target.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
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
    disabled,
    children,
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
        <select
          {...rest}
          ref={ref}
          aria-busy={loading || undefined}
          aria-describedby={describedBy(hint, hintId, error, errorId, rest["aria-describedby"])}
          aria-invalid={error ? true : undefined}
          className={cx(CONTROL_BASE, "cursor-pointer appearance-none pr-9", className)}
          disabled={disabled || loading}
          id={fieldId}
          required={required}
        >
          {children}
        </select>
        <span className="pointer-events-none absolute inset-y-0 right-3 grid place-items-center">
          {loading ? (
            <>
              <LoaderCircle
                aria-hidden="true"
                className="text-ink-muted animate-spin motion-reduce:animate-none"
                size={16}
              />
              <span className="sr-only" role="status">
                {loadingLabel ?? "Loading options…"}
              </span>
            </>
          ) : (
            <ChevronDown aria-hidden="true" className="text-ink-muted" size={16} />
          )}
        </span>
      </span>
    </FieldShell>
  );
});
