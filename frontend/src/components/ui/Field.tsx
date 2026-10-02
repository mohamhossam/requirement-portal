import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { cx } from "./cx";
import { describedBy as describedFor } from "./describedBy";

/**
 * The label, hint and error scaffold shared by every field (§11).
 *
 * Three rules it exists to enforce, so that no screen has to:
 *
 *   1. A real `<label for>`, above the control, at Label type. A placeholder
 *      standing in for a label is a named anti-pattern — it disappears the
 *      moment a person starts typing, which is when they most want to check
 *      what they were asked for.
 *   2. The error sits *below the field, beside the problem* — never only in a
 *      toast — and is linked by `aria-describedby`, not merely painted red.
 *   3. Hint and error are both described-by, in that order, so the hint is not
 *      lost the moment validation fails.
 *
 * Sentence case throughout. All-caps survives in exactly one place in this
 * product, the NEXT marker (§5), and a field label is not it.
 */
export function FieldShell({
  id,
  label,
  hint,
  hintId,
  error,
  errorId,
  required,
  labelFor = true,
  className,
  children,
}: {
  id: string;
  label: ReactNode;
  hint?: ReactNode;
  hintId: string;
  error?: ReactNode;
  errorId: string;
  required?: boolean;
  /**
   * False when the control is not a single labelable element — a checkbox
   * carries its own inline `<label>`, so the group gets a `<span>` heading
   * instead and `for` would point at nothing.
   */
  labelFor?: boolean;
  className?: string;
  children: ReactNode;
}) {
  const Label = labelFor ? "label" : "span";
  const labelId = `${id}-label`;
  return (
    // When there is no `for` to give, the wrapper becomes a named group
    // instead. A `<span>` sitting above a set of checkboxes is a heading to
    // anyone who can see it and nothing at all to anyone who cannot: the
    // controls announce their own labels and never the question they answer.
    // `role="group"` plus `aria-labelledby` is what carries it across.
    <div
      aria-describedby={labelFor ? undefined : describedFor(hint, hintId, error, errorId)}
      aria-labelledby={labelFor ? undefined : labelId}
      className={cx("grid gap-1.5", className)}
      role={labelFor ? undefined : "group"}
    >
      <Label
        className="text-label text-ink block"
        htmlFor={labelFor ? id : undefined}
        id={labelFor ? undefined : labelId}
      >
        {label}
        {required && (
          <>
            <span aria-hidden="true" className="text-danger ml-0.5">
              *
            </span>
            <span className="sr-only"> (required)</span>
          </>
        )}
      </Label>
      {hint && (
        <p className="text-ink-muted text-meta m-0" id={hintId}>
          {hint}
        </p>
      )}
      {children}
      {error && <FieldError id={errorId}>{error}</FieldError>}
    </div>
  );
}

/**
 * The message, below the field and beside the problem.
 *
 * `role="alert"` rather than an `aria-live` region mounted permanently and left
 * empty: this element appears when the error does, which is the one case a
 * polite region can be swallowed by whatever is already being read. It carries
 * a glyph as well as the colour, because red alone is not a channel (§4.5).
 */
export function FieldError({ id, children }: { id: string; children: ReactNode }) {
  return (
    <p
      className="text-danger text-meta m-0 flex items-start gap-1.5 font-semibold"
      id={id}
      role="alert"
    >
      <TriangleAlert aria-hidden="true" className="mt-px shrink-0" size={14} />
      {children}
    </p>
  );
}
