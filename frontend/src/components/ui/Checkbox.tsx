import { Check, LoaderCircle, Minus } from "lucide-react";
import { useEffect, useId, useRef, type InputHTMLAttributes, type ReactNode } from "react";

import { cx } from "./cx";
import { describedBy } from "./describedBy";
import { FieldError } from "./Field";
import { TRANSITION } from "./recipes";

export type CheckboxProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "type"> & {
  label: ReactNode;
  /** One line under the label. Where the consequence of ticking it belongs. */
  hint?: ReactNode;
  error?: ReactNode;
  /**
   * Neither on nor off — the "some rows selected" state of a table's select-all
   * box. A DOM property with no HTML attribute, so it is set through a ref.
   */
  indeterminate?: boolean;
  /** Disables while something resolves; the ring replaces the box. */
  loading?: boolean;
  loadingLabel?: string;
  id?: string;
  fieldClassName?: string;
};

/**
 * A checkbox with a 24×24 target (§6, WCAG 2.2 2.5.8).
 *
 * The box itself is 20px, which is the size it should look; the 24px floor is
 * met by the grid cell around it, so the target is legal without the control
 * growing into something that reads as a button. The whole label is inside the
 * `<label>`, so the text is part of the target too.
 *
 * `appearance-none` on the input and the glyph painted over it: the native tick
 * takes `accent-color` but not a token-driven border, radius or focus ring, and
 * this control has to match `Input` at the same 1px `--line-strong` boundary.
 * It is still a real `<input type="checkbox">` — it is only wearing different
 * paint, so form semantics, the space key and `:checked` all still apply.
 */
export function Checkbox({
  label,
  hint,
  error,
  indeterminate = false,
  loading = false,
  loadingLabel,
  disabled,
  className,
  fieldClassName,
  id,
  ...rest
}: CheckboxProps) {
  const generated = useId();
  const fieldId = id ?? generated;
  const hintId = `${fieldId}-hint`;
  const errorId = `${fieldId}-error`;
  const labelId = `${fieldId}-label`;
  const box = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (box.current) box.current.indeterminate = indeterminate;
  }, [indeterminate]);

  return (
    <div className={cx("grid gap-1.5", fieldClassName)}>
      <label
        className={cx(
          "grid cursor-pointer grid-cols-[auto_minmax(0,1fr)] items-start gap-2",
          (disabled || loading) && "cursor-not-allowed",
        )}
      >
        <span className="relative grid min-h-6 min-w-6 shrink-0 place-items-center">
          {loading ? (
            <LoaderCircle
              aria-hidden="true"
              className="text-ink-muted animate-spin motion-reduce:animate-none"
              size={18}
            />
          ) : null}
          <input
            {...rest}
            ref={box}
            aria-describedby={describedBy(hint, hintId, error, errorId, rest["aria-describedby"])}
            // The hint sits inside the <label> so that it is part of the target,
            // which also made it part of the name: "Include in analysis When
            // included, the text passages…", then the same words again as the
            // description. With a hint, the name is the label text alone.
            aria-labelledby={rest["aria-labelledby"] ?? (hint ? labelId : undefined)}
            aria-invalid={error ? true : undefined}
            className={cx(
              "peer size-5 cursor-pointer appearance-none rounded-xs border border-solid",
              "border-line-strong bg-surface",
              "checked:border-accent checked:bg-accent",
              "indeterminate:border-accent indeterminate:bg-accent",
              "hover:border-accent",
              "aria-invalid:border-danger",
              "disabled:cursor-not-allowed disabled:border-line disabled:bg-surface-sunken",
              loading && "invisible",
              TRANSITION,
              className,
            )}
            disabled={disabled || loading}
            id={fieldId}
            type="checkbox"
          />
          {/* Later siblings, so `peer-*` reaches them. Both are painted on top
              of the box and neither is a target of its own. */}
          <Check
            aria-hidden="true"
            className="text-on-accent pointer-events-none absolute opacity-0 peer-checked:opacity-100 peer-indeterminate:opacity-0"
            size={14}
            strokeWidth={3}
          />
          <Minus
            aria-hidden="true"
            className="text-on-accent pointer-events-none absolute opacity-0 peer-indeterminate:opacity-100"
            size={14}
            strokeWidth={3}
          />
        </span>
        <span className="grid gap-0.5">
          <span
            className={cx(
              "text-body leading-6",
              disabled || loading ? "text-ink-faint" : "text-ink",
            )}
            id={labelId}
          >
            {label}
          </span>
          {hint && (
            <span className="text-ink-muted text-meta" id={hintId}>
              {hint}
            </span>
          )}
          {loading && (
            <span className="sr-only" role="status">
              {loadingLabel ?? "Saving…"}
            </span>
          )}
        </span>
      </label>
      {error && <FieldError id={errorId}>{error}</FieldError>}
    </div>
  );
}
