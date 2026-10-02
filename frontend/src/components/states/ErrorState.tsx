import { TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "../ui/Button";

/**
 * A read that failed, and the way out of it.
 *
 * Distinct from `ErrorNotice` on purpose. `ErrorNotice` is the inline alert
 * beside a control that just refused — it reports and stops. This is the block
 * that stands in for content that never arrived, so it always offers a next
 * step: a retry when the caller can retry, a way elsewhere when it cannot.
 * "Error without a recovery path" is a named anti-pattern.
 *
 * Two channels, never colour alone (docs/design-system.md §4.5): the 3px
 * `--danger` left edge and the glyph carry the state alongside the wash, and the
 * message says what happened in the person's own words.
 */
export function ErrorState({
  title = "We couldn’t load this",
  message,
  onRetry,
  retryLabel = "Try again",
  action,
  headingLevel: Heading = "h3",
}: {
  title?: string;
  /** What went wrong, from the API or from `errorMessage(error)`. */
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  /** An alternative route out, when retrying is not the one. */
  action?: ReactNode;
  headingLevel?: "h2" | "h3" | "h4";
}) {
  return (
    <div
      className="error-state border-line bg-danger-wash grid gap-2 rounded-md border border-solid border-l-[3px] border-l-[var(--danger)] p-5"
      data-state="error"
      role="alert"
    >
      <p className="text-danger text-label m-0 flex items-center gap-2">
        <TriangleAlert size={16} aria-hidden="true" />
        Something went wrong
      </p>
      <Heading className="text-title text-ink m-0">{title}</Heading>
      <p className="text-ink-soft text-body m-0 max-w-[80ch]">{message}</p>
      {(onRetry || action) && (
        <div className="mt-1 flex flex-wrap items-center gap-2">
          {onRetry ? (
            <Button variant="secondary" onClick={onRetry}>
              {retryLabel}
            </Button>
          ) : null}
          {action}
        </div>
      )}
    </div>
  );
}
